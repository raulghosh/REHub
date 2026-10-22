import json

import pytest
from anthropic.types.beta import BetaMessage

from sfr_evaluator.web import assistant
from sfr_evaluator.web.server import SAMPLE


def message(stop, *blocks):
    return BetaMessage.model_validate({
        "id": "msg", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
        "stop_reason": stop, "stop_sequence": None, "usage": {"input_tokens": 1, "output_tokens": 1},
        "content": list(blocks)})


def tool(name, changes, id="t1"):
    return {"type": "tool_use", "id": id, "name": name, "input": {"changes": changes}}


@pytest.fixture
def fake(monkeypatch):
    """Replace the Anthropic client with a script of responses; record each request."""
    calls, script = [], []

    class Messages:
        def create(self, **kw):
            calls.append(json.loads(json.dumps(kw)))   # snapshot: the loop appends to messages
            return script.pop(0)

    class Client:
        def __init__(self, api_key, max_retries):
            assert api_key == "sk-test"
            self.beta = type("Beta", (), {"messages": Messages()})()

    monkeypatch.setattr(assistant.anthropic, "Anthropic", Client)
    return calls, script


def test_merge():
    base = {"a": {"b": 1, "c": 2}, "l": [1, 2], "x": 5}
    assert assistant.merge(base, {"a": {"b": 9}, "l": [3], "x": None}) == {"a": {"b": 9, "c": 2}, "l": [3], "x": None}
    assert base["a"]["b"] == 1


def test_update_form_then_answer(fake):
    calls, script = fake
    deal = SAMPLE.model_dump(mode="json")
    script += [
        message("tool_use", {"type": "thinking", "thinking": "", "signature": "sig"},
                tool("evaluate_deal", {"purchase": {"price": "cheap"}}, "t0"),
                tool("update_form", {"purchase": {"price": 95_000}})),
        message("end_turn", {"type": "text", "text": "Done: lowered the price."}),
    ]
    out = assistant.chat("sk-test", "claude-opus-5-5", [], "Try 95k", deal)
    assert out["reply"] == "Done: lowered the price."
    assert out["deal"]["purchase"]["price"] == 95_000
    assert [s["error"] for s in out["steps"]] == [True, False]
    # history: question, tool calls (thinking kept for replay), both results in one message, answer
    roles = [m["role"] for m in out["messages"]]
    assert roles == ["user", "assistant", "user", "assistant"]
    assert out["messages"][1]["content"][0]["signature"] == "sig"
    bad, good = out["messages"][2]["content"]
    assert bad["is_error"] and "purchase.price" in bad["content"]
    assert json.loads(good["content"].removeprefix("Form updated. Result: "))["offer"]["verdict"]
    first = calls[0]
    assert "<current_inputs>" in first["messages"][0]["content"][0]["text"]
    assert first["fallbacks"] == "default" and first["output_config"] == {"effort": "medium"}
    # the second request replays the first exactly and only appends (preserved thinking)
    assert calls[1]["messages"][:1] == first["messages"]
    assert calls[1]["system"] == first["system"] and calls[1]["tools"] == first["tools"]


def test_refusal_drops_turn_and_haiku_skips_fallback(fake):
    calls, script = fake
    history = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]
    script.append(message("refusal"))
    out = assistant.chat("sk-test", "claude-haiku-5-5", history, "q", SAMPLE.model_dump(mode="json"))
    assert out["messages"] == history and out["deal"] is None and "declined" in out["reply"]
    assert "fallbacks" not in calls[0]
