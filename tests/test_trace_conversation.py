import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import trace_conversation  # noqa: E402

AGENTS = {"router-id": "router-agent", "regio-id": "regio-agent", "knwu-id": "knwu-agent"}

# Shape van GET /v1/conversations/{id}/history: een MNC-vraag via de router
# naar de regio-agent, daarna een verzetvraag die bij de regio-agent blijft.
STICKY_HISTORY = [
    {"type": "message.input", "role": "user", "content": "Wanneer is de volgende MNC-veldrit?"},
    {"type": "agent.handoff", "previous_agent_name": "router-agent", "next_agent_name": "regio-agent"},
    {"type": "tool.execution", "name": "document_library", "agent_id": "regio-id"},
    {"type": "message.output", "agent_id": "regio-id", "content": [{"type": "text", "text": "..."}]},
    {
        "type": "message.input",
        "role": "user",
        "content": "Welk verzet? 2015\n\nContextregels van de app (geen tekst van de gebruiker):\n- regel",
    },
    {"type": "tool.execution", "name": "web_search", "agent_id": "regio-id"},
    {"type": "message.output", "agent_id": "regio-id", "content": "..."},
]


class TestSummarizeTurns(unittest.TestCase):
    def test_one_turn_per_user_message(self):
        turns = trace_conversation.summarize_turns(STICKY_HISTORY, AGENTS)
        self.assertEqual(len(turns), 2)
        self.assertEqual(turns[0]["handoffs"], ["router-agent -> regio-agent"])
        self.assertEqual(turns[0]["tools"], ["document_library"])
        self.assertEqual(turns[0]["answered_by"], ["regio-agent"])

    def test_follow_up_without_handoff_shows_sticky_agent(self):
        follow_up = trace_conversation.summarize_turns(STICKY_HISTORY, AGENTS)[1]
        self.assertEqual(follow_up["handoffs"], [])
        self.assertEqual(follow_up["answered_by"], ["regio-agent"])

    def test_context_lines_are_stripped_from_question(self):
        follow_up = trace_conversation.summarize_turns(STICKY_HISTORY, AGENTS)[1]
        self.assertEqual(follow_up["question"], "Welk verzet? 2015")
        self.assertTrue(follow_up["context_lines"])

    def test_unknown_agent_id_is_shown_raw(self):
        entries = [
            {"type": "message.input", "content": "vraag"},
            {"type": "message.output", "agent_id": "onbekend-id", "content": "x"},
        ]
        self.assertEqual(trace_conversation.summarize_turns(entries, AGENTS)[0]["answered_by"], ["onbekend-id"])

    def test_format_turns(self):
        text = trace_conversation.format_turns(trace_conversation.summarize_turns(STICKY_HISTORY, AGENTS))
        self.assertIn("Beurt 2: Welk verzet? 2015 (+ contextregels)", text)
        self.assertIn("  antwoord door: regio-agent", text)


class TestApi(unittest.TestCase):
    def test_find_by_app_id_filters_on_metadata(self):
        response = mock.Mock(status_code=200, json=lambda: [{"id": "conv-1"}])
        with mock.patch.object(trace_conversation.requests, "get", return_value=response) as get:
            found = trace_conversation.find_by_app_id("abc", "key")
        self.assertEqual(found, [{"id": "conv-1"}])
        self.assertEqual(get.call_args.kwargs["params"], {"metadata": '{"app_conversation_id": "abc"}'})

    def test_api_error_is_informative(self):
        response = mock.Mock(status_code=401, text="Unauthorized")
        with mock.patch.object(trace_conversation.requests, "get", return_value=response):
            with self.assertRaisesRegex(RuntimeError, "401"):
                trace_conversation.fetch_entries("conv-1", "key")


if __name__ == "__main__":
    unittest.main()
