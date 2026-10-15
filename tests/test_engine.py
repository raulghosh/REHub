"""Engine checks against hand-computed numbers, plus the invariants that must always hold."""

from datetime import date

import pytest

from sfr_evaluator.analysis import evaluate
from sfr_evaluator.metrics.returns import irr, metrics
from sfr_evaluator.schemas import DealInput
from sfr_evaluator.underwrite import capex, debt
from sfr_evaluator.underwrite.model import project, resolve

ALL_KNOWN = ["property_tax", "insurance", "hoa", "utilities", "other", "closing", "inspection"]


def golden(**overrides) -> DealInput:
    """All-cash, 25-year-old 1,000 sqft house; every line pinned so the math is checkable by hand."""
    deal = {
        "property": {"zip_code": "38118", "year_built": date.today().year - 25, "sqft": 1000,
                     "units": [{"beds": 2, "baths": 1, "rent": 1000}]},
        "purchase": {"price": 100_000, "market_value": 100_000, "closing_costs_pct": 0.02,
                     "inspection_costs": 500},
        "loan": {"down_payment_pct": 1.0},
        "management": {"mode": "pm", "pm_fee_pct": 0.10, "leasing_fee_pct": 0, "renewal_fee": 0,
                       "maintenance_markup_pct": 0},
        "operations": {"vacancy_pct": 0.05, "credit_loss_pct": 0, "lease_up_months": 0,
                       "avg_tenancy_years": 2, "turnover_cost": 1000, "property_tax_rate": 0.01,
                       "insurance_annual": 1200, "utilities_monthly": 0, "other_expenses_annual": 0,
                       "replacement_cost_psf": 100, "known": ALL_KNOWN},
        "growth": {"appreciation": 0.03},
        "targets": {"estimate_allowance_pct": 0.10, "min_cash_on_cash": 0.05,
                    "min_monthly_cash_flow_per_unit": None, "min_dscr": None, "min_irr": None},
    }
    for path, value in overrides.items():
        *parents, leaf = path.split("__")
        node = deal
        for p in parents:
            node = node.setdefault(p, {})
        node[leaf] = value
    return DealInput.model_validate(deal)


def test_golden_pro_forma():
    r = resolve(golden())
    pj = project(golden(), r, 100_000)
    s = pj.stabilized
    assert s.egi == pytest.approx(11_400)                   # 12,000 rent - 5% vacancy
    assert s.management == pytest.approx(1_140)             # 10% of collected rent
    assert s.property_tax == pytest.approx(1_000)           # reassessed at price, quoted: no allowance
    assert s.insurance == pytest.approx(1_200)
    assert s.upkeep == pytest.approx(0.013 * 100_000 * 1.1)  # age 25 -> 1.3% of rebuild, + allowance
    assert s.turnover == pytest.approx(1_000 / 2 * 1.1)
    assert s.noi == pytest.approx(6_080)
    assert pj.acquisition.total_cash_needed == pytest.approx(102_500)
    m = metrics(r, pj)
    assert m.cash_on_cash == pytest.approx(6_080 / 102_500)
    assert m.cap_rate == pytest.approx(0.0608)
    assert m.dscr is None


def test_each_line_grows_with_its_own_index():
    d = golden()
    y1, y2 = project(d, resolve(d), 100_000).years[:2]
    assert y2.insurance / y1.insurance == pytest.approx(1.05)        # insurance index
    assert y2.gross_rent / y1.gross_rent == pytest.approx(1.03)      # CPI rent
    assert y2.property_tax / y1.property_tax == pytest.approx(1.03)  # follows appreciation
    # Upkeep: construction-cost growth AND the house is a year older.
    assert y2.upkeep == pytest.approx(capex.upkeep_rate(26) * 100_000 * 1.035 * 1.1)


def test_quoted_lines_skip_the_allowance():
    est = golden(operations__known=[])
    s = project(est, resolve(est), 100_000).stabilized
    assert s.insurance == pytest.approx(1_320)
    assert s.property_tax == pytest.approx(1_100)


def test_max_offer_solves_the_target_exactly():
    d = golden()
    o = evaluate(d).offer
    # CoC(p) = (7,080 - 0.01p) / (1.02p + 500) = 5%  ->  p = 7,055 / 0.061
    assert o.investment_value == pytest.approx(7_055 / 0.061, rel=1e-4)
    assert o.max_offer == pytest.approx(100_000)        # 10% MoS lands above market value: capped
    assert o.verdict == "buy"
    assert o.margin_at_price == pytest.approx(1 - 100_000 * 0.061 / 7_055, abs=1e-4)


def test_verdicts_follow_the_margin():
    assert evaluate(golden(purchase__price=110_000, purchase__market_value=130_000)).offer.verdict == "negotiate"
    assert evaluate(golden(purchase__price=125_000, purchase__market_value=130_000)).offer.verdict == "pass"
    # No targets: the margin of safety is measured against market value alone.
    for price, verdict in ((85_000, "buy"), (95_000, "negotiate"), (105_000, "pass")):
        o = evaluate(golden(purchase__price=price, targets__min_cash_on_cash=None)).offer
        assert (o.verdict, o.max_offer) == (verdict, pytest.approx(90_000)), price


def test_upkeep_rises_with_age_and_depends_on_type():
    rates = [capex.upkeep_rate(a) for a in range(0, 100, 5)]
    assert rates == sorted(rates) and rates[0] == 0.004 and rates[-1] == 0.018
    old, new = (evaluate(golden(property__year_built=date.today().year - a)).stabilized.upkeep for a in (70, 2))
    assert old > 3 * new
    condo = evaluate(golden(property__property_type="condo", property__hoa_monthly=300)).stabilized.upkeep
    assert condo == pytest.approx(0.6 * evaluate(golden()).stabilized.upkeep)


def test_self_managed_vs_property_manager():
    d = golden(management__mode="self", management__hourly_value=0)
    self_cf, pm_cf = (s.monthly_cash_flow for s in evaluate(d).management)
    # The 10% fee, plus DIY on a quarter of the labor (60%) of repairs (40% of upkeep) and turnovers.
    diy = 1_430 * 0.25 * 0.6 * 0.4 + 550 * 0.25 * 0.6
    assert self_cf - pm_cf == pytest.approx((1_140 + diy) / 12)
    valued = golden(management__mode="self", management__hourly_value=30, management__hours_per_unit_month=2)
    assert evaluate(valued).metrics.monthly_cash_flow == pytest.approx(evaluate(d).metrics.monthly_cash_flow - 60)


def test_mortgage_math():
    assert debt.monthly_payment(100_000, 0.06, 30) == pytest.approx(599.55, abs=0.01)
    years = debt.schedule(100_000, 0.06, 30, 30)
    assert sum(y.principal for y in years) == pytest.approx(100_000, abs=0.01)
    pmi = debt.schedule(95_000, 0.07, 30, 30, pmi_rate=0.01, pmi_stop_balance=78_000)
    assert pmi[0].pmi == pytest.approx(950) and pmi[-1].pmi == 0


def test_irr():
    assert irr([-100, 110]) == pytest.approx(0.10)
    assert irr([-100, 0, 121]) == pytest.approx(0.10)
    assert irr([-100, -5, 50]) == pytest.approx(-0.3175, abs=1e-4)   # losing money is a negative IRR
    assert irr([-100, -5, -5]) is None


@pytest.mark.parametrize("extra", [
    {},
    {"loan__down_payment_pct": 0.25},
    {"loan__down_payment_pct": 0.10},                              # PMI
    {"tax__exchange_1031": True, "loan__down_payment_pct": 0.25},
    {"tax__real_estate_professional": True, "tax__cost_seg_pct": 0.3, "loan__down_payment_pct": 0.2},
    {"rehab": {"budget": 25_000, "months": 4, "refinance": True, "arv": 140_000}, "loan__down_payment_pct": 0.2},
    {"purchase__known_repairs": [{"cost": 8000, "year": 0}, {"cost": 3000, "year": 4}]},
])
def test_profit_breakdown_adds_up(extra):
    d = golden(**{k: v for k, v in extra.items() if k != "rehab"})
    if "rehab" in extra:
        d = d.model_copy(update={"rehab": DealInput.model_validate(
            {**d.model_dump(), "rehab": extra["rehab"]}).rehab})
    r = resolve(d)
    pj = project(d, r, d.purchase.price)
    res = evaluate(d)
    assert res.returns.total == pytest.approx(sum(pj.after_tax), abs=0.01)


def test_brrrr_refinance_returns_cash():
    d = golden(loan__down_payment_pct=1.0, purchase__price=70_000)
    d = d.model_copy(update={"rehab": DealInput.model_validate(
        {**d.model_dump(), "rehab": {"budget": 30_000, "months": 3, "refinance": True, "arv": 140_000}}).rehab})
    res = evaluate(d)
    cash_out = sum(y.refi_cash_out for y in res.years)
    assert cash_out == pytest.approx(0.75 * 140_000 * 1.03 ** 0.75 * 0.98, rel=1e-6)  # month 9, minus 2% costs
    assert res.metrics.cash_left_in_deal == pytest.approx(res.acquisition.total_cash_needed - cash_out)
    assert res.years[0].gross_rent == pytest.approx(12_000 * 9 / 12)   # 3 rehab + 0 lease-up months
    assert res.offer.rule_70 == pytest.approx(0.7 * 140_000 - 30_000 * 1.15)


def test_overpaying_lowers_returns():
    lo, hi = (evaluate(golden(purchase__price=p)).metrics for p in (90_000, 120_000))
    assert lo.cash_on_cash > hi.cash_on_cash and lo.irr_after_tax > hi.irr_after_tax
