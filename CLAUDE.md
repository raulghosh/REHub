# REHub

REHub is a hub of real-estate tools for **individual investors** (not institutions). Each module
does one job. The first module is the **deal evaluator** in this repo: enter a rental property
and get a buy / negotiate / pass verdict and the most to offer, with a margin of safety. The
Python package is still named `sfr_evaluator`; renaming it to `rehub` with shared `core/` and
`modules/` folders is planned, so ask before starting that restructure.

## Commands

```bash
pip install -e ".[dev]"
pytest                              # must pass before every push
ruff check src tests scripts        # must be clean
sfr-eval serve                      # web app on http://127.0.0.1:8000 (PORT / HOST env vars)
sfr-eval evaluate config/sample_deal.yaml
```

Deployed on Render from `main` with the `Dockerfile`; there is no server-side state.

## Where things are

- `src/sfr_evaluator/schemas.py`: `DealInput` (what users enter) and `Result` (what they get back).
- `analysis.py`: `evaluate(deal)` is the single entry point; it also writes the plain-language warnings.
- `underwrite/`: `model.py` (`resolve` derives every assumption once; `project` runs the
  year-by-year pro forma at a price), `capex.py` (upkeep by age, components), `rates.py`
  (loan pricing), `taxes.py`, `compliance.py` (regulatory checklist), `inspection.py`
  (inspection risk), `debt.py`.
- `metrics/returns.py`: IRR, the max-offer solver, the profit breakdown, sell or keep, down-payment table.
- `market.py` + `data/`: zip-code market data (Redfin and Realtor.com research files) and the rate snapshot.
- `web/server.py`: stdlib HTTP server (`/`, `/guide`, `/api/defaults`, `/api/evaluate`, `/api/chat`).
- `web/index.html`: the whole front end in one file (vanilla JS, no build step, no CDN).
  `web/guide.html`: the investor guide. `web/assistant.py`: Ask Claude.

## Rules for the model

- Every derived default records where it came from (`note(...)` in `resolve`); it shows in the
  assumptions table. No unexplained numbers.
- Estimated costs carry the estimate allowance; costs the user marks as quotes don't.
- Each cost line grows with its own index (rent, insurance, construction, CPI); never one blanket inflation rate.
- The profit breakdown must keep summing to the after-tax cash flows (there is a test for it).
  A new purchase-time cost has to be added to `Acquisition`, the cash needed, the basis and the breakdown.
- Typical figures (costs, probabilities, rules of thumb) are labeled as typical, not presented as data.
- The golden-deal tests in `tests/test_engine.py` are hand-computed; switch new features off
  there rather than changing the expected numbers.

## Rules for the page

- Users are often new to investing: plain words, and every new measure or input term gets a
  tooltip (`TERMS` in `index.html`) **and** a section in `guide.html` with the same id.
- Color means something: green or red only against a user's target, amber for warnings, blue for "start here".
- The verdict stays on top; results live in the five question tabs; optional inputs stay collapsed
  as assumption rows whose summary (`SUMS` in `index.html`) shows the current setting. Each tab
  leads with tiles or a chart; long tables fold behind a one-line summary (`fold()`, `more()`).
- Anything from outside (URL hash, pasted text, uploads, listing imports) is untrusted:
  range-check numbers, set text with `textContent` / `h()`, never `innerHTML`; links only if `https:`.
- Before pushing a UI change, load the page in a headless browser (Playwright with the
  preinstalled Chromium) at desktop and phone widths, light and dark, and check for console
  errors and sideways scrolling.

## Data and AI

- No scraping of Zillow, Redfin or Realtor.com from the server. Use user-provided content
  (paste, upload, the bookmarklet, which runs in the user's browser), licensed APIs, or public data.
- The AI model is Claude through the official `anthropic` SDK; the model list is `MODELS` in
  `web/assistant.py`. Two ways to pay: the site's own access (Workload Identity Federation on
  Cloud Run, so no key is stored, or whatever the host provides), capped per visitor and by a
  daily budget; or a visitor's own key, sent per request and never stored or logged, which
  always wins. Never commit a key; federation IDs are not secrets.

## Workflow

- The owner merges pull requests quickly. Before new work, `git fetch origin main` and start from
  it; if the branch's pull request is already merged, restart the branch from `main` and open a new one.
- Commit messages say what changed and why; README and ROADMAP stay in step with features.
