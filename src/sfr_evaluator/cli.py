"""Command line.

    sfr-eval serve                                     web app on http://127.0.0.1:8000
    sfr-eval evaluate config/sample_deal.yaml          one deal, plain-text summary (--json for all)
    sfr-eval screen --input listings.csv --out ranked.csv [--profile config/investor_profile.yaml]
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

import yaml
from pydantic import ValidationError

from .analysis import evaluate
from .ingest.normalize import dedup
from .ingest.sources import from_csv
from .metrics.returns import metrics, offer
from .schemas import DealInput, Result
from .underwrite.model import project, resolve

VERDICT_ORDER = {"buy": 0, "negotiate": 1, "pass": 2}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sfr-eval", description="Rental deal evaluator for individual investors.")
    sub = p.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="Run the web app.")
    serve.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"),
                       help="0.0.0.0 to accept outside connections (env HOST).")
    serve.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")),
                       help="Env PORT, as hosting platforms set it.")

    ev = sub.add_parser("evaluate", help="Evaluate one deal from a YAML or JSON file.")
    ev.add_argument("deal")
    ev.add_argument("--json", action="store_true", help="Print the full result as JSON.")

    screen = sub.add_parser("screen", help="Rank a CSV of listings by margin of safety.")
    screen.add_argument("--input", required=True, help="Listings CSV (needs rent and price columns).")
    screen.add_argument("--out", required=True, help="Ranked output CSV.")
    screen.add_argument("--profile", help="Investor profile YAML: financing, management, taxes, targets.")
    screen.add_argument("--column-map", help="JSON mapping our column names to yours.")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "serve":
            from .web.server import serve
            serve(args.host, args.port)
            return 0
        if args.command == "evaluate":
            return cmd_evaluate(args)
        return cmd_screen(args)
    except (OSError, ValueError, ValidationError, yaml.YAMLError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


def _load(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}   # YAML is a superset of JSON


def cmd_evaluate(args) -> int:
    result = evaluate(DealInput.model_validate(_load(args.deal)))
    print(result.model_dump_json(indent=2) if args.json else summary(result))
    return 0


def summary(r: Result) -> str:
    o, m, a = r.offer, r.metrics, r.acquisition

    def pct(v):
        return "n/a" if v is None else f"{v:.1%}"

    max_offer = "none" if o.max_offer is None else f"${o.max_offer:,.0f}"
    inv = "none" if o.investment_value is None else f"${o.investment_value:,.0f}"
    dscr = "n/a" if m.dscr is None else f"{m.dscr:.2f}x"
    lines = [
        f"{o.verdict.upper()}: {o.summary}",
        (f"Max offer {max_offer} | highest price meeting targets {inv} (limited by {o.limited_by}) "
         f"| value ${o.market_value:,.0f}"),
        (f"Normal year: cash flow ${m.monthly_cash_flow:,.0f}/mo, cash-on-cash {pct(m.cash_on_cash)}, "
         f"cap rate {pct(m.cap_rate)}, DSCR {dscr}"),
        (f"IRR {pct(m.irr_before_tax)} before tax, {pct(m.irr_after_tax)} after | "
         f"cash to close ${a.total_cash_needed:,.0f}"),
        " | ".join(f"{s.name}: ${s.monthly_cash_flow:,.0f}/mo" for s in r.management),
        (f"Loan: {r.financing.loan_type} at {r.financing.rate:.2%} (market {r.financing.base_rate:.2%} "
         f"as of {r.financing.base_as_of})" if r.financing.loan_type != "all cash" else "Loan: all cash"),
    ]
    best = max((e for e in r.exit_timeline if e.irr_if_sold is not None), key=lambda e: e.irr_if_sold, default=None)
    last = r.exit_timeline[-1]
    lines.append(f"Sell in year {r.sale.year}: ${r.returns.total:,.0f} after tax"
                 + (f" | best IRR if sold in year {best.year}" if best else "")
                 + f" | keep to year {last.year}: ${last.wealth_if_kept:,.0f} wealth")
    if r.warnings:
        lines += ["Watch out:"] + [f"  - {w}" for w in r.warnings]
    return "\n".join(lines)


def cmd_screen(args) -> int:
    profile = _load(args.profile) if args.profile else {}
    mapping = json.loads(Path(args.column_map).read_text()) if args.column_map else None
    deals, bad = [], 0
    for line, item in from_csv(Path(args.input), profile, mapping):
        if isinstance(item, str):
            bad += 1
            print(f"skipped line {line}: {item}", file=sys.stderr)
        else:
            deals.append(item)
    rows = []
    for d in dedup(deals):
        r = resolve(d)
        m = metrics(r, project(d, r, d.purchase.price))   # no stress tests: fast enough for hundreds
        o = offer(d, r, m)
        rows.append({
            "address": d.property.address, "zip": d.property.zip_code, "price": round(d.purchase.price),
            "verdict": o.verdict,
            "max_offer": "" if o.max_offer is None else round(o.max_offer),
            "margin_at_price": "" if o.margin_at_price is None else round(o.margin_at_price, 3),
            "monthly_cash_flow": round(m.monthly_cash_flow),
            "cash_on_cash": "" if m.cash_on_cash is None else round(m.cash_on_cash, 4),
            "cap_rate": round(m.cap_rate, 4),
            "irr_after_tax": "" if m.irr_after_tax is None else round(m.irr_after_tax, 4),
            "limited_by": o.limited_by, "summary": o.summary,
        })
    rows.sort(key=lambda x: (VERDICT_ORDER[x["verdict"]],
                             -(x["margin_at_price"] if x["margin_at_price"] != "" else -9)))
    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["rank", *rows[0]] if rows else ["rank"])
        w.writeheader()
        for i, row in enumerate(rows, 1):
            w.writerow({"rank": i, **row})
    counts = {v: sum(r["verdict"] == v for r in rows) for v in VERDICT_ORDER}
    print(f"Ranked {len(rows)} listings ({counts['buy']} buy, {counts['negotiate']} negotiate, "
          f"{counts['pass']} pass; {bad} skipped) -> {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
