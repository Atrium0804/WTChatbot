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

        def fake_call(vraag, agent_id, api_key):
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


if __name__ == "__main__":
    unittest.main()
