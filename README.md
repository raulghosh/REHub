# RealEstateEvaluator

A buy-side **screening and underwriting pipeline for single-family and townhouse acquisitions.**

The job of this system is not to compute a cap rate. It is **triage at scale**: ingest
hundreds of listings a week, kill 90%+ in seconds on hard gates, and surface the survivors
with their numbers already stress-tested — as a ranked queue plus a one-page memo per deal.

> Status: **scaffold**. Architecture and data contracts are defined; the math modules are
> stubbed (`NotImplementedError`) and built out per [ROADMAP.md](ROADMAP.md).

---

## Why a funnel, not a spreadsheet

Most "real estate evaluators" build a beautiful single-property DCF and have no funnel. That
is backwards. The alpha is in the funnel — the ability to look at 500 listings and confidently
ignore 470 of them, then underwrite the remaining 30 properly. This pipeline is organized
around that flow:

```
  listings ──▶ normalize/dedup ──▶ enrich ──▶ rent triangulation ──▶ underwrite
                                                                          │
                              ranked scorecard ◀── risk/sensitivity ◀──── gates
```

## The opinions baked into the model

These are the places junior underwriting gets it wrong. The engine is designed to make the
right behavior the default.

| Topic | The amateur mistake | What this model does |
|---|---|---|
| **Rent** | Trust one "Rent Zestimate" | Triangulate 3 signals (comps, submarket $/sqft, haircut model); **flag divergence >10% as a signal, not noise** |
| **CapEx** | Flat % of rent | Component **replacement clocks** (roof/HVAC/water heater have ages); model as a sinking-fund reserve ($/yr) |
| **Vacancy** | One blended number | Separate **physical vacancy** (submarket) from **credit loss** (tenant quality) |
| **Exit** | Exit cap = entry cap | Exit cap defaults to entry **+50–100 bps** and is a required sensitivity axis |
| **Taxes** | Use seller's tax bill | Model **post-sale reassessment** (millage reset on new basis) |
| **Returns** | Cap rate only | Levered IRR, equity multiple, DSCR, cash-on-cash, **yield-on-cost vs. exit cap spread**, break-even occupancy |

## The gates (SFR/townhouse)

A deal must clear all hard gates to enter the human-review queue. Defaults are configurable
in `config/assumptions.yaml`.

- **Rent-to-price** ≥ 0.8% / month (1% rule as a *filter*, not a verdict)
- **Price-per-sqft vs. replacement cost** — flag if buying above rebuild cost
- **Going-in cash-on-cash** ≥ target (default 6%)
- **DSCR** ≥ 1.25x at stressed rate
- **Yield-on-cost − exit cap** ≥ 150 bps (the development/value-add spread)
- **5-yr levered IRR** ≥ hurdle (default 15%)

Soft factors (school zone, flood zone, DOM/price-cut history, submarket concentration) adjust
the score but don't auto-kill.

## Output

1. **Ranked queue** — every screened property, green/yellow/red on each gate, sorted by a
   blended score with the two reasons it passed or died.
2. **One-page memo** per green/yellow deal — assumptions, returns, sensitivity tornado,
   the bear case.

---

## Project layout

```
src/sfr_evaluator/
├── schemas.py          # data contracts: Property, Assumptions, UnderwritingResult
├── ingest/
│   ├── sources.py      # listing source adapters (MLS/Zillow/Redfin/wholesaler)
│   ├── normalize.py    # address normalization + cross-source dedup
│   └── enrich.py       # geocode, FEMA flood, school zone, tax history
├── rents/
│   └── triangulate.py  # 3-signal rent estimate + divergence flag
├── underwrite/
│   ├── model.py        # the engine: pro forma → cash flows
│   ├── capex.py        # component replacement clocks / reserve sizing
│   ├── debt.py         # debt sizing, amortization, DSCR
│   └── taxes.py        # post-sale reassessment
├── metrics/
│   └── gates.py        # IRR / CoC / yield-on-cost / gate evaluation
├── risk/
│   └── sensitivity.py  # tornado + Monte Carlo on rent growth & exit cap
└── score/
    └── scorecard.py    # ranked queue + one-page memo
```

## Quickstart (once built)

```bash
pip install -e ".[dev]"
sfr-eval screen  --input listings.csv --assumptions config/assumptions.yaml --out queue.csv
sfr-eval memo    --property-id <id>   --assumptions config/assumptions.yaml
pytest
```

See [ROADMAP.md](ROADMAP.md) for the phased build plan.
