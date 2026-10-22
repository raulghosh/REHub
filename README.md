# RealEstateEvaluator

A rental-property deal evaluator for **individual investors** (not institutions):
single-family homes, townhouses, condos, 2-4 unit and 5+ unit buildings, and fixer-uppers.
Enter a deal in the web page; get a **buy / negotiate / pass** verdict, the **maximum price
you should offer** with a margin of safety, and the numbers behind it.

```bash
pip install -e .
sfr-eval serve                # open http://127.0.0.1:8000
```

The page recalculates as you type and remembers your last deal in the browser. The verdict
stays on top; everything else sits in five tabs (Should I buy it? · What will I earn? · How do I
pay for it? · What could go wrong? · Every number), and the inputs start with the basics, with
the optional fine-tuning collapsed below. New to the
terms? Every measure has an ⓘ tooltip (definition, formula, rule of thumb), and the
**Investor guide** (`/guide`) walks one example deal through every number. **Ask Claude**
opens a chat that runs the model for you, using your own Anthropic API key. The same model runs
from the command line (`sfr-eval evaluate`, `sfr-eval screen`) and over a small JSON API, and the
whole app deploys as one Docker container (see [Deploy](#deploy-it-for-other-people)).

This is the first module of **REHub**, a hub of real-estate tools. The earlier institutional
screening funnel (triage hundreds of listings into a ranked queue) is in this repo's history
(commit 936590a) and returns as a REHub screener module.

## What it models that most calculators skip

| Detail | How the model handles it |
|---|---|
| **Maintenance by age** | Upkeep (repairs + capex reserve) is a % of the home's *rebuild cost*, derived from its effective age: ~0.4%/yr new, 1.3% at 25 years, 1.8% past 75. It rises every year of the hold. Condos (HOA covers the shell) and multifamily (more kitchens and baths per sqft) get their own factors, and a rehab makes the house "younger". Specific items from your inspection go on top. |
| **The right inflation index per line** | Rent grows with CPI rent (3%), insurance 5% (premiums outrun CPI), repairs with construction costs (3.5%), HOA 4%, utilities 3.5%, admin costs with CPI-U (2.5%), property tax with assessed value. Tax brackets index with CPI; the $25k passive-loss limit and NIIT thresholds don't. |
| **Your tax situation** | 2026 federal brackets, the household's tax computed with and without the property each year: depreciation (land split, optional cost segregation with 100% bonus), the $25k active-participation allowance and its $100k-150k phase-out, real estate professional status, suspended losses freed at sale, depreciation recapture, capital-gain stacking, NIIT, state tax, 1031 exchange. |
| **Margin of safety** | For each of your targets (cash-on-cash, cash flow per unit, DSCR, after-tax IRR) the model solves for the highest price that still meets it. The lowest is the investment value; your margin of safety discounts it; it never exceeds market value (or ARV minus rehab). |
| **Allowance on estimates** | Every estimated expense carries an allowance (default +10%). Tick "quote" on any line you have in writing and the allowance drops off. Rehab budgets carry their own contingency (default 15%). |
| **Self-managed vs. property manager** | PM: management fee, leasing and renewal fees, markup on vendor repairs. Self: no fees, DIY savings on repair labor, and optionally your time at an hourly rate. Every result shows both side by side. |
| **Zip-code value** | Market value = the zip's recent *sold* $/sqft for that property type x your sqft (Redfin, 12-month median). Appreciation = a 3.5% long-run baseline nudged by the zip's 10-year trend vs. the US (25% weight, +/-1.5 pts max). Last month's market is ignored on purpose. |
| **Closing and inspection costs** | Itemized: closing costs %, lender fees and points, inspections, other costs, seller credits, repairs needed at purchase, plus the reserves lenders expect you to hold. Property tax is reassessed at your price, not the seller's bill. |
| **Fixer-uppers** | Rehab budget + contingency, months without rent, holding costs, after-repair value, reassessment at ARV, optional cash-out refinance (BRRRR) and the 70% rule. |
| **Your mortgage rate** | Freddie Mac's weekly 30-year rate (refreshed live by the web app, bundled snapshot otherwise), adjusted for your credit score, down payment and occupancy with Fannie Mae's loan-level price adjustments (points converted at ~0.25% rate per point). PMI by credit score and LTV; FHA upfront and annual MIP; DSCR loans priced by their own coverage tier; commercial 5+ unit loans with a balloon refinance. A lender quote overrides all of it. |
| **Less than 20% down** | A down-payment table (3.5% to 30%) shows rate, mortgage insurance, cash to close, cash flow and returns for each, and which loan programs allow it (investment: 15% down for 1 unit, 25% for 2-4; owner-occupied: 3-5%; FHA: 3.5%). |
| **House hacking** | Live in one unit (or the whole house) for N months: that unit's rent is replaced by the rent you save, your share of costs and depreciation becomes personal for taxes, and owner-occupied loan terms open up. |
| **Sell or keep** | For every year until the loan is paid off: after-tax profit and IRR if you sell that year, versus your wealth if you keep it (equity plus cash collected, no sale). |
| **Roof and components** | Enter the ages you know from the inspection. The roof is sized from footprint, pitch and material ($/sqft and life by material); HVAC, water heater, appliances, flooring, paint, windows, electrical, plumbing and kitchen/bath get real replacement dates and costs, and drop out of the age curve so nothing is counted twice. Anything past its life is a cost at purchase. |
| **Inspection risk** | Before you inspect, each likely finding gets a probability by the home's age and era (foundation, sewer line, termites, water and mold, radon, knob-and-tube or recalled panels, galvanized or polybutylene pipes) and a typical cost. Who pays depends on the market: in a buyer's market the seller usually repairs or credits most of it; in a hot market (the zip's days on market) you pay most; as-is sales leave it all with you. Your expected share goes into cash at purchase and lowers the max offer. Tick "already inspected" and enter the real findings instead. |
| **Regulatory costs** | A checklist that switches on what usually applies: lead paint (pre-1978), rental licensing, smoke/CO detectors, permit-triggered code upgrades on rehabs, Florida condo inspections and reserves, California soft-story retrofits, large-building energy benchmarking. Typical costs; untick what doesn't apply. |
| **HOA dues** | Enter the HOA's dues history: its own growth rate is used and fades toward the long run (an HOA budget's insurance + upkeep mix). Reserve-study funding below 30% flags a likely special assessment; enter one and its year. |

## What you get back

- Verdict, max offer, investment value, and which target limits the price
- Normal-year pro forma (monthly and annual), cash-on-cash, cap rate, DSCR, break-even
  occupancy, rent-to-price, upkeep as % of rent and value
- 10-year (or your hold) projection with before- and after-tax cash flow, equity build-up,
  and the sale: gain, recapture, released losses, tax, proceeds
- Where the profit comes from: cash flow, loan paydown, appreciation, buying below value,
  transaction costs, taxes
- Stress tests: rent -10%, vacancy +5 pts, insurance +50%, no appreciation, rate +1 pt,
  rehab overrun
- Your loan: how the rate was built, mortgage insurance, program limits; the down-payment
  table; the sell-or-keep table to loan payoff; the component replacement schedule
- Every derived assumption with its source, and plain-language warnings

## Ask Claude (bring your own key)

**Ask Claude** opens a chat beside the results. Paste an Anthropic API key (from
console.anthropic.com) and ask things like:

- "What's the most I can pay and still get 8% cash-on-cash?"
- "Should I sell in year 7 or keep it until the loan is paid off?"
- "What if I hire a property manager and put 10% down?"
- Or paste a listing, and Claude fills in the form.

Claude doesn't do the math: it runs this model as a tool and quotes its results. What-ifs leave
your form alone; it changes your inputs only when you ask, and every run it made is listed in the
chat. Pick Claude Opus 5.5 (default), Sonnet 5.5 or Haiku 5.5. Usage is billed to your key. On
Opus and Sonnet, a question Anthropic's safety filters wrongly decline is retried on a fallback
model automatically (`fallbacks: "default"`).

Your key goes with each question to the server, which uses it for that request only and never
stores or logs it. "Remember it" keeps it in your browser. The page's security policy only lets
it talk to its own server.

## Command line

```bash
sfr-eval evaluate config/sample_deal.yaml          # one deal (YAML or JSON); --json for everything
sfr-eval screen --input sample_listings.csv --out ranked.csv --profile config/investor_profile.yaml
```

`screen` ranks a CSV of listings (address, zip_code, year_built, sqft, beds, baths, units,
rent, price, ...) by margin of safety, merging duplicate listings. Financing, management,
your tax situation and targets come from `config/investor_profile.yaml`. Rent is required:
the model never backs rent out of the price.

API: `GET /api/defaults` returns a sample deal; `POST /api/evaluate` takes the `DealInput`
JSON from `schemas.py` and returns the full `Result` (422 with field errors if invalid);
`POST /api/chat` is the assistant (key in the `X-Anthropic-Key` header).

## Deploy it for other people

The server keeps no state. Each visitor's deals stay in their own browser, and the assistant
runs on each visitor's own key. There are no accounts or database to run.

```bash
docker build -t deal-evaluator .
docker run -p 8000:8000 deal-evaluator          # http://localhost:8000
```

Any host that runs a Dockerfile works:

- **Render:** New → Web Service → this repo. It finds the Dockerfile and sets `PORT`.
- **Railway** and **Google Cloud Run** work the same way.
- **Fly.io:** run `fly launch`.

Serve it over **HTTPS only**, because visitors' API keys pass through it. All of these hosts do
that by default. Without Docker: `pip install . && sfr-eval serve --host 0.0.0.0`, with the port
from `$PORT` (default 8000).

Anyone with the URL can run the evaluator. Each evaluation is a fraction of a second of CPU, and
the assistant only spends the visitor's own key. There is no built-in rate limit. If the link
will be public and busy, use your host's limits or put Cloudflare in front of it.

## Data

`src/sfr_evaluator/data/zip_market.csv.gz` covers ~20,000 zip codes, built by
`scripts/build_market_data.py` from:

- **Redfin Data Center** (Redfin, a national real estate brokerage): sold $/sqft by property
  type, sales volume, days on market, long-run $/sqft trend vs. the US.
- **Realtor.com economic research data**: city names, listing $/sqft.
- **US Census ACS 5-year** (optional): median rent by bedrooms, effective property-tax rate,
  rental vacancy. The bundled file was built where api.census.gov was unreachable, so these
  columns are empty. Run `python scripts/build_market_data.py` on a normal connection to add
  them; the model then uses them as defaults automatically.

`src/sfr_evaluator/data/rates.json` holds the weekly mortgage-rate snapshot (Freddie Mac PMMS,
7.28% on 2026-10-01); the build script and the running web app refresh it from FRED.

Long-run defaults come from public series: CPI rent of primary residence (~3.3%/yr since 1990),
FHFA house prices (~4.5%/yr since 1991, much of it on falling mortgage rates), NAIC homeowners
premiums, and NAHB construction costs (~$162/sqft, 2024).

## Limits worth knowing

- **Not tax advice.** The tax model is a careful approximation (one property gets the whole $25k
  allowance; straight-line depreciation without mid-month convention; capex depreciated over
  27.5 years). Check big decisions with a CPA.
- **Zip $/sqft is a coarse value.** It ignores condition, lot and layout. Enter an appraisal or
  your comps when you have them; for 5+ units, get a broker opinion of value (they trade on
  income).
- **Property tax and insurance defaults are national estimates.** The page flags them; enter
  your county rate and a landlord-policy quote.
- **Loan pricing is a model of the grid, not a quote.** The Fannie Mae adjustment grid is
  transcribed in `underwrite/rates.py` (check it against the current matrix); PMI, DSCR,
  FHA and commercial spreads are typical figures. Get a lender quote and enter it.
- **Component and compliance costs are typical 2026 ranges** (roofing from Angi/NerdWallet,
  HVAC from contractor guides, retrofit and reserve-law costs from city and industry
  sources). Local prices vary; enter quotes.
- **Rebuild cost defaults to a national $160/sqft.** Labor is cheaper in much of the Midwest
  and South and dearer on the coasts; adjust it under Income & expenses.

## Project layout

```
src/sfr_evaluator/
├── schemas.py            # DealInput (what you enter) and Result (what you get back)
├── analysis.py           # evaluate(deal): the one entry point
├── market.py             # zip-code value, appreciation default, Census refs when present
├── underwrite/
│   ├── model.py          # resolve defaults -> year-by-year pro forma -> sale -> cash flows
│   ├── capex.py          # age-based upkeep curve, roof and component catalog
│   ├── debt.py           # amortization, PMI / FHA MIP, cash-out and balloon refinances
│   ├── rates.py          # weekly market rate + credit score / LTV / occupancy pricing
│   ├── compliance.py     # regulatory checklist
│   └── taxes.py          # 2026 federal + state income tax, passive rules, recapture
├── metrics/returns.py    # IRR, metrics, profit breakdown, max offer, sell-or-keep, down payments
├── risk/sensitivity.py   # stress tests, self vs. PM comparison
├── ingest/               # listing CSV -> deals, address dedup (for `screen`)
├── web/                  # stdlib HTTP server, single-page front end, Claude assistant
└── data/                 # bundled zip-code market table
```

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check src tests scripts
```

The tests check the pro forma, the max-offer solver and the tax math against hand-computed
numbers, and that the profit breakdown always sums to the after-tax cash flows.
