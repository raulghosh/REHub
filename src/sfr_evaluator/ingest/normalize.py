"""Address normalization and cross-source dedup.

The same house shows up on three feeds with three address spellings and three prices. We
canonicalize the address (USPS-style) within its zip, then keep the lowest-price record.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from ..schemas import DealInput

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


def canonical_address(address: str, zip_code: str) -> str:
    """Uppercase, expand street suffixes, collapse spaces, scope to the zip."""
    addr = address.strip().upper()
    for pattern, replacement in ABBREVIATIONS:
        addr = re.sub(pattern, replacement, addr, flags=re.IGNORECASE)
    addr = re.sub(r"\s+", " ", addr).strip()
    return f"{addr}, {zip_code}"


def dedup(deals: Iterable[DealInput]) -> list[DealInput]:
    """Collapse duplicates by canonical address, keeping the lowest price. Rows without an
    address are never merged."""
    seen: dict[str, DealInput] = {}
    out: list[DealInput] = []
    for d in deals:
        if not d.property.address.strip():
            out.append(d)
            continue
        key = canonical_address(d.property.address, d.property.zip_code)
        if key not in seen or d.purchase.price < seen[key].purchase.price:
            seen[key] = d
    return out + list(seen.values())
