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
