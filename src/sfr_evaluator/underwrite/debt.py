"""Fixed-rate mortgage schedule with PMI and an optional mid-hold refinance (BRRRR)."""

from __future__ import annotations

from dataclasses import dataclass


def monthly_payment(principal: float, annual_rate: float, years: int) -> float:
    n = years * 12
    if principal <= 0:
        return 0.0
    if annual_rate == 0:
        return principal / n
    r = annual_rate / 12
    return principal * r / (1 - (1 + r) ** -n)


@dataclass
class Refi:
    month: int                # 1-based month of the hold in which it closes
    amount: float | None      # None: roll the remaining balance (rate-and-term, e.g. a balloon)
    rate: float
    term_years: int
    cost_pct: float


@dataclass
class DebtYear:
    interest: float = 0.0
    principal: float = 0.0
    pmi: float = 0.0              # PMI or FHA MIP
    balance: float = 0.0          # end of year
    refi_cash_out: float = 0.0    # new loan - payoff - costs (negative = cash in)
    refi_costs: float = 0.0


def schedule(amount: float, rate: float, term_years: int, years: int,
             mi_rate: float = 0.0, mi_stop_balance: float = 0.0, refis: tuple[Refi, ...] = (),
             mi_on_balance: bool = False, mi_months: int | None = None) -> list[DebtYear]:
    """Monthly amortization rolled up by year. Conventional PMI is a % of the original loan,
    charged while the balance is above `mi_stop_balance` (78% of original value); FHA MIP is
    a % of the current balance for `mi_months`. A refinance ends mortgage insurance."""
    out = [DebtYear() for _ in range(years)]
    by_month = {f.month: f for f in refis}
    bal, r = amount, rate / 12
    pmt, left = monthly_payment(amount, rate, term_years), term_years * 12
    for m in range(1, years * 12 + 1):
        y = out[(m - 1) // 12]
        f = by_month.get(m)
        if f is not None:
            new = bal if f.amount is None else f.amount
            costs = f.cost_pct * new
            y.refi_cash_out += new - bal - costs
            y.refi_costs += costs
            bal, r = new, f.rate / 12
            pmt, left = monthly_payment(new, f.rate, f.term_years), f.term_years * 12
            mi_rate = 0.0   # ponytail: refinances assumed at <= 80% LTV
        if bal > 0.005 and left > 0:
            if mi_on_balance:
                if mi_months is None or m <= mi_months:
                    y.pmi += mi_rate * bal / 12
            elif bal > mi_stop_balance:
                y.pmi += mi_rate * amount / 12
            interest = bal * r
            princ = min(pmt - interest, bal)
            bal -= princ
            left -= 1
            y.interest += interest
            y.principal += princ
        y.balance = bal
    return out
