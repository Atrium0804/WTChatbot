import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import clean_pdf


def maak_pdf(path: Path) -> None:
    """Eén pagina: verzettabelregel met doorgehaalde oude waarde, een rode
    (gewijzigde) zin en gewone tekst — zoals in Titel 20 / Nationale Besluiten."""
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "U11", fontsize=11)
    page.insert_text((120, 100), "5,78", fontsize=11)
    page.insert_text((160, 100), "5,90 meter", fontsize=11)
    page.draw_line((118, 96.5), (146, 96.5))
    page.insert_text((72, 130), "Nieuwe regel per 2026.", fontsize=11, color=(1, 0, 0))
    page.insert_text((72, 160), "Gewone tekst.", fontsize=11)
    doc.save(path)


class CleanPdfTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.pdf = Path(tmp.name) / "doc.pdf"
        maak_pdf(self.pdf)
        self.tekst = clean_pdf.clean_pdf(self.pdf)

    def test_doorgehaalde_tekst_verdwijnt(self) -> None:
        self.assertNotIn("5,78", self.tekst)
        self.assertIn("5,90 meter", self.tekst)

    def test_rode_tekst_wordt_gemarkeerd_als_gewijzigd(self) -> None:
        self.assertRegex(self.tekst, r"\[GEWIJZIGD\]\s*Nieuwe regel per 2026\.\s*\[/GEWIJZIGD\]")

    def test_gewone_tekst_blijft_ongemarkeerd(self) -> None:
        self.assertIn("Gewone tekst.", self.tekst)
        self.assertNotRegex(self.tekst, r"(?<!/)\[GEWIJZIGD\]\s*Gewone")


class RapportTests(unittest.TestCase):
    """Opschoonrapport (#30): weggehaalde stukken met context, twijfelgevallen bovenaan."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.map = Path(tmp.name)

    def rapport(self, teken) -> str:
        pdf = self.map / "doc.pdf"
        doc = pymupdf.open()
        teken(doc.new_page())
        doc.save(pdf)
        return clean_pdf.opschonen(pdf)[1]

    def twijfels(self, rapport: str) -> str:
        return rapport.split("## Weggehaalde stukken")[0]

    def test_weggehaald_stuk_staat_per_pagina_met_context(self) -> None:
        rapport = self.rapport(lambda p: maak_pdf_pagina(p))
        weggehaald = rapport.split("## Weggehaalde stukken")[1]
        self.assertIn("Pagina 1", weggehaald)
        self.assertIn("U11 ~~5,78~~ 5,90 meter", weggehaald)
        self.assertIn("Geen.", self.twijfels(rapport))

    def test_doorgehaald_maar_niet_rood_is_twijfelgeval(self) -> None:
        def teken(page: pymupdf.Page) -> None:
            page.insert_text((72, 100), "Leeftijd 12 jaar", fontsize=11)
            page.draw_line((110, 96.5), (123, 96.5))

        twijfels = self.twijfels(self.rapport(teken))
        self.assertIn("- [ ] Pagina 1, doorgehaald maar niet rood: Leeftijd ~~12~~ jaar", twijfels)

    def test_doorgehaald_teken_zonder_letters_of_cijfers_is_geen_twijfelgeval(self) -> None:
        def teken(page: pymupdf.Page) -> None:
            page.insert_text((72, 100), "* Als je je hebt", fontsize=11)
            page.draw_line((72, 96.5), (76, 96.5))

        rapport = self.rapport(teken)
        self.assertIn("Geen.", self.twijfels(rapport))
        self.assertIn("~~*~~ Als je je", rapport.split("## Weggehaalde stukken")[1])

    def test_rode_tekst_met_lijn_net_buiten_de_band_is_bijna_doorhaling(self) -> None:
        def teken(page: pymupdf.Page) -> None:
            page.insert_text((72, 100), "Leeftijd", fontsize=11)
            page.insert_text((110.5, 100), "12", fontsize=11, color=(1, 0, 0))
            page.insert_text((125.8, 100), "jaar", fontsize=11)
            page.draw_line((110, 91.2), (123, 91.2))  # 20% van de tekenhoogte: boven de band

        rapport = self.rapport(teken)
        self.assertIn("- [ ] Pagina 1, bijna-doorhaling (blijft staan): Leeftijd ~~12~~ jaar", self.twijfels(rapport))
        self.assertIn("12", clean_pdf.clean_pdf(self.map / "doc.pdf"))

    def test_rode_tekst_zonder_enige_doorhaling_is_twijfelgeval(self) -> None:
        def teken(page: pymupdf.Page) -> None:
            page.insert_text((72, 100), "Nieuwe regel per 2026.", fontsize=11, color=(1, 0, 0))

        self.assertIn("- [ ] Rode tekst maar geen enkele doorhaling", self.twijfels(self.rapport(teken)))

    def test_document_zonder_rood_en_zonder_doorhaling_heeft_geen_twijfels(self) -> None:
        def teken(page: pymupdf.Page) -> None:
            page.insert_text((72, 100), "Gewone tekst.", fontsize=11)

        self.assertIn("Geen.", self.twijfels(self.rapport(teken)))


class CliTests(unittest.TestCase):
    def test_schrijft_opgeschoonde_versie_en_rapport(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            map_ = Path(tmp)
            pdf = map_ / "Titel.pdf"
            maak_pdf(pdf)

            code = clean_pdf.main([str(pdf), "--out", str(map_ / "knwu"), "--review", str(map_ / "review")])

            self.assertEqual(code, 0)
            self.assertNotIn("5,78", (map_ / "knwu" / "Titel.md").read_text(encoding="utf-8"))
            rapport = (map_ / "review" / "Titel.md").read_text(encoding="utf-8")
            self.assertIn("# Opschoonrapport: Titel.pdf", rapport)
            self.assertIn("~~5,78~~", rapport)

    def test_rapport_standaard_in_knowledge_documents_review(self) -> None:
        self.assertEqual(clean_pdf.DEFAULT_REVIEW_DIR, ROOT / "knowledge-documents" / "review")


class SplitTests(unittest.TestCase):
    """--split: één bestand per hoofdstuk, zodat de bestandsnaam (die Mistral bij elke
    chunk meegeeft) de discipline draagt."""

    def test_split_schrijft_een_bestand_per_hoofdstuk(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            map_ = Path(tmp)
            pdf = map_ / "NB_20260918.pdf"
            maak_kop_pdf(pdf, [
                ("Titelpagina", 11, False),
                ("INHOUDSOPGAVE", 20, True),
                ("1. ALGEMEEN ..... 4", 11, False),
                ("1. ALGEMEEN", 20, True),
                ("Over licenties.", 11, False),
                ("Hoofdstuk 2 : WEG", 20, True),
                ("2.4 NATIONALE KAMPIOENSCHAPPEN", 15, True),
                ("Over het NK.", 11, False),
            ])
            profielen = map_ / "kopprofielen.json"
            profielen.write_text(json.dumps({"NB": PROFIEL}), encoding="utf-8")
            out = map_ / "knwu"

            code = clean_pdf.main([
                str(pdf), "--out", str(out), "--review", str(map_ / "review"),
                "--kopprofielen", str(profielen), "--split",
            ])

            self.assertEqual(code, 0)
            namen = sorted(p.name for p in out.iterdir())
            self.assertEqual(namen, ["NB_20260918 - 1. ALGEMEEN.md", "NB_20260918 - Hoofdstuk 2 - WEG.md"])
            eerste = (out / namen[0]).read_text(encoding="utf-8")
            tweede = (out / namen[1]).read_text(encoding="utf-8")
            self.assertTrue(eerste.startswith("Titelpagina\n\n# 1. ALGEMEEN\n"))
            self.assertNotIn("INHOUDSOPGAVE", eerste)
            self.assertTrue(tweede.startswith("# Hoofdstuk 2 : WEG\n"))
            self.assertIn("## Hoofdstuk 2 : WEG › 2.4 NATIONALE KAMPIOENSCHAPPEN", tweede)
            self.assertTrue((map_ / "review" / "NB_20260918.md").exists())

    def test_zonder_split_een_bestand_met_koppen_uit_het_profiel(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            map_ = Path(tmp)
            pdf = map_ / "NB_20260918.pdf"
            maak_kop_pdf(pdf, [("1. ALGEMEEN", 20, True), ("Over licenties.", 11, False)])
            profielen = map_ / "kopprofielen.json"
            profielen.write_text(json.dumps({"NB": PROFIEL}), encoding="utf-8")

            clean_pdf.main([
                str(pdf), "--out", str(map_ / "knwu"), "--review", str(map_ / "review"),
                "--kopprofielen", str(profielen),
            ])

            self.assertIn("# 1. ALGEMEEN\n", (map_ / "knwu" / "NB_20260918.md").read_text(encoding="utf-8"))

    def test_hoofdstuk_buiten_scope_krijgt_geen_bestand_maar_staat_in_het_rapport(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            map_ = Path(tmp)
            pdf = map_ / "NB_20260918.pdf"
            maak_kop_pdf(pdf, [
                ("1. ALGEMEEN", 20, True), ("Over licenties.", 11, False),
                ("4. MOUNTAINBIKE", 20, True), ("Over het LJC.", 11, False),
            ])
            profielen = map_ / "kopprofielen.json"
            profielen.write_text(json.dumps({"NB": {**PROFIEL, "buiten_scope": [r"^4\. "]}}), encoding="utf-8")
            out = map_ / "knwu"

            clean_pdf.main([
                str(pdf), "--out", str(out), "--review", str(map_ / "review"),
                "--kopprofielen", str(profielen), "--split",
            ])

            self.assertEqual([p.name for p in out.iterdir()], ["NB_20260918 - 1. ALGEMEEN.md"])
            rapport = (map_ / "review" / "NB_20260918.md").read_text(encoding="utf-8")
            self.assertIn("## Niet in de library (buiten scope)\n\n- 4. MOUNTAINBIKE", rapport)


def maak_pdf_pagina(page: pymupdf.Page) -> None:
    page.insert_text((72, 100), "U11", fontsize=11)
    page.insert_text((120, 100), "5,78", fontsize=11, color=(1, 0, 0))
    page.insert_text((160, 100), "5,90 meter", fontsize=11)
    page.draw_line((118, 96.5), (146, 96.5))


class TabelTests(unittest.TestCase):
    """Tabellen als markdown-tabel, zodat de kolombetekenis blijft (#33)."""

    def test_tabel_wordt_markdown_tabel_met_doorhaling_en_rood_per_cel(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "tabel.pdf"
            doc = pymupdf.open()
            page = doc.new_page()
            page.insert_text((72, 60), "De toegestane verzetten:", fontsize=11)
            # Vier rijen: bij minder rijen valt pymupdf terug op een tabel op basis van tekst.
            kolommen, rijen = [70, 170, 300, 430], [80, 110, 140, 170, 200]
            for x in kolommen:
                page.draw_line((x, rijen[0]), (x, rijen[-1]))
            for y in rijen:
                page.draw_line((kolommen[0], y), (kolommen[-1], y))
            for x, tekst in zip(kolommen, ["Categorie", "Weg", "Baan"]):
                page.insert_text((x + 5, 100), tekst, fontsize=11)
            page.insert_text((75, 130), "U10", fontsize=11, color=(1, 0, 0))
            # Eén tekstrun zoals in de PDF, met alleen een spatie tussen oude en nieuwe waarde.
            page.insert_text((175, 130), "5,46 5,50", fontsize=11, color=(1, 0, 0))
            breedte_oud = pymupdf.get_text_length("5,46", fontsize=11)
            page.draw_rect((175, 126.2, 175 + breedte_oud, 126.8), color=None, fill=(1, 0, 0))
            page.insert_text(
                (175 + pymupdf.get_text_length("5,46 5,50 ", fontsize=11), 130), "meter", fontsize=11
            )
            page.insert_text((305, 130), "5,46 meter", fontsize=11)
            for y, categorie in [(160, "U11"), (190, "U12")]:
                page.insert_text((75, y), categorie, fontsize=11)
                page.insert_text((175, y), "5,90 meter", fontsize=11)
                page.insert_text((305, y), "5,78 meter", fontsize=11)
            page.insert_text((72, 230), "Na de tabel.", fontsize=11)
            doc.save(pdf)

            tekst = clean_pdf.clean_pdf(pdf)

        self.assertIn(
            "| Categorie | Weg | Baan |\n| --- | --- | --- |\n"
            f"| {GEW}U10{GEW_SLUIT} | {GEW}5,50{GEW_SLUIT} meter | 5,46 meter |",
            tekst,
        )
        self.assertLess(tekst.index("De toegestane verzetten:"), tekst.index("| Categorie"))
        self.assertLess(tekst.index("| Categorie"), tekst.index("Na de tabel."))


class NationaleBesluitenTabelTests(unittest.TestCase):
    def test_titelrij_over_de_volle_breedte_staat_er_een_keer(self) -> None:
        kandidaten = sorted((ROOT / "knowledge-documents").glob("*/Nationale_Besluiten_20260918*.pdf"))
        if not kandidaten:
            self.skipTest("Nationale_Besluiten_20260918.pdf niet lokaal aanwezig")
        tekst = clean_pdf.clean_pdf(kandidaten[0])
        self.assertIn("| 5 Tussensprints en eindsprint |  |  |  |  |", tekst)
        self.assertNotIn("| 5 Tussensprints en eindsprint | 5 Tussensprints", tekst)


GEW, GEW_SLUIT = clean_pdf.GEWIJZIGD_OPEN, clean_pdf.GEWIJZIGD_SLUIT


class TitelTwintigTests(unittest.TestCase):
    """Feiten uit de handmatige review van eval run 3 (#28), geverifieerd in de PDF."""

    @classmethod
    def setUpClass(cls) -> None:
        # PDF's staan niet in git (.gitignore): zonder lokale kopie overslaan.
        kandidaten = sorted((ROOT / "knowledge-documents").glob("*/TITEL_20-Jeugdwielrennen_20260921*.pdf"))
        if not kandidaten:
            raise unittest.SkipTest("TITEL_20-Jeugdwielrennen_20260921.pdf niet lokaal aanwezig")
        tekst = clean_pdf.clean_pdf(kandidaten[0])
        cls.tekst = re.sub(r"\s+", " ", tekst.replace(GEW, "").replace(GEW_SLUIT, ""))

    def test_doorgehaalde_nk_uitsluiting_verdwijnt(self) -> None:
        self.assertNotIn("kunnen zich niet kwalificeren voor het NK", self.tekst)
        self.assertNotIn("wel uitsluiting van deelname", self.tekst)

    def test_geldende_nk_regel_blijft(self) -> None:
        self.assertIn("ook mogen deelnemen aan het Nationaal Kampioenschap", self.tekst)

    def test_verzet_u11_weg_590_baan_578_veld_vrij(self) -> None:
        # Kolommen: Jongens | Meisjes | Wegwielrennen | Baanwielrennen | Veldrijden (#33)
        self.assertIn("| Jongens | Meisjes | Wegwielrennen | Baanwielrennen | Veldrijden |", self.tekst)
        self.assertIn("| U11 | U12 | 5,90 meter | 5,78 meter | vrij |", self.tekst)


PROFIEL = {
    "koppen": [
        {"niveau": 1, "grootte": 20},
        {"niveau": 2, "grootte": 15},
        {"niveau": 3, "grootte": 11, "patroon": r"^\d+\.\d+\.\d+"},
    ],
    "weglaten": ["^INHOUDSOPGAVE$"],
}


def maak_kop_pdf(path: Path, regels: list[tuple[str, int, bool]]) -> None:
    """Eén pagina met (tekst, lettergrootte, vet)-regels onder elkaar, elk een eigen blok."""
    doc = pymupdf.open()
    page = doc.new_page()
    y = 60
    for tekst, grootte, vet in regels:
        page.insert_text((72, y), tekst, fontsize=grootte, fontname="hebo" if vet else "helv")
        y += grootte + 16
    doc.save(path)


class KopTests(unittest.TestCase):
    """Koppen uit de PDF-opmaak als markdown-kop met het volledige pad, zodat elke chunk
    zijn discipline en paragraaf draagt (feedback NK weg jeugd, 2026-11-13)."""

    def opschonen(self, regels: list[tuple[str, int, bool]], profiel: dict | None = PROFIEL) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "doc.pdf"
            maak_kop_pdf(pdf, regels)
            return clean_pdf.opschonen(pdf, profiel)[0]

    def test_kop_krijgt_het_pad_van_bovenliggende_koppen(self) -> None:
        tekst = self.opschonen([
            ("2. WEGWIELRENNEN", 20, True),
            ("2.4 NATIONALE KAMPIOENSCHAPPEN", 15, True),
            ("2.4.3 SELECTIEPROCEDURES NK WEG", 11, True),
            ("De selectie gaat via de regio.", 11, False),
        ])
        self.assertIn("# 2. WEGWIELRENNEN\n", tekst)
        self.assertIn("## 2. WEGWIELRENNEN › 2.4 NATIONALE KAMPIOENSCHAPPEN\n", tekst)
        self.assertIn(
            "### 2. WEGWIELRENNEN › 2.4 NATIONALE KAMPIOENSCHAPPEN › 2.4.3 SELECTIEPROCEDURES NK WEG\n",
            tekst,
        )
        self.assertIn("De selectie gaat via de regio.", tekst)

    def test_titel_en_artikelnummer_in_een_blok_worden_een_kop_met_nummer_voorop(self) -> None:
        profiel = {"koppen": [{"niveau": 2, "grootte": 11, "patroon": r"^20\.\d+\.\d{3}$", "titel_erbij": True}]}
        tekst = self.opschonen(
            [("Categorie-indeling\n20.0.004", 11, True), ("De jeugd wordt onderverdeeld.", 11, False)],
            profiel,
        )
        self.assertIn("## 20.0.004 Categorie-indeling\n", tekst)
        self.assertNotIn("\nCategorie-indeling\n", tekst)

    def test_zonder_titel_erbij_blijft_een_vet_tussenkopje_lopende_tekst(self) -> None:
        profiel = {"koppen": [{"niveau": 4, "grootte": 11, "hoofdletters": True}]}
        tekst = self.opschonen([("NK WEG MASTERS\nAanmelden", 11, True), ("Tijdig aanmelden.", 11, False)], profiel)
        self.assertIn("#### NK WEG MASTERS\n\nAanmelden", tekst)

    def test_opsomming_van_drie_vette_regels_is_geen_kop(self) -> None:
        profiel = {"koppen": [{"niveau": 4, "grootte": 11, "patroon": "^NK "}]}
        tekst = self.opschonen(
            [("NK WEG JUNIOR MEN\nNK WEG U17 JONGENS\nNK WEG JEUGD", 11, True), ("Aan het NK Weg ...", 11, False)],
            profiel,
        )
        self.assertNotIn("#", tekst)
        self.assertIn("NK WEG JEUGD", tekst)

    def test_hoofdletterregel_herkent_alleen_vette_regels_in_hoofdletters(self) -> None:
        profiel = {"koppen": [{"niveau": 4, "grootte": 11, "hoofdletters": True}]}
        tekst = self.opschonen(
            [("JEUGD", 11, True), ("Let op: dit is nadruk.", 11, True), ("20260921", 11, True), ("Gewone tekst.", 11, False)],
            profiel,
        )
        self.assertIn("#### JEUGD\n", tekst)
        self.assertNotIn("# Let op", tekst)
        self.assertNotIn("# 20260921", tekst)

    def test_zinsrest_en_lange_zin_in_vet_zijn_geen_kop(self) -> None:
        profiel = {"koppen": [{"niveau": 5, "grootte": 12}]}
        lange_zin = "Na het NK veldrijden zijn er 6 weken puntloze wedstrijden, deze tellen niet mee voor de"
        tekst = self.opschonen(
            [("Landelijk Jeugd Toernooi(LJT)", 12, True), ("deelnemen in dit weekend", 12, True),
             (lange_zin, 12, True), ("Gewone tekst.", 11, False)],
            profiel,
        )
        self.assertIn("##### Landelijk Jeugd Toernooi(LJT)\n", tekst)
        self.assertNotIn("# deelnemen", tekst)
        self.assertNotIn("# Na het NK", tekst)

    def test_inhoudsopgave_valt_weg_tot_de_volgende_kop_van_hetzelfde_niveau(self) -> None:
        tekst = self.opschonen([
            ("Titelpagina", 11, False),
            ("INHOUDSOPGAVE", 20, True),
            ("1.1 KALENDERS .......... 4", 15, True),
            ("2. WEGWIELRENNEN .......... 15", 11, False),
            ("2. WEGWIELRENNEN", 20, True),
            ("Inhoud van het hoofdstuk.", 11, False),
        ])
        self.assertNotIn("INHOUDSOPGAVE", tekst)
        self.assertNotIn("..........", tekst)
        self.assertIn("Titelpagina", tekst)
        self.assertIn("# 2. WEGWIELRENNEN\n\nInhoud van het hoofdstuk.", tekst)

    def rapport(self, regels: list[tuple[str, int, bool]], profiel: dict | None = PROFIEL) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "doc.pdf"
            maak_kop_pdf(pdf, regels)
            return clean_pdf.opschonen(pdf, profiel)[1]

    def test_rapport_toont_gevonden_koppen_ingesprongen_per_niveau(self) -> None:
        rapport = self.rapport([("2. WEGWIELRENNEN", 20, True), ("2.4 NATIONALE KAMPIOENSCHAPPEN", 15, True)])
        koppen = rapport.split("## Gevonden koppen (2)")[1]
        self.assertIn("- p1 2. WEGWIELRENNEN\n  - p1 2.4 NATIONALE KAMPIOENSCHAPPEN", koppen)

    def test_profiel_zonder_gevonden_koppen_is_een_twijfelgeval(self) -> None:
        rapport = self.rapport([("Alleen gewone tekst.", 11, False)])
        twijfels = rapport.split("## Weggehaalde stukken")[0]
        self.assertIn("geen enkele kop gevonden", twijfels)

    def test_zonder_profiel_geen_koppensectie(self) -> None:
        self.assertNotIn("Gevonden koppen", self.rapport([("2. WEGWIELRENNEN", 20, True)], profiel=None))


def kop_boven(tekst: str, fragment: str) -> str:
    """De dichtstbijzijnde markdown-kop vóór `fragment`."""
    voor = tekst[: tekst.index(fragment)]
    return [r for r in voor.splitlines() if r.startswith("#")][-1]


class EchteKoppenTests(unittest.TestCase):
    """Koppen in de echte KNWU-PDF's met scripts/kopprofielen.json (feedback NK weg jeugd)."""

    @staticmethod
    def opgeschoond(patroon: str) -> str:
        kandidaten = sorted((ROOT / "knowledge-documents").glob(f"*/{patroon}*.pdf"))
        if not kandidaten:
            raise unittest.SkipTest(f"{patroon}.pdf niet lokaal aanwezig")
        profiel = clean_pdf.kopprofiel(kandidaten[0].stem, clean_pdf.DEFAULT_KOPPROFIELEN)
        tekst = clean_pdf.opschonen(kandidaten[0], profiel)[0]
        return tekst.replace(GEW, "").replace(GEW_SLUIT, "")

    def test_nationale_besluiten(self) -> None:
        tekst = self.opgeschoond("Nationale_Besluiten_20260918")
        ljt = kop_boven(tekst, "Het LJT is onderdeel van de selectieprocedure")
        self.assertIn("2. WEGWIELRENNEN", ljt)
        self.assertIn("› NK Weg Jeugd ›", ljt)
        self.assertTrue(ljt.endswith("Landelijk Jeugd Toernooi(LJT)"), ljt)
        mtb = kop_boven(tekst, "Voor deelname aan het NK mountainbike jeugd")
        self.assertIn("4. MOUNTAINBIKE", mtb)
        self.assertTrue(mtb.endswith("› JEUGD"), mtb)
        self.assertIn("2.4.1 ALGEMEEN", kop_boven(tekst, "Aan het NK Weg kan alleen worden deelgenomen"))
        self.assertNotIn("INHOUDSOPGAVE", tekst)

    def test_titel_twintig(self) -> None:
        tekst = self.opgeschoond("TITEL_20-Jeugdwielrennen_20260921")
        nk = kop_boven(tekst, "Uitnodiging tot deelname aan de nationale kampioenschappen")
        self.assertIn("Hoofdstuk 2 : WEDSTRIJDEN OP DE WEG", nk)
        self.assertTrue(nk.endswith("20.2.008 NK Weg Jeugd"), nk)
        categorie = kop_boven(tekst, "De categorie jeugd wordt onderverdeeld")
        self.assertIn("ALGEMENE BEPALINGEN", categorie)
        self.assertTrue(categorie.endswith("20.0.004 Categorie-indeling"), categorie)
        self.assertNotIn("INHOUDSOPGAVE", tekst)


class HandboekRapportTests(unittest.TestCase):
    def test_doorgehaald_opsommingsteken_is_zichtbaar_maar_geen_twijfelgeval(self) -> None:
        kandidaten = sorted((ROOT / "knowledge-documents").glob("*/Handboek Veldrijden Jeugd 2026-2027*.pdf"))
        if not kandidaten:
            self.skipTest("Handboek Veldrijden Jeugd 2026-2027.pdf niet lokaal aanwezig")
        twijfels, weggehaald = clean_pdf.opschonen(kandidaten[0])[1].split("## Weggehaalde stukken")
        self.assertIn("Geen.", twijfels)
        self.assertIn("categorie, tenzij anders bepaald. ~~U+F0B7~~", weggehaald)


if __name__ == "__main__":
    unittest.main()
