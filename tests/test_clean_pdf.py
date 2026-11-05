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


if __name__ == "__main__":
    unittest.main()
