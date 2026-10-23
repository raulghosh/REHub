"""Chat assistant: Claude, with the deal model as its tools.

Two ways to pay for it:
- The site's own access ("house"), when the host provides it: on Google Cloud Run a Google identity
  token exchanged through Workload Identity Federation (no key stored anywhere); elsewhere an
  ANTHROPIC_API_KEY or the SDK's federation settings in the environment. Free questions are capped
  per visitor and by a daily dollar budget.
- A visitor's own API key, sent with each request and used for that request only (never stored or
  logged). It always wins, and it is how a visitor goes past the free cap.

The browser keeps the conversation (Anthropic message format, thinking blocks included) and sends
it back whole each turn, so the history is append-only; the system prompt and tools never change.
"""

from __future__ import annotations

import functools
import json
import os
import threading
import urllib.request
from datetime import date

import anthropic
from pydantic import ValidationError

from ..analysis import evaluate
from ..schemas import DealInput

MODELS = ("claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5")
FALLBACK = {"claude-opus-5-5", "claude-sonnet-5-5"}   # server-side refusal fallback; Haiku has none
MAX_STEPS = 8                                          # tool rounds per question
# $ per million tokens: input, output, cache read, cache write (5 min)
PRICES = {
    "claude-opus-5-5": (4.0, 20.0, 0.20, 5.0),
    "claude-sonnet-5-5": (2.0, 10.0, 0.20, 2.50),
    "claude-haiku-5-5": (0.10, 0.50, 0.01, 0.125),
}
GOOGLE_TOKEN_URL = ("http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/"
                    "identity?audience=https://api.anthropic.com&format=full")

SYSTEM = f"""You are the assistant inside a rental-property deal evaluator for individual investors.

Each user message starts with the user's current form inputs as JSON in <current_inputs> tags: a
DealInput, whose JSON schema is at the end of this prompt. Fields left out or null are filled by
the model (zip-code value, tax rate, insurance, upkeep by age, loan pricing, and so on).

The numbers come from the deal model, never from you. Call evaluate_deal before you quote any
result (verdict, max offer, cash flow, cap rate, IRR, profit if sold), and call it with changes
to answer what-if questions (a lower price, more down, a property manager, a different hold).
Call update_form only when the user asks you to fill in or change their inputs, for example when
they paste a listing; it changes their form, so say what you changed.

Changes are a partial DealInput: nested objects merge, lists (units, known_repairs, known_ages,
hoa_history) replace whole, and null sets a field back to automatic. Percentages are fractions
(0.25 is 25%). From a listing, take what it states and leave the rest automatic; then name the
inputs that are still estimates and matter most (rent, property tax, insurance, condition).

Answer in plain text, not Markdown: the chat shows raw text. Lead with the answer, give the
numbers that support it, and explain what drives them in a few short sentences or "- " lists.
This is not financial, tax or legal advice; say so only when the user is about to rely on a tax
or legal point.

DealInput JSON schema:
{json.dumps(DealInput.model_json_schema(), separators=(",", ":"), sort_keys=True)}"""

CHANGES = {
    "type": "object",
    "properties": {"changes": {
        "type": "object",
        "description": "Partial DealInput merged onto the current inputs; {} for the inputs as they are.",
    }},
    "required": ["changes"],
}
TOOLS = [
    {"name": "evaluate_deal", "input_schema": CHANGES, "description": (
        "Run the deal model on the user's current inputs with the given changes (a what-if) and "
        "return the full result: verdict and max offer, metrics, returns, financing, "
        "down-payment options, sell-or-keep by year, stress tests, assumptions with sources, "
        "warnings. Does not change the user's form.")},
    {"name": "update_form", "input_schema": CHANGES, "description": (
        "Apply the changes to the user's form, then return the result as evaluate_deal does. "
        "Use only when the user asks to fill in or change their inputs.")},
]


def merge(base: object, changes: object) -> object:
    """Nested dicts merge; anything else (lists, scalars, null) replaces."""
    if not (isinstance(base, dict) and isinstance(changes, dict)):
        return changes
    return {**base, **{k: merge(base.get(k), v) for k, v in changes.items()}}


def _brief(x: object) -> object:
    if isinstance(x, float):
        return round(x, 4) if abs(x) < 10 else round(x)
    if isinstance(x, dict):
        return {k: _brief(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_brief(v) for v in x]
    return x


def run_tool(changes: object, deal: dict) -> tuple[str, bool, DealInput | None, str]:
    """-> (tool_result text, is_error, merged deal, one-line summary for the chat log)."""
    if not isinstance(changes, dict):
        return "changes must be a JSON object", True, None, "invalid changes"
    try:
        merged = DealInput.model_validate(merge(deal, changes))
    except ValidationError as e:
        errors = [{"loc": ".".join(map(str, err["loc"])), "msg": err["msg"]} for err in e.errors()]
        return json.dumps(errors), True, None, "inputs rejected: " + "; ".join(
            f"{x['loc']} {x['msg']}" for x in errors[:3])
    result = evaluate(merged)
    # the year-by-year table is the bulk of the result; `stabilized` and `exit_timeline` cover it
    text = json.dumps(_brief(result.model_dump(mode="json", exclude={"years"})), separators=(",", ":"))
    return text, False, merged, f"{result.offer.verdict.upper()}: {result.offer.summary}"


def house_available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_FEDERATION_RULE_ID"))


def _google_identity_token() -> str:
    """Cloud Run's metadata server signs a fresh identity token for the service's own account."""
    req = urllib.request.Request(GOOGLE_TOKEN_URL, headers={"Metadata-Flavor": "Google"})
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=5) as r:
        return r.read().decode()


@functools.cache
def house_client() -> anthropic.Anthropic | None:
    """The site's own access, from whatever the host provides; None if nothing is configured."""
    env = os.environ
    if env.get("K_SERVICE") and env.get("ANTHROPIC_FEDERATION_RULE_ID") and not env.get("ANTHROPIC_IDENTITY_TOKEN_FILE"):
        # Cloud Run (K_SERVICE is set there): Google identity token -> Anthropic WIF; the SDK
        # exchanges it and refreshes the short-lived Anthropic token before it expires
        return anthropic.Anthropic(max_retries=2, credentials=anthropic.WorkloadIdentityCredentials(
            identity_token_provider=_google_identity_token,
            federation_rule_id=env["ANTHROPIC_FEDERATION_RULE_ID"],
            organization_id=env["ANTHROPIC_ORGANIZATION_ID"],
            service_account_id=env.get("ANTHROPIC_SERVICE_ACCOUNT_ID") or None,
            workspace_id=env.get("ANTHROPIC_WORKSPACE_ID") or None))
    if house_available():
        return anthropic.Anthropic(max_retries=2)   # the SDK reads the key or federation settings itself
    return None


class Allowance:
    """Free questions on the house account: so many per visitor per day, and a daily $ budget.
    ponytail: kept in memory, so a restart starts the day over; the spend limit set in the
    Anthropic Console is the hard cap. Visitors are told apart by IP, which a VPN changes;
    the daily budget is what actually bounds the bill."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.day, self.spent, self.asked = None, 0.0, {}

    @staticmethod
    def limits() -> tuple[int, float]:
        return (int(os.environ.get("REHUB_FREE_QUESTIONS_PER_DAY", "10")),
                float(os.environ.get("REHUB_DAILY_BUDGET_USD", "2")))

    def _today(self) -> None:
        if self.day != date.today():
            self.day, self.spent, self.asked = date.today(), 0.0, {}

    def take(self, visitor: str) -> str | None:
        """Count one question; returns why not instead when the visitor or the day is out."""
        per_visitor, budget = self.limits()
        with self.lock:
            self._today()
            if self.spent >= budget:
                return ("Today's free budget for Ask Claude is used up. Add your own Anthropic API key "
                        "to keep going, or come back tomorrow.")
            if self.asked.get(visitor, 0) >= per_visitor:
                return (f"You've used today's {per_visitor} free questions. Add your own Anthropic API key "
                        "to keep going.")
            self.asked[visitor] = self.asked.get(visitor, 0) + 1
            return None

    def spend(self, usd: float) -> None:
        with self.lock:
            self._today()
            self.spent += usd

    def left(self, visitor: str) -> int:
        with self.lock:
            self._today()
            return max(0, self.limits()[0] - self.asked.get(visitor, 0))


ALLOWANCE = Allowance()


def cost(model: str, usage) -> float:
    i, o, read, write = PRICES.get(model, PRICES["claude-opus-5-5"])
    return (i * (usage.input_tokens or 0) + o * (usage.output_tokens or 0)
            + read * (getattr(usage, "cache_read_input_tokens", 0) or 0)
            + write * (getattr(usage, "cache_creation_input_tokens", 0) or 0)) / 1e6


def chat(client: anthropic.Anthropic, model: str, history: list, question: str, deal: dict) -> dict:
    extra = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"} if model in FALLBACK else {}
    inputs = json.dumps(deal, separators=(",", ":"))
    messages = [*history, {"role": "user", "content": [
        {"type": "text", "text": f"<current_inputs>{inputs}</current_inputs>\n\n{question}"}]}]
    steps, form, usd = [], None, 0.0
    for _ in range(MAX_STEPS):
        resp = client.beta.messages.create(
            model=model, max_tokens=16000, system=SYSTEM, tools=TOOLS, messages=messages,
            output_config={"effort": "medium"}, cache_control={"type": "ephemeral"}, **extra)
        usd += cost(model, resp.usage)   # priced at the requested model, also if a fallback answered
        if resp.stop_reason in ("refusal", "max_tokens"):
            # drop the whole turn: a refused or cut-off turn can't be continued cleanly
            reason = ("Claude declined to answer that. Try rephrasing the question."
                      if resp.stop_reason == "refusal" else
                      "The answer ran past the length limit. Try a narrower question.")
            return {"messages": history, "reply": reason, "steps": steps, "deal": None, "model": resp.model,
                    "cost": usd}
        # ponytail: content is replayed as returned; a non-streaming mid-output fallback already
        # omits the declined partial, so there is nothing to strip
        messages.append({"role": "assistant", "content": [b.to_dict() for b in resp.content]})
        if resp.stop_reason != "tool_use":
            break
        results = []
        for b in resp.content:
            if b.type != "tool_use":
                continue
            changes = b.input.get("changes") if isinstance(b.input, dict) else None
            if b.name in ("evaluate_deal", "update_form"):
                text, error, merged, summary = run_tool(changes, deal)
            else:
                text, error, merged, summary = f"unknown tool {b.name}", True, None, "unknown tool"
            if b.name == "update_form" and merged is not None:
                deal = merged.model_dump(mode="json")
                form = deal
                text = "Form updated. Result: " + text
            steps.append({"tool": b.name, "changes": changes, "summary": summary, "error": error})
            results.append({"type": "tool_result", "tool_use_id": b.id, "content": text, "is_error": error})
        messages.append({"role": "user", "content": results})
    reply = "\n\n".join(b.text for b in resp.content if b.type == "text").strip()
    if resp.stop_reason == "tool_use":
        reply = f"I stopped after {MAX_STEPS} rounds of calculations. Ask me to continue."
    return {"messages": messages, "reply": reply, "steps": steps, "deal": form, "model": resp.model, "cost": usd}
