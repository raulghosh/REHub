"""Upkeep = routine repairs + capital replacements, as a % of rebuild cost that rises with
the home's effective age — not a flat % of rent.

Why rebuild cost and not price: land doesn't need a new roof. "1% of value" overstates upkeep
on a $1M coastal lot and understates it on a $90k Midwest house; sqft x rebuild cost tracks
the thing that actually wears out.

The curve: a new home coasts on new components (~0.4%/yr); the first replacement wave (water
heater, appliances, paint, flooring) lands around year 10; roof and HVAC by 25; original
wiring, supply lines and sewer laterals push it higher past 50. Calibrated to large SFR
landlords' reported repairs + recurring capex (~$2/sqft/yr on ~30-year-old homes), plus a
retail premium for not having their scale. Roughly 40% of upkeep is deductible repairs and
60% capital work (depreciated), which matters for taxes.
"""

from __future__ import annotations

from itertools import pairwise
from math import ceil

from ..schemas import PropertyType

UPKEEP_CURVE = [(0, 0.004), (10, 0.009), (25, 0.013), (50, 0.016), (75, 0.018)]

TYPE_FACTOR = {
    PropertyType.SINGLE_FAMILY: 1.0,
    PropertyType.TOWNHOUSE: 0.85,     # shared walls; owner usually still has roof/exterior
    PropertyType.CONDO: 0.6,          # HOA dues cover roof, exterior, structure
    PropertyType.MULTI_2_4: 1.15,     # more kitchens, baths and systems per sqft
    PropertyType.MULTI_5_PLUS: 1.1,   # same, offset by shared roof/structure economies
}

REPAIR_SHARE = 0.4   # deductible now; the rest is capitalized
LABOR_SHARE = 0.6    # of repair and turnover invoices; what DIY saves
# Vendor markups (PM) and DIY savings (self) apply to repairs and turnovers; capital jobs
# (roof, HVAC) are contracted out at the same price either way.


def upkeep_rate(effective_age: float) -> float:
    """Annual upkeep as a fraction of rebuild cost, linear between curve points."""
    pts = UPKEEP_CURVE
    if effective_age >= pts[-1][0]:
        return pts[-1][1]
    for (a0, r0), (a1, r1) in pairwise(pts):
        if effective_age <= a1:
            return r0 + (r1 - r0) * (max(effective_age, a0) - a0) / (a1 - a0)
    return pts[-1][1]


def effective_age(actual_age: float, rehab_total: float, rebuild_cost: float) -> float:
    """A renovation makes a house act younger: a rehab worth half the rebuild cost (a gut
    job) resets it to new; smaller rehabs scale down proportionally."""
    return actual_age * max(0.0, 1 - rehab_total / (0.5 * rebuild_cost))


# --------------------------------------------------------------------------- #
# Components you know the age of (inspection, disclosure, permits)
# --------------------------------------------------------------------------- #
# Known components get real costs on real dates; unknown ones stay inside the age curve. A
# known component's steady-state share of the curve's capital part is removed so nothing is
# counted twice. Costs are 2026 installed mid-points (Angi/NerdWallet for roofs, Pearl and
# contractor guides for HVAC; the rest typical ranges) and carry the estimate allowance.

ROOF = {   # $/sqft of roof area installed incl. tear-off, useful life
    "asphalt_3tab": (5.0, 20), "architectural": (5.5, 25), "metal": (10.0, 45),
    "tile": (15.0, 50), "slate": (20.0, 75), "flat": (8.0, 20),
}
PITCH = {"low": 1.05, "medium": 1.15, "steep": 1.30}   # roof area per sqft of footprint, with overhang

# key: label, basis, unit cost, life. Basis: unit / sqft / system / building.
CATALOG = {
    "hvac": ("HVAC (furnace + AC)", "system", 13_000, 17),
    "water_heater": ("Water heater", "unit", 2_000, 12),
    "appliances": ("Appliances", "unit", 4_000, 12),
    "flooring": ("Flooring", "sqft", 5.0, 15),
    "interior_paint": ("Interior paint", "sqft", 3.0, 8),
    "exterior": ("Exterior paint / siding", "sqft", 2.5, 12),
    "windows": ("Windows & doors", "sqft", 10.0, 30),
    "electrical": ("Electrical panel & wiring", "unit", 3_500, 40),
    "plumbing": ("Supply lines & sewer lateral", "building", 10_000, 50),
    "kitchen_bath": ("Kitchen & bath refresh", "unit", 10_000, 25),
}
HOA_COVERS = {PropertyType.CONDO: {"roof", "exterior", "windows", "plumbing"}}


def component_costs(ptype: PropertyType, sqft: float, units: int, stories: int,
                    roof_material: str, roof_pitch: str) -> dict[str, tuple[str, float, float]]:
    """Every component's (label, replacement cost today, life) for this building."""
    psf, roof_life = ROOF[roof_material]
    out = {"roof": (f"Roof ({roof_material.replace('_', ' ')})",
                    sqft / stories * PITCH[roof_pitch] * psf, roof_life)}
    systems = units if units > 1 else max(1, round(sqft / 2500))
    count = {"unit": units, "sqft": sqft, "system": systems, "building": 1}
    for key, (label, basis, cost, life) in CATALOG.items():
        out[key] = (label, cost * count[basis], life)
    for key in HOA_COVERS.get(ptype, ()):
        label, _, life = out[key]
        out[key] = (f"{label} (HOA)", 0.0, life)
    return out


def known_schedule(costs: dict[str, tuple[str, float, float]], known: list, hold: int,
                   ) -> tuple[list[tuple[int, float, str]], float, dict[str, int | None]]:
    """Replacement events (year, cost today, label) for known-age components, the share of
    the curve's capital part they replace, and each one's next replacement year."""
    steady = {k: c / life for k, (_, c, life) in costs.items()}
    total = sum(steady.values()) or 1.0
    events, share, next_year = [], 0.0, {}
    for k in known:
        label, cost, life = costs[k.key]
        cost = k.cost if k.cost is not None else cost
        life = k.life or life
        share += steady[k.key] / total
        year = max(0, ceil(life - k.age))
        next_year[k.key] = year
        while year <= hold and cost > 0:
            events.append((year, cost, label))
            year += max(1, round(life))
    return events, min(share, 1.0), next_year
