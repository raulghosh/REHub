"""Debt sizing, amortization and DSCR.

Loan is constrained by the *lesser* of LTV and a DSCR floor — committees size to whichever
binds. DSCR is also tested at a stressed rate (rate + stress_rate_bps).

Phase 1. Stubbed.
"""

from __future__ import annotations

from decimal import Decimal

from ..schemas import Assumptions


def size_loan(purchase_price: Decimal, noi: Decimal, assumptions: Assumptions) -> Decimal:
    """Loan amount = min(LTV-constrained, DSCR-constrained)."""
    raise NotImplementedError("Phase 1: loan sizing not yet implemented.")


def annual_debt_service(loan: Decimal, rate: float, amort_years: int) -> Decimal:
    """Annual debt service for a fully-amortizing fixed-rate loan."""
    raise NotImplementedError("Phase 1: amortization not yet implemented.")


def dscr(noi: Decimal, debt_service: Decimal) -> float:
    raise NotImplementedError("Phase 1: DSCR not yet implemented.")
