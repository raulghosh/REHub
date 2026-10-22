"""Investor income tax: the same property is a different investment for different people.

2026 federal law (Rev. Proc. 2025-32; the One Big Beautiful Bill Act made the TCJA brackets
and 100% bonus depreciation permanent). Each year the household's tax is computed with and
without the property, so bracket changes, the $25k passive-loss allowance and its phase-out,
NIIT, and the sale's recapture / capital-gain stacking all fall out of one calculation.
State tax is a flat marginal rate on the same income.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import inf

from ..schemas import TaxProfile

BASE_YEAR = 2026
BRACKETS = {
    "single": [(12_400, .10), (50_400, .12), (105_700, .22), (201_775, .24),
               (256_225, .32), (640_600, .35), (inf, .37)],
    "mfj": [(24_800, .10), (100_800, .12), (211_400, .22), (403_550, .24),
            (512_450, .32), (768_700, .35), (inf, .37)],
}
STANDARD_DEDUCTION = {"single": 16_100, "mfj": 32_200}
LTCG_TOPS = {"single": (49_450, 545_500), "mfj": (98_900, 613_700)}   # tops of the 0% / 15% bands
# Fixed in statute, never indexed for inflation — bracket creep erodes them over a hold:
NIIT_THRESHOLD = {"single": 200_000, "mfj": 250_000}
NIIT_RATE = 0.038
PASSIVE_ALLOWANCE, PHASEOUT_START = 25_000, 100_000   # fully phased out at $150k MAGI
UNRECAPTURED_1250_RATE = 0.25
RESIDENTIAL_LIFE = 27.5
COST_SEG_LIFE = 7   # ponytail: one blended life for any non-bonus 5/7/15-yr remainder


def _bracket_tax(lo: float, hi: float, status: str, index: float, cap: float = 1.0) -> float:
    tax, lower = 0.0, 0.0
    for upper, rate in BRACKETS[status]:
        upper *= index
        overlap = min(hi, upper) - max(lo, lower)
        if overlap > 0:
            tax += overlap * min(rate, cap)
        lower = upper
    return tax


def federal_tax(ordinary: float, unrecaptured_1250: float, ltcg: float, status: str,
                index: float = 1.0) -> float:
    """Regular federal tax, Schedule D stacking: ordinary income, then unrecaptured §1250
    gain (ordinary rates capped at 25%), then 0/15/20% gains on top. `ordinary` is before
    the standard deduction and may be negative; `index` inflates the 2026 thresholds."""
    taxable = max(0.0, ordinary + unrecaptured_1250 + ltcg - STANDARD_DEDUCTION[status] * index)
    pref = min(unrecaptured_1250 + ltcg, taxable)
    u = min(unrecaptured_1250, pref)   # ponytail: losses offset 0/15/20 gain first (conservative)
    g = pref - u
    base = taxable - pref
    tax = _bracket_tax(0, base, status, index) + _bracket_tax(base, base + u, status, index,
                                                              UNRECAPTURED_1250_RATE)
    zero_top, fifteen_top = (b * index for b in LTCG_TOPS[status])
    top = base + u
    tax += 0.15 * max(0.0, min(top + g, fifteen_top) - max(top, zero_top))
    tax += 0.20 * max(0.0, top + g - max(top, fifteen_top))
    return tax


def passive_allowance(magi: float) -> float:
    return max(0.0, PASSIVE_ALLOWANCE - 0.5 * max(0.0, magi - PHASEOUT_START))


def _household_tax(p: TaxProfile, income: float, ordinary: float, u1250: float, ltcg: float,
                   nii: float, index: float) -> float:
    magi = income + ordinary + u1250 + ltcg
    fed = federal_tax(income + ordinary, u1250, ltcg, p.filing_status, index)
    niit = NIIT_RATE * max(0.0, min(nii, magi - NIIT_THRESHOLD[p.filing_status]))
    return fed + niit + p.state_rate * max(0.0, magi)


@dataclass
class TaxInputs:
    operating: list[float]           # per year: rental income less deductible cash costs and interest
    capital_added: list[float]       # per year: capitalized spending, depreciated from the next year
    loan_costs: list[float]          # per year: amortized points/fees, incl. write-offs at refi/sale
    building_basis: float            # depreciable at purchase (incl. rehab and repairs at closing)
    land_basis: float
    sale_price: float
    selling_costs: float
    rental_share: list[float] | None = None   # per year; < 1 while you live in part of it


@dataclass
class TaxResult:
    taxable: list[float] = field(default_factory=list)     # Schedule E net income, per year
    tax: list[float] = field(default_factory=list)         # incremental tax; negative = savings
    suspended: list[float] = field(default_factory=list)   # passive-loss carryforward, year end
    adjusted_basis: float = 0.0
    gain: float = 0.0
    recapture: float = 0.0
    capital_gain: float = 0.0
    released: float = 0.0
    sale_tax: float = 0.0
    deferred_tax: float = 0.0


def compute(ti: TaxInputs, p: TaxProfile, inflation: float, start_index: float) -> TaxResult:
    n = len(ti.operating)
    growth = inflation if p.income_growth is None else p.income_growth
    cost_seg = ti.building_basis * p.cost_seg_pct
    bonus = cost_seg * p.bonus_depreciation_pct
    sl_basis = ti.building_basis - cost_seg
    taken_bldg = taken_added = taken_cs = 0.0
    added: list[float] = []
    susp = 0.0
    out = TaxResult()

    for t in range(1, n + 1):
        index = start_index * (1 + inflation) ** (t - 1)
        income = p.household_income * (1 + growth) ** (t - 1)
        dep_bldg = min(sl_basis / RESIDENTIAL_LIFE, sl_basis - taken_bldg)
        dep_added = sum(a / RESIDENTIAL_LIFE for a in added)   # ponytail: additions held < 27.5 yrs
        dep_sl = dep_bldg + dep_added
        dep_cs = (bonus if t == 1 else 0.0) + ((cost_seg - bonus) / COST_SEG_LIFE if t <= COST_SEG_LIFE else 0.0)
        if ti.rental_share is not None:   # ponytail: personal-use years forgo that share's depreciation
            dep_bldg, dep_added, dep_cs = (x * ti.rental_share[t - 1] for x in (dep_bldg, dep_added, dep_cs))
            dep_sl = dep_bldg + dep_added
        taken_bldg += dep_bldg
        taken_added += dep_added
        taken_cs += dep_cs
        added.append(ti.capital_added[t - 1])
        net = ti.operating[t - 1] - dep_sl - dep_cs - ti.loan_costs[t - 1]
        base_tax = _household_tax(p, income, 0, 0, 0, 0, index)
        susp_before = susp

        if p.real_estate_professional:   # non-passive: losses offset W-2 income, no NIIT
            allowed, nii = net, 0.0
        elif net >= 0:                   # passive income first absorbs carried-forward losses
            use = min(susp, net)
            susp -= use
            allowed = nii = net - use
        else:
            cap = passive_allowance(income) if p.active_participation else 0.0
            allowed = -min(-net, cap)
            susp += -net + allowed
            nii = 0.0
        tax_ops = _household_tax(p, income, allowed, 0, 0, nii, index) - base_tax
        out.taxable.append(net)
        out.tax.append(tax_ops)
        out.suspended.append(susp)

        if t < n:
            continue
        # Sale in the final year. A fully taxable sale frees every suspended loss (§469(g)).
        taken_sl = taken_bldg + taken_added
        out.adjusted_basis = ti.land_basis + ti.building_basis + sum(added) - taken_sl - taken_cs
        gain = ti.sale_price - ti.selling_costs - out.adjusted_basis
        released = 0.0 if p.real_estate_professional else susp_before
        all_in = net - released if not p.real_estate_professional else net
        if gain >= 0:
            rec_1245 = min(gain, taken_cs)
            u1250 = min(gain - rec_1245, taken_sl)
            ltcg = gain - rec_1245 - u1250
            ordinary = all_in + rec_1245
        else:   # §1231 loss is ordinary
            rec_1245 = u1250 = ltcg = 0.0
            ordinary = all_in + gain
        nii = 0.0 if p.real_estate_professional else ordinary + u1250 + ltcg
        sale_tax = _household_tax(p, income, ordinary, u1250, ltcg, nii, index) - base_tax - tax_ops
        out.gain, out.recapture, out.capital_gain = gain, rec_1245 + u1250, ltcg
        if p.exchange_1031:   # gain and suspended losses roll into the replacement property
            out.deferred_tax = max(0.0, sale_tax)
        else:
            out.sale_tax, out.released = sale_tax, released
            out.suspended[-1] = 0.0
    return out
