"""Ranked queue + one-page memo — the actual deliverables.

The screening output is a *ranked* table: every property, green/yellow/red on each gate,
sorted by a blended score, annotated with the two reasons it passed or died. Hard-gate
failures sink to red; soft factors (school zone, flood, DOM/price-cuts, concentration)
nudge the score.

Phase 4-5. Stubbed.
"""

from __future__ import annotations

from ..schemas import UnderwritingResult


def score(result: UnderwritingResult) -> float:
    """Blended 0-100 score. Hard-gate failure caps the score low (red)."""
    raise NotImplementedError("Phase 4: scoring not yet implemented.")


def rank_queue(results: list[UnderwritingResult]) -> list[tuple[UnderwritingResult, float]]:
    """Sort screened deals best-first with their scores."""
    raise NotImplementedError("Phase 4: ranked queue not yet implemented.")


def memo(result: UnderwritingResult) -> str:
    """Render a one-page screening memo (markdown): assumptions, returns, tornado, bear case."""
    raise NotImplementedError("Phase 5: memo generation not yet implemented.")
