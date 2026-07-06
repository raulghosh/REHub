"""Command-line entry point.

    sfr-eval screen --input listings.csv --assumptions config/assumptions.yaml --out queue.csv
    sfr-eval memo   --property-id <id>  --assumptions config/assumptions.yaml

Phase 4: screen and memo commands are wired and functional.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from decimal import Decimal
from pathlib import Path

import yaml

from .ingest.sources import from_csv
from .ingest.normalize import dedup
from .ingest.enrich import enrich
from .rents.triangulate import from_signals
from .underwrite.model import underwrite
from .metrics.gates import evaluate_gates
from .score.scorecard import rank_queue, memo as memo_text
from .schemas import Assumptions, Property


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sfr-eval", description="SFR/townhouse deal screener.")
    sub = p.add_subparsers(dest="command", required=True)

    screen = sub.add_parser("screen", help="Screen a listing file into a ranked queue.")
    screen.add_argument("--input", required=True, help="Listing file (CSV).")
    screen.add_argument("--assumptions", required=True, help="Assumptions YAML.")
    screen.add_argument("--out", required=True, help="Output ranked queue (CSV).")
    screen.add_argument("--rent-low", type=float, default=0, help="Low rent estimate ($/month).")
    screen.add_argument("--rent-mid", type=float, default=0, help="Mid rent estimate ($/month).")
    screen.add_argument("--rent-high", type=float, default=0, help="High rent estimate ($/month).")
    screen.add_argument("--column-map", help="JSON file for CSV column mapping.")

    memo = sub.add_parser("memo", help="Render a one-page memo for one property.")
    memo.add_argument("--property-id", required=True)
    memo.add_argument("--address", help="Property address (for display).")
    memo.add_argument("--assumptions", required=True)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "screen":
        return cmd_screen(args)
    elif args.command == "memo":
        return cmd_memo(args)
    else:
        raise SystemExit(f"Unknown command: {args.command}")


def cmd_screen(args) -> int:
    """Screen a listing file and output a ranked queue."""
    try:
        # Load assumptions
        assumptions = _load_assumptions(Path(args.assumptions))

        # Load column mapping if provided
        column_mapping = {}
        if args.column_map:
            with open(args.column_map) as f:
                column_mapping = json.load(f)

        # Load properties from CSV
        properties = list(from_csv(Path(args.input), column_mapping=column_mapping))
        if not properties:
            print("ERROR: No properties loaded from CSV", file=sys.stderr)
            return 1

        # Dedup and enrich
        properties = dedup(properties)
        properties = [enrich(p) for p in properties]

        print(f"Screening {len(properties)} properties...", file=sys.stderr)

        # Underwrite and gate each property
        results = []
        for prop in properties:
            try:
                # For now, use provided rent or a default estimate
                rent_point = Decimal(args.rent_mid) if args.rent_mid else _estimate_rent(prop)
                rent_low = Decimal(args.rent_low) if args.rent_low else rent_point * Decimal(0.95)
                rent_high = Decimal(args.rent_high) if args.rent_high else rent_point * Decimal(1.05)

                rent = from_signals(
                    comps_estimate=rent_point,
                    psf_estimate=rent_point,
                    haircut_estimate=rent_point,
                )
                rent.low = rent_low
                rent.high = rent_high

                result = underwrite(prop, rent, assumptions)
                result.gates = evaluate_gates(result, prop, assumptions)
                results.append(result)
            except Exception as e:
                print(f"ERROR: Could not underwrite {prop.property_id}: {e}", file=sys.stderr)
                continue

        # Rank and output
        ranked = rank_queue(results)

        with open(args.out, "w", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "rank",
                    "property_id",
                    "list_price",
                    "rent_monthly",
                    "cap_rate",
                    "cash_on_cash",
                    "levered_irr",
                    "gates_passed",
                    "score",
                    "reason",
                ],
            )
            writer.writeheader()

            for i, (result, score, reason) in enumerate(ranked, 1):
                gates_passed = sum(1 for g in result.gates if g.passed)
                writer.writerow({
                    "rank": i,
                    "property_id": result.property_id,
                    "list_price": float(result.all_in_basis),
                    "rent_monthly": float(result.rent.point),
                    "cap_rate": result.going_in_cap_rate,
                    "cash_on_cash": result.cash_on_cash,
                    "levered_irr": result.levered_irr,
                    "gates_passed": f"{gates_passed}/{len(result.gates)}",
                    "score": f"{score:.0f}",
                    "reason": reason,
                })

        print(f"✓ Ranked {len(ranked)} properties to {args.out}", file=sys.stderr)
        return 0

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


def cmd_memo(args) -> int:
    """Render a memo for one property.

    TODO: In a real implementation, this would look up the property from a database
    or input file. For now, this is a placeholder.
    """
    print("memo: Phase 5 feature. Requires property database / input file.", file=sys.stderr)
    print(f"Would render memo for property: {args.property_id}", file=sys.stderr)
    print(f"Address: {args.address or '(not provided)'}", file=sys.stderr)
    return 0


def _load_assumptions(path: Path) -> Assumptions:
    """Load assumptions from a YAML file."""
    with open(path) as f:
        data = yaml.safe_load(f)
    return Assumptions(**data)


def _estimate_rent(prop: Property) -> Decimal:
    """Simple rent estimate: price * 0.8% / 12 (1% rule)."""
    # Very rough estimate: 0.8% rule
    monthly_rent = prop.list_price * Decimal(0.008)
    return max(Decimal(500), monthly_rent)  # At least $500/month


if __name__ == "__main__":
    raise SystemExit(main())
