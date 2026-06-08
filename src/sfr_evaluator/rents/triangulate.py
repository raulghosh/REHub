"""Triangulate monthly rent from three independent signals.

Never trust a single "Rent Zestimate". We combine:
    1. comps        — recent leased comparables, adjusted
    2. psf          — submarket $/sqft * subject sqft
    3. haircut      — a conservative discount model off asking rents

The point estimate is a weighted blend; the band (low/high) is the spread across signals and
feeds the engine as a sensitivity input. When signals disagree beyond a threshold we raise
`divergence_flag` — that disagreement is itself information, not noise.

Phase 2. Stubbed.
"""

from __future__ import annotations

from ..schemas import Property, RentEstimate

DIVERGENCE_THRESHOLD = 0.10  # flag if max signal spread exceeds 10% of the point estimate


def triangulate_rent(prop: Property) -> RentEstimate:
    raise NotImplementedError("Phase 2: rent triangulation not yet implemented.")
