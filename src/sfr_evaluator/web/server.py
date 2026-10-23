"""Web app — `sfr-eval serve`, then open http://127.0.0.1:8000.

Standard library HTTP server, stateless (each browser keeps its own deals), safe to host publicly:
    GET  /                the page (index.html)
    GET  /guide           the investor guide (guide.html)
    GET  /api/defaults    a sample deal plus default rehab inputs, so the page holds no defaults
    POST /api/evaluate    DealInput JSON -> Result JSON (422 + field errors if invalid)
    POST /api/chat        {model, messages, question, deal}, optionally with the visitor's own key in
                          the X-Anthropic-Key header (else the site's own access, capped)
                          -> {messages, reply, steps, deal, model, free_left}
"""

from __future__ import annotations

import json
import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import anthropic
from pydantic import ValidationError

from ..analysis import evaluate
from ..schemas import DealInput, Rehab
from ..underwrite import rates
from . import assistant

INDEX = Path(__file__).with_name("index.html")
GUIDE = Path(__file__).with_name("guide.html")
MAX_BODY = {"/api/evaluate": 256 * 1024, "/api/chat": 8 * 1024 * 1024}
# the page is self-contained; connect-src 'self' also keeps a stored key from leaving for anywhere else
CSP = ("default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src 'self' data:; "
       "connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")
API_ERRORS = (   # most specific first; messages never contain the key
    (anthropic.AuthenticationError, 401, "Anthropic rejected this API key."),
    (anthropic.PermissionDeniedError, 403, "This API key can't use that model."),
    (anthropic.RateLimitError, 429, "Rate limited by Anthropic. Wait a moment and try again."),
    (anthropic.BadRequestError, 400, None),
    (anthropic.APIStatusError, 502, None),
    (anthropic.APIConnectionError, 502, "Couldn't reach Anthropic. Try again."),
)
SAMPLE = DealInput.model_validate({
    "property": {"zip_code": "38118", "year_built": 1978, "sqft": 1350,
                 "units": [{"beds": 3, "baths": 1.5, "rent": 1395}]},
    "purchase": {"price": 105_000},
    "management": {"mode": "self"},
})
DEFAULTS = json.dumps({
    "deal": SAMPLE.model_dump(mode="json"),
    "rehab": Rehab(budget=30_000).model_dump(mode="json"),
    "assistant": {"house": assistant.house_available(), "free_questions": assistant.Allowance.limits()[0]},
}).encode()


class Handler(BaseHTTPRequestHandler):
    timeout = 60   # drop idle or stalled client connections

    def _send(self, code: int, body: bytes, ctype: str = "application/json") -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj: object) -> None:
        self._send(code, json.dumps(obj).encode())

    def do_GET(self) -> None:
        url = urlparse(self.path)
        if url.path in ("/", "/index.html"):
            return self._send(200, INDEX.read_bytes(), "text/html; charset=utf-8")
        if url.path in ("/guide", "/guide.html"):
            return self._send(200, GUIDE.read_bytes(), "text/html; charset=utf-8")
        if url.path == "/api/defaults":
            return self._send(200, DEFAULTS)
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path not in MAX_BODY:
            return self._json(404, {"error": "not found"})
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = -1
        if not 0 < length <= MAX_BODY[path]:
            return self._json(413 if length > MAX_BODY[path] else 400, {"error": "bad request body"})
        body = self.rfile.read(length)
        try:
            if path == "/api/evaluate":
                return self._evaluate(body)
            return self._chat(body)
        except Exception:   # noqa: BLE001 — report instead of dropping the connection
            traceback.print_exc()
            self._json(500, {"error": "the model could not evaluate this deal"})

    def _evaluate(self, body: bytes) -> None:
        try:
            deal = DealInput.model_validate_json(body)
        except ValidationError as e:
            errors = [{"loc": ".".join(map(str, err["loc"])), "msg": err["msg"]} for err in e.errors()]
            return self._json(422, {"errors": errors})
        self._send(200, evaluate(deal).model_dump_json().encode())

    def _chat(self, body: bytes) -> None:
        key = (self.headers.get("X-Anthropic-Key") or "").strip()
        try:
            req = json.loads(body)
            ok = (req["model"] in assistant.MODELS and isinstance(req["messages"], list)
                  and isinstance(req["deal"], dict) and isinstance(req["question"], str)
                  and 0 < len(req["question"].strip()) <= 20_000)
        except (ValueError, KeyError, TypeError):
            ok = False
        if not ok:
            return self._json(400, {"error": "bad chat request"})
        visitor = None
        if key:
            client = anthropic.Anthropic(api_key=key, max_retries=2)
        else:
            client = assistant.house_client()
            if client is None:
                return self._json(401, {"error": "Add your Anthropic API key first."})
            # ponytail: the first X-Forwarded-For entry; a visitor can fake it, so the per-visitor count
            # is a courtesy limit and the daily budget is what bounds the bill
            visitor = (self.headers.get("X-Forwarded-For") or self.client_address[0]).split(",")[0].strip()
            refusal = assistant.ALLOWANCE.take(visitor)
            if refusal:
                return self._json(429, {"error": refusal, "need_key": True})
        try:
            out = assistant.chat(client, req["model"], req["messages"], req["question"].strip(), req["deal"])
        except anthropic.WorkloadIdentityError:   # the site's own access is misconfigured
            traceback.print_exc()
            return self._json(503, {"error": "This site's own Claude access isn't working right now. "
                                             "Add your own Anthropic API key to keep going.", "need_key": True})
        except anthropic.APIError as e:
            code, msg = next(((c, m) for cls, c, m in API_ERRORS if isinstance(e, cls)), (502, None))
            if not key and code != 429:   # the site's own access failed: the cause goes to the log
                traceback.print_exc()
                msg = "This site's own Claude access isn't working right now. Add your own Anthropic API key to keep going."
            return self._json(code, {"error": msg or f"Anthropic: {e.message}", "need_key": not key})
        usd = out.pop("cost")
        if visitor is not None:
            assistant.ALLOWANCE.spend(usd)
            out["free_left"] = assistant.ALLOWANCE.left(visitor)
        self._json(200, out)

    def log_message(self, fmt: str, *args: object) -> None:
        pass


def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    rates.LIVE = True   # refresh the weekly market rate when online; falls back to the snapshot
    httpd = ThreadingHTTPServer((host, port), Handler)
    httpd.daemon_threads = True
    print(f"Deal evaluator running on http://{host}:{port}  (Ctrl+C to stop)", file=sys.stderr)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
