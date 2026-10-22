"""One call from a deal to the full answer: verdict, max offer, returns, risks."""

from __future__ import annotations

from .metrics.returns import (
    breakdown,
    down_payment_options,
    exit_timeline,
    financing,
    metrics,
    offer,
)
from .risk.sensitivity import management_compare, stress
from .schemas import DealInput, PropertyType, Result
from .underwrite.model import project, resolve


def evaluate(deal: DealInput) -> Result:
    r = resolve(deal)
    pj = project(deal, r, deal.purchase.price)
    m = metrics(r, pj)
    warnings = list(r.warnings)
    s, a = pj.stabilized, pj.acquisition

    fin = financing(deal, r, pj)
    if not fin.eligible:
        warnings.append(f"{fin.notes[-1]} Pick a larger down payment or another loan type.")
    if m.monthly_cash_flow < 0:
        warnings.append(f"Negative cash flow (${m.monthly_cash_flow:,.0f}/mo) in a normal year: "
                        "you would be feeding this property.")
    if m.dscr is not None and m.dscr < 1.0:
        warnings.append(f"DSCR {m.dscr:.2f}x: rent doesn't cover the mortgage; DSCR lenders want 1.2x+.")
    if not deal.rehab and a.price > 1.05 * r.market_value:
        warnings.append(f"Price is {a.price / r.market_value - 1:.0%} above the estimated market value.")
    if a.repairs_at_purchase:
        warnings.append(f"Ask the seller for a ${a.repairs_at_purchase:,.0f} credit for repairs needed now.")
    insp = r.inspection
    if insp and not insp.done and insp.p_any >= 0.25:
        warnings.append(f"{insp.p_any:.0%} chance the inspection turns up a major repair; in a {insp.market} "
                        f"you'd likely pay {insp.buyer_share:.0%} of it (up to ${insp.bad_case:,.0f}). "
                        "Keep the inspection contingency in your offer.")
    if m.rent_to_price < 0.006:
        warnings.append(f"Rent is {m.rent_to_price:.2%} of price per month: returns lean on appreciation.")
    if any(y.suspended_losses > 0 for y in pj.years[:-1]):
        warnings.append("Tax losses are suspended (passive rules at your income); they pay off only "
                        "against future rental profit or when you sell.")
    if deal.rehab and deal.rehab.refinance and any(y.refi_cash_out < 0 for y in pj.years):
        warnings.append("The refinance needs cash in: the value won't support the planned loan.")
    if deal.property.property_type is PropertyType.CONDO:
        warnings.append("Condo: read the HOA reserve study, special-assessment history and rental caps.")
    if r.market:
        for u in deal.property.units:
            ref = r.market.rent_by_beds.get(min(u.beds, 4))
            if ref and u.rent > 1.2 * ref:
                warnings.append(f"${u.rent:,.0f} rent for a {u.beds}-bed is {u.rent / ref - 1:.0%} above the "
                                f"zip's Census median gross rent (${ref:,.0f}); verify with leased comps.")
                break

    return Result(
        offer=offer(deal, r, m), metrics=m, returns=breakdown(r, pj), financing=fin,
        down_payment_options=down_payment_options(deal, r), exit_timeline=exit_timeline(deal, r, pj),
        components=r.components, compliance=r.compliance, inspection=r.inspection, acquisition=a,
        stabilized=s,
        years=pj.years, sale=pj.sale, management=management_compare(deal, r), stress=stress(deal, r),
        assumptions=r.assumptions, market=r.market, warnings=warnings,
    )
