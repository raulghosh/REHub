"""Return metrics and the hard gates that admit a deal to human review.

The headline screening gate is the development spread: yield-on-cost minus exit cap.
"""

from __future__ import annotations

from decimal import Decimal

from ..schemas import Assumptions, GateResult, UnderwritingResult, Property, RentEstimate


def evaluate_gates(result: UnderwritingResult, prop: Property, assumptions: Assumptions) -> list[GateResult]:
    """Apply the SFR/townhouse hard gates and return one GateResult each.

    Gates:
    1. Rent-to-price: monthly_rent / purchase_price >= min_rent_to_price
    2. Cash-on-cash (Year 1): >= min_cash_on_cash
    3. DSCR (stressed): >= min_dscr
    4. Yield-on-cost - exit cap spread: >= min_yoc_exit_spread_bps
    5. Levered IRR: >= min_levered_irr
    """
    gates = []

    # Gate 1: Rent-to-price
    monthly_rent_to_price = float(result.rent.point / prop.list_price) if prop.list_price > 0 else 0.0
    gates.append(GateResult(
        name="Rent-to-Price",
        value=monthly_rent_to_price,
        threshold=assumptions.min_rent_to_price,
        passed=monthly_rent_to_price >= assumptions.min_rent_to_price,
        note=f"{monthly_rent_to_price:.2%} / month",
    ))

    # Gate 2: Cash-on-cash
    gates.append(GateResult(
        name="Cash-on-Cash",
        value=result.cash_on_cash,
        threshold=assumptions.min_cash_on_cash,
        passed=result.cash_on_cash >= assumptions.min_cash_on_cash,
        note=f"Year 1: {result.cash_on_cash:.2%}",
    ))

    # Gate 3: DSCR (stressed)
    gates.append(GateResult(
        name="DSCR (Stressed)",
        value=result.dscr_stressed,
        threshold=assumptions.min_dscr,
        passed=result.dscr_stressed >= assumptions.min_dscr,
        note=f"At rate + {assumptions.stress_rate_bps} bps",
    ))

    # Gate 4: Yield-on-cost - exit cap spread
    yoc_exit_spread = (result.yield_on_cost - result.exit_cap_rate) * 10000  # in basis points
    gates.append(GateResult(
        name="YoC - Exit Cap Spread",
        value=yoc_exit_spread,
        threshold=assumptions.min_yoc_exit_spread_bps,
        passed=yoc_exit_spread >= assumptions.min_yoc_exit_spread_bps,
        note=f"{yoc_exit_spread:.0f} bps",
    ))

    # Gate 5: Levered IRR
    gates.append(GateResult(
        name="Levered IRR",
        value=result.levered_irr,
        threshold=assumptions.min_levered_irr,
        passed=result.levered_irr >= assumptions.min_levered_irr,
        note=f"{result.levered_irr:.1%}",
    ))

    return gates
