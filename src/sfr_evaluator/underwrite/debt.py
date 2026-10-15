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
    month: int        # 1-based month of the hold in which it closes
    amount: float
    rate: float
    term_years: int
    cost_pct: float


@dataclass
class DebtYear:
    interest: float = 0.0
    principal: float = 0.0
    pmi: float = 0.0
    balance: float = 0.0          # end of year
    refi_cash_out: float = 0.0    # new loan - payoff - costs (negative = cash in)
    refi_costs: float = 0.0


def schedule(amount: float, rate: float, term_years: int, years: int,
             pmi_rate: float = 0.0, pmi_stop_balance: float = 0.0,
             refi: Refi | None = None) -> list[DebtYear]:
    """Monthly amortization rolled up by year. PMI is charged while the balance is above
    `pmi_stop_balance` (78% of original value)."""
    out = [DebtYear() for _ in range(years)]
    bal, r = amount, rate / 12
    pmt, left = monthly_payment(amount, rate, term_years), term_years * 12
    pmi_monthly = pmi_rate * amount / 12
    for m in range(1, years * 12 + 1):
        y = out[(m - 1) // 12]
        if refi is not None and m == refi.month:
            costs = refi.cost_pct * refi.amount
            y.refi_cash_out += refi.amount - bal - costs
            y.refi_costs += costs
            bal, r = refi.amount, refi.rate / 12
            pmt, left = monthly_payment(refi.amount, refi.rate, refi.term_years), refi.term_years * 12
            pmi_monthly = 0.0   # ponytail: refi assumed at <= 80% LTV
        if bal > 0.005 and left > 0:
            if bal > pmi_stop_balance:
                y.pmi += pmi_monthly
            interest = bal * r
            princ = min(pmt - interest, bal)
            bal -= princ
            left -= 1
            y.interest += interest
            y.principal += princ
        y.balance = bal
    return out
