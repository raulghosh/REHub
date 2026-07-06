"""Sensitivity (tornado) analysis.

Tornado ranks the inputs by their swing on levered IRR. Vary one input at a time,
compute IRR for base/low/high cases, and report the swing.

Phase 4: tornado only. Monte Carlo deferred to Phase 5 if needed.
"""

from __future__ import annotations

from copy import copy
from decimal import Decimal

from ..schemas import Assumptions, Property, RentEstimate
from ..underwrite.model import underwrite


def tornado(
    prop: Property,
    rent: RentEstimate,
    base: Assumptions,
) -> dict[str, tuple[float, float]]:
    """Tornado sensitivity analysis: vary each key input, return IRR swings.

    Returns dict mapping input name -> (low_irr, high_irr) for a ±10% swing
    on each numeric assumption.
    """
    base_result = underwrite(prop, rent, base)
    base_irr = base_result.levered_irr

    swings = {}

    # Key assumptions to test (±10% variation)
    test_vars = [
        ("rent_growth", 0.10),
        ("vacancy", 0.05),  # Vary physical_vacancy by 5%
        ("exit_cap", 0.01),  # ±100 bps
        ("interest_rate", 0.02),  # ±200 bps
        ("property_tax_rate", 0.002),  # ±20 bps via millage
    ]

    for var_name, var_amount in test_vars:
        low_assumptions = copy(base)
        high_assumptions = copy(base)

        # Vary the assumption
        if var_name == "rent_growth":
            low_assumptions.rent_growth = max(0, base.rent_growth - var_amount)
            high_assumptions.rent_growth = base.rent_growth + var_amount
        elif var_name == "vacancy":
            low_assumptions.physical_vacancy = max(0, base.physical_vacancy - var_amount)
            high_assumptions.physical_vacancy = min(1, base.physical_vacancy + var_amount)
        elif var_name == "exit_cap":
            # Exit cap: higher cap = lower valuation = lower IRR
            if base.exit_cap_rate is None:
                # Derive from entry cap + spread
                base_exit = base_result.going_in_cap_rate + (base.exit_cap_spread_bps / 10000)
            else:
                base_exit = base.exit_cap_rate
            low_assumptions.exit_cap_rate = base_exit - var_amount
            high_assumptions.exit_cap_rate = base_exit + var_amount
        elif var_name == "interest_rate":
            low_assumptions.interest_rate = max(0, base.interest_rate - var_amount)
            high_assumptions.interest_rate = base.interest_rate + var_amount
        elif var_name == "property_tax_rate":
            low_assumptions.millage_rate = max(0, base.millage_rate - var_amount)
            high_assumptions.millage_rate = base.millage_rate + var_amount

        # Compute IRRs for the cases
        low_result = underwrite(prop, rent, low_assumptions)
        high_result = underwrite(prop, rent, high_assumptions)

        swings[var_name] = (low_result.levered_irr, high_result.levered_irr)

    return swings
