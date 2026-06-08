"""CapEx as a sinking-fund reserve driven by component replacement clocks.

Not a flat % of rent. Each major component has a remaining life; the annual reserve is
the sum of (replacement_cost / remaining_life) across components. Unknown ages are treated
as mid-life (conservative), never as new.

Phase 1. Stubbed.
"""

from __future__ import annotations

from decimal import Decimal

from ..schemas import Assumptions, Property


def annual_reserve(prop: Property, assumptions: Assumptions) -> Decimal:
    """Annual capex reserve ($) = sum of component cost / remaining life.

    For each of roof / hvac / water_heater:
        remaining = max(life - age, 1)   # age defaults to life/2 if unknown
        reserve  += cost / remaining
    """
    raise NotImplementedError("Phase 1: capex reserve model not yet implemented.")
