"""Address normalization and cross-source dedup.

The same house shows up on three feeds with three address spellings and three prices. We
canonicalize the address (USPS-style), then collapse duplicates — keeping the lowest-price
record.
"""

from __future__ import annotations

import re
from typing import Iterable

from ..schemas import Property


# Common abbreviations expanded to full form (USPS style)
ABBREVIATIONS = [
    (r"\bSt\.?(\s|$)", "STREET "),
    (r"\bAve\.?(\s|$)", "AVENUE "),
    (r"\bBlvd\.?(\s|$)", "BOULEVARD "),
    (r"\bDr\.?(\s|$)", "DRIVE "),
    (r"\bLn\.?(\s|$)", "LANE "),
    (r"\bRd\.?(\s|$)", "ROAD "),
    (r"\bPl\.?(\s|$)", "PLACE "),
    (r"\bCt\.?(\s|$)", "COURT "),
    (r"\bCir\.?(\s|$)", "CIRCLE "),
    (r"\bTer\.?(\s|$)", "TERRACE "),
    (r"\bApt\.?(\s|$)", "APT "),
    (r"\bUnit\.?(\s|$)", "UNIT "),
    (r"\bNo\.?(\s|$)", "NUMBER "),
]


def canonical_address(address: str, city: str, state: str, zip_code: str) -> str:
    """Normalize address to a canonical form for dedup.

    - Trim and uppercase
    - Expand street suffixes (St. -> Street, etc.)
    - Remove extra spaces
    - Combine with city/state/zip for uniqueness
    """
    addr = address.strip().upper()

    # Expand abbreviations
    for pattern, replacement in ABBREVIATIONS:
        addr = re.sub(pattern, replacement, addr, flags=re.IGNORECASE)

    # Remove extra spaces
    addr = re.sub(r"\s+", " ", addr).strip()

    # Combine with city, state, zip for full uniqueness
    return f"{addr}, {city.upper()}, {state.upper()} {zip_code}"


def dedup(properties: Iterable[Property]) -> list[Property]:
    """Collapse cross-source duplicates by canonical address.

    For each canonical address, keep the record with:
    1. Lowest list price (better deal)
    2. If tied, prefer most recent (not tracked here; keep first seen)
    """
    seen = {}  # canonical_address -> Property

    for prop in properties:
        addr = canonical_address(prop.address, prop.city, prop.state, prop.zip_code)

        if addr not in seen:
            seen[addr] = prop
        else:
            # Keep the lower-price listing
            if prop.list_price < seen[addr].list_price:
                seen[addr] = prop

    return list(seen.values())
