"""Mortgage pricing: the weekly market rate, adjusted to you and to the property.

Base: Freddie Mac's weekly 30-year average (PMMS), which assumes ~20% down and excellent
credit on a home the borrower lives in. Conventional loans add Fannie Mae's loan-level price
adjustments (credit score x loan-to-value, plus the investment-property charge), quoted in
points and converted to rate. DSCR, commercial and FHA loans have no public grid; they are
priced as typical spreads over the same base. A rate you type in always wins.
"""

from __future__ import annotations

import json
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from ..schemas import Loan

SNAPSHOT = Path(__file__).resolve().parents[1] / "data" / "rates.json"
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=MORTGAGE30US"
LIVE = False                 # the web server turns this on; tests and the CLI use the snapshot
_cache: dict[str, tuple[float, tuple[float, str, str]]] = {}

POINTS_TO_RATE = 0.25        # rule of thumb: one point of price ~ 0.25% of rate on a 30-year loan

# Fannie Mae LLPA matrix, purchase loans > 15 yrs (points). Rows: credit score floor.
# Columns: LTV up to 30 / 60 / 70 / 75 / 80 / 85 / 90 / 95 / 97%.
LTV_TOPS = (0.30, 0.60, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 1.00)
SCORE_FLOORS = (780, 760, 740, 720, 700, 680, 660, 640, 0)
LLPA = (
    (0, 0, 0, 0, 0.375, 0.375, 0.25, 0.25, 0.125),
    (0, 0, 0, 0.25, 0.625, 0.625, 0.5, 0.5, 0.25),
    (0, 0, 0.125, 0.375, 0.875, 1.0, 0.75, 0.625, 0.5),
    (0, 0, 0.25, 0.75, 1.25, 1.25, 1.0, 0.875, 0.75),
    (0, 0, 0.375, 0.875, 1.375, 1.5, 1.25, 1.125, 0.875),
    (0, 0, 0.625, 1.125, 1.75, 1.875, 1.5, 1.375, 1.125),
    (0, 0, 0.75, 1.375, 1.875, 2.125, 1.75, 1.625, 1.25),
    (0, 0, 1.125, 1.5, 2.25, 2.5, 2.0, 1.875, 1.5),
    (0, 0.125, 1.5, 2.125, 2.75, 2.875, 2.625, 2.25, 1.75),
)
INVESTOR_LLPA = (1.125, 1.125, 1.625, 2.125, 3.375, 4.125, 4.125, 4.125, 4.125)
REFERENCE_LLPA = 0.375       # PMMS borrower: 780+ score, 20% down

# Borrower-paid PMI, annual % of the original loan, by LTV band and score floor (760..620).
# ponytail: illustrative of carrier rate cards (Urban Institute: 0.46-1.5% typical); use a quote.
PMI_SCORES = (760, 740, 720, 700, 680, 660, 640, 0)
PMI = {0.85: (0.19, 0.23, 0.27, 0.32, 0.38, 0.47, 0.55, 0.60),
       0.90: (0.28, 0.34, 0.41, 0.49, 0.59, 0.73, 0.85, 0.93),
       0.95: (0.41, 0.50, 0.60, 0.72, 0.87, 1.07, 1.25, 1.37),
       1.00: (0.55, 0.67, 0.80, 0.96, 1.16, 1.43, 1.67, 1.83)}
INVESTOR_PMI_LOAD = 1.3

FHA_UPFRONT_MIP = 0.0175     # financed into the loan
DSCR_INVESTOR = 0.375        # conventional investor premium over PMMS (25-50 bps)
COMMERCIAL_SPREAD = 0.0025   # small-balance 5+ unit loans quoted near PMMS in 2026


def base_rate() -> tuple[float, str, str]:
    """(rate, as-of date, source). Live from FRED when enabled, else the bundled snapshot."""
    snap = json.loads(SNAPSHOT.read_text())
    fallback = (snap["rate_30y"], snap["as_of"], snap["source"])
    if not LIVE:
        return fallback
    hit = _cache.get("pmms")
    if hit and time.time() - hit[0] < 6 * 3600:
        return hit[1]
    try:
        rows = urllib.request.urlopen(FRED_URL, timeout=5).read().decode().strip().splitlines()
        day, value = next(r.split(",") for r in reversed(rows) if r.split(",")[1] not in ("", "."))
        result = (float(value) / 100, day, "Freddie Mac PMMS via FRED (live)")
    except Exception:  # noqa: BLE001 — offline or blocked: use the snapshot
        result = fallback
    _cache["pmms"] = (time.time(), result)
    return result


def _band(value: float, tops: tuple[float, ...]) -> int:
    return next(i for i, top in enumerate(tops) if value <= top + 1e-9)


def _row(score: int, floors: tuple[int, ...]) -> int:
    return next(i for i, f in enumerate(floors) if score >= f)


def max_ltv(loan_type: str, units: int, owner_occupied: bool, score: int) -> tuple[float, str]:
    """Highest loan-to-value the program allows, and why."""
    if loan_type == "fha":
        if not owner_occupied:
            return 0.0, "FHA requires you to live in the property (one unit of a 2-4)."
        if units > 4 or score < 500:
            return 0.0, "FHA: 1-4 units and a 500+ credit score."
        return (0.965, "FHA: 3.5% down with 580+") if score >= 580 else (0.90, "FHA: 10% down below 580")
    if loan_type == "conventional":
        if score < 620:
            return 0.0, "Conventional loans need a 620+ credit score."
        if units > 4:
            return 0.0, "5+ units need a commercial loan."
        if owner_occupied:
            return (0.97, "Owner-occupied: 3% down") if units == 1 else (0.95, "Owner-occupied 2-4: 5% down")
        return (0.85, "Investment: 15% down minimum") if units == 1 else (0.75, "Investment 2-4 units: 25% down")
    if loan_type == "dscr":
        if score < 620:
            return 0.0, "DSCR lenders want a 620+ credit score."
        return (0.80, "DSCR: 20% down") if score >= 700 else (0.75, "DSCR: 25% down below 700")
    return 0.80, "Commercial 5+: 20-25% down, lender sizes to 1.25x DSCR"


@dataclass
class Pricing:
    rate: float
    steps: list[tuple[str, str]]
    mi_rate: float = 0.0          # annual
    mi_on_balance: bool = False   # FHA MIP runs on the current balance
    mi_months: int | None = None  # None: conventional PMI drops at 78% of value
    upfront_mi: float = 0.0       # fraction of base loan, financed
    mi_note: str = ""
    amort_years: int = 30
    balloon_years: int | None = None
    max_ltv: float = 1.0
    eligible: bool = True
    notes: list[str] = field(default_factory=list)


def price(loan: Loan, units: int, owner_occupied: bool, ltv: float, dscr: float | None,
          base: float) -> Pricing:
    t, score = loan.type, loan.credit_score
    cap, cap_note = max_ltv(t, units, owner_occupied, score)
    p = Pricing(rate=base, steps=[("Weekly 30-yr market rate", f"{base:.3%}")], max_ltv=cap,
                amort_years=loan.term_years or (25 if t == "commercial" else 30))
    p.notes.append(cap_note)
    if ltv > cap + 1e-9:
        p.eligible = False
        p.notes.append(f"{ltv:.1%} loan-to-value is above this program's {cap:.0%} limit.")

    def add(label: str, delta: float) -> None:
        if abs(delta) > 1e-9:
            p.rate += delta
            p.steps.append((label, f"{delta:+.3%}"))

    if t == "conventional":
        band = _band(ltv, LTV_TOPS)
        llpa = LLPA[_row(score, SCORE_FLOORS)][band]
        add(f"Credit {score} at {ltv:.0%} LTV ({llpa:.3f} pts vs {REFERENCE_LLPA} for the base borrower)",
            (llpa - REFERENCE_LLPA) * POINTS_TO_RATE / 100)
        if not owner_occupied:
            add(f"Investment property ({INVESTOR_LLPA[band]:.3f} pts)", INVESTOR_LLPA[band] * POINTS_TO_RATE / 100)
        if ltv > 0.80:
            pmi_band = min((b for b in PMI if ltv <= b + 1e-9), default=1.00)
            p.mi_rate = PMI[pmi_band][_row(score, PMI_SCORES)] / 100 * (1 if owner_occupied else INVESTOR_PMI_LOAD)
            p.mi_note = "PMI until the loan falls to 78% of the original value"
    elif t == "fha":
        add("FHA pricing vs conventional", -0.0025)
        if score < 620:
            add("Credit below 620", 0.0025 if score >= 580 else 0.005)
        p.upfront_mi = FHA_UPFRONT_MIP
        p.mi_rate = 0.0055 if ltv > 0.95 else 0.0050
        p.mi_on_balance = True
        p.mi_months = p.amort_years * 12 if ltv > 0.90 else 132
        p.mi_note = ("FHA MIP for the life of the loan (under 10% down)" if ltv > 0.90
                     else "FHA MIP for 11 years") + ", plus 1.75% upfront, financed"
    elif t == "dscr":
        add("Investor premium", DSCR_INVESTOR / 100)
        cover = dscr if dscr is not None else 1.25
        add(f"DSCR {cover:.2f}x tier", 0.0075 if cover >= 1.25 else 0.0125 if cover >= 1.0 else 0.02)
        credit_adj = (0 if score >= 740 else 0.00125 if score >= 720 else 0.0025 if score >= 700
                      else 0.005 if score >= 680 else 0.0075 if score >= 660 else 0.0125)
        add(f"Credit {score}", credit_adj)
    else:   # commercial
        add("Small-balance multifamily spread", COMMERCIAL_SPREAD)
        p.balloon_years = loan.balloon_years or 10
        p.notes.append(f"Balloon in year {p.balloon_years}: modelled as a refinance at the same rate.")
    return p
