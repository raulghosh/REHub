"""Zip-code market data: what the neighborhood says a property is worth and how it trends.

Backed by the bundled table from scripts/build_market_data.py (Redfin + Realtor.com, plus
Census ACS when it was reachable at build time). Only slow-moving signals are used —
12-month sale medians and a 10+ year price trend — never last month's market.
"""

from __future__ import annotations

import csv
import gzip
import json
from functools import lru_cache
from pathlib import Path

from .schemas import MarketInfo, PropertyType

DATA = Path(__file__).parent / "data"

# Long-run appreciation baseline: ~CPI (2.5%) + ~1% real. FHFA's US index averaged ~4.5%/yr
# 1991-2025, but much of that rode 30 years of falling mortgage rates, which won't repeat.
LONG_RUN_APPRECIATION = 0.035
TREND_WEIGHT = 0.25    # credibility given to a zip's decade of out/under-performance vs the US
TREND_CAP = 0.015      # the zip can move the baseline by at most +/-1.5 pts
MIN_SALES = 10         # fewer sales in 12 months and a zip $/sqft is noise

PPSF_COLUMN = {
    PropertyType.SINGLE_FAMILY: "ppsf_sfr",
    PropertyType.TOWNHOUSE: "ppsf_townhouse",
    PropertyType.CONDO: "ppsf_condo",
    PropertyType.MULTI_2_4: "ppsf_mf",
    PropertyType.MULTI_5_PLUS: "ppsf_mf",   # ponytail: 2-4 unit sales as a proxy; 5+ trades on cap rate
}


@lru_cache(maxsize=1)
def _table() -> dict[str, dict[str, str]]:
    path = DATA / "zip_market.csv.gz"
    if not path.exists():
        return {}
    with gzip.open(path, "rt", newline="", encoding="utf-8") as f:
        return {row["zip"]: row for row in csv.DictReader(f)}


@lru_cache(maxsize=1)
def _meta() -> dict:
    path = DATA / "zip_market_meta.json"
    return json.loads(path.read_text()) if path.exists() else {}


def _num(row: dict[str, str], key: str) -> float | None:
    v = row.get(key, "")
    return float(v) if v else None


def lookup(zip_code: str, property_type: PropertyType = PropertyType.SINGLE_FAMILY) -> MarketInfo | None:
    row = _table().get(zip_code)
    if row is None:
        return None
    meta = _meta()
    sales = _num(row, "sales_12m")
    ppsf = _num(row, PPSF_COLUMN[property_type]) or _num(row, "ppsf_all")
    trend_from, trend_to = row.get("appr_from", ""), row.get("appr_to", "")
    rents = {beds: _num(row, f"rent_{beds}br") for beds in range(5)}
    return MarketInfo(
        zip=zip_code,
        city=row["city"],
        state=row["state"],
        metro=row["metro"],
        sales_12m=int(sales) if sales is not None else None,
        median_price=_num(row, "median_price"),
        median_dom=_num(row, "median_dom"),
        ppsf=ppsf if (sales or 0) >= MIN_SALES else None,
        list_ppsf=_num(row, "list_ppsf"),
        appreciation_trend=_num(row, "appr_cagr"),
        appreciation_vs_us=_num(row, "appr_excess"),
        trend_years=f"{trend_from}-{trend_to}" if trend_from else "",
        rent_by_beds={b: r for b, r in rents.items() if r},
        tax_rate=_num(row, "tax_rate"),
        rental_vacancy=_num(row, "rental_vacancy"),
        median_year_built=_num(row, "median_year_built"),
        median_income=_num(row, "median_income"),
        as_of=f"Redfin sales through {meta.get('redfin_through', '?')}",
        sources=meta.get("sources", []),
    )


def appreciation_default(market: MarketInfo | None) -> tuple[float, str]:
    """Long-run baseline nudged by how the zip did vs. the US over the last decade."""
    if market is None or market.appreciation_vs_us is None:
        return LONG_RUN_APPRECIATION, "US long-run baseline (CPI + ~1% real); no zip trend"
    nudge = max(-TREND_CAP, min(TREND_CAP, TREND_WEIGHT * market.appreciation_vs_us))
    us = market.appreciation_trend - market.appreciation_vs_us
    source = (f"{LONG_RUN_APPRECIATION:.1%} long-run baseline {nudge:+.1%} for zip trend "
              f"({market.appreciation_trend:.1%}/yr vs US {us:.1%}/yr, {market.trend_years}, "
              f"{TREND_WEIGHT:.0%} weight)")
    return LONG_RUN_APPRECIATION + nudge, source
