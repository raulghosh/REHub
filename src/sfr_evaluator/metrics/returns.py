"""Return metrics, the four-way return breakdown, and the margin-of-safety offer.

The max offer is solved, not guessed: for each of the investor's targets we bisect on price
for the highest price that still meets it. The lowest of those is the investment value;
the margin of safety discounts it, and we never pay above market (or ARV minus rehab).
"""

from __future__ import annotations

from collections.abc import Callable

from ..schemas import DealInput, Metrics, Offer, ReturnBreakdown, TargetCheck
from ..underwrite.model import Projection, Resolved, project


def irr(flows: list[float]) -> float | None:
    """Annual IRR by bisection; None when the flows never cross zero (e.g. you lose money)."""
    def npv(rate: float) -> float:
        return sum(cf / (1 + rate) ** t for t, cf in enumerate(flows))

    lo, hi = -0.99, 1.0
    while npv(hi) > 0 and hi < 1e4:   # BRRRR deals that return all the cash can run very high
        hi *= 4
    if npv(lo) * npv(hi) > 0:
        return None
    for _ in range(100):
        mid = (lo + hi) / 2
        if npv(mid) > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def metrics(r: Resolved, pj: Projection) -> Metrics:
    s, a = pj.stabilized, pj.acquisition
    cash_left = a.total_cash_needed - sum(y.refi_cash_out for y in pj.years)
    all_in = (a.price + a.closing_costs + a.inspections + a.other_costs - a.seller_credits
              + a.rehab + a.repairs_at_purchase)
    gpi = s.gross_rent + s.other_income
    return Metrics(
        market_value=r.base_value,
        cap_rate=s.noi / r.base_value,
        cap_rate_on_cost=s.noi / all_in,
        cash_on_cash=s.cash_flow / cash_left if cash_left > 1 else None,
        monthly_cash_flow=s.cash_flow / 12,
        monthly_cash_flow_per_unit=s.cash_flow / 12 / r.units,
        dscr=s.noi / s.debt_service if s.debt_service > 0 else None,
        break_even_occupancy=(s.opex + s.debt_service) / gpi if gpi else 1.0,
        gross_rent_multiplier=a.price / s.gross_rent if s.gross_rent else 0.0,
        rent_to_price=r.rent_monthly / (a.price + a.rehab),
        expense_ratio=s.opex / s.egi if s.egi else 0.0,
        upkeep_pct_of_value=s.upkeep / r.base_value,
        upkeep_pct_of_rent=s.upkeep / s.gross_rent if s.gross_rent else 0.0,
        irr_before_tax=irr(pj.before_tax),
        irr_after_tax=irr(pj.after_tax),
        equity_multiple=sum(pj.after_tax[1:]) / a.total_cash_needed,
        cash_left_in_deal=cash_left,
    )


def breakdown(r: Resolved, pj: Projection) -> ReturnBreakdown:
    """Where the after-tax profit comes from; the parts sum to sum(after-tax cash flows)."""
    a, sale = pj.acquisition, pj.sale
    parts = {
        "operating_cash_flow": sum(y.cash_flow - y.refi_cash_out for y in pj.years),
        "principal_paydown": sum(y.principal for y in pj.years),
        "appreciation": sale.price - r.base_value,
        "equity_at_purchase": r.base_value - a.price - a.rehab - a.repairs_at_purchase,
        "transaction_costs": -(a.closing_costs + a.lender_costs + a.inspections + a.other_costs
                               - a.seller_credits + sale.selling_costs + pj.refi_costs),
        "taxes": -(sum(y.tax for y in pj.years) + sale.tax),
    }
    return ReturnBreakdown(**parts, total=sum(parts.values()))


# name, Targets field, metric getter, value used when the metric is undefined
TARGETS: list[tuple[str, str, Callable[[Metrics], float | None], float]] = [
    ("Cash-on-cash", "min_cash_on_cash", lambda m: m.cash_on_cash, float("inf")),   # no cash left in
    ("Monthly cash flow per unit", "min_monthly_cash_flow_per_unit",
     lambda m: m.monthly_cash_flow_per_unit, 0.0),
    ("DSCR", "min_dscr", lambda m: m.dscr, float("inf")),                           # no debt
    ("After-tax IRR", "min_irr", lambda m: m.irr_after_tax, float("-inf")),         # money lost
]


def _meets(value: float | None, undefined: float, threshold: float) -> bool:
    return (undefined if value is None else value) >= threshold


def offer(deal: DealInput, r: Resolved, at_price: Metrics) -> Offer:
    price, t = deal.purchase.price, deal.targets
    ceiling = r.arv - r.rehab_total if r.arv else r.market_value
    ref = max(price, r.base_value)
    checks: list[TargetCheck] = []
    for name, key, get, undefined in TARGETS:
        threshold = getattr(t, key)
        if threshold is None:
            continue

        def ok(p: float, get=get, undefined=undefined, threshold=threshold) -> bool:
            return _meets(get(metrics(r, project(deal, r, p))), undefined, threshold)

        v = get(at_price)
        lo, hi = 0.05 * ref, 3 * ref
        if ok(hi):
            best: float | None = hi
        elif not ok(lo):
            best = None
        else:
            for _ in range(22):
                mid = (lo + hi) / 2
                lo, hi = (mid, hi) if ok(mid) else (lo, mid)
            best = lo
        checks.append(TargetCheck(name=name, threshold=threshold, value=v,
                                  passed=_meets(v, undefined, threshold), max_price=best))

    reachable = [c for c in checks if c.max_price is not None]
    blocked = [c for c in checks if c.max_price is None]
    binding = min(reachable, key=lambda c: c.max_price, default=None)
    investment = None if blocked else (binding.max_price if binding else None)
    limited = (blocked[0].name if blocked else binding.name if binding else "market value only")
    mos = t.margin_of_safety_pct
    cap_name = "ARV minus rehab" if r.arv else "market value"
    # The margin of safety is measured against your investment value; with no targets set,
    # against market value. Either way you never pay above market (or ARV minus rehab).
    anchor = ceiling if investment is None else investment
    max_offer = None if blocked else min(anchor * (1 - mos), ceiling)
    margin = None if blocked or anchor <= 0 else 1 - price / anchor

    if blocked:
        verdict = "pass"
        summary = (f"No price meets your {blocked[0].name.lower()} target "
                   f"({_fmt(blocked[0].name, blocked[0].threshold)}): the rent can't carry the "
                   "fixed costs. Pass, or change the plan (rent, financing, management).")
    elif price <= max_offer + 0.5:
        verdict = "buy"
        what = "meets every target" if checks else f"is below {cap_name}"
        summary = f"At ${price:,.0f} the deal {what} with a {margin:.0%} margin of safety."
    elif price <= min(anchor, ceiling):
        verdict = "negotiate"
        what = "Meets your targets" if checks else f"Below {cap_name}"
        summary = (f"{what} at ${price:,.0f}, but only a {margin:.0%} cushion "
                   f"(you want {mos:.0%}). Offer up to ${max_offer:,.0f}.")
    else:
        verdict = "pass"
        reason = (f"{cap_name} (${ceiling:,.0f})" if price > ceiling
                  else f"your {limited.lower()} target")
        summary = f"At ${price:,.0f} you'd pay more than {reason} supports. Offer up to ${max_offer:,.0f}."

    return Offer(price=price, market_value=r.base_value, investment_value=investment,
                 limited_by=limited, margin_of_safety_pct=t.margin_of_safety_pct, max_offer=max_offer,
                 margin_at_price=margin, verdict=verdict, summary=summary,
                 rule_70=0.7 * r.arv - r.rehab_total if r.arv else None, targets=checks)


def _fmt(name: str, v: float) -> str:
    if "cash flow" in name:
        return f"${v:,.0f}/mo"
    if name == "DSCR":
        return f"{v:.2f}x"
    return f"{v:.0%}"
