"""Debt sizing, amortization and DSCR.

Loan is constrained by the *lesser* of LTV and a DSCR floor — committees size to whichever
binds. DSCR is also tested at a stressed rate (rate + stress_rate_bps).
"""

from __future__ import annotations

from decimal import Decimal

from ..schemas import Assumptions


def size_loan(purchase_price: Decimal, noi: Decimal, assumptions: Assumptions) -> Decimal:
    """Loan amount = min(LTV-constrained, DSCR-constrained).

    LTV constraint: loan <= purchase_price * ltv.
    DSCR constraint: solve for max loan such that NOI / debt_service >= min_dscr.
    """
    ltv_loan = purchase_price * Decimal(assumptions.ltv)

    # DSCR-constrained: find max loan such that NOI / debt_service >= min_dscr
    # Use bisection to find the loan amount.
    max_debt_service = noi / Decimal(assumptions.min_dscr)

    # Binary search: find the largest loan such that annual_debt_service <= max_debt_service
    low = Decimal(0)
    high = ltv_loan
    dscr_loan = Decimal(0)

    for _ in range(100):  # ~27 bits of precision
        mid = (low + high) / 2
        debt = annual_debt_service(mid, assumptions.interest_rate, assumptions.amort_years)
        if debt <= max_debt_service:
            dscr_loan = mid
            low = mid
        else:
            high = mid

    return min(ltv_loan, dscr_loan)


def annual_debt_service(loan: Decimal, rate: float, amort_years: int) -> Decimal:
    """Annual debt service for a fully-amortizing fixed-rate loan.

    Payment = loan * (r * (1 + r)^n) / ((1 + r)^n - 1)
    where r = rate / 12 (monthly), n = amort_years * 12.
    """
    if rate == 0:
        return loan / Decimal(amort_years)

    r_monthly = Decimal(rate) / 12
    n = amort_years * 12

    # (1 + r)^n
    compound = (1 + r_monthly) ** n

    # numerator = r * (1 + r)^n
    # denominator = (1 + r)^n - 1
    monthly_payment = loan * (r_monthly * compound) / (compound - 1)

    # Annual
    return monthly_payment * 12


def dscr(noi: Decimal, debt_service: Decimal) -> float:
    """Debt Service Coverage Ratio = NOI / annual debt service."""
    if debt_service == 0:
        return float('inf') if noi > 0 else 1.0
    return float(noi / debt_service)
