"""Stress tests and the self-managed vs. property-manager comparison.

Each scenario changes one thing a retail investor actually gets surprised by, and reports
what it does to the monthly cash flow, cash-on-cash and after-tax IRR.
"""

from __future__ import annotations

from dataclasses import replace

from ..metrics.returns import metrics
from ..schemas import DealInput, Scenario
from ..underwrite.model import Resolved, project


def _run(name: str, deal: DealInput, r: Resolved) -> Scenario:
    m = metrics(r, project(deal, r, deal.purchase.price))
    return Scenario(name=name, monthly_cash_flow=m.monthly_cash_flow, cash_on_cash=m.cash_on_cash,
                    irr_after_tax=m.irr_after_tax)


def stress(deal: DealInput, r: Resolved) -> list[Scenario]:
    if deal.loan.rate is not None:
        rate_case = (deal.model_copy(update={"loan": deal.loan.model_copy(update={"rate": deal.loan.rate + 0.01})}), r)
    else:
        rate_case = (deal, replace(r, base_rate=r.base_rate + 0.01))
    cases = [
        ("Base case", deal, r),
        ("Rent 10% lower", deal, replace(r, rent_monthly=r.rent_monthly * 0.9)),
        ("Vacancy +5 pts", deal, replace(r, vacancy=r.vacancy + 0.05)),
        ("Insurance +50%", deal, replace(r, insurance=r.insurance * 1.5)),
        ("No appreciation", deal, replace(r, appreciation=0.0)),
        ("Interest rate +1 pt", *rate_case),
    ]
    if deal.rehab:
        cases.append(("Rehab 25% over budget", deal, replace(r, rehab_total=r.rehab_total * 1.25)))
    return [_run(name, d, rr) for name, d, rr in cases]


def management_compare(deal: DealInput, r: Resolved) -> list[Scenario]:
    def as_mode(mode: str) -> DealInput:
        return deal.model_copy(update={"management": deal.management.model_copy(update={"mode": mode})})

    return [_run("Self-managed", as_mode("self"), r), _run("Property manager", as_mode("pm"), r)]
