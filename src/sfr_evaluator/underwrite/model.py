"""The underwriting engine.

Composes capex, debt and tax modules into a full hold-period pro forma and reversion,
then computes the metrics that gate a deal. Pure function over the data contracts.

Phase 1. Stubbed.
"""

from __future__ import annotations

from ..schemas import Assumptions, Property, RentEstimate, UnderwritingResult


def underwrite(
    prop: Property,
    rent: RentEstimate,
    assumptions: Assumptions,
) -> UnderwritingResult:
    """Run the full pro forma and return returns + gate verdicts.

    Flow (to implement):
        1. EGI = rent * 12 * (1 - physical_vacancy - credit_loss)
        2. OpEx = mgmt + maintenance + insurance + taxes(reassessed) + HOA + other
        3. CapEx reserve = capex.annual_reserve(prop, assumptions)
        4. NOI = EGI - OpEx - CapEx reserve
        5. Debt service & DSCR via debt.size_loan / debt.annual_debt_service
        6. Project years 1..hold with rent_growth / expense_growth
        7. Reversion = year-N NOI / exit_cap - selling costs
        8. Levered IRR / equity multiple over the equity cash-flow stream
        9. metrics.gates.evaluate(...) -> list[GateResult]
    """
    raise NotImplementedError("Phase 1: underwriting engine not yet implemented.")
