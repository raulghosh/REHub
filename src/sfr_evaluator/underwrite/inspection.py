"""Inspection risk: what a home inspection is likely to find that the listing didn't show, and
how much of it ends up on the buyer.

Before the inspection, each finding is a probability (by the home's age and the era of its
materials) times a typical repair cost. Who pays is a negotiation: in a buyer's market the
seller usually repairs or credits most of it, in a hot market the buyer absorbs most of it, and
an as-is or bank-owned sale leaves all of it with the buyer. Expected cost to you =
sum(probability x cost) x your share. Once the inspection is done, tick it and enter what it
actually found as repairs: the expectation is then replaced by the facts.

Probabilities and costs are typical figures (inspector and contractor guides, EPA for radon),
not data for this house. The component schedule already covers normal wear (roof, HVAC, ...);
these are defects beyond wear.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from ..schemas import DealInput, InspectionRisk, InspectionRow, PropertyType

T = PropertyType
TERMITE_STATES = {"FL", "TX", "LA", "MS", "AL", "GA", "SC", "NC", "TN", "AR", "HI", "CA", "AZ"}

# who pays for what the inspection finds: your share of the cost
BUYER_SHARE = {"buyers": 0.25, "balanced": 0.5, "sellers": 0.75, "as_is": 1.0}
MARKET_LABEL = {"buyers": "buyer's market", "balanced": "balanced market",
                "sellers": "seller's market", "as_is": "as-is sale"}


@dataclass
class Finding:
    label: str
    probability: Callable[[int, str], float]   # (year built, state) -> chance it's found
    cost: Callable[[int], float]               # units -> typical repair cost today
    note: str
    shell: bool = False                        # building shell: the HOA's problem in a condo


def _by_age(young: float, mid: float, old: float) -> Callable[[int, str], float]:
    return lambda built, state: young if date.today().year - built < 20 else (
        mid if date.today().year - built < 50 else old)


FINDINGS = {
    "structural": Finding(
        "Foundation or structural repair", _by_age(0.03, 0.08, 0.12), lambda u: 10_000,
        "Settlement cracks, failing piers, sagging framing. $5k-20k typical; underpinning costs more.",
        shell=True),
    "sewer": Finding(
        "Sewer line repair", _by_age(0.02, 0.08, 0.15), lambda u: 7_000,
        "Roots, breaks or bellies in the lateral; only a camera scope finds them ($150-300).",
        shell=True),
    "termites": Finding(
        "Termites or wood rot", lambda b, s: 0.15 if s in TERMITE_STATES else 0.06, lambda u: 3_000,
        "Treatment plus repair of damaged wood; far more common in the South and West.", shell=True),
    "moisture": Finding(
        "Water intrusion or mold", _by_age(0.05, 0.08, 0.10), lambda u: 4_000 * u ** 0.5,
        "Leaks at roof, windows or basement, and the mold that follows."),
    "radon": Finding(
        "Radon above the EPA action level", lambda b, s: 0.067, lambda u: 1_200,
        "EPA: about 1 in 15 US homes. A mitigation system costs $800-2,500."),
    "wiring": Finding(
        "Hazardous wiring or panel",
        lambda b, s: 0.30 if b < 1950 else 0.15 if b < 1990 else 0.02, lambda u: 4_000 * u,
        "Knob-and-tube (before 1950), aluminum branch wiring (1965-73), recalled Federal Pacific "
        "or Zinsco panels (1950s-80s). Insurers often won't cover them."),
    "pipes": Finding(
        "Problem supply pipes",
        lambda b, s: 0.30 if b < 1960 else 0.20 if 1978 <= b <= 1995 else 0.03, lambda u: 6_000 * u,
        "Galvanized steel (before 1960) or polybutylene (1978-95): both fail and need a repipe."),
}


def market(deal: DealInput, median_dom: float | None) -> tuple[str, str]:
    """(bargaining position, why)."""
    chosen = deal.purchase.bargaining
    if chosen != "auto":
        return chosen, "your input"
    if deal.rehab is not None:
        return "as_is", "fixer-upper: these usually sell as-is"
    if median_dom is None:
        return "balanced", "no days-on-market data for this zip"
    pos = "sellers" if median_dom <= 30 else "buyers" if median_dom >= 60 else "balanced"
    return pos, f"homes in this zip sell in {median_dom:.0f} days (median, Redfin)"


def risk(deal: DealInput, state: str, median_dom: float | None) -> InspectionRisk:
    p = deal.property
    units = len(p.units)
    condo = p.property_type is T.CONDO
    rows = [InspectionRow(key=k, label=f.label, probability=f.probability(p.year_built, state),
                          cost=f.cost(units), note=f.note)
            for k, f in FINDINGS.items() if not (condo and f.shell)]
    pos, why = market(deal, median_dom)
    share = BUYER_SHARE[pos]
    none_found = 1.0
    for r in rows:
        none_found *= 1 - r.probability
    expected = sum(r.probability * r.cost for r in rows)
    done = deal.purchase.inspection_done
    return InspectionRisk(
        done=done, market=MARKET_LABEL[pos], basis=why, buyer_share=share,
        p_any=1 - none_found, expected_cost=expected,
        expected_to_you=0.0 if done else expected * share,
        bad_case=0.0 if done else max(r.cost for r in rows) * share, rows=rows)
