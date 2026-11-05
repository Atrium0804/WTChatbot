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


def maak_pdf_pagina(page: pymupdf.Page) -> None:
    page.insert_text((72, 100), "U11", fontsize=11)
    page.insert_text((120, 100), "5,78", fontsize=11, color=(1, 0, 0))
    page.insert_text((160, 100), "5,90 meter", fontsize=11)
    page.draw_line((118, 96.5), (146, 96.5))


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
        self.assertIn("U11 U12 5,90 meter 5,78 meter vrij", self.tekst)


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
