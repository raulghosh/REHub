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


class FakeClient:
    """Stands in for anthropic.Anthropic: replays a script of responses, records each request."""

    def __init__(self):
        self.calls, self.script = [], []
        outer = self

        class Messages:
            def create(self, **kw):
                outer.calls.append(json.loads(json.dumps(kw)))   # snapshot: the loop appends to messages
                return outer.script.pop(0)

        self.beta = type("Beta", (), {"messages": Messages()})()


@pytest.fixture
def fake():
    return FakeClient()


def test_merge():
    base = {"a": {"b": 1, "c": 2}, "l": [1, 2], "x": 5}
    assert assistant.merge(base, {"a": {"b": 9}, "l": [3], "x": None}) == {"a": {"b": 9, "c": 2}, "l": [3], "x": None}
    assert base["a"]["b"] == 1


def test_update_form_then_answer(fake):
    calls, script = fake.calls, fake.script
    deal = SAMPLE.model_dump(mode="json")
    script += [
        message("tool_use", {"type": "thinking", "thinking": "", "signature": "sig"},
                tool("evaluate_deal", {"purchase": {"price": "cheap"}}, "t0"),
                tool("update_form", {"purchase": {"price": 95_000}})),
        message("end_turn", {"type": "text", "text": "Done: lowered the price."}),
    ]
    out = assistant.chat(fake, "claude-opus-5-5", [], "Try 95k", deal)
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
    calls, script = fake.calls, fake.script
    history = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]
    script.append(message("refusal"))
    out = assistant.chat(fake, "claude-haiku-5-5", history, "q", SAMPLE.model_dump(mode="json"))
    assert out["messages"] == history and out["deal"] is None and "declined" in out["reply"]
    assert "fallbacks" not in calls[0]


def test_cost_uses_the_model_price_table():
    usage = type("U", (), {"input_tokens": 1_000_000, "output_tokens": 100_000,
                           "cache_read_input_tokens": 2_000_000, "cache_creation_input_tokens": 0})()
    assert assistant.cost("claude-opus-5-5", usage) == pytest.approx(4.0 + 2.0 + 0.40)
    assert assistant.cost("claude-haiku-5-5", usage) == pytest.approx(0.10 + 0.05 + 0.02)


def test_allowance_caps_visitors_and_the_day(monkeypatch):
    monkeypatch.setenv("REHUB_FREE_QUESTIONS_PER_DAY", "2")
    monkeypatch.setenv("REHUB_DAILY_BUDGET_USD", "1")
    a = assistant.Allowance()
    assert a.take("1.1.1.1") is None and a.take("1.1.1.1") is None
    assert "2 free questions" in a.take("1.1.1.1")          # third question that day
    assert a.left("1.1.1.1") == 0 and a.take("2.2.2.2") is None
    a.spend(1.0)
    assert "budget" in a.take("3.3.3.3")                    # the day's budget is gone for everyone
    a.day = None                                            # next day: counters start over
    assert a.take("1.1.1.1") is None and a.left("1.1.1.1") == 1


def test_house_client_picks_the_hosts_credentials(monkeypatch):
    for v in ("ANTHROPIC_API_KEY", "ANTHROPIC_FEDERATION_RULE_ID", "ANTHROPIC_IDENTITY_TOKEN_FILE", "K_SERVICE"):
        monkeypatch.delenv(v, raising=False)
    assistant.house_client.cache_clear()
    assert assistant.house_client() is None and not assistant.house_available()
    # Cloud Run: the Google identity token is exchanged through Workload Identity Federation
    monkeypatch.setenv("K_SERVICE", "rehub")
    monkeypatch.setenv("ANTHROPIC_FEDERATION_RULE_ID", "fdrl_x")
    monkeypatch.setenv("ANTHROPIC_ORGANIZATION_ID", "00000000-0000-0000-0000-000000000000")
    built = {}
    monkeypatch.setattr(assistant.anthropic, "WorkloadIdentityCredentials", lambda **kw: built.update(kw) or "creds")
    monkeypatch.setattr(assistant.anthropic, "Anthropic", lambda **kw: kw)
    assistant.house_client.cache_clear()
    client = assistant.house_client()
    assert client["credentials"] == "creds" and built["identity_token_provider"] is assistant._google_identity_token
    assert built["federation_rule_id"] == "fdrl_x" and built["workspace_id"] is None
    # elsewhere: the SDK reads ANTHROPIC_API_KEY (or a token file) from the environment itself
    monkeypatch.delenv("K_SERVICE")
    assistant.house_client.cache_clear()
    assert "credentials" not in assistant.house_client()
    assistant.house_client.cache_clear()
