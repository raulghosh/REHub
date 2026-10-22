"""Loan pricing, down-payment options, the sell-year table, components, compliance, HOA, house hacking."""

from datetime import date

import pytest

from sfr_evaluator.analysis import evaluate
from sfr_evaluator.schemas import Loan
from sfr_evaluator.underwrite import capex, rates
from sfr_evaluator.underwrite.model import project, resolve

from .test_engine import golden


def test_conventional_pricing_follows_the_llpa_grid():
    loan = Loan(type="conventional", credit_score=740)
    p = rates.price(loan, units=1, owner_occupied=False, ltv=0.80, dscr=None, base=0.07)
    # 740 at 80% LTV = 0.875 pts, investor at 80% = 3.375 pts, minus the 0.375 base borrower.
    assert p.rate == pytest.approx(0.07 + (0.875 + 3.375 - 0.375) * 0.25 / 100)
    assert p.mi_rate == 0
    owner = rates.price(loan, 1, True, 0.95, None, 0.07)
    assert owner.mi_rate > 0 and owner.rate < p.rate          # PMI above 80%, no investor charge


def test_program_limits():
    assert rates.max_ltv("conventional", 1, False, 740)[0] == 0.85
    assert rates.max_ltv("conventional", 2, False, 740)[0] == 0.75
    assert rates.max_ltv("fha", 2, False, 740)[0] == 0           # FHA needs owner occupancy
    assert rates.max_ltv("fha", 2, True, 600)[0] == 0.965
    assert rates.max_ltv("dscr", 1, False, 680)[0] == 0.75


def test_down_payment_options_flag_what_the_loan_allows():
    res = evaluate(golden(loan__down_payment_pct=0.25, loan__type="conventional", loan__credit_score=740))
    by_dp = {round(o.down_pct, 3): o for o in res.down_payment_options}
    assert not by_dp[0.10].eligible and "15% down" in by_dp[0.10].note
    assert by_dp[0.15].eligible and by_dp[0.15].mortgage_insurance > 0
    assert by_dp[0.20].mortgage_insurance == 0
    assert by_dp[0.15].cash_needed < by_dp[0.25].cash_needed
    assert by_dp[0.15].monthly_cash_flow < by_dp[0.25].monthly_cash_flow


def test_dscr_loans_price_off_their_own_coverage():
    def dscr_deal(rent):
        return evaluate(golden(loan__down_payment_pct=0.25, loan__type="dscr", loan__credit_score=760,
                               property__units=[{"beds": 2, "baths": 1, "rent": rent}]))
    strong, weak = dscr_deal(2_000), dscr_deal(1_000)
    assert strong.metrics.dscr >= 1.25 and weak.metrics.dscr < 1.0
    assert weak.financing.rate - strong.financing.rate == pytest.approx(0.02 - 0.0075)


def test_sell_year_table():
    d = golden(loan__down_payment_pct=0.25, exit__hold_years=10)
    res = evaluate(d)
    tl = res.exit_timeline
    assert len(tl) == 30 and tl[-1].loan_balance == pytest.approx(0, abs=1)
    assert tl[9].profit_if_sold == pytest.approx(res.returns.total, abs=0.01)   # same as the 10-yr plan
    assert tl[-1].wealth_if_kept > tl[9].wealth_if_kept


def test_known_components_replace_their_share_of_the_curve():
    old_roof = golden(components__known_ages=[{"key": "roof", "age": 30}])
    r = resolve(old_roof)
    roof_cost = 1000 / 1 * capex.PITCH["medium"] * capex.ROOF["architectural"][0]
    assert r.events == [(0, pytest.approx(roof_cost), "Roof (architectural)"),
                        (25, pytest.approx(roof_cost), "Roof (architectural)")]
    pj = project(old_roof, r, 100_000)
    assert pj.acquisition.repairs_at_purchase == pytest.approx(roof_cost * 1.1)
    plain = project(golden(), resolve(golden()), 100_000)
    assert pj.stabilized.upkeep < plain.stabilized.upkeep             # roof no longer in the curve


def test_compliance_checklist():
    old = golden(property__year_built=1950, operations__compliance={})
    keys = {c.key: c for c in evaluate(old).compliance}
    assert keys["lead_paint"].included and keys["rental_license"].included
    off = golden(property__year_built=1950, operations__compliance={"lead_paint": False})
    assert evaluate(off).stabilized.compliance < evaluate(old).stabilized.compliance


def test_hoa_history_fades_to_the_long_run():
    d = golden(property__hoa_monthly=400, property__hoa_history=[300, 340, 400], growth__hoa=None)
    r = resolve(d)
    first, later = r.hoa_index[1] - 1, r.hoa_index[20] / r.hoa_index[19] - 1
    assert first == pytest.approx((400 / 300) ** 0.5 - 1)
    assert later == pytest.approx(r.hoa_growth, abs=0.002)


def test_house_hack_excludes_your_unit_and_counts_rent_saved():
    duplex = golden(property__property_type="multi_2_4",
                    property__units=[{"beds": 2, "baths": 1, "rent": 1000}] * 2,
                    occupancy__owner_occupied=True, occupancy__months=12,
                    loan__type="fha", loan__down_payment_pct=0.035)
    res = evaluate(duplex)
    y1, y2 = res.years[:2]
    assert y1.gross_rent == pytest.approx(12_000)        # only the other unit
    assert y1.housing_saved == pytest.approx(12_000)
    assert y2.housing_saved == 0 and y2.gross_rent == pytest.approx(24_000 * 1.03)
    assert res.financing.mortgage_insurance > 0 and res.metrics.house_hack_monthly is not None
    assert res.acquisition.loan_amount == pytest.approx(100_000 * 0.965 * 1.0175)
    assert date.today().year >= 2026
