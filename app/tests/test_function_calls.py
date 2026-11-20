"""Tests voor de function-call-lus (#149) — offline, zonder HTTP."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import function_calls  # noqa: E402
import knwu_categories  # noqa: E402
from mistral_client import FunctionCall  # noqa: E402

RULES = knwu_categories.load_rules()
VALID_ARGS = {
    "birth_year": 2012,
    "gender": "jongens",
    "chainring": 50,
    "smallest_sprocket": 11,
    "largest_sprocket": 28,
    "tire_width_mm": 28,
    "rim_diameter_mm": 622,
}


def _execute(arguments, name="bereken_verzet"):
    raw = arguments if isinstance(arguments, str) else json.dumps(arguments)
    return function_calls.execute(FunctionCall("c1", name, raw), year=2026, rules=RULES)


def test_bereken_verzet_returns_calculation_for_road():
    outcome = _execute(VALID_ARGS)

    result = json.loads(outcome.result)
    assert outcome.status == "ok"
    assert result["discipline"] == "weg"
    assert result["category"] == "U15"
    assert result["limit_m"] == 6.7
    assert result["current"]["heaviest_gear_m"] == 9.68
    assert result["current"]["within_limit"] is False
    assert outcome.trace_input == "50 11-28 28-622"
    assert outcome.trace_outcome == "U15 max 6.7 m: 9.68 m te zwaar"


def test_bereken_verzet_accepts_small_chainring():
    outcome = _execute({**VALID_ARGS, "small_chainring": 34})

    assert outcome.status == "ok"
    assert json.loads(outcome.result)["current"]["setup"]["small_chainring"] == 34
    assert outcome.trace_input == "50/34 11-28 28-622"


@pytest.mark.parametrize(
    "arguments, status, fragment",
    [
        ("{geen json", "invalid_input", "JSON"),
        ({k: v for k, v in VALID_ARGS.items() if k != "chainring"}, "invalid_input", "chainring"),
        ({**VALID_ARGS, "chainring": "50"}, "invalid_input", "chainring"),
        ({**VALID_ARGS, "chainring": True}, "invalid_input", "chainring"),
        ({**VALID_ARGS, "gender": "man"}, "invalid_input", "gender"),
        ({**VALID_ARGS, "wheel_size": 28}, "invalid_input", "wheel_size"),
        ({**VALID_ARGS, "rim_diameter_mm": 600}, "invalid_input", "velgdiameter"),
    ],
)
def test_bereken_verzet_returns_errors_as_tool_result(arguments, status, fragment):
    outcome = _execute(arguments)

    assert outcome.status == status
    assert fragment in json.loads(outcome.result)["error"]


def test_unknown_function_returns_error_result():
    outcome = _execute(VALID_ARGS, name="iets_anders")

    assert outcome.status == "error"
    assert "iets_anders" in json.loads(outcome.result)["error"]


def test_invalid_input_trace_outcome_omits_birth_year():
    wrong_type = _execute({**VALID_ARGS, "birth_year": "2012"})
    adult = _execute({**VALID_ARGS, "birth_year": 1990})

    assert wrong_type.trace_outcome == "ongeldig argument: birth_year"
    assert "1990" in json.loads(adult.result)["error"]
    assert adult.trace_outcome
    assert "1990" not in adult.trace_outcome


class FakeAgent:
    """Speelt Mistral na: elke beurt een lijst function calls (of geen) en een tekst."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.sent = []

    def send(self, inputs, conversation_id, on_function_call):
        self.sent.append((inputs, conversation_id))
        calls, text = self.replies.pop(0)
        for call in calls:
            on_function_call(call)
        return "conv-1", text


def _call(n):
    return FunctionCall(f"c{n}", "bereken_verzet", "{}")


def _run(agent, outcomes=None):
    executed = []

    def execute(call):
        executed.append(call.tool_call_id)
        return function_calls.Outcome('{"ok": true}', "ok")

    traced = []
    answer = function_calls.run_turn(
        send=agent.send,
        message="vraag",
        conversation_id=None,
        execute=execute,
        on_outcome=lambda call, outcome: traced.append((call.tool_call_id, outcome.status)),
    )
    return answer, executed, traced


def test_run_turn_without_function_calls_returns_answer():
    agent = FakeAgent([([], "antwoord")])

    answer, executed, _ = _run(agent)

    assert answer == ("conv-1", "antwoord")
    assert executed == []
    assert agent.sent == [("vraag", None)]


def test_run_turn_sends_results_back_to_same_conversation():
    agent = FakeAgent([([_call(1)], ""), ([], "Je verzet is te zwaar.")])

    answer, executed, traced = _run(agent)

    assert answer == ("conv-1", "Je verzet is te zwaar.")
    assert executed == ["c1"]
    assert traced == [("c1", "ok")]
    assert agent.sent[1] == (
        [{"type": "function.result", "tool_call_id": "c1", "result": '{"ok": true}'}],
        "conv-1",
    )


def test_run_turn_executes_at_most_three_calls_and_refuses_the_rest():
    agent = FakeAgent([([_call(1), _call(2)], ""), ([_call(3), _call(4)], ""), ([], "klaar")])

    answer, executed, traced = _run(agent)

    assert answer[1] == "klaar"
    assert executed == ["c1", "c2", "c3"]
    assert traced[-1] == ("c4", "limit")
    refusal = agent.sent[2][0][1]
    assert refusal["tool_call_id"] == "c4"
    assert "error" in json.loads(refusal["result"])


def test_run_turn_keeps_refusing_after_limit_until_agent_answers():
    agent = FakeAgent([([_call(1), _call(2), _call(3), _call(4)], ""), ([_call(5)], ""), ([], "klaar")])

    answer, executed, traced = _run(agent)

    assert answer[1] == "klaar"
    assert executed == ["c1", "c2", "c3"]
    assert traced[-2:] == [("c4", "limit"), ("c5", "limit")]


def test_run_turn_gives_up_when_agent_never_stops_calling():
    agent = FakeAgent([([_call(n)], "") for n in range(1, 20)])

    with pytest.raises(function_calls.TooManyRoundsError):
        _run(agent)

    assert len(agent.sent) == function_calls.MAX_ROUNDS_PER_TURN
