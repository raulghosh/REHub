"""Zip data, CSV screening, the CLI, and the web API."""

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from sfr_evaluator import market
from sfr_evaluator.cli import main
from sfr_evaluator.ingest.normalize import canonical_address, dedup
from sfr_evaluator.ingest.sources import from_csv
from sfr_evaluator.schemas import PropertyType
from sfr_evaluator.web.server import SAMPLE, Handler

ROOT = Path(__file__).resolve().parents[1]


def test_zip_lookup_and_appreciation_bounds():
    m = market.lookup("38118", PropertyType.SINGLE_FAMILY)
    assert m.city == "Memphis" and m.state == "TN" and m.ppsf > 0
    assert market.lookup("00000") is None
    rate, source = market.appreciation_default(m)
    assert abs(rate - market.LONG_RUN_APPRECIATION) <= market.TREND_CAP + 1e-9
    assert "zip trend" in source
    assert market.appreciation_default(None)[0] == market.LONG_RUN_APPRECIATION


def test_csv_rows_become_deals_and_bad_rows_are_reported(tmp_path):
    csv_path = tmp_path / "l.csv"
    csv_path.write_text("address,zip,year_built,sqft,beds,baths,units,rent,price\n"
                        "1 A St,38118,1980,1200,3,1,1,1300,100000\n"
                        "2 B St,38118,1980,2000,2,1,2,2400,180000\n"
                        "3 C St,38118,1980,1200,3,1,1,,100000\n")
    rows = list(from_csv(csv_path, {}, {"zip_code": "zip"}))
    assert rows[0][1].property.units[0].rent == 1300
    duplex = rows[1][1]
    assert duplex.property.property_type is PropertyType.MULTI_2_4
    assert [u.rent for u in duplex.property.units] == [1200, 1200]
    assert rows[2] == (4, "rent and price are required")


def test_dedup_keeps_the_cheapest():
    assert canonical_address("123 Main St", "78704") == canonical_address("123 Main Street", "78704")
    d1 = SAMPLE.model_copy(deep=True)
    d2 = SAMPLE.model_copy(deep=True)
    d1.property.address, d2.property.address = "9 Elm St", "9 Elm Street"
    d2.purchase.price = 99_000
    assert [d.purchase.price for d in dedup([d1, d2])] == [99_000]


def test_cli_evaluate_and_screen(tmp_path, capsys):
    assert main(["evaluate", str(ROOT / "config/sample_deal.yaml")]) == 0
    assert "Max offer" in capsys.readouterr().out
    out = tmp_path / "ranked.csv"
    assert main(["screen", "--input", str(ROOT / "sample_listings.csv"), "--out", str(out),
                 "--profile", str(ROOT / "config/investor_profile.yaml")]) == 0
    lines = out.read_text().splitlines()
    assert lines[0].startswith("rank,address") and len(lines) == 7   # 7 listings, one duplicate


@pytest.fixture(scope="module")
def server():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def post(url, body: bytes):
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_web_api(server):
    with urllib.request.urlopen(server + "/") as r:
        assert b"Deal Evaluator" in r.read()
    with urllib.request.urlopen(server + "/api/defaults") as r:
        defaults = json.loads(r.read())
    status, result = post(server + "/api/evaluate", json.dumps(defaults["deal"]).encode())
    assert status == 200 and result["offer"]["verdict"] in ("buy", "negotiate", "pass")
    assert result["market"]["city"] == "Memphis"
    status, body = post(server + "/api/evaluate", b'{"property": {"zip_code": "1"}}')
    assert status == 422 and any(e["loc"] == "property.zip_code" for e in body["errors"])
    status, _ = post(server + "/api/evaluate", b"x" * 300_000)
    assert status == 413
