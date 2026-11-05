"""List the remote contents of the configured Mistral libraries.

Reads libraries_config.json and prints, per library (folder), first the
library metadata (name, uuid, description) and then its remote documents:
filename, size, creation datetime and process status. The web UI offers no
workspace-wide overview; this script does.

Usage:
    python scripts/list_libraries.py           # human-readable table on stdout
    python scripts/list_libraries.py --json    # machine-readable JSON on stdout
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
except ModuleNotFoundError:
    raise SystemExit(
        "error: afhankelijkheden niet gevonden — activeer eerst de venv "
        "(.venv\\Scripts\\activate) of draai met .venv\\Scripts\\python"
    )

import sync_libraries


class DocumentInfo(TypedDict):
    id: str
    name: str
    size: int | None
    created_at: str
    process_status: str


class LibraryOverview(TypedDict):
    name: str
    id: str | None
    description: str
    exists: bool
    documents: list[DocumentInfo]


class RemoteLibraryInfo(TypedDict):
    name: str
    nb_documents: int
    total_size: int


class Totals(TypedDict):
    documents: int
    size_bytes: int
    libraries_existing: int
    libraries_configured: int


class Overview(TypedDict):
    libraries: list[LibraryOverview]
    unconfigured_remote: list[RemoteLibraryInfo]
    totals: Totals


def format_size(size: int | None) -> str:
    if size is None:
        return "-"
    if size >= 1024 * 1024:
        return f"{size / 1024 / 1024:.1f}".replace(".", ",") + " MB"
    if size >= 1024:
        return f"{size / 1024:.1f}".replace(".", ",") + " KB"
    return f"{size} B"


def collect_overview(client: Mistral, config: sync_libraries.Config) -> Overview:
    remote = sync_libraries.list_all_libraries(client)
    remote_by_name = {lib.name: lib for lib in remote}
    configured_names = {c["name"] for c in config["libraries"]}
    overview: Overview = {
        "libraries": [],
        "unconfigured_remote": sorted(
            (
                {"name": n, "nb_documents": lib.nb_documents, "total_size": lib.total_size}
                for n, lib in remote_by_name.items()
                if n not in configured_names
            ),
            key=lambda i: i["name"],
        ),
        "totals": {"documents": 0, "size_bytes": 0, "libraries_existing": 0, "libraries_configured": len(config["libraries"])},
    }
    for cfg in config["libraries"]:
        name = cfg["name"]
        lib = remote_by_name.get(name)
        documents: list[DocumentInfo] = []
        if lib is not None:
            for doc in sync_libraries.list_all_documents(client, lib.id):
                documents.append(
                    {
                        "id": doc.id,
                        "name": doc.name,
                        "size": doc.size,
                        "created_at": doc.created_at.isoformat(),
                        "process_status": str(doc.process_status),
                    }
                )
        overview["libraries"].append(
            {
                "name": name,
                "id": lib.id if lib is not None else None,
                # Remote beschrijving is de werkelijke metadata; zonder remote library alleen de config.
                "description": (lib.description or "") if lib is not None else cfg["description"],
                "exists": lib is not None,
                "documents": sorted(documents, key=lambda d: d["name"]),
            }
        )
        if lib is not None:
            overview["totals"]["libraries_existing"] += 1
            overview["totals"]["documents"] += len(documents)
            overview["totals"]["size_bytes"] += sum(d["size"] for d in documents if d["size"] is not None)
    return overview


def print_table(overview: Overview) -> None:
    for lib in overview["libraries"]:
        print(f"== {lib['name']} ==")
        print(f"uuid:         {lib['id'] if lib['exists'] else '- (library bestaat niet remote)'}")
        print(f"beschrijving: {lib['description']}")
        if lib["exists"]:
            size = sum(d["size"] for d in lib["documents"] if d["size"] is not None)
            print(f"documenten:   {len(lib['documents'])} ({format_size(size)})")
        print()
        if lib["documents"]:
            header = f"  {'bestand':<60} {'grootte':>10} {'aangemaakt':<32} {'status':<12}"
            print(header)
            print("  " + "-" * (len(header) - 2))
            for doc in lib["documents"]:
                print(
                    f"  {doc['name'][:60]:<60} {format_size(doc['size']):>10} "
                    f"{doc['created_at']:<32} {doc['process_status']:<12}"
                )
            print()
    totals = overview["totals"]
    print(
        f"totaal: {totals['documents']} documenten ({format_size(totals['size_bytes'])}) "
        f"in {totals['libraries_existing']} van {totals['libraries_configured']} geconfigureerde libraries"
    )
    for info in overview["unconfigured_remote"]:
        print(
            f"warning: remote library '{info['name']}' ({info['nb_documents']} documenten) staat niet in de config",
            file=sys.stderr,
        )


def print_json(overview: Overview) -> None:
    print(json.dumps(overview, indent=2, ensure_ascii=False))


def main() -> int:
    parser = argparse.ArgumentParser(description="List remote contents of the configured Mistral libraries.")
    parser.add_argument("--json", action="store_true", help="JSON output instead of a table")
    parser.add_argument("--config", type=Path, default=sync_libraries.DEFAULT_CONFIG_PATH, help="path to config JSON")
    args = parser.parse_args()

    load_dotenv()
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        print("error: MISTRAL_API_KEY is not set; check .env", file=sys.stderr)
        return 2
    client = Mistral(api_key=api_key)
    config = sync_libraries.load_config(args.config)
    overview = collect_overview(client, config)
    if args.json:
        print_json(overview)
    else:
        print_table(overview)
    return 0


if __name__ == "__main__":
    sys.exit(main())
