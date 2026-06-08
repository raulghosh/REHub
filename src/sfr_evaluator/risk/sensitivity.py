"""Sensitivity (tornado) and Monte Carlo.

Tornado ranks the inputs by their swing on levered IRR. Monte Carlo simulates the two
variables that actually dominate SFR IRR — rent growth and exit cap — rather than wasting
cycles on inputs that barely move the answer. Seeded for reproducibility.

Phase 4. Stubbed.
"""

from __future__ import annotations

from ..schemas import Assumptions, Property, RentEstimate


def tornado(prop: Property, rent: RentEstimate, base: Assumptions) -> dict[str, float]:
    """Map each varied input -> IRR swing (high case - low case)."""
    raise NotImplementedError("Phase 4: tornado analysis not yet implemented.")


def monte_carlo(
    prop: Property,
    rent: RentEstimate,
    base: Assumptions,
    n: int = 10_000,
    seed: int = 42,
) -> dict[str, float]:
    """Return IRR distribution stats (p10/p50/p90, prob below hurdle)."""
    raise NotImplementedError("Phase 4: Monte Carlo not yet implemented.")
