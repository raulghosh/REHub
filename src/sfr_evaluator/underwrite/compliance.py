"""Regulatory costs: the checklist of rules that commonly cost landlords money.

Rules are local, so this is a checklist, not a database: each item says when it usually
applies (state, age, type), a typical cost, and where the number comes from. Items that apply
are on by default (the conservative choice); untick what doesn't fit your city or building.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ..schemas import DealInput, PropertyType

T = PropertyType
MULTI = (T.MULTI_2_4, T.MULTI_5_PLUS)


@dataclass
class Rule:
    label: str
    applies: Callable[[DealInput, str], bool]     # (deal, state)
    one_time: Callable[[int], float]              # units -> $ at purchase
    annual: Callable[[int], float]                # units -> $/yr, today's dollars
    note: str
    default_on: bool = True


RULES = {
    "lead_paint": Rule(
        "Lead paint (built before 1978)", lambda d, s: d.property.year_built < 1978,
        lambda u: 500, lambda u: 150 * u,
        "Disclosure, lead-safe (EPA RRP) work by certified firms, risk assessment; some states and "
        "cities require lead-safe certificates at each turnover. EPA fines reach $37,500/day."),
    "rental_license": Rule(
        "Rental license & inspections", lambda d, s: True,
        lambda u: 0, lambda u: 150 * u,
        "Many cities license rentals ($50-300/unit/yr) and inspect periodically; untick if yours doesn't."),
    "detectors": Rule(
        "Smoke & CO detectors", lambda d, s: True,
        lambda u: 250 * u, lambda u: 25 * u,
        "Required in rentals almost everywhere; 10-year sealed units, replaced each decade."),
    "permit_upgrades": Rule(
        "Code upgrades triggered by permits", lambda d, s: d.rehab is not None and d.property.year_built < 1980,
        lambda u: 2_500 + 500 * u, lambda u: 0,
        "A permitted rehab of an older building usually pulls in GFCI/AFCI, panel, egress and "
        "smoke-detector upgrades beyond the scope you priced."),
    "fl_condo_reserves": Rule(
        "Florida condo inspections & reserves", lambda d, s: s == "FL" and d.property.property_type is T.CONDO
        and d.property.year_built <= 2001,
        lambda u: 10_000 * u, lambda u: 0,
        "Post-Surfside law: milestone inspections and fully funded structural reserves. Special "
        "assessments of $10k-100k+ per unit are common in older buildings; read the SIRS."),
    "ca_soft_story": Rule(
        "California soft-story seismic retrofit", lambda d, s: s == "CA" and d.property.property_type in MULTI
        and d.property.year_built < 1978,
        lambda u: 10_000 * u, lambda u: 0,
        "Wood-frame buildings over open parking in LA, SF, Oakland, Berkeley and others: about "
        "$5k-15k per unit. Untick if not soft-story or already retrofitted.", default_on=False),
    "energy_benchmarking": Rule(
        "Energy benchmarking (large buildings)", lambda d, s: d.property.property_type is T.MULTI_5_PLUS
        and d.property.sqft >= 25_000,
        lambda u: 0, lambda u: 1_500,
        "NYC, Boston, DC, Denver, Seattle and others require annual reporting; some add retrofit mandates."),
}


def checklist(deal: DealInput, state: str) -> list[tuple[str, Rule, bool]]:
    """(key, rule, included) for every rule that applies to this deal."""
    chosen = deal.operations.compliance
    return [(k, r, chosen.get(k, r.default_on)) for k, r in RULES.items() if r.applies(deal, state)]
