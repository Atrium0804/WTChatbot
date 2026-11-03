"""Synchronize local knowledge-documents folders with Mistral Studio libraries.

Each subfolder of the configured rag_folder maps to one Mistral library
(folder name == library name, lowercase). Local folders are the source of
truth: missing libraries are created, descriptions are updated, and
documents are uploaded or deleted so every remote library mirrors its
local folder. Remote documents without a local counterpart are deleted
from the active library; archiving old versions is a manual step (ADR-0005).

Dry-run by default; pass --apply to execute changes.

https://docs.mistral.ai/api/endpoint/beta/libraries
https://docs.mistral.ai/api/endpoint/beta/libraries/documents
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import TypedDict

try:
    from dotenv import load_dotenv
    from mistralai.client import Mistral
    from mistralai.client.models import Document, Library
except ModuleNotFoundError:
    raise SystemExit(
        "error: afhankelijkheden niet gevonden — activeer eerst de venv "
        "(.venv\\Scripts\\activate) of draai met .venv\\Scripts\\python"
    )

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = SCRIPT_DIR / "libraries_config.json"


class LibraryConfig(TypedDict):
    name: str
    description: str


class Config(TypedDict):
    rag_folder: str
    libraries: list[LibraryConfig]


class SyncReport(TypedDict):
    created_libraries: list[str]
    updated_libraries: list[str]
    uploads: list[str]
    deletes: list[str]
    unchanged: int
    errors: list[str]


class DocumentPlan(TypedDict):
    uploads: list[tuple[str, Path]]
    deletes: list[Document]
    unchanged: int


def load_config(path: Path) -> Config:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise SystemExit(f"error: config file not found: {path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"error: invalid JSON in {path}: {exc}")
    for key in ("rag_folder", "libraries"):
        if key not in data:
            raise SystemExit(f"error: config {path} is missing key '{key}'")
    for entry in data["libraries"]:
        for key in ("name", "description"):
            if key not in entry:
                raise SystemExit(f"error: config {path}: library entry missing '{key}': {entry}")
    return data


def list_all_libraries(client: Mistral) -> list[Library]:
    libraries: list[Library] = []
    page_token: str | None = None
    while True:
        response = client.beta.libraries.list(page_size=100, page_token=page_token)
        libraries.extend(response.data)
        if response.next_page_token is None:
            return libraries
        page_token = response.next_page_token


def list_all_documents(client: Mistral, library_id: str) -> list[Document]:
    documents: list[Document] = []
    page = 0
    while True:
        response = client.beta.libraries.documents.list(library_id=library_id, page=page, page_size=100)
        documents.extend(response.data)
        if not response.pagination.has_more:
            return documents
        page += 1


def list_local_files(folder: Path) -> dict[str, Path]:
    if not folder.is_dir():
        return {}
    return {p.name: p for p in sorted(folder.iterdir()) if p.is_file()}


def plan_document_sync(local_files: dict[str, Path], remote_docs: list[Document]) -> DocumentPlan:
    local_sizes = {name: path.stat().st_size for name, path in local_files.items()}
    remote_by_name: dict[str, list[Document]] = {}
    for doc in remote_docs:
        remote_by_name.setdefault(doc.name, []).append(doc)

    uploads: list[tuple[str, Path]] = []
    deletes: list[Document] = []
    unchanged = 0
    for name, path in local_files.items():
        matches = remote_by_name.get(name, [])
        if any(doc.size == local_sizes[name] for doc in matches):
            unchanged += 1
            continue
        deletes.extend(matches)
        uploads.append((name, path))
    for name, docs in remote_by_name.items():
        if name not in local_files:
            deletes.extend(docs)
    return {"uploads": uploads, "deletes": deletes, "unchanged": unchanged}


def sync_libraries(
    client: Mistral,
    configured: list[LibraryConfig],
    existing: list[Library],
    apply: bool,
    report: SyncReport,
) -> dict[str, Library | None]:
    existing_by_name = {lib.name: lib for lib in existing}
    synced: dict[str, Library | None] = {}
    for cfg in configured:
        name = cfg["name"]
        lib = existing_by_name.get(name)
        if lib is None:
            if apply:
                lib = client.beta.libraries.create(name=name, description=cfg["description"])
                report["created_libraries"].append(name)
                print(f"created library '{name}'")
            else:
                print(f"[dry-run] would create library '{name}'")
        elif (lib.description or "") != cfg["description"]:
            if apply:
                client.beta.libraries.update(library_id=lib.id, description=cfg["description"])
                report["updated_libraries"].append(name)
                print(f"updated description of library '{name}'")
            else:
                print(f"[dry-run] would update description of library '{name}'")
        synced[name] = lib
    return synced


def sync_documents(
    client: Mistral,
    library: Library | None,
    library_name: str,
    local_files: dict[str, Path],
    apply: bool,
    report: SyncReport,
) -> None:
    if library is None:
        for file_name in local_files:
            report["uploads"].append(f"{library_name}/{file_name}")
            print(f"[dry-run] would upload '{file_name}' to new library '{library_name}'")
        return
    remote_docs = list_all_documents(client, library.id)
    plan = plan_document_sync(local_files, remote_docs)
    report["unchanged"] += plan["unchanged"]
    for file_name, path in plan["uploads"]:
        report["uploads"].append(f"{library_name}/{file_name}")
        if not apply:
            print(f"[dry-run] would upload '{file_name}' to library '{library_name}'")
            continue
        try:
            with open(path, "rb") as f:
                client.beta.libraries.documents.upload(
                    library_id=library.id, file={"file_name": file_name, "content": f}
                )
            print(f"uploaded '{file_name}' to library '{library_name}'")
        except Exception as exc:
            report["errors"].append(f"upload {library_name}/{file_name}: {exc}")
            print(f"error: upload {library_name}/{file_name}: {exc}", file=sys.stderr)
    for doc in plan["deletes"]:
        report["deletes"].append(f"{library_name}/{doc.name}")
        if not apply:
            print(f"[dry-run] would delete '{doc.name}' from library '{library_name}'")
            continue
        try:
            client.beta.libraries.documents.delete(library_id=library.id, document_id=doc.id)
            print(f"deleted '{doc.name}' from library '{library_name}'")
        except Exception as exc:
            report["errors"].append(f"delete {library_name}/{doc.name}: {exc}")
            print(f"error: delete {library_name}/{doc.name}: {exc}", file=sys.stderr)


def print_summary(report: SyncReport, apply: bool) -> None:
    mode = "apply" if apply else "dry-run"
    print(f"\n--- summary ({mode}) ---")
    print(f"libraries created: {len(report['created_libraries'])} {report['created_libraries']}")
    print(f"descriptions updated: {len(report['updated_libraries'])} {report['updated_libraries']}")
    print(f"documents {'uploaded' if apply else 'to upload'}: {len(report['uploads'])}")
    print(f"documents {'deleted' if apply else 'to delete'}: {len(report['deletes'])}")
    print(f"documents unchanged: {report['unchanged']}")
    if report["errors"]:
        print(f"errors ({len(report['errors'])}):")
        for error in report["errors"]:
            print(f"  - {error}")


def run_sync(
    client: Mistral,
    config: Config,
    apply: bool,
    only_library: str | None = None,
    config_path: Path | None = None,
) -> int:
    configured = config["libraries"]
    if only_library is not None:
        configured = [c for c in configured if c["name"] == only_library]
        if not configured:
            print(f"error: library '{only_library}' is not in the config", file=sys.stderr)
            return 2
    rag_folder = Path(config["rag_folder"])
    if not rag_folder.is_absolute() and config_path is not None:
        rag_folder = config_path.parent / rag_folder
    rag_folder = rag_folder.resolve()
    print(f"rag folder: {rag_folder}")
    if not rag_folder.is_dir():
        print(f"error: rag folder not found: {rag_folder}", file=sys.stderr)
        return 2
    configured_names = {c["name"] for c in configured}
    for entry in sorted(rag_folder.iterdir()):
        if entry.is_dir() and entry.name not in configured_names:
            print(f"warning: local folder '{entry.name}' is not configured, skipping")

    existing = list_all_libraries(client)
    report: SyncReport = {
        "created_libraries": [],
        "updated_libraries": [],
        "uploads": [],
        "deletes": [],
        "unchanged": 0,
        "errors": [],
    }
    libraries = sync_libraries(client, configured, existing, apply, report)
    for cfg in configured:
        name = cfg["name"]
        local_files = list_local_files(rag_folder / name)
        sync_documents(client, libraries.get(name), name, local_files, apply, report)
    print_summary(report, apply)
    return 1 if report["errors"] else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync knowledge-documents folders with Mistral libraries.")
    parser.add_argument("--apply", action="store_true", help="execute changes (default: dry-run)")
    parser.add_argument("--library", help="sync only this library (must be in the config)")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH, help="path to config JSON")
    args = parser.parse_args()

    load_dotenv()
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        print("error: MISTRAL_API_KEY is not set; check .env", file=sys.stderr)
        return 2
    client = Mistral(api_key=api_key)
    config = load_config(args.config)
    return run_sync(client, config, apply=args.apply, only_library=args.library, config_path=args.config)


if __name__ == "__main__":
    sys.exit(main())
