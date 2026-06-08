"""Command-line entry point.

    sfr-eval screen --input listings.csv --assumptions config/assumptions.yaml --out queue.csv
    sfr-eval memo   --property-id <id>  --assumptions config/assumptions.yaml

Wiring is stubbed until the pipeline phases land; the arg surface is fixed now so the
interface is stable.
"""

from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sfr-eval", description="SFR/townhouse deal screener.")
    sub = p.add_subparsers(dest="command", required=True)

    screen = sub.add_parser("screen", help="Screen a listing file into a ranked queue.")
    screen.add_argument("--input", required=True, help="Listing file (CSV).")
    screen.add_argument("--assumptions", required=True, help="Assumptions YAML.")
    screen.add_argument("--out", required=True, help="Output ranked queue (CSV).")

    memo = sub.add_parser("memo", help="Render a one-page memo for one property.")
    memo.add_argument("--property-id", required=True)
    memo.add_argument("--assumptions", required=True)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    raise NotImplementedError(
        f"Command '{args.command}' is scaffolded but not yet wired — see ROADMAP.md."
    )


if __name__ == "__main__":
    raise SystemExit(main())
