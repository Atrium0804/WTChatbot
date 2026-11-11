"""Naamgeving- en linkborging voor docs/ (issue #55).

- alle pagina's in docs/how-to/ hebben een kebab-case bestandsnaam (de
  actieve werkwoordsvorm is een review-conventie, zie DOCUMENTATION_GUIDE.md);
- elke how-to-pagina staat in de README.md-index van de map;
- alle relative markdown-links naar .md-bestanden in docs/ en de
  root-*.md-bestanden resolven naar bestaande bestanden (vangt rename-missers op).
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS = REPO_ROOT / "docs"
HOW_TO = DOCS / "how-to"

KEBAB_CASE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*\.md$")
MD_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


class HowToNamingTests(unittest.TestCase):
    def test_how_to_bestandsnamen_zijn_kebab_case(self) -> None:
        pages = [p for p in HOW_TO.glob("*.md") if p.name != "README.md"]
        self.assertTrue(pages, "geen how-to-pagina's gevonden")
        for page in pages:
            self.assertRegex(page.name, KEBAB_CASE)

    def test_elke_how_to_pagina_staat_in_index(self) -> None:
        index = (HOW_TO / "README.md").read_text(encoding="utf-8")
        for page in HOW_TO.glob("*.md"):
            if page.name == "README.md":
                continue
            self.assertIn(f"({page.name})", index)

    def test_relative_md_links_resolven(self) -> None:
        md_files = sorted(DOCS.rglob("*.md")) + sorted(REPO_ROOT.glob("*.md"))
        broken = []
        for md in md_files:
            for target in MD_LINK.findall(md.read_text(encoding="utf-8")):
                target = target.split("#", 1)[0].strip()
                if target.startswith(("http://", "https://", "mailto:")):
                    continue
                if not target.endswith(".md"):
                    continue
                if not (md.parent / target).resolve().exists():
                    broken.append(f"{md.relative_to(REPO_ROOT)} -> {target}")
        self.assertEqual(broken, [])


if __name__ == "__main__":
    unittest.main()
