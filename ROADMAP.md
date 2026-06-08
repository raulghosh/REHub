# Build Roadmap

Phased so each phase is independently useful. Earlier phases are higher-leverage: a working
funnel front-end with a rough engine beats a perfect engine with no funnel.

## Phase 0 — Scaffold ✅ (this commit)
- Package structure, data contracts (`schemas.py`), CLI entry points, stubbed modules.
- Goal: the architecture is reviewable before any math is written.

## Phase 1 — Underwriting engine (the core)
Make a single property produce trustworthy numbers.
- [ ] `underwrite/model.py` — pro forma → annual cash flows → reversion (sale).
- [ ] `underwrite/capex.py` — component clocks (roof/HVAC/WH/flooring) → sinking-fund reserve.
- [ ] `underwrite/debt.py` — sizing (LTV / DSCR-constrained), amortization, refi.
- [ ] `underwrite/taxes.py` — post-sale reassessment on new basis.
- [ ] `metrics/gates.py` — unlevered/levered IRR, equity multiple, CoC, yield-on-cost,
      break-even occupancy, gate pass/fail.
- **Exit criterion:** hand-checked against a known deal in Excel, IRR within 25 bps.

## Phase 2 — Rent triangulation
Stop trusting a single rent number.
- [ ] `rents/triangulate.py` — comps, submarket $/sqft, haircut model → point estimate + band.
- [ ] Divergence flag when the three signals disagree > threshold.
- **Exit criterion:** rent band, not point estimate, flows into the engine as a sensitivity input.

## Phase 3 — Ingestion & enrichment (the funnel front-end)
Turn raw listings into clean, enriched property records.
- [ ] `ingest/sources.py` — CSV adapter first; pluggable scrapers/APIs later.
- [ ] `ingest/normalize.py` — address normalization (USPS), cross-source dedup.
- [ ] `ingest/enrich.py` — geocode → census tract / school zone / FEMA flood / tax history /
      DOM & price-cut history.
- **Exit criterion:** one command ingests a multi-source listing dump into deduped records.

## Phase 4 — Risk & ranking
- [ ] `risk/sensitivity.py` — tornado (rent growth, exit cap, vacancy, rate); Monte Carlo on
      the two variables that dominate IRR (rent growth + exit cap).
- [ ] `score/scorecard.py` — blended score, ranked queue, two-reason annotation.
- **Exit criterion:** `sfr-eval screen` emits a ranked, color-coded queue from a listing file.

## Phase 5 — Memo & polish
- [ ] `score/scorecard.py` one-page memo (assumptions, returns, tornado, bear case).
- [ ] CLI UX, config validation, golden-file tests on the engine.

## Engineering guardrails
- **Money math:** `Decimal` or integer cents in the engine — never float for dollars.
- **No magic numbers:** every assumption lives in `Assumptions` / `config/assumptions.yaml`.
- **Determinism:** Monte Carlo seeded; golden-file tests on the engine.
- **Validation:** Pydantic on every external input; fail loud on bad data, never silently default.
- **Each module pure-ish:** ingest/enrich do I/O; underwrite/metrics/risk are pure functions
  over the data contracts so they're trivially testable.
