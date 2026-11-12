"""Importeer de Website-teksten van de jeugdsite in de Club-library.

Kopieert alle .md-bestanden uit de WebsiteWTCjeugd-repo
(`websiteteksten/website_teksten md`) naar `knowledge-documents/club/`.
Het CMS-paginanummer achter de naam (" - 1014") valt weg:
"Trainingen - 1014.md" wordt "Trainingen.md". De website geldt als actueel,
dus een gewijzigde tekst overschrijft de bestaande kopie.

Idempotent: een bestand wordt alleen geschreven als de inhoud verschilt.
Bestanden in de Club-library zonder bron op de website blijven staan
(de Club-library bevat ook andere clubdocumenten).

Dry-run by default; pass --apply to write files. Daarna de Club-library
syncen met `scripts/sync_libraries.py`.
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Literal, TypedDict

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = REPO_ROOT.parent / "WebsiteWTCjeugd" / "websiteteksten" / "website_teksten md"
DEFAULT_DEST = REPO_ROOT / "knowledge-documents" / "club"
PAGE_SUFFIX = re.compile(r" - \d+$")

Status = Literal["new", "changed", "unchanged"]


class ImportAction(TypedDict):
    source: Path
    dest: Path
    status: Status


def strip_page_suffix(file_name: str) -> str:
    path = Path(file_name)
    return PAGE_SUFFIX.sub("", path.stem) + path.suffix


def plan_import(source_dir: Path, dest_dir: Path) -> list[ImportAction]:
    if not source_dir.is_dir():
        raise SystemExit(f"error: bronmap niet gevonden: {source_dir}; geef het pad mee met --source")
    actions: list[ImportAction] = []
    seen: dict[str, Path] = {}
    for source in sorted(source_dir.glob("*.md")):
        dest_name = strip_page_suffix(source.name)
        if dest_name in seen:
            raise SystemExit(
                f"error: '{source.name}' en '{seen[dest_name].name}' worden allebei '{dest_name}'; "
                "hernoem een van beide in de bron"
            )
        seen[dest_name] = source
        dest = dest_dir / dest_name
        actions.append({"source": source, "dest": dest, "status": compare(source, dest)})
    return actions


def compare(source: Path, dest: Path) -> Status:
    if not dest.is_file():
        return "new"
    if normalize_newlines(dest.read_bytes()) == normalize_newlines(source.read_bytes()):
        return "unchanged"
    return "changed"


def normalize_newlines(content: bytes) -> bytes:
    # Git (core.autocrlf) kan LF in de checkout naar CRLF omzetten; dat is geen inhoudswijziging.
    return content.replace(b"\r\n", b"\n")


def apply_import(actions: list[ImportAction], dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    for action in actions:
        if action["status"] != "unchanged":
            action["dest"].write_bytes(action["source"].read_bytes())


def print_report(actions: list[ImportAction], apply: bool) -> None:
    prefix = "" if apply else "[dry-run] "
    verbs = {"new": "nieuw", "changed": "gewijzigd"}
    for action in actions:
        if action["status"] in verbs:
            print(f"{prefix}{verbs[action['status']]}: {action['source'].name} -> {action['dest'].name}")
    counts = {status: sum(1 for a in actions if a["status"] == status) for status in ("new", "changed", "unchanged")}
    mode = "apply" if apply else "dry-run"
    print(f"\n--- summary ({mode}) ---")
    print(f"nieuw: {counts['new']}, gewijzigd: {counts['changed']}, ongewijzigd: {counts['unchanged']}")


def run_import(source_dir: Path, dest_dir: Path, apply: bool) -> list[ImportAction]:
    print(f"bron: {source_dir}")
    print(f"doel: {dest_dir}")
    actions = plan_import(source_dir, dest_dir)
    if apply:
        apply_import(actions, dest_dir)
    print_report(actions, apply)
    return actions


def main() -> int:
    parser = argparse.ArgumentParser(description="Importeer de Website-teksten in knowledge-documents/club/.")
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
        help=f"map met de website-teksten (default: {DEFAULT_SOURCE})",
    )
    parser.add_argument("--dest", type=Path, default=DEFAULT_DEST, help=f"doelmap (default: {DEFAULT_DEST})")
    parser.add_argument("--apply", action="store_true", help="bestanden schrijven (default: dry-run)")
    args = parser.parse_args()
    run_import(args.source.resolve(), args.dest.resolve(), apply=args.apply)
    return 0


if __name__ == "__main__":
    sys.exit(main())
