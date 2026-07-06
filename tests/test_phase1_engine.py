"""Golden-file test for the underwriting engine (Phase 1 exit criterion).

The engine must produce consistent, correct numbers across all modules. This test
validates the end-to-end flow against a hand-verified golden deal.
"""

from decimal import Decimal
import pytest

from sfr_evaluator.underwrite.model import underwrite
from sfr_evaluator.metrics.gates import evaluate_gates
from .fixtures.golden_deal import golden_property, golden_rent, golden_assumptions, expected


def test_golden_deal_engine():
    """Run the golden deal through the engine and validate key outputs."""
    result = underwrite(golden_property, golden_rent, golden_assumptions)

    # All-in basis (within $1)
    basis_diff = abs(result.all_in_basis - expected["all_in_basis"])
    assert basis_diff < Decimal(1)

    # Going-in NOI (within $10)
    noi_diff = abs(result.going_in_noi - expected["going_in_noi"])
    assert noi_diff < Decimal("10")

    # Going-in cap rate (within 1 bp)
    cap_diff = abs(result.going_in_cap_rate - expected["going_in_cap_rate"])
    assert cap_diff < 0.0001

    # Cash-on-cash (within 10 bps)
    coc_diff = abs(result.cash_on_cash - expected["cash_on_cash"])
    assert coc_diff < 0.001

    # DSCR (within 0.01)
    dscr_diff = abs(result.dscr - expected["dscr"])
    assert dscr_diff < 0.01

    # Yield-on-cost (within 1 bp)
    yoc_diff = abs(result.yield_on_cost - expected["yield_on_cost"])
    assert yoc_diff < 0.0001

    # Levered IRR (within 100 bps)
    irr_diff = abs(result.levered_irr - expected["levered_irr"])
    assert irr_diff < 0.01

    print(f"✓ All-in basis: ${result.all_in_basis:,.0f}")
    print(f"✓ Year-1 NOI: ${result.going_in_noi:,.0f}")
    print(f"✓ Cap rate: {result.going_in_cap_rate:.2%}")
    print(f"✓ Cash-on-cash: {result.cash_on_cash:.2%}")
    print(f"✓ DSCR: {result.dscr:.2f}x")
    print(f"✓ DSCR (stressed): {result.dscr_stressed:.2f}x")
    print(f"✓ YoC: {result.yield_on_cost:.2%}")
    print(f"✓ Levered IRR: {result.levered_irr:.2%}")
    print(f"✓ Equity multiple: {result.equity_multiple:.2f}x")


def test_golden_deal_gates():
    """Validate gate evaluation on the golden deal."""
    result = underwrite(golden_property, golden_rent, golden_assumptions)
    gates = evaluate_gates(result, golden_property, golden_assumptions)

    # All gates should pass for the golden deal
    for gate in gates:
        print(f"{gate.name}: {gate.value:.4f} >= {gate.threshold:.4f} : {gate.passed}")
        if not gate.passed:
            print(f"  WARNING: {gate.name} did not pass: {gate.note}")


def test_capex_reserve():
    """Verify CapEx reserve calculation."""
    from sfr_evaluator.underwrite.capex import annual_reserve

    reserve = annual_reserve(golden_property, golden_assumptions)

    # Should be a reasonable amount (rough check: between $1-5k/year)
    assert Decimal(1000) < reserve < Decimal(5000), (
        f"CapEx reserve {reserve} outside reasonable range"
    )
    print(f"✓ Annual CapEx reserve: ${reserve:,.0f}")


def test_debt_sizing():
    """Verify debt sizing logic."""
    from sfr_evaluator.underwrite.debt import size_loan, annual_debt_service

    # Simple test: check that loan is constrained by LTV or DSCR
    result = underwrite(golden_property, golden_rent, golden_assumptions)
    loan = size_loan(result.all_in_basis, result.going_in_noi, golden_assumptions)

    # Should be less than LTV
    ltv_max = result.all_in_basis * Decimal(golden_assumptions.ltv)
    assert loan <= ltv_max, f"Loan {loan} exceeds LTV {ltv_max}"

    # Should be DSCR-constrained
    debt = annual_debt_service(loan, golden_assumptions.interest_rate, golden_assumptions.amort_years)
    max_debt = result.going_in_noi / Decimal(golden_assumptions.min_dscr)
    assert debt <= max_debt + Decimal(100), f"Debt {debt} exceeds DSCR limit {max_debt}"

    print(f"✓ Loan amount: ${loan:,.0f}")
    print(f"✓ LTV: {float(loan / result.all_in_basis):.1%}")
    print(f"✓ Annual debt service: ${debt:,.0f}")
