# Roadmap

## Done (v0.1)

The project pivoted from an institutional SFR screening funnel to a deal evaluator for
individual investors. The funnel stays in this repo's history
and returns as the REHub screener module. The old engine's bugs went with it (the sale ignored the loan payoff,
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

## Done (v0.2)

- Mortgage rate priced from the weekly market rate, credit score, LTV and occupancy;
  conventional, DSCR, commercial (balloon) and FHA loans; PMI and FHA MIP.
- Down-payment comparison from 3.5% to 30% with program limits; house hacking.
- Sell-or-keep table for every year until the loan is paid off.
- Roof sized by footprint, pitch and material; known-age component schedule.
- Regulatory checklist; HOA dues history, reserves and special assessments; flood insurance.

## Done (v0.3)

- Hostable: one Docker container, `PORT`/`HOST` from the environment, security headers, no
  server-side state.
- Ask Claude: chat with the user's own Anthropic key; Claude runs the model as a tool for
  what-ifs and fills in the form from a pasted listing.

## Next

- Run the data build with Census access to bundle rent-by-bedroom, tax-rate and vacancy
  defaults; refresh the mortgage-rate snapshot.
- Zip-level homeowners premiums and their 2018-2022 trend (Treasury FIO data, mirrored by the
  Consumer Federation of America) as the insurance default; NFIP flood premiums by zip.
- Verify the LLPA grid against the current Fannie Mae matrix PDF.
- State property-tax assessment caps (CA 2%, OR 3%, FL non-homestead 10%, ...) as defaults.
- Section 121 exclusion when a house hack is sold within 3 years of moving out.
- Regional rebuild-cost factors so upkeep and insurance defaults track local labor costs.
- Save and compare multiple deals side by side; export a one-page PDF memo.
- Stream the assistant's answer as it's written; let it compare saved deals.
