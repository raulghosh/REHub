# Build Progress

## Completed ✅

### Phase 0 — Scaffold ✅
- Package structure with data contracts (`schemas.py`)
- CLI entry points (stub → functional)
- All modules stubbed with phase-specific markers

### Phase 1 — Underwriting Engine ✅
**Exit Criterion Met: Golden-deal test validates engine to within 100 bps (levered IRR)**

- ✅ Schema fixes: added `flooring_life/cost`, `electrical_life/cost`, `plumbing_life/cost`; made `exit_cap_rate` Optional
- ✅ `underwrite/capex.py` — sinking-fund reserve (component clocks, mid-life assumption for unknown ages)
- ✅ `underwrite/taxes.py` — post-sale reassessment on new basis
- ✅ `underwrite/debt.py` — LTV & DSCR-constrained sizing, amortization, stressed DSCR
- ✅ `underwrite/model.py` — pro forma → cash flows → reversion, levered IRR via bisection
- ✅ `metrics/gates.py` — all 5 gates (rent-to-price, CoC, DSCR, YoC-exit spread, IRR)
- ✅ Golden deal fixture + golden-file test suite (4 tests, all passing)

### Phase 2 — Rent Triangulation ✅
**Exit Criterion Met: Three signals → point estimate + band, with divergence flag**

- ✅ `rents/triangulate.py` — blend comps, psf, haircut into point + band
- ✅ Divergence flag when signals spread > 10%
- ✅ Helper functions: `from_comps()`, `from_submarket_psf()`, `from_asking_with_haircut()`
- ✅ Full test suite (7 tests, all passing)

### Phase 3 — Ingestion & Enrichment ✅
**Exit Criterion Met: CSV → deduped records**

- ✅ `ingest/sources.py` — CSV adapter with flexible column mapping
- ✅ `ingest/normalize.py` — USPS-style address canonicalization, cross-source dedup
- ✅ `ingest/enrich.py` — stub with API placeholders (geocode, flood, school, tax)
- ✅ Full test suite (5 tests, all passing)

### Phase 4 — Risk, Ranking & CLI Wiring ✅
**Exit Criterion Met: `sfr-eval screen` emits ranked queue from real listing file**

- ✅ `risk/sensitivity.py` — tornado analysis (±10% variation on key inputs)
- ✅ `score/scorecard.py` — blended scoring, ranked queue, one-page memo template
- ✅ `cli.py` — fully wired `screen` command end-to-end
  - Loads CSV, deduplicates, enriches, underwrite, gates, ranks, outputs CSV
  - Benchmarked: 5 properties screened in <1s
- ✅ Integration tests (2 tests, all passing)

### Overall Test Suite ✅
- **21 tests passing** across all phases
- Golden-deal validation (Phase 1 engine correctness)
- Rent triangulation (Phase 2)
- CSV import, normalization, dedup (Phase 3)
- CLI end-to-end (Phase 4)

---

## Phase 5 — Memo & Polish (In Progress)

### Not Yet Implemented
- [ ] Full one-page memo generation (template exists; needs formatting)
- [ ] `sfr-eval memo` command wire-up (stub added; needs data layer)
- [ ] Calibration pass on real market dump
- [ ] CLI UX polish (help text, config validation, error messages)
- [ ] Expanded test coverage (edge cases: zero HOA, unknown component ages, tight DSCR)

---

## Known Limitations

### Data APIs (Deferred to Phase 3+)
- **Geocoding**: stubs in place; Census.gov API not yet called
- **Flood zones**: FEMA NFHL API stubs; not yet live
- **School zones**: GreatSchools API out of scope (paywalled)
- **Tax history**: CSV field only; county-specific scrapers not implemented

### IRR Solver
- Uses bisection (no scipy/numpy dependency); ~100 bps tolerance
- Tightens if numerical precision is needed

### Assumptions
- All assumptions live in `config/assumptions.yaml`; no hardcoded knobs
- Per-market config possible; not yet wired to multiple assumption sets

---

## File Structure (Final)

```
src/sfr_evaluator/
├── schemas.py              # Data contracts (Property, RentEstimate, etc.)
├── cli.py                  # Command line: screen, memo
├── ingest/
│   ├── sources.py         # CSV adapter with column mapping
│   ├── normalize.py       # Address canonicalization, dedup
│   └── enrich.py          # API stubs: geocode, flood, school
├── rents/
│   └── triangulate.py     # 3-signal rent blending
├── underwrite/
│   ├── model.py           # Full pro forma engine
│   ├── capex.py           # Component clocks + reserves
│   ├── debt.py            # Amortization, DSCR, sizing
│   └── taxes.py           # Reassessment, millage
├── metrics/
│   └── gates.py           # IRR, CoC, DSCR, yield-on-cost gates
├── risk/
│   └── sensitivity.py     # Tornado analysis
└── score/
    └── scorecard.py       # Scoring, ranking, memo template

tests/
├── test_smoke.py          # Schema validation
├── test_phase1_engine.py  # Underwriting engine (golden deal)
├── test_phase2_rents.py   # Rent triangulation
├── test_phase3_ingest.py  # CSV import, normalize, dedup
└── test_integration.py    # End-to-end CLI

config/
└── assumptions.yaml       # Market assumptions (tunable, no hardcodes)
```

---

## Next Steps (Phase 5+)

1. **Calibration**: Run screening on a real market's weekly dump; validate kill rate (~90%)
2. **Memo polish**: Full formatting, tornado charts, bear-case narrative
3. **Data APIs**: Wire Census geocoder, FEMA NFHL (optional in Phase 5, can be later)
4. **Config management**: Multi-market assumption sets, CLI override flags
5. **Performance**: Profile on large listing dumps (1000+ properties)

---

## How to Run

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Screen a listing file
sfr-eval screen \
  --input sample_listings.csv \
  --assumptions config/assumptions.yaml \
  --out queue.csv \
  --rent-mid 2200

# Output: ranked CSV with properties sorted by score
```

---

## Notes for Future Maintainers

- **Money math**: All dollar amounts stay as Decimal until IRR solver (bisection converts to float briefly)
- **Rent**: Never a point estimate; always a (low, point, high) band with signal sources
- **Gates**: Hard filters that kill deals; soft factors (flood, school, concentration) deferred to future scoring
- **Data sources**: Each enrichment names its source and fallback; nothing silently defaults
- **Tests**: Golden-deal test validates engine correctness; suite covers all major paths; CI runs all on push
