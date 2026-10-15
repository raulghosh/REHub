# Roadmap

## Done (v0.1)

The project pivoted from an institutional SFR screening funnel to a deal evaluator for
individual investors. The old engine's bugs went with it (the sale ignored the loan payoff,
cash flows never grew, overdue components reserved 10x their cost, yield-on-cost was
divided by equity, and rent was backed out of the price it was then judged against).

- Property types: single-family, townhouse, condo, 2-4 and 5+ units; fixer-upper with
  rehab, holding costs, ARV, reassessment and BRRRR refinance.
- Age-based upkeep curve on rebuild cost; known inspection items on top.
- Per-line growth indexes; zip-adjusted long-run appreciation.
- Investor-specific taxes: 2026 brackets, passive-loss rules, REPS, cost segregation,
  recapture, NIIT, state, 1031.
- Margin-of-safety max offer solved from the investor's targets; estimate allowance on
  every estimated line; self-managed vs. PM comparison; stress tests.
- Itemized closing, lender, inspection and repair costs; lender reserves.
- Bundled zip-code market data (Redfin, Realtor.com), refresh script with optional Census ACS.
- Web front end (`sfr-eval serve`), CLI (`evaluate`, `screen`), JSON API, tests.

## Next

- Run the data build with Census access to bundle rent-by-bedroom, tax-rate and vacancy
  defaults.
- State property-tax assessment caps (CA 2%, OR 3%, FL non-homestead 10%, ...) as defaults.
- House hacking: owner-occupy one unit of a 2-4 (FHA/conventional terms, partial rental tax
  treatment).
- Regional rebuild-cost factors so upkeep and insurance defaults track local labor costs.
- Save and compare multiple deals side by side; export a one-page PDF memo.
