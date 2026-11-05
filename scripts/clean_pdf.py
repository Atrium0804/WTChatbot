"""Schoon een KNWU-reglement (PDF) op voor de document-library.

KNWU-PDF's (Titel 20, Nationale Besluiten) markeren vervallen tekst met een
getekende doorhaallijn en gewijzigde tekst in rood. Tekstextractie verliest
beide, waardoor de agent doorgehaalde waarden als geldend leest. Dit script
maakt er markdown van waarin doorgehaalde tekst ontbreekt en rode tekst
tussen [GEWIJZIGD] en [/GEWIJZIGD] staat.

Gebruik:
    python scripts/clean_pdf.py <pdf> [<pdf> ...] --out <map> [--review <map>]

Per PDF ontstaat <map>/<bestandsnaam zonder .pdf>.md, plus een opschoonrapport
met dezelfde naam in de reviewmap (standaard knowledge-documents/review/).
Het rapport somt per pagina alle weggehaalde stukken op en zet bovenaan de
twijfelgevallen die een mens moet nalopen (issue #30).
"""

import argparse
import re
import sys
import unicodedata
from pathlib import Path
from typing import NamedTuple

import pymupdf

GEWIJZIGD_OPEN = "[GEWIJZIGD]"
GEWIJZIGD_SLUIT = "[/GEWIJZIGD]"
DEFAULT_REVIEW_DIR = Path(__file__).resolve().parents[1] / "knowledge-documents" / "review"
CONTEXT_WOORDEN = 4
# Hoogte van een lijn als fractie van de tekenhoogte (0 = bovenkant). Gemeten in
# de KNWU-PDF's (#30): doorhalingen op 0,5-0,65; onderstrepingen en tabelranden
# op <= 0,075 of >= 0,875. De lege tussenruimte is de bijna-doorhaling.
DOORHAAL_BAND = (0.3, 0.8)
BIJNA_BANDEN = [(0.1, 0.3), (0.8, 0.85)]


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
    return _lijn_in_band(bbox, lijnen, [DOORHAAL_BAND])


def _bijna_doorgehaald(bbox: tuple, lijnen: list) -> bool:
    """Een lijn net boven of onder de doorhaalband: daar liggen in echte KNWU-PDF's
    geen onderstrepingen of tabelranden, dus mogelijk een gemiste doorhaling."""
    return _lijn_in_band(bbox, lijnen, BIJNA_BANDEN)


def _lijn_in_band(bbox: tuple, lijnen: list, banden: list[tuple[float, float]]) -> bool:
    """Is er een lijn door het horizontale midden van het teken op een hoogte
    (als fractie van de tekenhoogte, 0 = bovenkant) binnen een van de banden?"""
    x0, y0, x1, y1 = bbox
    midden_x = (x0 + x1) / 2
    return any(
        lx0 <= midden_x <= lx1 and y0 + (y1 - y0) * laag <= ly <= y0 + (y1 - y0) * hoog
        for lx0, lx1, ly in lijnen
        for laag, hoog in banden
    )


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


class _Teken(NamedTuple):
    c: str
    weg: bool
    rood: bool
    bijna: bool = False


def _context(tekens: list[_Teken], start: int, eind: int) -> str:
    """Het weggehaalde stuk tussen ~~ met een paar woorden geldende tekst eromheen."""

    def geldend(stuk: list[_Teken]) -> str:
        return re.sub(r"\s+", " ", "".join(t.c for t in stuk if not t.weg))

    voor = geldend(tekens[:start]).split(" ")[-CONTEXT_WOORDEN - 1 :]
    na = geldend(tekens[eind:]).split(" ")[: CONTEXT_WOORDEN + 1]
    stuk = re.sub(r"\s+", " ", "".join(_zichtbaar(t.c) for t in tekens[start:eind])).strip()
    return f"{' '.join(voor)}~~{stuk}~~{' '.join(na)}".strip()


def _zichtbaar(teken: str) -> str:
    """Glyphs uit een private-use-lettertype (bijv. opsommingstekens) als U+XXXX,
    anders staat er een leeg ~~~~ in het rapport."""
    return f"U+{ord(teken):04X}" if unicodedata.category(teken) in ("Co", "Cn") else teken


def _stukken(tekens: list[_Teken], kenmerk) -> list[tuple[int, int]]:
    """Aaneengesloten reeksen tekens met kenmerk; witruimte ertussen hoort erbij."""
    reeksen, start, laatste = [], None, None
    for i, t in enumerate(tekens):
        if kenmerk(t) and t.c.strip():
            if start is None:
                start = i
            laatste = i
        elif t.c.strip() and start is not None:
            reeksen.append((start, laatste + 1))
            start = None
    if start is not None:
        reeksen.append((start, laatste + 1))
    return reeksen


def _rapport(naam: str, twijfels: list[str], weggehaald: dict[int, list[str]]) -> str:
    regels = [f"# Opschoonrapport: {naam}", "", "## Twijfelgevallen", ""]
    regels += [f"- [ ] {t}" for t in twijfels] or ["Geen."]
    regels.append("")
    aantal = sum(len(s) for s in weggehaald.values())
    regels += [f"## Weggehaalde stukken ({aantal} op {len(weggehaald)} pagina's)", ""]
    for pagina, stukken in weggehaald.items():
        regels += [f"### Pagina {pagina}", ""] + [f"- {s}" for s in stukken] + [""]
    return "\n".join(regels)


def opschonen(path: Path) -> tuple[str, str]:
    """(opgeschoonde markdown, opschoonrapport in markdown) voor één PDF."""
    doc = pymupdf.open(path)
    paginas = []
    weggehaald: dict[int, list[str]] = {}
    twijfels: list[str] = []
    for page in doc:
        lijnen = _doorhaallijnen(page)
        blokken = []
        for blok in page.get_text("rawdict")["blocks"]:
            segmenten: list[tuple[str, bool]] = []
            tekens: list[_Teken] = []
            for regel in blok.get("lines", []):
                for span in regel["spans"]:
                    rood = _rood(span["color"])
                    for c in span["chars"]:
                        weg = _doorgehaald(c["bbox"], lijnen)
                        bijna = rood and not weg and _bijna_doorgehaald(c["bbox"], lijnen)
                        tekens.append(_Teken(c["c"], weg, rood, bijna))
                    span_tekens = tekens[len(tekens) - len(span["chars"]) :]
                    segmenten.append(("".join(t.c for t in span_tekens if not t.weg), rood))
                segmenten.append(("\n", False))
                tekens.append(_Teken(" ", False, False))
            pagina = page.number + 1
            for start, eind in _stukken(tekens, lambda t: t.weg):
                stuk = _context(tekens, start, eind)
                weggehaald.setdefault(pagina, []).append(stuk)
                if any(t.weg and t.c.strip() and not t.rood for t in tekens[start:eind]):
                    twijfels.append(f"Pagina {pagina}, doorgehaald maar niet rood: {stuk}")
            for start, eind in _stukken(tekens, lambda t: t.bijna):
                twijfels.append(f"Pagina {pagina}, bijna-doorhaling (blijft staan): {_context(tekens, start, eind)}")
            tekst = _blok_naar_tekst(segmenten)
            if tekst:
                blokken.append(tekst)
        paginas.append("\n\n".join(blokken))
    tekst = "\n\n".join(p for p in paginas if p) + "\n"
    if GEWIJZIGD_OPEN in tekst and not weggehaald:
        twijfels.insert(
            0,
            "Rode tekst maar geen enkele doorhaling gevonden: haalt de KNWU in deze versie "
            "anders door (bijv. via lettertype-opmaak)? Controleer de PDF.",
        )
    return tekst, _rapport(path.name, twijfels, weggehaald)


def clean_pdf(path: Path) -> str:
    """Markdown-tekst van de PDF zonder doorgehaalde tekst, rood gemarkeerd."""
    return opschonen(path)[0]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Schoon KNWU-PDF's op tot markdown.")
    parser.add_argument("pdfs", nargs="+", type=Path)
    parser.add_argument("--out", type=Path, required=True, help="doelmap voor de .md-bestanden")
    parser.add_argument(
        "--review",
        type=Path,
        default=DEFAULT_REVIEW_DIR,
        help=f"map voor de opschoonrapporten (standaard: {DEFAULT_REVIEW_DIR})",
    )
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    args.review.mkdir(parents=True, exist_ok=True)
    for pdf in args.pdfs:
        tekst, rapport = opschonen(pdf)
        doel = args.out / (pdf.stem + ".md")
        doel.write_text(tekst, encoding="utf-8")
        rapport_pad = args.review / (pdf.stem + ".md")
        rapport_pad.write_text(rapport, encoding="utf-8")
        print(f"{pdf} -> {doel} (rapport: {rapport_pad})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
