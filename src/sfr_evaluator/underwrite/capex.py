"""CapEx as a sinking-fund reserve driven by component replacement clocks.

Not a flat % of rent. Each major component has a remaining life; the annual reserve is
the sum of (replacement_cost / remaining_life) across components. Unknown ages are treated
as mid-life (conservative), never as new.
"""

from __future__ import annotations

from decimal import Decimal

from ..schemas import Assumptions, ComponentAge, Property


def annual_reserve(prop: Property, assumptions: Assumptions) -> Decimal:
    """Annual capex reserve ($) = sum of component cost / remaining life.

    Unknown age → mid-life (conservative): if a roof has unknown age, assume it's half its
    useful life remaining.
    """
    components = [
        ("roof", prop.component_age.roof, assumptions.roof_life, assumptions.roof_cost),
        ("hvac", prop.component_age.hvac, assumptions.hvac_life, assumptions.hvac_cost),
        ("water_heater", prop.component_age.water_heater, assumptions.water_heater_life, assumptions.water_heater_cost),
        ("flooring", prop.component_age.flooring, assumptions.flooring_life, assumptions.flooring_cost),
        ("electrical", prop.component_age.electrical, assumptions.electrical_life, assumptions.electrical_cost),
        ("plumbing", prop.component_age.plumbing, assumptions.plumbing_life, assumptions.plumbing_cost),
    ]

    total = Decimal(0)
    for name, age, life, cost in components:
        if age is None:
            # Unknown age: assume mid-life, years_remaining = life / 2
            years_remaining = life / 2
        else:
            years_remaining = max(0.1, life - age)  # At least 0.1 years to avoid division by zero

        annual_reserve = cost / Decimal(years_remaining)
        total += annual_reserve

    return total
