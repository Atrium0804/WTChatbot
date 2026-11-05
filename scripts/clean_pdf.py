"""Schoon een KNWU-reglement (PDF) op voor de document-library.

KNWU-PDF's (Titel 20, Nationale Besluiten) markeren vervallen tekst met een
getekende doorhaallijn en gewijzigde tekst in rood. Tekstextractie verliest
beide, waardoor de agent doorgehaalde waarden als geldend leest. Dit script
maakt er markdown van waarin doorgehaalde tekst ontbreekt en rode tekst
tussen [GEWIJZIGD] en [/GEWIJZIGD] staat.

Gebruik:
    python scripts/clean_pdf.py <pdf> [<pdf> ...] --out <map>

Per PDF ontstaat <map>/<bestandsnaam zonder .pdf>.md.
"""

import argparse
import re
import sys
from pathlib import Path

import pymupdf

GEWIJZIGD_OPEN = "[GEWIJZIGD]"
GEWIJZIGD_SLUIT = "[/GEWIJZIGD]"


def _doorhaallijnen(page: pymupdf.Page) -> list[tuple[float, float, float]]:
    """Horizontale lijnen en dunne rechthoeken: (x0, x1, y)."""
    lijnen = []
    for drawing in page.get_drawings():
        for item in drawing["items"]:
            if item[0] == "l":
                p1, p2 = item[1], item[2]
                if abs(p1.y - p2.y) < 1.5 and abs(p1.x - p2.x) > 3:
                    lijnen.append((min(p1.x, p2.x), max(p1.x, p2.x), (p1.y + p2.y) / 2))
            elif item[0] == "re":
                rect = item[1]
                if rect.height < 2.5 and rect.width > 3:
                    lijnen.append((rect.x0, rect.x1, (rect.y0 + rect.y1) / 2))
    return lijnen


def _doorgehaald(bbox: tuple, lijnen: list) -> bool:
    """Een lijn door het midden van het teken (niet eronder: onderstreping)."""
    x0, y0, x1, y1 = bbox
    midden_x = (x0 + x1) / 2
    laag, hoog = y0 + (y1 - y0) * 0.3, y0 + (y1 - y0) * 0.8
    return any(lx0 <= midden_x <= lx1 and laag <= ly <= hoog for lx0, lx1, ly in lijnen)


def _rood(kleur: int) -> bool:
    r, g, b = kleur >> 16, (kleur >> 8) & 255, kleur & 255
    return r > 150 and g < 90 and b < 90


def _blok_naar_tekst(segmenten: list[tuple[str, bool]]) -> str:
    """Voeg (tekst, rood)-segmenten samen; aaneengesloten rood krijgt één markering.

    Witruimte tussen twee rode stukken onderbreekt de markering niet.
    """
    uit, in_rood, buffer = [], False, ""
    for tekst, rood in segmenten:
        if not tekst.strip():
            buffer += tekst
            continue
        if rood and not in_rood:
            uit.append(buffer + GEWIJZIGD_OPEN)
            in_rood = True
        elif not rood and in_rood:
            uit.append(GEWIJZIGD_SLUIT + buffer)
            in_rood = False
        else:
            uit.append(buffer)
        buffer = ""
        uit.append(tekst)
    if in_rood:
        uit.append(GEWIJZIGD_SLUIT)
    uit.append(buffer)
    tekst = "".join(uit)
    tekst = re.sub(r"[ \t]+", " ", tekst)
    return "\n".join(regel.strip() for regel in tekst.splitlines()).strip()


def clean_pdf(path: Path) -> str:
    """Markdown-tekst van de PDF zonder doorgehaalde tekst, rood gemarkeerd."""
    doc = pymupdf.open(path)
    paginas = []
    for page in doc:
        lijnen = _doorhaallijnen(page)
        blokken = []
        for blok in page.get_text("rawdict")["blocks"]:
            segmenten: list[tuple[str, bool]] = []
            for regel in blok.get("lines", []):
                for span in regel["spans"]:
                    tekens = "".join(
                        c["c"] for c in span["chars"] if not _doorgehaald(c["bbox"], lijnen)
                    )
                    segmenten.append((tekens, _rood(span["color"])))
                segmenten.append(("\n", False))
            tekst = _blok_naar_tekst(segmenten)
            if tekst:
                blokken.append(tekst)
        paginas.append("\n\n".join(blokken))
    return "\n\n".join(p for p in paginas if p) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Schoon KNWU-PDF's op tot markdown.")
    parser.add_argument("pdfs", nargs="+", type=Path)
    parser.add_argument("--out", type=Path, required=True, help="doelmap voor de .md-bestanden")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    for pdf in args.pdfs:
        doel = args.out / (pdf.stem + ".md")
        doel.write_text(clean_pdf(pdf), encoding="utf-8")
        print(f"{pdf} -> {doel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
