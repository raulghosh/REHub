"""The underwriting engine.

Composes capex, debt and tax modules into a full hold-period pro forma and reversion,
then computes the metrics that gate a deal. Pure function over the data contracts.
"""

from __future__ import annotations

from decimal import Decimal

from . import capex, debt, taxes
from ..schemas import Assumptions, Property, RentEstimate, UnderwritingResult


def underwrite(
    prop: Property,
    rent: RentEstimate,
    assumptions: Assumptions,
) -> UnderwritingResult:
    """Run the full pro forma and return returns + gate verdicts.

    Flow:
        1. All-in basis = price + closing + rehab
        2. Year-0 NOI from rent, vacancy, opex, capex, taxes
        3. Debt size (LTV or DSCR constrained)
        4. Project years 1..hold with growth
        5. Reversion (sale) in final year
        6. Compute levered IRR, equity multiple, CoC, etc.
    """
    # All-in basis
    all_in_basis = (
        prop.list_price
        + (prop.list_price * Decimal(assumptions.closing_cost_pct))
        + assumptions.rehab_budget
    )

    # Year-0 economics (year 1, before any growth)
    monthly_rent = rent.point
    annual_rent = monthly_rent * 12
    egi = annual_rent * Decimal(1 - assumptions.physical_vacancy - assumptions.credit_loss)

    mgmt = egi * Decimal(assumptions.mgmt_fee)
    maintenance = egi * Decimal(assumptions.maintenance_pct)
    insurance = assumptions.insurance_annual
    hoa = prop.hoa_monthly * 12
    other_opex = assumptions.other_opex_annual

    annual_tax = taxes.annual_property_tax(prop, prop.list_price, assumptions)
    capex_reserve = capex.annual_reserve(prop, assumptions)

    total_opex = mgmt + maintenance + insurance + hoa + other_opex + annual_tax + capex_reserve
    noi_y1 = egi - total_opex

    # Debt sizing
    loan = debt.size_loan(all_in_basis, noi_y1, assumptions)
    equity = all_in_basis - loan
    annual_debt = debt.annual_debt_service(loan, assumptions.interest_rate, assumptions.amort_years)

    # Year 0 metrics
    unlevered_cap_rate = float(noi_y1 / all_in_basis) if all_in_basis > 0 else 0.0
    yield_on_cost = float((noi_y1 - annual_tax) / equity) if equity > 0 else 0.0
    cash_on_cash = float((noi_y1 - annual_debt) / equity) if equity > 0 else 0.0
    dscr_y1 = debt.dscr(noi_y1, annual_debt)

    # Stressed DSCR
    stressed_rate = assumptions.interest_rate + (assumptions.stress_rate_bps / 10000)
    stressed_debt = debt.annual_debt_service(loan, stressed_rate, assumptions.amort_years)
    dscr_stressed = debt.dscr(noi_y1, stressed_debt)

    # Project hold period and compute reversion
    noi_current = noi_y1
    for year in range(1, assumptions.hold_years):
        noi_current = noi_current * Decimal(1 + assumptions.rent_growth)

    # Exit cap rate
    if assumptions.exit_cap_rate is None:
        exit_cap = unlevered_cap_rate + (assumptions.exit_cap_spread_bps / 10000)
    else:
        exit_cap = assumptions.exit_cap_rate

    # Reversion: NOI / exit cap - selling costs
    exit_value = (noi_current / Decimal(exit_cap)) if exit_cap > 0 else Decimal(0)
    selling_costs = exit_value * Decimal(assumptions.selling_cost_pct)
    proceeds_from_sale = exit_value - selling_costs

    # Levered cash flows: equity invested, then annual CF, then exit
    # Simplified IRR: just equity in, annual CF (from noi_y1), and exit proceed
    cash_flow_annual = noi_y1 - annual_debt

    # Equity multiple and levered IRR (simplified for now)
    total_cash_returned = (cash_flow_annual * assumptions.hold_years) + proceeds_from_sale
    equity_multiple = float(total_cash_returned / equity) if equity > 0 else 0.0

    # Levered IRR via bisection
    levered_irr = _compute_levered_irr(
        -float(equity),  # initial investment (outflow)
        float(cash_flow_annual),
        float(proceeds_from_sale),
        assumptions.hold_years
    )

    # Break-even occupancy: at what occupancy does NOI = debt service?
    if annual_rent > 0:
        breakeven_occupancy = float(annual_debt / annual_rent) if annual_rent > 0 else 1.0
        breakeven_occupancy = min(1.0, breakeven_occupancy / (1 - assumptions.physical_vacancy - assumptions.credit_loss))
    else:
        breakeven_occupancy = 1.0

    return UnderwritingResult(
        property_id=prop.property_id,
        rent=rent,
        all_in_basis=all_in_basis,
        going_in_noi=noi_y1,
        going_in_cap_rate=unlevered_cap_rate,
        yield_on_cost=yield_on_cost,
        cash_on_cash=cash_on_cash,
        dscr=dscr_y1,
        dscr_stressed=dscr_stressed,
        levered_irr=levered_irr,
        equity_multiple=equity_multiple,
        break_even_occupancy=breakeven_occupancy,
        exit_cap_rate=exit_cap,
        exit_value=exit_value,
        gates=[],
    )


def _compute_levered_irr(initial_cf: float, annual_cf: float, exit_cf: float, years: int) -> float:
    """Compute levered IRR via bisection on the NPV equation."""
    def npv(rate: float) -> float:
        total = initial_cf
        for y in range(1, years + 1):
            if y < years:
                total += annual_cf / ((1 + rate) ** y)
            else:
                # Final year: annual CF + exit
                total += (annual_cf + exit_cf) / ((1 + rate) ** y)
        return total

    # Bisection
    low = -0.5
    high = 2.0
    for _ in range(100):
        mid = (low + high) / 2
        if npv(mid) > 0:
            low = mid
        else:
            high = mid

    return (low + high) / 2
