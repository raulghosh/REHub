"""Local web app — `sfr-eval serve`, then open http://127.0.0.1:8000.

Standard library only:
    GET  /                the page (index.html)
    GET  /api/defaults    a sample deal plus default rehab inputs, so the page holds no defaults
    POST /api/evaluate    DealInput JSON -> Result JSON (422 + field errors if invalid)
"""

from __future__ import annotations

import json
import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from pydantic import ValidationError

from ..analysis import evaluate
from ..schemas import DealInput, Rehab

INDEX = Path(__file__).with_name("index.html")
MAX_BODY = 256 * 1024
SAMPLE = DealInput.model_validate({
    "property": {"zip_code": "38118", "year_built": 1978, "sqft": 1350,
                 "units": [{"beds": 3, "baths": 1.5, "rent": 1395}]},
    "purchase": {"price": 105_000},
    "management": {"mode": "self"},
})
DEFAULTS = json.dumps({
    "deal": SAMPLE.model_dump(mode="json"),
    "rehab": Rehab(budget=30_000).model_dump(mode="json"),
}).encode()


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str = "application/json") -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj: object) -> None:
        self._send(code, json.dumps(obj).encode())

    def do_GET(self) -> None:
        url = urlparse(self.path)
        if url.path in ("/", "/index.html"):
            return self._send(200, INDEX.read_bytes(), "text/html; charset=utf-8")
        if url.path == "/api/defaults":
            return self._send(200, DEFAULTS)
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/evaluate":
            return self._json(404, {"error": "not found"})
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = -1
        if not 0 < length <= MAX_BODY:
            return self._json(413 if length > MAX_BODY else 400, {"error": "bad request body"})
        try:
            deal = DealInput.model_validate_json(self.rfile.read(length))
        except ValidationError as e:
            errors = [{"loc": ".".join(map(str, err["loc"])), "msg": err["msg"]} for err in e.errors()]
            return self._json(422, {"errors": errors})
        try:
            self._send(200, evaluate(deal).model_dump_json().encode())
        except Exception:   # noqa: BLE001 — report instead of dropping the connection
            traceback.print_exc()
            self._json(500, {"error": "the model could not evaluate this deal"})

    def log_message(self, fmt: str, *args: object) -> None:
        pass


def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"Deal evaluator running on http://{host}:{port}  (Ctrl+C to stop)", file=sys.stderr)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
