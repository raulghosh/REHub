"""Listing source adapters.

Each source (MLS export, Zillow, Redfin, a wholesaler's CSV blast) maps its own schema onto
our `Property` contract. Start with a CSV adapter; add API/scraper adapters behind the same
interface later so the rest of the pipeline never learns where a listing came from.

Phase 3. Stubbed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from ..schemas import Property


def from_csv(path: Path) -> Iterable[Property]:
    """Yield Property records from a CSV export. First adapter to build."""
    raise NotImplementedError("Phase 3: CSV source adapter not yet implemented.")
