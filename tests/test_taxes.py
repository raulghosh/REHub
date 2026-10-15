"""2026 federal tax math and the passive-loss rules, checked by hand."""

import pytest

from sfr_evaluator.schemas import TaxProfile
from sfr_evaluator.underwrite import taxes


def test_ordinary_brackets_mfj():
    # 100k - 32,200 std = 67,800: 10% of 24,800 + 12% of 43,000
    assert taxes.federal_tax(100_000, 0, 0, "mfj") == pytest.approx(2_480 + 5_160)


def test_capital_gains_stack_on_top():
    # single, no wages: 100k gain - 16,100 std = 83,900 taxable; 0% up to 49,450
    assert taxes.federal_tax(0, 0, 100_000, "single") == pytest.approx(0.15 * (83_900 - 49_450))


def test_unrecaptured_1250_capped_at_25pct():
    base = taxes.federal_tax(700_000, 0, 0, "single")        # already in the 37% bracket
    assert taxes.federal_tax(700_000, 10_000, 0, "single") - base == pytest.approx(2_500)
    low = taxes.federal_tax(40_000, 0, 0, "single")           # 12% bracket: ordinary rate applies
    assert taxes.federal_tax(40_000, 1_000, 0, "single") - low == pytest.approx(120)


def test_passive_allowance_phase_out():
    assert taxes.passive_allowance(90_000) == 25_000
    assert taxes.passive_allowance(125_000) == 12_500
    assert taxes.passive_allowance(150_000) == 0


def run(profile: TaxProfile, operating=-20_000.0):
    ti = taxes.TaxInputs(operating=[operating] * 3, capital_added=[0.0] * 3, loan_costs=[0.0] * 3,
                         building_basis=200_000, land_basis=50_000, sale_price=300_000, selling_costs=20_000)
    return taxes.compute(ti, profile, inflation=0.0, start_index=1.0)


def test_losses_depend_on_who_you_are():
    reps = run(TaxProfile(real_estate_professional=True, household_income=300_000))
    assert reps.tax[0] < 0 and reps.suspended == [0, 0, 0]                 # offsets W-2 income
    high = run(TaxProfile(household_income=200_000))
    assert high.tax[0] == pytest.approx(0) and high.suspended[1] > 0       # suspended
    assert high.released > 0 and high.suspended[-1] == 0                   # freed by the sale
    modest = run(TaxProfile(household_income=80_000))
    assert modest.tax[0] < 0                                               # $25k allowance


def test_sale_recapture_and_1031():
    sold = run(TaxProfile(household_income=100_000), operating=10_000)
    dep = 3 * 200_000 / 27.5
    assert sold.adjusted_basis == pytest.approx(250_000 - dep)
    assert sold.gain == pytest.approx(280_000 - (250_000 - dep))
    assert sold.recapture == pytest.approx(dep)
    swap = run(TaxProfile(household_income=100_000, exchange_1031=True), operating=10_000)
    assert swap.sale_tax == 0 and swap.deferred_tax == pytest.approx(sold.sale_tax)


def test_cost_segregation_front_loads_depreciation():
    plain = run(TaxProfile(real_estate_professional=True, household_income=300_000))
    seg = run(TaxProfile(real_estate_professional=True, household_income=300_000, cost_seg_pct=0.25))
    assert seg.tax[0] < plain.tax[0] - 10_000          # 50k bonus in year 1
    assert seg.recapture > plain.recapture * 0.99      # and it comes back at sale
