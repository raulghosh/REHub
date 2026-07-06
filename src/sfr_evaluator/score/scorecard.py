"""Ranked queue + one-page memo — the actual deliverables.

The screening output is a *ranked* table: every property, green/yellow/red on each gate,
sorted by a blended score, annotated with the top reasons it passed or died.
"""

from __future__ import annotations

from typing import Optional

from ..schemas import UnderwritingResult


def score(result: UnderwritingResult) -> float:
    """Blended 0-100 score.

    - Base: levered IRR / hurdle ratio (scaled to 0-100)
    - Hard-gate failures cap the score at red (~30)
    - Soft factors would nudge score (todo: school zone, flood, etc.)
    """
    base_score = 50.0  # Neutral baseline

    # If all gates passed, boost score based on IRR
    if result.passed_all_gates:
        # Assume hurdle is 15%, so 25% IRR = excellent (100), 15% = acceptable (50)
        irr_ratio = result.levered_irr / 0.15
        base_score = min(100, 50 + (irr_ratio - 1) * 50)
    else:
        # Hard-gate failure: red zone
        base_score = 30.0

    return base_score


def rank_queue(
    results: list[UnderwritingResult],
) -> list[tuple[UnderwritingResult, float, str]]:
    """Sort screened deals best-first with their scores and a top reason.

    Returns list of (result, score, reason) tuples, best first.
    """
    scored = []
    for result in results:
        s = score(result)
        reason = _top_reason(result)
        scored.append((result, s, reason))

    # Sort by score descending
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


def _top_reason(result: UnderwritingResult) -> str:
    """Generate a one-line reason why a deal passed or failed."""
    # If not all gates passed, find the first failing gate
    for gate in result.gates:
        if not gate.passed:
            return f"FAILED: {gate.name} {gate.note}"

    # All gates passed; highlight the best metric
    if result.levered_irr >= 0.20:
        return f"Strong IRR: {result.levered_irr:.1%}"
    elif result.levered_irr >= 0.15:
        return f"Target IRR: {result.levered_irr:.1%}"
    else:
        return f"Marginal IRR: {result.levered_irr:.1%}"


def memo(result: UnderwritingResult, prop_address: str = "") -> str:
    """Render a one-page screening memo (markdown).

    Phase 5: full memo with assumptions, returns, tornado, bear case.
    Phase 4: stub that shows the basic structure.
    """
    addr = prop_address or result.property_id

    memo_lines = [
        f"# Screening Memo: {addr}",
        "",
        "## Property Metrics",
        f"- **List Price:** ${result.all_in_basis:,.0f}",
        f"- **Est. Rent:** ${result.rent.point:,.0f}/month",
        f"- **Cap Rate:** {result.going_in_cap_rate:.2%}",
        "",
        "## Gate Status",
    ]

    for gate in result.gates:
        status = "✓" if gate.passed else "✗"
        memo_lines.append(f"- {status} **{gate.name}:** {gate.note}")

    memo_lines.extend([
        "",
        "## Levered Returns",
        f"- **Levered IRR:** {result.levered_irr:.1%}",
        f"- **Equity Multiple:** {result.equity_multiple:.2f}x",
        f"- **Year-1 CoC:** {result.cash_on_cash:.2%}",
        f"- **DSCR:** {result.dscr:.2f}x",
        "",
        "## Exit",
        f"- **Exit Cap:** {result.exit_cap_rate:.2%}",
        f"- **Exit Value:** ${result.exit_value:,.0f}",
        "",
    ])

    if not result.passed_all_gates:
        reason = _top_reason(result)
        memo_lines.append(f"## Status")
        memo_lines.append(f"**REJECTED:** {reason}")
    else:
        memo_lines.append(f"## Status")
        memo_lines.append(f"**PASSES SCREENING** — advanced to underwriting queue")

    return "\n".join(memo_lines)
