"""Address normalization and cross-source dedup.

The same house shows up on three feeds with three address spellings and three prices. We
canonicalize the address (USPS-style), then collapse duplicates — keeping the freshest /
lowest-price record and preserving the price-cut trail.

Phase 3. Stubbed.
"""

from __future__ import annotations

from typing import Iterable

from ..schemas import Property


def canonical_address(address: str, city: str, state: str, zip_code: str) -> str:
    raise NotImplementedError("Phase 3: address normalization not yet implemented.")


def dedup(properties: Iterable[Property]) -> list[Property]:
    """Collapse cross-source duplicates by canonical address."""
    raise NotImplementedError("Phase 3: dedup not yet implemented.")
