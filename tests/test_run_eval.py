import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "eval"))

import run_eval


# Realistische shape van POST /v1/conversations (captured 2026-11-04):
# content zit top-level in het output-entry, niet onder "message".
REAL_OUTPUTS = [
    {
        "object": "entry",
        "type": "message.output",
        "role": "assistant",
        "content": [
            {"type": "thinking", "thinking": [{"type": "text", "text": "even nadenken"}]}
        ],
    },
    {
        "object": "entry",
        "type": "tool.execution",
        "name": "document_library",
        "arguments": "{\"query\": \"verzet U15\"}",
        "info": {"result": "..."},
    },
    {
        "object": "entry",
        "type": "message.output",
        "role": "assistant",
        "content": [
            {"type": "text", "text": "Maximaal 6,70 meter.\n\nBron: TITEL_20-Jeugdwielrennen_20260921.pdf, versie 2026-09-21"}
        ],
    },
]


class ExtractTextTests(unittest.TestCase):
    def test_real_conversations_shape(self) -> None:
        # Regressie: de oude code las out["message"]["content"] en kreeg ""
        # -> eval 0/20. Nu: top-level content, alleen text-chunks.
        self.assertEqual(
            run_eval.extract_text(REAL_OUTPUTS),
            "Maximaal 6,70 meter.\n\nBron: TITEL_20-Jeugdwielrennen_20260921.pdf, versie 2026-09-21",
        )

    def test_string_content(self) -> None:
        self.assertEqual(
            run_eval.extract_text([{"type": "message.output", "content": "platte tekst"}]),
            "platte tekst",
        )

    def test_tool_execution_entries_ignored(self) -> None:
        self.assertEqual(run_eval.extract_text(REAL_OUTPUTS[1:2]), "")


class AskWithRetryTests(unittest.TestCase):
    def test_retries_once_on_timeout_then_succeeds(self) -> None:
        import requests
        from unittest.mock import patch

        calls = {"n": 0}

        def fake_call(vraag, agent_id, api_key, timeout=None):
            calls["n"] += 1
            if calls["n"] == 1:
                raise requests.ReadTimeout("read timed out")
            return "antwoord"

        with patch.object(run_eval, "call_agent", side_effect=fake_call):
            antwoord, error = run_eval.ask_with_retry("vraag", "agent", "key")
        self.assertEqual(antwoord, "antwoord")
        self.assertEqual(error, "")
        self.assertEqual(calls["n"], 2)

    def test_gives_up_after_attempts_and_reports_error(self) -> None:
        import requests
        from unittest.mock import patch

        with patch.object(
            run_eval, "call_agent", side_effect=requests.ReadTimeout("read timed out")
        ):
            antwoord, error = run_eval.ask_with_retry("vraag", "agent", "key", attempts=2)
        self.assertEqual(antwoord, "")
        self.assertIn("ReadTimeout", error)

    def timeouts_per_poging(self, vraagtype: str) -> list:
        import requests
        from unittest.mock import patch

        timeouts = []

        def fake_call(vraag, agent_id, api_key, timeout):
            timeouts.append(timeout)
            raise requests.ReadTimeout("read timed out")

        with patch.object(run_eval, "call_agent", side_effect=fake_call):
            run_eval.ask_with_retry("vraag", "agent", "key", vraagtype=vraagtype)
        return timeouts

    def test_websearch_krijgt_ruimere_timeout_en_extra_poging(self) -> None:
        self.assertEqual(self.timeouts_per_poging("websearch"), [300, 300, 300])

    def test_standaard_houdt_gewone_timeout(self) -> None:
        self.assertEqual(self.timeouts_per_poging("standaard"), [180, 180])


class NormalizeTests(unittest.TestCase):
    def test_phone_number_dash_space_parens(self) -> None:
        self.assertEqual(run_eval.normalize("085-070 19 00"), run_eval.normalize("+31 (0)85 070 1900")[:0] or run_eval.normalize("085-070 19 00"))
        self.assertIn(run_eval.normalize("085-070 19 00"), run_eval.normalize("+31 (0)85 070 1900"))

    def test_decimal_comma_and_article(self) -> None:
        self.assertEqual(run_eval.normalize("6.70 meter"), "6,70meter")
        self.assertEqual(run_eval.normalize("artikel 20.1.007"), run_eval.normalize("Artikel 20.1.007"))


class BronMatchTests(unittest.TestCase):
    def test_exact_filename_in_line(self) -> None:
        self.assertTrue(
            run_eval.bron_match(
                "TITEL_20-Jeugdwielrennen_20260921.pdf",
                "TITEL_20-Jeugdwielrennen_20260921.pdf, versie 2026-09-21",
            )
        )

    def test_url_with_path(self) -> None:
        self.assertTrue(
            run_eval.bron_match(
                "kenniscentrum.knwu.nl/knwu-licenties",
                "Bron: https://kenniscentrum.knwu.nl/knwu-licenties, geraadpleegd op 2026-11-04",
            )
        )

    def test_short_line_matches_longer_expected(self) -> None:
        self.assertTrue(run_eval.bron_match("wtcwoerden.nl?page=674", "wtcwoerden.nl"))

    def test_unrelated_does_not_match(self) -> None:
        self.assertFalse(run_eval.bron_match("knwumidden.nl/competities", "wtcwoerden.nl?page=607"))
        self.assertFalse(run_eval.bron_match("", "iets"))

    def test_sessie_parameter_en_index_php_tellen_niet_mee(self) -> None:
        line = "https://www.wtcwoerden.nl/index.php?page=674&sid=1, geraadpleegd op 2026-11-05."
        self.assertTrue(run_eval.bron_match("wtcwoerden.nl?page=674", line))

    def test_andere_pagina_matcht_niet(self) -> None:
        line = "https://www.wtcwoerden.nl/index.php?page=607&sid=1"
        self.assertFalse(run_eval.bron_match("wtcwoerden.nl?page=674", line))


class ResultTraceTests(unittest.TestCase):
    def test_result_bevat_verwachting_en_antwoord(self) -> None:
        # run_eval.main() slaat per entry vraag + verwacht_antwoord/verwachte_bron
        # + het echte antwoord op in last_run.json (visuele trace voor review).
        entry = {
            "id": "x",
            "categorie": "knwu",
            "type": "standaard",
            "vraag": "V?",
            "verwacht_antwoord": "a; b",
            "bron": "doc.pdf",
            "versiedatum": "2026-09-21",
            "doorhaal_waarde": "oud",
        }
        result = run_eval.check_entry(entry, "antwoord\n\nBron: doc.pdf, versie 2026-09-21")
        for key in ("vraag", "verwacht_antwoord", "verwachte_bron", "versiedatum", "doorhaal_waarde", "antwoord"):
            self.assertIn(key, result)

    def test_lang_antwoord_wordt_volledig_bewaard(self) -> None:
        lang = "x" * 3000 + "\n\nBron: doc.pdf"
        result = run_eval.check_entry(entry("x-y", "x", "doc.pdf"), lang)
        self.assertEqual(result["antwoord"], lang)


import json

# Echte antwoorden uit eval run 3, per vraag handmatig beoordeeld (#28).
RUN3 = json.loads(
    (Path(__file__).parent / "fixtures" / "eval_run3_antwoorden.json").read_text(encoding="utf-8")
)["antwoorden"]


def entry(id: str, verwacht: str, bron: str, type: str = "standaard", doorhaal: str = "") -> dict:
    return {
        "id": id,
        "categorie": id.split("-")[0],
        "type": type,
        "vraag": "?",
        "verwacht_antwoord": verwacht,
        "bron": bron,
        "doorhaal_waarde": doorhaal,
    }


class CheckEntryRun3Tests(unittest.TestCase):
    """Fixtures: gecorrigeerde evalset-entry + echt run-3-antwoord + reviewoordeel."""

    def assertOk(self, e: dict) -> None:
        result = run_eval.check_entry(e, RUN3[e["id"]])
        self.assertTrue(result["ok"], result)

    def test_tijd_met_punt_matcht_tijd_met_dubbele_punt(self) -> None:
        self.assertOk(
            entry(
                "regio-mnc-veldrijden-starttijden",
                "2026-2027; 11:05; 11:30",
                "knwumidden.nl/competities",
            )
        )


# Oordeel per vraag uit de handmatige review van run 3 (#28): True = het
# antwoord is inhoudelijk goed mét juiste bron. De entries zelf komen uit
# eval/evalset.yaml, zodat evalset en test niet uit elkaar lopen.
RUN3_OORDEEL = {
    # false negatives van de oude matcher/evalset
    "club-zmc-wanneer": True,
    "knwu-licentie-pakketten": True,
    "knwu-verzekering-dekking": True,
    "knwu-inschrijfgeld-jeugd": True,
    "knwu-nk-dispensatie-u10": True,
    "knwu-actuele-versie-titel20": True,
    "knwu-wijziging-nationale-besluiten": True,
    "regio-mnc-veldrijden-starttijden": True,
    "regio-hvh-kalender-2026": True,
    "regio-juiste-knwu-regio": True,
    "regio-techniekwedstrijden-2026": True,
    # true positives
    "club-zmc-kosten": True,
    "knwu-verzet-u15": True,
    "knwu-verzet-u17": True,
    # true negatives: moeten blijven falen
    "knwu-contact": False,  # inhoud goed, maar bron verkeerd toegeschreven
    "club-contributie-jeugd-2026": False,
    "club-vertrouwenspersoon": False,
    "club-gedragscode": False,
    "knwu-verzet-u11": False,
    "regio-nk-kwalificatie": False,
}


class Run3ReviewTests(unittest.TestCase):
    def test_evalset_oordeel_matcht_handmatige_review(self) -> None:
        evalset = run_eval.load_evalset(Path(run_eval.EVAL_DIR) / "evalset.yaml")
        self.assertEqual({e["id"] for e in evalset}, set(RUN3_OORDEEL))
        for e in evalset:
            with self.subTest(id=e["id"]):
                result = run_eval.check_entry(e, RUN3[e["id"]])
                self.assertEqual(result["ok"], RUN3_OORDEEL[e["id"]], result)


class KernfeitGrenzenTests(unittest.TestCase):
    def missing(self, verwacht: str, antwoord: str) -> list:
        return run_eval.check_entry(entry("x-y", verwacht, "doc.pdf"), antwoord + "\n\nBron: doc.pdf")[
            "missende_kernfeiten"
        ]

    def test_getal_matcht_niet_binnen_een_groter_getal(self) -> None:
        self.assertEqual(self.missing("5", "Er zijn 15 wedstrijden."), ["5"])

    def test_kort_woord_matcht_niet_binnen_een_langer_woord(self) -> None:
        self.assertEqual(self.missing("ja", "Dit jaar niet."), ["ja"])

    def test_bedrag_met_nullen_matcht_bedrag_met_streepje(self) -> None:
        self.assertEqual(self.missing("10,00", "maximaal € 10,- extra"), [])

    def test_tijd_met_voorloopnul_matcht_tijd_zonder(self) -> None:
        self.assertEqual(self.missing("08:30", "tussen 8.30 en 12.00 uur"), [])


class EnvTests(unittest.TestCase):
    def test_env_bestand_wint_van_verouderde_shellvariabele(self) -> None:
        import os
        import tempfile
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp:
            env = Path(tmp) / ".env"
            env.write_text("MISTRAL_API_KEY=\n", encoding="utf-8")
            with (
                patch.object(run_eval, "ENV_PATH", env),
                patch.dict(os.environ, {"MISTRAL_API_KEY": "verouderd-uit-de-shell"}),
                self.assertRaisesRegex(RuntimeError, "MISTRAL_API_KEY ontbreekt"),
            ):
                run_eval.main()


if __name__ == "__main__":
    unittest.main()
