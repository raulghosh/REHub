"""Return metrics and the hard gates that admit a deal to human review.

IRR / equity multiple operate on a cash-flow stream (year 0 = -equity, years 1..N = levered
CF, year N also += net reversion). The headline screening gate is the development spread:
yield-on-cost minus exit cap.

Phase 1. Stubbed.
"""

from __future__ import annotations

from decimal import Decimal

from ..schemas import Assumptions, GateResult


def irr(cash_flows: list[Decimal]) -> float:
    """Internal rate of return on a periodic cash-flow stream (year 0 negative)."""
    raise NotImplementedError("Phase 1: IRR not yet implemented.")


def equity_multiple(cash_flows: list[Decimal]) -> float:
    raise NotImplementedError("Phase 1: equity multiple not yet implemented.")


def break_even_occupancy(opex: Decimal, debt_service: Decimal, gpr: Decimal) -> float:
    """(OpEx + debt service) / gross potential rent."""
    raise NotImplementedError("Phase 1: break-even occupancy not yet implemented.")


def evaluate_gates(metrics: dict, assumptions: Assumptions) -> list[GateResult]:
    """Apply the SFR/townhouse hard gates and return one GateResult each.

    Gates: rent-to-price, cash-on-cash, DSCR (stressed), yield-on-cost - exit-cap spread,
    levered IRR. See README "The gates" table.
    """
    raise NotImplementedError("Phase 1: gate evaluation not yet implemented.")
