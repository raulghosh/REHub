"""The engine: a deal -> year-by-year pro forma -> sale -> before- and after-tax cash flows.

`resolve()` turns every blank input into an explicit, sourced assumption once per deal;
`project()` runs the pro forma at a given price (the max-offer solver calls it many times).
Each expense line grows with its own index, estimated lines carry the estimate allowance,
and self-managed vs. PM-managed deals differ in fees, vendor markups and DIY savings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .. import market as mkt
from ..schemas import Acquisition, Assumption, DealInput, MarketInfo, PropertyType, Sale, YearRow
from . import capex, debt, taxes

T = PropertyType
MULTI = (T.MULTI_2_4, T.MULTI_5_PLUS)

NATIONAL_TAX_RATE = 0.011   # US owner-occupied effective rate is ~0.9%; rentals get no homestead break
INSURANCE_RATE = 0.007      # landlord (DP-3) premium per $ of rebuild cost, ~2026 US average
INSURANCE_FACTOR = {T.SINGLE_FAMILY: 1.0, T.TOWNHOUSE: 0.8, T.CONDO: 0.35,   # condo: HO-6 walls-in
                    T.MULTI_2_4: 1.0, T.MULTI_5_PLUS: 1.0}
DEFAULT_VACANCY = 0.05
PMI_LTV, PMI_STOP_LTV = 0.80, 0.78
RESERVE_MONTHS = 6          # lenders want ~6 months of PITI in the bank for investment loans
REFI_SEASONING_MONTHS = 6


@dataclass
class Resolved:
    """Everything derived from the deal that does not depend on the price paid."""
    market: MarketInfo | None
    units: int
    rent_monthly: float
    market_value: float        # as-is
    base_value: float          # what the exit grows from: market value, or ARV after a rehab
    arv: float | None
    appreciation: float
    tax_growth: float
    tax_rate: float
    tax_annual: float | None
    insurance: float
    utilities_monthly: float
    other_annual: float
    vacancy: float
    tenancy: float
    turnover_cost: float
    inspections: float
    lender_fees: float
    land_pct: float
    rebuild_cost: float
    age: float                 # effective age at purchase (after any rehab)
    rehab_total: float
    refi_month: int | None
    assumptions: list[Assumption] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def resolve(deal: DealInput) -> Resolved:
    p, pu, ops, rh = deal.property, deal.purchase, deal.operations, deal.rehab
    m = mkt.lookup(p.zip_code, p.property_type)
    notes: list[Assumption] = []
    warn: list[str] = []

    def note(label: str, value: str, source: str) -> None:
        notes.append(Assumption(label=label, value=value, source=source))

    units = len(p.units)
    rebuild = p.sqft * ops.replacement_cost_psf
    rehab_total = rh.budget * (1 + rh.contingency_pct) if rh else 0.0

    zip_value = m.ppsf * p.sqft if m and m.ppsf else None
    zip_src = (f"zip {p.zip_code} {p.property_type.value.replace('_', ' ')} sales: ${m.ppsf:,.0f}/sqft x "
               f"{p.sqft:,.0f} sqft ({m.sales_12m} sales, 12 mo)") if zip_value else ""
    if m is None:
        warn.append(f"Zip {p.zip_code} is not in the market data: enter market value and appreciation.")
    elif not m.ppsf:
        warn.append(f"Only {m.sales_12m or 0} sales in zip {p.zip_code} in 12 months: zip $/sqft too thin to value.")
    if p.property_type is T.MULTI_5_PLUS and pu.market_value is None:
        warn.append("5+ unit buildings trade on income (cap rate): get a broker opinion of value or appraisal.")

    if pu.market_value:
        market_value, src = pu.market_value, "your appraisal / comps"
    elif rh:
        market_value, src = pu.price, "as-is value taken as the price"
    elif zip_value:
        market_value, src = zip_value, zip_src
    else:
        market_value, src = pu.price, "no zip value: assumed equal to price"
    note("Market value (as-is)", f"${market_value:,.0f}", src)

    arv = None
    if rh:
        if rh.arv:
            arv, src = rh.arv, "your after-repair value"
        elif zip_value:
            arv, src = zip_value, zip_src
        else:
            arv, src = pu.price + rehab_total, "no zip value: price + rehab"
        note("After-repair value", f"${arv:,.0f}", src)
    base_value = arv or market_value

    if deal.growth.appreciation is not None:
        appreciation, src = deal.growth.appreciation, "your input"
    else:
        appreciation, src = mkt.appreciation_default(m)
    note("Appreciation", f"{appreciation:.1%}/yr", src)
    tax_growth = deal.growth.property_tax if deal.growth.property_tax is not None else appreciation

    tax_annual, tax_rate = ops.property_tax_annual, ops.property_tax_rate
    if tax_annual is not None:
        note("Property tax", f"${tax_annual:,.0f}/yr", "your figure")
    elif tax_rate is not None:
        note("Property tax rate", f"{tax_rate:.2%}", "your county rate, applied to the price")
    elif m and m.tax_rate:
        tax_rate = m.tax_rate
        note("Property tax rate", f"{tax_rate:.2%}", "Census ACS zip median for owner-occupants; "
             "rentals often pay more (no homestead exemption)")
    else:
        tax_rate = NATIONAL_TAX_RATE
        note("Property tax rate", f"{tax_rate:.2%}", "US average estimate: enter your county rate")
        warn.append("Property tax is a national estimate: enter the county rate or the post-sale bill.")
    note("Property tax growth", f"{tax_growth:.1%}/yr",
         "your input" if deal.growth.property_tax is not None else "tracks appreciation (enter your state's "
         "assessment cap if any, e.g. CA 2%)")

    insurance = ops.insurance_annual
    if insurance is None:
        insurance = INSURANCE_RATE * rebuild * INSURANCE_FACTOR[p.property_type]
        note("Insurance", f"${insurance:,.0f}/yr", f"estimate: {INSURANCE_RATE:.1%} of ${rebuild:,.0f} rebuild "
             "cost; get a landlord policy quote")

    vacancy = ops.vacancy_pct
    if vacancy is None:
        if m and m.rental_vacancy is not None:
            vacancy = min(0.12, max(0.04, m.rental_vacancy))
            note("Vacancy", f"{vacancy:.1%}", "Census ACS rental vacancy for the zip (bounded 4-12%)")
        else:
            vacancy = DEFAULT_VACANCY
            note("Vacancy", f"{vacancy:.1%}", "default")

    tenancy = ops.avg_tenancy_years or (2.0 if p.property_type in MULTI else 3.0)
    turnover = ops.turnover_cost if ops.turnover_cost is not None else 600 + 0.4 * p.sqft / units
    note("Tenant turnover", f"every {tenancy:g} yrs, ${turnover:,.0f} per move-out",
         "cleaning, paint touch-up, repairs, rekey, marketing")
    utilities = ops.utilities_monthly
    if utilities is None:
        utilities = 60.0 * units if p.property_type in MULTI else 0.0
    other = ops.other_expenses_annual
    if other is None:
        other = 600.0 + 200.0 * (units - 1)
    inspections = pu.inspection_costs if pu.inspection_costs is not None else 600.0 + 150.0 * (units - 1)
    lender_fees = deal.loan.lender_fees
    if lender_fees is None:
        lender_fees = 0.0 if deal.loan.down_payment_pct >= 1 else (
            6000.0 if p.property_type is T.MULTI_5_PLUS else 2000.0)

    land_pct = deal.tax.land_pct
    if land_pct is None:
        land_pct = min(0.8, max(0.2, 1 - rebuild / base_value))
        note("Land share (not depreciable)", f"{land_pct:.0%}", "value above rebuild cost, 20-80%; "
             "use your assessor's land/improvement split")

    actual_age = max(0, date.today().year - p.year_built)
    age = float(actual_age)
    if rh:
        age = rh.effective_age_after if rh.effective_age_after is not None else capex.effective_age(
            actual_age, rehab_total, rebuild)
    rate = ops.upkeep_pct_override if ops.upkeep_pct_override is not None else (
        capex.upkeep_rate(age) * capex.TYPE_FACTOR[p.property_type])
    note("Upkeep (repairs + capex reserve)", f"{rate:.2%} of rebuild cost = ${rate * rebuild:,.0f}/yr",
         "your override" if ops.upkeep_pct_override is not None else
         f"effective age {age:.0f} yrs (built {p.year_built}{', after rehab' if rh else ''}), rises yearly")
    if actual_age >= 50 and not rh:
        warn.append(f"Built {p.year_built}: have the inspector check wiring, supply lines, sewer lateral, "
                    "lead paint and asbestos.")
    note("Estimate allowance", f"+{deal.targets.estimate_allowance_pct:.0%}",
         "on every estimated expense" + (f" (quotes: {', '.join(ops.known)})" if ops.known else ""))

    refi_month = None
    if rh and rh.refinance:
        refi_month = rh.refi_month or rh.months + REFI_SEASONING_MONTHS

    return Resolved(
        market=m, units=units, rent_monthly=sum(u.rent for u in p.units), market_value=market_value,
        base_value=base_value, arv=arv, appreciation=appreciation, tax_growth=tax_growth,
        tax_rate=tax_rate or 0.0, tax_annual=tax_annual, insurance=insurance,
        utilities_monthly=utilities, other_annual=other, vacancy=vacancy, tenancy=tenancy,
        turnover_cost=turnover, inspections=inspections, lender_fees=lender_fees, land_pct=land_pct,
        rebuild_cost=rebuild, age=age, rehab_total=rehab_total, refi_month=refi_month,
        assumptions=notes, warnings=warn,
    )


@dataclass
class Projection:
    acquisition: Acquisition
    years: list[YearRow]
    stabilized: YearRow        # a full, normal year: no lease-up, rehab or one-off repairs
    sale: Sale
    before_tax: list[float]    # year 0..N
    after_tax: list[float]
    refi_costs: float


def project(deal: DealInput, r: Resolved, price: float) -> Projection:
    d, ops, g, mg = deal, deal.operations, deal.growth, deal.management
    allow = 1 + d.targets.estimate_allowance_pct

    def est(line: str) -> float:
        return 1.0 if line in ops.known else allow

    n, units, rh = d.exit.hold_years, r.units, d.rehab
    ptype = d.property.property_type

    loan_amt = price * (1 - d.loan.down_payment_pct)
    lender = r.lender_fees + d.loan.points_pct * loan_amt if loan_amt > 0 else 0.0
    closing = price * d.purchase.closing_costs_pct * est("closing")
    inspections = r.inspections * est("inspection")
    repairs_now = sum(k.cost for k in d.purchase.known_repairs if k.year == 0) * allow
    capitalized = closing + inspections + d.purchase.other_costs - d.purchase.seller_credits
    cash_needed = price - loan_amt + lender + capitalized + r.rehab_total + repairs_now

    refi = None
    if r.refi_month is not None and r.refi_month <= n * 12:
        value_then = r.base_value * (1 + r.appreciation) ** (r.refi_month / 12)
        refi = debt.Refi(r.refi_month, rh.refi_ltv * value_then,
                         d.loan.rate if rh.refi_rate is None else rh.refi_rate,
                         rh.refi_term_years, rh.refi_cost_pct)
    pmi_rate = d.loan.pmi_rate if loan_amt > PMI_LTV * price else 0.0
    sched = debt.schedule(loan_amt, d.loan.rate, d.loan.term_years, n, pmi_rate, PMI_STOP_LTV * price, refi)

    rehab_months = rh.months if rh else 0
    vacant = rehab_months + ops.lease_up_months
    first_lease_year = int(vacant // 12) + 1 if vacant > 0 else None

    def operating(t: int, occ: float, one_offs: bool) -> dict[str, float]:
        def grow(rate: float) -> float:
            return (1 + rate) ** (t - 1)

        rent_month = r.rent_monthly * grow(g.rent)
        rent = rent_month * 12 * occ
        other_inc = ops.other_income_monthly * 12 * grow(g.rent) * occ
        vac = (r.vacancy + ops.credit_loss_pct) * (rent + other_inc)
        egi = rent + other_inc - vac
        if r.tax_annual is not None:
            ptax = r.tax_annual
        else:   # reassessed at the purchase price; a permitted rehab gets reassessed at ARV
            reassessed = rh is not None and r.arv is not None and (t >= 2 or not one_offs)
            ptax = r.tax_rate * (max(price, r.arv) if reassessed else price)
        ptax *= grow(r.tax_growth) * est("property_tax")
        new_leases = units * occ / r.tenancy + (units if one_offs and t == first_lease_year else 0)
        renewals = units * occ * max(0.0, 1 - 1 / r.tenancy)
        if mg.mode == "pm":
            mgmt = mg.pm_fee_pct * egi
            leasing = (new_leases * mg.leasing_fee_pct * rent_month / units
                       + renewals * mg.renewal_fee * grow(g.general_inflation))
            upkeep_f = 1 + mg.maintenance_markup_pct * capex.REPAIR_SHARE
            turn_f = 1 + mg.maintenance_markup_pct
            owner = 0.0
        else:
            mgmt = leasing = 0.0
            upkeep_f = 1 - mg.diy_pct * capex.LABOR_SHARE * capex.REPAIR_SHARE
            turn_f = 1 - mg.diy_pct * capex.LABOR_SHARE
            owner = mg.hours_per_unit_month * 12 * units * mg.hourly_value * grow(g.general_inflation)
        if ops.upkeep_pct_override is not None:
            upkeep_rate = ops.upkeep_pct_override
        else:
            upkeep_rate = capex.upkeep_rate(r.age + t - 1) * capex.TYPE_FACTOR[ptype]
        expenses = {
            "property_tax": ptax,
            "insurance": r.insurance * grow(g.insurance) * est("insurance"),
            "hoa": d.property.hoa_monthly * 12 * grow(g.hoa) * est("hoa"),
            "utilities": r.utilities_monthly * 12 * grow(g.utilities) * est("utilities"),
            "other": r.other_annual * grow(g.general_inflation) * est("other"),
            "management": mgmt,
            "leasing": leasing,
            "upkeep": upkeep_rate * r.rebuild_cost * grow(g.maintenance) * occ * upkeep_f * allow,
            "turnover": units * occ / r.tenancy * r.turnover_cost * grow(g.maintenance) * turn_f * allow,
            "known_repairs": (sum(k.cost for k in d.purchase.known_repairs if k.year == t)
                              * grow(g.maintenance) * allow) if one_offs else 0.0,
            "owner_time": owner,
            "holding": (max(0, min(12, rehab_months - 12 * (t - 1))) * rh.holding_utilities_monthly
                        * grow(g.utilities)) if (one_offs and rh) else 0.0,
        }
        opex = sum(expenses.values())
        return {"gross_rent": rent, "other_income": other_inc, "vacancy_loss": vac, "egi": egi,
                **expenses, "opex": opex, "noi": egi - opex}

    years = []
    for t in range(1, n + 1):
        occ = max(0.0, min(12.0, 12 * t - vacant)) / 12
        o = operating(t, occ, one_offs=True)
        y = sched[t - 1]
        ds = y.interest + y.principal + y.pmi
        value = r.base_value * (1 + r.appreciation) ** t
        years.append(YearRow(year=t, **o, debt_service=ds, interest=y.interest, principal=y.principal,
                             pmi=y.pmi, refi_cash_out=y.refi_cash_out,
                             cash_flow=o["noi"] - ds + y.refi_cash_out,
                             loan_balance=y.balance, value=value, equity=value - y.balance))

    # Stabilized year: normal operations on the long-term loan (the refi loan, after a BRRRR).
    if refi is not None:
        s = debt.schedule(refi.amount, refi.rate, refi.term_years, 1)[0]
    else:
        s = debt.schedule(loan_amt, d.loan.rate, d.loan.term_years, 1, pmi_rate, PMI_STOP_LTV * price)[0]
    o = operating(1, 1.0, one_offs=False)
    s_ds = s.interest + s.principal + s.pmi
    stabilized = YearRow(year=1, **o, debt_service=s_ds, interest=s.interest, principal=s.principal,
                         pmi=s.pmi, refi_cash_out=0.0, cash_flow=o["noi"] - s_ds,
                         loan_balance=s.balance, value=r.base_value, equity=r.base_value - s.balance)

    # Taxes.
    loan_costs = [0.0] * n

    def amortize(cost: float, start: int, term: int, end: int) -> None:
        left = cost
        for t in range(start, end + 1):
            amt = left if t == end else min(left, cost / term)
            loan_costs[t - 1] += amt
            left -= amt

    refi_year = (refi.month - 1) // 12 + 1 if refi else None
    if lender:
        amortize(lender, 1, d.loan.term_years, refi_year or n)
    refi_costs = sum(y.refi_costs for y in sched)
    if refi_costs:
        amortize(refi_costs, refi_year, refi.term_years, n)

    land_basis = (price + capitalized) * r.land_pct
    building_basis = (price + capitalized) * (1 - r.land_pct) + r.rehab_total + repairs_now
    sale_price = r.base_value * (1 + r.appreciation) ** n
    selling = sale_price * d.exit.selling_cost_pct
    deductible = ("property_tax", "insurance", "hoa", "utilities", "other", "management", "leasing",
                  "turnover", "holding", "interest", "pmi")
    tr = taxes.compute(
        taxes.TaxInputs(
            operating=[y.egi - sum(getattr(y, k) for k in deductible) - capex.REPAIR_SHARE * y.upkeep
                       for y in years],
            capital_added=[(1 - capex.REPAIR_SHARE) * y.upkeep + y.known_repairs for y in years],
            loan_costs=loan_costs, building_basis=building_basis, land_basis=land_basis,
            sale_price=sale_price, selling_costs=selling),
        d.tax, g.general_inflation,
        start_index=(1 + g.general_inflation) ** max(0, date.today().year - taxes.BASE_YEAR))
    for y, ti, tx, su in zip(years, tr.taxable, tr.tax, tr.suspended):
        y.taxable_income, y.tax, y.suspended_losses = ti, tx, su
        y.cash_flow_after_tax = y.cash_flow - tx

    payoff = sched[-1].balance
    proceeds = sale_price - selling - payoff
    sale = Sale(year=n, price=sale_price, selling_costs=selling, loan_payoff=payoff,
                proceeds_before_tax=proceeds, adjusted_basis=tr.adjusted_basis, gain=tr.gain,
                depreciation_recapture=tr.recapture, capital_gain=tr.capital_gain,
                suspended_losses_released=tr.released, tax=tr.sale_tax,
                proceeds_after_tax=proceeds - tr.sale_tax, deferred_tax=tr.deferred_tax)

    piti = s_ds + stabilized.property_tax + stabilized.insurance + stabilized.hoa
    acquisition = Acquisition(
        price=price, down_payment=price - loan_amt, loan_amount=loan_amt, closing_costs=closing,
        lender_costs=lender, inspections=inspections, other_costs=d.purchase.other_costs,
        seller_credits=d.purchase.seller_credits, rehab=r.rehab_total, repairs_at_purchase=repairs_now,
        total_cash_needed=cash_needed,
        lender_reserves=RESERVE_MONTHS * piti / 12 if loan_amt > 0 or refi else 0.0)

    before = [-cash_needed] + [y.cash_flow for y in years]
    after = [-cash_needed] + [y.cash_flow_after_tax for y in years]
    before[-1] += proceeds
    after[-1] += proceeds - tr.sale_tax
    return Projection(acquisition, years, stabilized, sale, before, after, refi_costs)
