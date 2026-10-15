#!/usr/bin/env python3
"""Build the bundled zip-code market table: src/sfr_evaluator/data/zip_market.csv.gz

Only slow-moving signals are kept (12-month medians and multi-year trends) — the model
deliberately ignores month-to-month market noise. All sources are free and public:

  Redfin Data Center   sold $/sqft by property type, sales volume, days on market, and the
                       zip's long-run $/sqft trend vs. the nation.
                       Cite as: "Redfin, a national real estate brokerage".
  Realtor.com          city name, listing $/sqft (realtor.com economic research data).
  US Census ACS 5-yr   median gross rent by bedrooms, property-tax rate, rental vacancy,
  (needs api.census.gov) median year built, median household income. Skipped with a
                       warning when the host is unreachable.

Run from the repo root (streams ~1.5 GB from Redfin, takes a few minutes):

    python scripts/build_market_data.py
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import os
import sys
import urllib.request
from collections import defaultdict
from datetime import date
from pathlib import Path

REDFIN_ZIP = ("https://redfin-public-data.s3.us-west-2.amazonaws.com/redfin_market_tracker/"
              "zip_code_market_tracker.tsv000.gz")
REDFIN_US = ("https://redfin-public-data.s3.us-west-2.amazonaws.com/redfin_market_tracker/"
             "us_national_market_tracker.tsv000.gz")
REALTOR_ZIP = "https://econdata.s3-us-west-2.amazonaws.com/Reports/Core/RDC_Inventory_Core_Metrics_Zip.csv"
ACS_URL = "https://api.census.gov/data/{year}/acs/acs5?get={vars}&for=zip%20code%20tabulation%20area:*"

DATA_DIR = Path(__file__).resolve().parents[1] / "src" / "sfr_evaluator" / "data"

TYPES = {
    "All Residential": "all",
    "Single Family Residential": "sfr",
    "Townhouse": "townhouse",
    "Condo/Co-op": "condo",
    "Multi-Family (2-4 Unit)": "mf",
}
TREND_START = 2014       # skip the 2012-13 post-crash rebound, which flatters bust-and-recover zips
MIN_TREND_SPAN = 6       # years between the averaged endpoints
MIN_ANNUAL_SALES = 10

ACS_VARS = {
    "B25031_001E": "rent_median", "B25031_002E": "rent_0br", "B25031_003E": "rent_1br",
    "B25031_004E": "rent_2br", "B25031_005E": "rent_3br", "B25031_006E": "rent_4br",
    "B25077_001E": "median_value", "B25103_001E": "median_tax", "B25035_001E": "median_year_built",
    "B19013_001E": "median_income", "B25003_003E": "renter_occupied",
    "B25004_002E": "vacant_for_rent", "B25004_003E": "rented_not_occupied",
}


def num(s: str) -> float | None:
    try:
        return float(s)
    except ValueError:   # "NA", ""
        return None


def tsv_gz(url: str):
    """Yield (column index, fields) for a Redfin gzipped TSV, streamed."""
    resp = urllib.request.urlopen(url, timeout=120)
    lines = io.TextIOWrapper(gzip.GzipFile(fileobj=resp), encoding="utf-8")
    header = [h.strip('"') for h in next(lines).rstrip("\n").split("\t")]
    col = {h: i for i, h in enumerate(header)}
    for line in lines:
        yield col, [f.strip('"') for f in line.rstrip("\n").split("\t")]


def month_key(period_end: str) -> int:
    return int(period_end[:4]) * 12 + int(period_end[5:7]) - 1


def cagr(series: dict[int, float], start: int, end: int) -> float | None:
    """CAGR between 2-year averaged endpoints (start, start+1) -> (end-1, end); damps noise."""
    try:
        a = (series[start] + series[start + 1]) / 2
        b = (series[end - 1] + series[end]) / 2
    except KeyError:
        return None
    return (b / a) ** (1 / (end - start - 1)) - 1 if a > 0 and b > 0 else None


def national_ppsf_by_year() -> dict[int, float]:
    sums: dict[int, list[float]] = defaultdict(list)
    for c, f in tsv_gz(REDFIN_US):
        if f[c["PROPERTY_TYPE"]] == "All Residential" and f[c["IS_SEASONALLY_ADJUSTED"]] == "false":
            v = num(f[c["MEDIAN_PPSF"]])
            if v:
                sums[int(f[c["PERIOD_END"]][:4])].append(v)
    return {y: sum(v) / len(v) for y, v in sums.items() if len(v) == 12}


def redfin_zips(national: dict[int, float]) -> tuple[dict[str, dict], int]:
    annual = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0]))   # (zip,type) -> year -> [ppsf*n, n]
    recent = defaultdict(dict)                                       # (zip,type) -> month -> row
    meta: dict[str, tuple[str, str]] = {}
    latest = 0
    for i, (c, f) in enumerate(tsv_gz(REDFIN_ZIP)):
        if i % 2_000_000 == 0:
            print(f"  redfin rows: {i:,}", file=sys.stderr, flush=True)
        t = TYPES.get(f[c["PROPERTY_TYPE"]])
        if t is None or f[c["PERIOD_DURATION"]] != "90" or f[c["IS_SEASONALLY_ADJUSTED"]] != "false":
            continue
        z = f[c["REGION"]][-5:]
        meta.setdefault(z, (f[c["STATE_CODE"]], f[c["PARENT_METRO_REGION"]]))
        ppsf, sold = num(f[c["MEDIAN_PPSF"]]), num(f[c["HOMES_SOLD"]])
        if not ppsf or not sold:
            continue
        end = f[c["PERIOD_END"]]
        m = month_key(end)
        latest = max(latest, m)
        if m % 3 == 2:   # quarter-end months: non-overlapping 90-day windows
            acc = annual[(z, t)][int(end[:4])]
            acc[0] += ppsf * sold
            acc[1] += sold
        if m >= (int(date.today().year) - 2) * 12:
            recent[(z, t)][m] = (ppsf, num(f[c["MEDIAN_SALE_PRICE"]]), sold, num(f[c["MEDIAN_DOM"]]))

    last_full_year = latest // 12 if latest % 12 == 11 else latest // 12 - 1
    quarters = [latest - 3 * k for k in range(4)]
    out: dict[str, dict] = {}
    for (z, t), by_month in recent.items():
        rows = [by_month[q] for q in quarters if q in by_month]
        n = sum(r[2] for r in rows)
        if not rows or n < 3:
            continue
        rec = out.setdefault(z, {"state": meta[z][0], "metro": meta[z][1]})
        rec[f"ppsf_{t}"] = round(sum(r[0] * r[2] for r in rows) / n, 1)
        if t == "all":
            priced = [r for r in rows if r[1]]
            dom = [r for r in rows if r[3] is not None]
            rec["sales_12m"] = int(n)
            if priced:
                rec["median_price"] = round(sum(r[1] * r[2] for r in priced) / sum(r[2] for r in priced))
            if dom:
                rec["median_dom"] = round(sum(r[3] * r[2] for r in dom) / sum(r[2] for r in dom))

    for (z, t), years in annual.items():
        if t != "all" or z not in out:
            continue
        series = {y: s / n for y, (s, n) in years.items() if n >= MIN_ANNUAL_SALES}
        start = min((y for y in series if y >= TREND_START and y + 1 in series), default=None)
        if start is None or last_full_year - start - 1 < MIN_TREND_SPAN:
            continue
        z_cagr = cagr(series, start, last_full_year)
        us_cagr = cagr(national, start, last_full_year)
        if z_cagr is None or us_cagr is None:
            continue
        out[z].update(appr_cagr=round(z_cagr, 4), appr_excess=round(z_cagr - us_cagr, 4),
                      appr_from=start, appr_to=last_full_year)
    return out, latest


def realtor_zips() -> dict[str, dict]:
    raw = urllib.request.urlopen(REALTOR_ZIP, timeout=120).read().decode("utf-8")
    out = {}
    for row in csv.DictReader(io.StringIO(raw)):
        z = (row.get("postal_code") or "").strip()
        if not z.isdigit():
            continue   # footer notes
        city = (row.get("zip_name") or "").rsplit(",", 1)[0].strip().title()
        out[z.zfill(5)] = {
            "city": city,
            "list_ppsf": num(row.get("median_listing_price_per_square_foot") or ""),
            "median_sqft": num(row.get("median_square_feet") or ""),
        }
    return out


def parse_acs(rows: list[list[str]]) -> dict[str, dict]:
    """Census API JSON (header row first) -> zip -> derived fields. Negative values are
    Census 'not available' sentinels."""
    header, out = rows[0], {}
    for r in rows[1:]:
        v = {ACS_VARS[h]: num(r[i] or "") for i, h in enumerate(header) if h in ACS_VARS}
        v = {k: x if x is not None and x >= 0 else None for k, x in v.items()}
        rec = {k: v[k] for k in ("rent_median", "rent_0br", "rent_1br", "rent_2br", "rent_3br",
                                 "rent_4br", "median_value", "median_year_built", "median_income")}
        if v["median_tax"] and v["median_value"]:
            rec["tax_rate"] = round(v["median_tax"] / v["median_value"], 4)
        stock = sum(v[k] or 0 for k in ("renter_occupied", "vacant_for_rent", "rented_not_occupied"))
        if stock >= 50:   # tiny samples are noise
            rec["rental_vacancy"] = round((v["vacant_for_rent"] or 0) / stock, 4)
        out[r[header.index("zip code tabulation area")]] = rec
    return out


def acs_zips() -> tuple[dict[str, dict], int | None]:
    key = os.environ.get("CENSUS_API_KEY")
    for year in (date.today().year - 2, date.today().year - 3):
        url = ACS_URL.format(year=year, vars=",".join(ACS_VARS)) + (f"&key={key}" if key else "")
        try:
            return parse_acs(json.load(urllib.request.urlopen(url, timeout=120))), year
        except Exception as e:  # noqa: BLE001 — optional source, report and move on
            print(f"  ACS {year} unavailable: {e}", file=sys.stderr)
    return {}, None


COLUMNS = ["zip", "state", "city", "metro", "sales_12m", "median_price", "median_dom",
           "ppsf_all", "ppsf_sfr", "ppsf_townhouse", "ppsf_condo", "ppsf_mf", "list_ppsf",
           "median_sqft", "appr_cagr", "appr_excess", "appr_from", "appr_to",
           "rent_median", "rent_0br", "rent_1br", "rent_2br", "rent_3br", "rent_4br",
           "median_value", "tax_rate", "rental_vacancy", "median_year_built", "median_income"]


def main() -> int:
    print("Redfin national ...", file=sys.stderr)
    national = national_ppsf_by_year()
    print("Redfin zips (streaming ~1.5 GB) ...", file=sys.stderr)
    zips, latest = redfin_zips(national)
    print("Realtor.com ...", file=sys.stderr)
    for z, rec in realtor_zips().items():
        if z in zips:
            zips[z].update({k: v for k, v in rec.items() if v})
    print("Census ACS ...", file=sys.stderr)
    acs, acs_year = acs_zips()
    for z, rec in acs.items():
        if z in zips:
            zips[z].update({k: v for k, v in rec.items() if v is not None})

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with gzip.open(DATA_DIR / "zip_market.csv.gz", "wt", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        w.writeheader()
        for z in sorted(zips):
            w.writerow({"zip": z, **zips[z]})
    meta = {
        "built": date.today().isoformat(),
        "redfin_through": f"{latest // 12}-{latest % 12 + 1:02d}",
        "acs_year": acs_year,
        "national_ppsf_by_year": {y: round(v, 1) for y, v in sorted(national.items())},
        "zips": len(zips),
        "sources": ["Redfin, a national real estate brokerage (Data Center)",
                    "Realtor.com economic research data"]
                   + ([f"US Census Bureau ACS 5-year {acs_year}"] if acs_year else []),
    }
    (DATA_DIR / "zip_market_meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(f"Wrote {len(zips):,} zips (Redfin through {meta['redfin_through']}, ACS {acs_year})",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
