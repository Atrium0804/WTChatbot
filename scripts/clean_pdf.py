"""Schoon een KNWU-reglement (PDF) op voor de document-library.

KNWU-PDF's (Titel 20, Nationale Besluiten) markeren vervallen tekst met een
getekende doorhaallijn en gewijzigde tekst in rood. Tekstextractie verliest
beide, waardoor de agent doorgehaalde waarden als geldend leest. Dit script
maakt er markdown van waarin doorgehaalde tekst ontbreekt en rode tekst
tussen [GEWIJZIGD] en [/GEWIJZIGD] staat. Tabellen worden markdown-tabellen,
zodat de kolombetekenis blijft (#33). Koppen worden markdown-koppen met het
volledige kopjespad (bijv. "2. WEGWIELRENNEN › … › NK Weg Jeugd › LJT"), zodat
elke chunk in de library zijn discipline en paragraaf draagt; welke opmaak een
kop is, staat per document in scripts/kopprofielen.json.

Gebruik:
    python scripts/clean_pdf.py <pdf> [<pdf> ...] --out <map> [--review <map>]
                                [--kopprofielen <json>] [--split]

Per PDF ontstaat <map>/<bestandsnaam zonder .pdf>.md, met --split één bestand
per hoofdstuk: <map>/<bestandsnaam zonder .pdf> - <hoofdstuk>.md (behalve de
hoofdstukken die het kopprofiel als buiten_scope noemt). Daarnaast een
opschoonrapport met dezelfde naam in de reviewmap (standaard
knowledge-documents/review/). Het rapport somt per pagina alle weggehaalde
stukken op, zet bovenaan de twijfelgevallen die een mens moet nalopen (issue
#30) en eindigt met de gevonden koppen.
"""

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import NamedTuple

import pymupdf

GEWIJZIGD_OPEN = "[GEWIJZIGD]"
GEWIJZIGD_SLUIT = "[/GEWIJZIGD]"
# pymupdf-spanvlag voor vet lettertype.
VET_VLAG = 16
DEFAULT_REVIEW_DIR = Path(__file__).resolve().parents[1] / "knowledge-documents" / "review"
DEFAULT_KOPPROFIELEN = Path(__file__).resolve().parent / "kopprofielen.json"
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


class _Kop(NamedTuple):
    niveau: int
    tekst: str
    pagina: int


# pymupdf zet naast tabelranden smalle opvulcellen (~5pt); echte cellen zijn breder.
MIN_CELBREEDTE = 8.0
KOLOMRAND_MARGE = 8.0


class _Cel(NamedTuple):
    bbox: tuple[float, float, float, float]
    rij: int
    kolommen: tuple[int, ...]


class _Tabel:
    """Een door pymupdf herkende tabel; tekens worden per cel verzameld."""

    def __init__(self, tabel) -> None:
        self.bbox = tuple(tabel.bbox)
        echte = [
            (rij, tuple(cel))
            for rij, r in enumerate(tabel.rows)
            for cel in r.cells
            if cel is not None and cel[2] - cel[0] >= MIN_CELBREEDTE
        ]
        randen = sorted(x for _, (x0, _, x1, _) in echte for x in (x0, x1))
        clusters: list[list[float]] = []
        for x in randen:
            if clusters and x - clusters[-1][-1] <= KOLOMRAND_MARGE:
                clusters[-1].append(x)
            else:
                clusters.append([x])
        grenzen = [sum(c) / len(c) for c in clusters]
        midden = [(a + b) / 2 for a, b in zip(grenzen, grenzen[1:])]
        self.aantal_kolommen = len(midden)
        self.aantal_rijen = len(tabel.rows)
        self.cellen = [
            _Cel(bbox, rij, tuple(k for k, m in enumerate(midden) if bbox[0] <= m <= bbox[2]))
            for rij, bbox in echte
        ]
        self.segmenten: dict[_Cel, list[tuple[str, bool]]] = {c: [] for c in self.cellen}

    def cel_voor(self, bbox: tuple) -> "_Cel | None":
        x, y = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
        return next(
            (c for c in self.cellen if c.bbox[0] <= x <= c.bbox[2] and c.bbox[1] <= y <= c.bbox[3]),
            None,
        )

    def markdown(self) -> str:
        rijen = [[""] * self.aantal_kolommen for _ in range(self.aantal_rijen)]
        for cel, segmenten in self.segmenten.items():
            tekst = _blok_naar_tekst(segmenten).replace("\n", " ").replace("|", "\\|")
            # Een cel over de volle breedte (titel- of notitierij) één keer, niet per kolom.
            kolommen = cel.kolommen[:1] if len(cel.kolommen) == self.aantal_kolommen > 1 else cel.kolommen
            for k in kolommen:
                rijen[cel.rij][k] = tekst
        rijen = [r for r in rijen if any(r)]
        if not rijen or not self.aantal_kolommen:
            return ""
        regels = ["| " + " | ".join(r) + " |" for r in rijen]
        regels.insert(1, "| " + " | ".join(["---"] * self.aantal_kolommen) + " |")
        return "\n".join(regels)


def _tabellen(page: pymupdf.Page) -> list[_Tabel]:
    # lines_strict: alleen getekende randen, geen opvulvlakken; geeft in de KNWU-PDF's
    # evenveel tabellen als de standaard, maar zonder smalle schijnkolommen.
    return [_Tabel(t) for t in page.find_tables(strategy="lines_strict").tables]


def _cel_in_tabellen(tabellen: list[_Tabel], bbox: tuple) -> tuple["_Tabel | None", "_Cel | None"]:
    x, y = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
    for tabel in tabellen:
        tx0, ty0, tx1, ty1 = tabel.bbox
        if tx0 <= x <= tx1 and ty0 <= y <= ty1:
            cel = tabel.cel_voor(bbox)
            if cel is not None:
                return tabel, cel
    return None, None


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


def _rapport(naam: str, twijfels: list[str], weggehaald: dict[int, list[str]], koppen: list[_Kop] | None) -> str:
    regels = [f"# Opschoonrapport: {naam}", "", "## Twijfelgevallen", ""]
    regels += [f"- [ ] {t}" for t in twijfels] or ["Geen."]
    regels.append("")
    aantal = sum(len(s) for s in weggehaald.values())
    regels += [f"## Weggehaalde stukken ({aantal} op {len(weggehaald)} pagina's)", ""]
    for pagina, stukken in weggehaald.items():
        regels += [f"### Pagina {pagina}", ""] + [f"- {s}" for s in stukken] + [""]
    if koppen is not None:
        # Ingesprongen per niveau, zodat een mens de nesting bij een documentwissel kan nalopen.
        regels += [f"## Gevonden koppen ({len(koppen)})", ""]
        regels += [f"{'  ' * (k.niveau - 1)}- p{k.pagina} {_zonder_markering(k.tekst)}" for k in koppen]
        regels.append("")
    return "\n".join(regels)


class _Regel(NamedTuple):
    segmenten: list[tuple[str, bool]]
    niveau: int | None
    vet: bool
    titel_erbij: bool = False


# Langere reeksen vette regels zijn een opsomming of nadruk, geen kop (bijv. de NK-lijst in NB 2.4.1).
MAX_KOPREGELS = 2
MAX_KOPLENGTE = 80


def _kopregel(tekst: str, grootte: float, vet: bool, profiel: dict | None) -> dict | None:
    """De eerste profielregel die bij deze regel past, anders None.

    Een vette zin of zinsrest (begint met een kleine letter of is langer dan
    MAX_KOPLENGTE) is nadruk in lopende tekst, geen kop.
    """
    if not profiel or not vet or not tekst or tekst[0].islower() or len(tekst) > MAX_KOPLENGTE:
        return None
    for regel in profiel["koppen"]:
        if round(grootte) != regel["grootte"]:
            continue
        if "patroon" in regel and not re.search(regel["patroon"], tekst):
            continue
        if regel.get("hoofdletters") and (tekst != tekst.upper() or not any(c.isalpha() for c in tekst)):
            continue
        return regel
    return None


def _regel_info(spans: list[dict], segmenten: list[tuple[str, bool]], profiel: dict | None) -> _Regel:
    gevuld = [s for s in spans if any(c["c"].strip() for c in s["chars"])]
    vet = bool(gevuld) and all(s["flags"] & VET_VLAG for s in gevuld)
    grootte = gevuld[0]["size"] if gevuld else 0.0
    tekst = " ".join("".join(c for c, _ in segmenten).split())
    kopregel = _kopregel(tekst, grootte, vet, profiel) or {}
    return _Regel(segmenten, kopregel.get("niveau"), vet and bool(tekst), kopregel.get("titel_erbij", False))


def _vette_reeksen(regels: list[_Regel]) -> list[list[_Regel]]:
    """Groepeer opeenvolgende vette regels; elke niet-vette regel is een eigen groep."""
    groepen: list[list[_Regel]] = []
    for regel in regels:
        if regel.vet and groepen and groepen[-1][-1].vet:
            groepen[-1].append(regel)
        else:
            groepen.append([regel])
    return groepen


def _kop(reeks: list[_Regel], pagina: int) -> _Kop:
    """Eén kop uit de vette regels; de regel die het profiel herkende (bijv. het
    artikelnummer) komt voorop."""
    geordend = sorted(reeks, key=lambda r: r.niveau is None)
    segmenten = [s for r in geordend for s in r.segmenten + [(" ", False)]]
    niveau = min(r.niveau for r in reeks if r.niveau is not None)
    return _Kop(niveau, " ".join(_blok_naar_tekst(segmenten).split()), pagina)


def _kopgroepen(reeks: list[_Regel]) -> list[list[_Regel]]:
    """Regels die samen één kop of één stuk tekst vormen. Een opsomming blijft tekst;
    alleen een profielregel met `titel_erbij` (Titel 20: nummer + titel) neemt de
    aangrenzende vette regel in de kop op."""
    if len(reeks) > MAX_KOPREGELS:
        return [reeks]
    if any(r.titel_erbij for r in reeks):
        return [reeks]
    return [[r] for r in reeks]


def _blok_elementen(regels: list[_Regel], pagina: int) -> list[str | _Kop]:
    """Splits een tekstblok in lopende tekst en koppen."""
    elementen: list[str | _Kop] = []
    lopend: list[tuple[str, bool]] = []
    for reeks in _vette_reeksen(regels):
        for groep in _kopgroepen(reeks):
            is_kop = len(groep) <= MAX_KOPREGELS and any(r.niveau is not None for r in groep)
            if not is_kop:
                lopend += [s for r in groep for s in r.segmenten]
                continue
            tekst = _blok_naar_tekst(lopend)
            if tekst:
                elementen.append(tekst)
            lopend = []
            elementen.append(_kop(groep, pagina))
    tekst = _blok_naar_tekst(lopend)
    if tekst:
        elementen.append(tekst)
    return elementen


def _zonder_markering(tekst: str) -> str:
    return tekst.replace(GEWIJZIGD_OPEN, "").replace(GEWIJZIGD_SLUIT, "")


def _zonder_weggelaten(elementen: list, profiel: dict | None) -> list:
    """Laat secties weg waarvan de kop een `weglaten`-patroon uit het profiel heeft
    (bijv. de inhoudsopgave), tot de volgende kop van hetzelfde of een hoger niveau."""
    patronen = (profiel or {}).get("weglaten", [])
    resultaat, weglaten_tot = [], None
    for element in elementen:
        if isinstance(element, _Kop):
            if weglaten_tot is not None and element.niveau <= weglaten_tot:
                weglaten_tot = None
            if weglaten_tot is None and any(re.search(p, _zonder_markering(element.tekst)) for p in patronen):
                weglaten_tot = element.niveau
        if weglaten_tot is None:
            resultaat.append(element)
    return resultaat


def _markdown(elementen: list) -> str:
    """Elementen als markdown; een kop krijgt het pad van zijn bovenliggende koppen."""
    delen, pad = [], {}
    for element in elementen:
        if isinstance(element, _Kop):
            pad = {niveau: tekst for niveau, tekst in pad.items() if niveau < element.niveau}
            koptekst = " › ".join([pad[n] for n in sorted(pad)] + [element.tekst])
            pad[element.niveau] = _zonder_markering(element.tekst)
            delen.append(f"{'#' * element.niveau} {koptekst}")
        elif isinstance(element, _Tabel):
            delen.append(element.markdown())
        else:
            delen.append(element)
    return "\n\n".join(d for d in delen if d) + "\n"


def opschonen(path: Path, profiel: dict | None = None) -> tuple[str, str]:
    """(opgeschoonde markdown, opschoonrapport in markdown) voor één PDF.

    Met een kopprofiel worden koppen markdown-koppen met het volledige pad.
    """
    elementen, rapport = _elementen_en_rapport(path, profiel)
    return _markdown(elementen), rapport


def hoofdstukken(path: Path, profiel: dict) -> tuple[list[tuple[str | None, str]], str]:
    """([(hoofdstuktitel, markdown), ...], opschoonrapport): één deel per kop van niveau 1.

    Tekst vóór het eerste hoofdstuk (titelpagina) hoort bij het eerste deel; zonder
    hoofdstukkoppen is er één deel zonder titel. Hoofdstukken waarvan de titel past
    bij een `buiten_scope`-patroon uit het profiel vallen weg en staan in het rapport.
    """
    elementen, rapport = _elementen_en_rapport(path, profiel)
    delen: list[tuple[str | None, list]] = [(None, [])]
    for element in elementen:
        if isinstance(element, _Kop) and element.niveau == 1:
            titel = _zonder_markering(element.tekst)
            if delen[-1][0] is None and len(delen) == 1:
                delen[0] = (titel, delen[0][1])
            else:
                delen.append((titel, []))
        delen[-1][1].append(element)
    patronen = profiel.get("buiten_scope", [])
    buiten = [titel for titel, _ in delen if titel and any(re.search(p, titel) for p in patronen)]
    if buiten:
        rapport += "\n".join(["## Niet in de library (buiten scope)", ""] + [f"- {t}" for t in buiten] + [""])
    return [(titel, _markdown(deel)) for titel, deel in delen if titel not in buiten], rapport


def _elementen_en_rapport(path: Path, profiel: dict | None) -> tuple[list, str]:
    doc = pymupdf.open(path)
    elementen: list[str | _Tabel | _Kop] = []
    weggehaald: dict[int, list[str]] = {}
    twijfels: list[str] = []
    for page in doc:
        lijnen = _doorhaallijnen(page)
        tabellen = _tabellen(page)
        blokken: list[str | _Tabel | _Kop] = []
        for blok in page.get_text("rawdict")["blocks"]:
            regels: list[_Regel] = []
            tekens: list[_Teken] = []
            for regel in blok.get("lines", []):
                segmenten: list[tuple[str, bool]] = []
                geraakte_cellen: set[tuple[_Tabel, _Cel]] = set()
                for span in regel["spans"]:
                    rood = _rood(span["color"])
                    for c in span["chars"]:
                        weg = _doorgehaald(c["bbox"], lijnen)
                        bijna = rood and not weg and _bijna_doorgehaald(c["bbox"], lijnen)
                        tekens.append(_Teken(c["c"], weg, rood, bijna))
                        tabel, cel = _cel_in_tabellen(tabellen, c["bbox"])
                        if tabel is not None:
                            if tabel not in blokken:
                                blokken.append(tabel)
                            geraakte_cellen.add((tabel, cel))
                            if not weg:
                                tabel.segmenten[cel].append((c["c"], rood))
                        elif not weg:
                            segmenten.append((c["c"], rood))
                segmenten.append(("\n", False))
                for tabel, cel in geraakte_cellen:
                    tabel.segmenten[cel].append(("\n", False))
                tekens.append(_Teken(" ", False, False))
                regels.append(_regel_info(regel["spans"], segmenten, profiel if not geraakte_cellen else None))
            pagina = page.number + 1
            for start, eind in _stukken(tekens, lambda t: t.weg):
                stuk = _context(tekens, start, eind)
                weggehaald.setdefault(pagina, []).append(stuk)
                # Alleen tekens met letters of cijfers: een doorgehaald opsommingsteken
                # (Word-export, doorhaling op de alinea-markering) is geen gemiste revisie.
                if any(t.weg and t.c.isalnum() and not t.rood for t in tekens[start:eind]):
                    twijfels.append(f"Pagina {pagina}, doorgehaald maar niet rood: {stuk}")
            for start, eind in _stukken(tekens, lambda t: t.bijna):
                twijfels.append(f"Pagina {pagina}, bijna-doorhaling (blijft staan): {_context(tekens, start, eind)}")
            blokken += _blok_elementen(regels, pagina)
        elementen += blokken
    elementen = _zonder_weggelaten(elementen, profiel)
    tekst = _markdown(elementen)
    if GEWIJZIGD_OPEN in tekst and not weggehaald:
        twijfels.insert(
            0,
            "Rode tekst maar geen enkele doorhaling gevonden: haalt de KNWU in deze versie "
            "anders door (bijv. via lettertype-opmaak)? Controleer de PDF.",
        )
    koppen = [e for e in elementen if isinstance(e, _Kop)] if profiel else None
    if profiel and not koppen:
        twijfels.insert(0, "Kopprofiel gebruikt, maar geen enkele kop gevonden: past het profiel nog bij de opmaak?")
    return elementen, _rapport(path.name, twijfels, weggehaald, koppen)


def clean_pdf(path: Path) -> str:
    """Markdown-tekst van de PDF zonder doorgehaalde tekst, rood gemarkeerd."""
    return opschonen(path)[0]


def kopprofiel(naam: str, profielen_pad: Path) -> dict | None:
    """Het kopprofiel waarvan de sleutel het langste voorvoegsel van `naam` is."""
    if not profielen_pad.exists():
        return None
    profielen = json.loads(profielen_pad.read_text(encoding="utf-8"))
    passend = [sleutel for sleutel in profielen if naam.startswith(sleutel)]
    return profielen[max(passend, key=len)] if passend else None


def _bestandsnaam(stem: str, hoofdstuk: str | None) -> str:
    if hoofdstuk is None:
        return f"{stem}.md"
    veilig = " ".join(re.sub(r'[<>:"/\\|?*]', "-", hoofdstuk).split()).rstrip(". ")
    return f"{stem} - {veilig}.md"


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
    parser.add_argument(
        "--kopprofielen",
        type=Path,
        default=DEFAULT_KOPPROFIELEN,
        help=f"kopprofielen per document (standaard: {DEFAULT_KOPPROFIELEN})",
    )
    parser.add_argument("--split", action="store_true", help="één .md-bestand per hoofdstuk (kop van niveau 1)")
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    args.review.mkdir(parents=True, exist_ok=True)
    for pdf in args.pdfs:
        profiel = kopprofiel(pdf.stem, args.kopprofielen)
        if args.split and profiel:
            delen, rapport = hoofdstukken(pdf, profiel)
        else:
            tekst, rapport = opschonen(pdf, profiel)
            delen = [(None, tekst)]
        for hoofdstuk, tekst in delen:
            doel = args.out / _bestandsnaam(pdf.stem, hoofdstuk)
            doel.write_text(tekst, encoding="utf-8")
            print(f"{pdf} -> {doel}")
        rapport_pad = args.review / (pdf.stem + ".md")
        rapport_pad.write_text(rapport, encoding="utf-8")
        print(f"rapport: {rapport_pad}{'' if profiel else ' (geen kopprofiel gevonden)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
