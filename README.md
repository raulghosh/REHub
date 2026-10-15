# RealEstateEvaluator

A rental-property deal evaluator for **individual investors** (not institutions):
single-family homes, townhouses, condos, 2-4 unit and 5+ unit buildings, and fixer-uppers.
Enter a deal in the web page; get a **buy / negotiate / pass** verdict, the **maximum price
you should offer** with a margin of safety, and the numbers behind it.

```bash
pip install -e .
sfr-eval serve                # open http://127.0.0.1:8000
```

The page recalculates as you type and remembers your last deal in the browser. The same model
runs from the command line (`sfr-eval evaluate`, `sfr-eval screen`) and over a small JSON API.

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
- Every derived assumption with its source, and plain-language warnings

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
JSON from `schemas.py` and returns the full `Result` (422 with field errors if invalid).

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
│   ├── capex.py          # age-based upkeep curve
│   ├── debt.py           # amortization, PMI, cash-out refinance
│   └── taxes.py          # 2026 federal + state income tax, passive rules, recapture
├── metrics/returns.py    # IRR, metrics, profit breakdown, max-offer solver
├── risk/sensitivity.py   # stress tests, self vs. PM comparison
├── ingest/               # listing CSV -> deals, address dedup (for `screen`)
├── web/                  # stdlib HTTP server + single-page front end
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
