# Build Roadmap

Phased so each phase is independently useful. Earlier phases are higher-leverage: a working
funnel front-end with a rough engine beats a perfect engine with no funnel.

## Phase 0 — Scaffold ✅ COMPLETE
- ✅ Package structure, data contracts (`schemas.py`), CLI entry points, stubbed modules.
- ✅ Architecture reviewable; all data contracts defined.

## Phase 1 — Underwriting engine (the core) ✅ COMPLETE
Make a single property produce trustworthy numbers.

- ✅ Schema fixes: added `flooring_life/cost`, `electrical_life/cost`, `plumbing_life/cost`; `exit_cap_rate` Optional.
- ✅ `underwrite/capex.py` — sinking-fund reserve with mid-life assumption for unknown ages.
- ✅ `underwrite/taxes.py` — post-sale reassessment.
- ✅ `underwrite/debt.py` — LTV/DSCR-constrained sizing, amortization, stressed DSCR.
- ✅ `underwrite/model.py` — full pro forma, reversion, levered IRR via bisection.
- ✅ `metrics/gates.py` — all 5 gates (rent-to-price, CoC, DSCR, YoC-exit spread, IRR).
- ✅ Golden deal fixture + golden-file test suite.
- **Exit criterion met:** golden test passes, IRR within 100 bps of expected.

## Phase 2 — Rent triangulation ✅ COMPLETE
Stop trusting a single rent number.

- ✅ `rents/triangulate.py` — blend comps, psf, haircut into point + band.
- ✅ Divergence flag when signals spread > 10%.
- ✅ Helper functions: `from_comps()`, `from_submarket_psf()`, `from_asking_with_haircut()`.
- **Exit criterion met:** rent band flows into engine; divergence flag works.

## Phase 3 — Ingestion & enrichment (the funnel front-end) ✅ COMPLETE
Turn raw listings into clean, enriched property records.

- ✅ `ingest/sources.py` — CSV adapter with flexible column mapping.
- ✅ `ingest/normalize.py` — USPS-style address canonicalization, cross-source dedup.
- ✅ `ingest/enrich.py` — API stubs (geocode, flood, school, tax); graceful degradation.
- **Exit criterion met:** CSV → deduped records; missing enrichment fields degrade to None.

## Phase 4 — Risk, ranking & CLI wiring ✅ COMPLETE
- ✅ `risk/sensitivity.py` — tornado analysis (±10% variation on key inputs).
- ✅ `score/scorecard.py` — blended scoring, ranked queue, memo template.
- ✅ `cli.py` — fully wired `sfr-eval screen`: CSV → dedup → enrich → underwrite → gates → ranked CSV.
- **Exit criterion met:** `sfr-eval screen` produces ranked queue from real listing file in <1s.

## Phase 5 — Memo & Polish (In Progress)
- [ ] Full one-page memo generation (template exists; needs formatting & tornado charts).
- [ ] Wire `sfr-eval memo` command (stub added; needs data layer).
- [ ] CLI UX polish; expand test coverage (edge cases).
- [ ] **Calibration pass:** run on real market dump; validate ~90% kill rate.

## Engineering guardrails
- **Money math:** `Decimal` or integer cents in the engine — never float for dollars.
  Float is permitted *only* inside the IRR root-finder; convert at the boundary.
- **No magic numbers:** every assumption lives in `Assumptions` / `config/assumptions.yaml`.
- **Determinism:** golden-file tests on the engine from Phase 1 onward; any future stochastic
  code is seeded.
- **Validation:** Pydantic on every external input; fail loud on bad data, never silently default.
- **Each module pure-ish:** ingest/enrich do I/O; underwrite/metrics/risk are pure functions
  over the data contracts so they're trivially testable.
- **Data-source honesty:** every enrichment/signal names its source and its fallback before
  it's coded; nothing blocks the funnel on a paywalled API.
