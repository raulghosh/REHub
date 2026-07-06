"""Triangulate monthly rent from three independent signals.

Never trust a single "Rent Zestimate". We combine:
    1. comps        — recent leased comparables, adjusted
    2. psf          — submarket $/sqft * subject sqft
    3. haircut      — a conservative discount model off asking rents

The point estimate is a weighted blend; the band (low/high) is the spread across signals and
feeds the engine as a sensitivity input. When signals disagree beyond a threshold we raise
`divergence_flag` — that disagreement is itself information, not noise.
"""

from __future__ import annotations

from decimal import Decimal
from statistics import median

from ..schemas import Property, RentEstimate, Assumptions

DIVERGENCE_THRESHOLD = 0.10  # flag if max signal spread exceeds 10% of the point estimate


def from_signals(
    comps_estimate: Decimal,
    psf_estimate: Decimal,
    haircut_estimate: Decimal,
) -> RentEstimate:
    """Blend three signals into a point estimate and band.

    Point = median of the three signals.
    Band = (min, max) across the three.
    Divergence = True if (max - min) / point > threshold.
    """
    signals = [comps_estimate, psf_estimate, haircut_estimate]
    point = Decimal(median([float(s) for s in signals]))
    low = min(signals)
    high = max(signals)

    spread = (high - low) / point if point > 0 else Decimal(0)
    divergence_flag = spread > Decimal(DIVERGENCE_THRESHOLD)

    return RentEstimate(
        point=point,
        low=low,
        high=high,
        signals={
            "comps": comps_estimate,
            "psf": psf_estimate,
            "haircut": haircut_estimate,
        },
        divergence_flag=divergence_flag,
    )


def from_comps(comparable_rents: list[Decimal], adjustment: float = 1.0) -> Decimal:
    """Estimate rent from a list of comparable recent leases.

    comparable_rents: list of monthly rents from nearby leased properties.
    adjustment: any market adjustment to apply (e.g., 1.05 for 5% appreciation).
    """
    if not comparable_rents:
        raise ValueError("No comparable rents provided")
    avg = sum(comparable_rents) / len(comparable_rents)
    return Decimal(adjustment) * avg


def from_submarket_psf(submarket_psf: Decimal, subject_sqft: int) -> Decimal:
    """Estimate rent from submarket $/sqft and subject property size.

    submarket_psf: e.g., $1.35/sqft/month from Fair Market Rents or Census data.
    subject_sqft: total livable sqft of the subject property.
    """
    return submarket_psf * Decimal(subject_sqft)


def from_asking_with_haircut(asking_rent: Decimal, haircut: float = 0.05) -> Decimal:
    """Estimate actual rent from asking rent with a conservative discount.

    Advertised rents are often optimistic. Apply a haircut (default 5%) to get a
    realistic estimate.

    haircut: discount to apply (0.05 = 5%).
    """
    return asking_rent * Decimal(1 - haircut)
