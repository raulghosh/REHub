"""Listing CSV -> DealInput, for screening many listings at once.

Each row supplies the property and its price; everything else (financing, management, your
tax situation, targets) comes from your investor profile. Rent is required: the model never
backs rent out of the price, and a row it can't read is reported, not silently dropped.

Columns (rename yours with a column map): address, zip_code, property_type, year_built,
sqft, beds, baths, units, rent (total $/month), price, and optionally hoa_monthly,
market_value, property_tax_annual, insurance_annual, rehab_budget, arv.
"""

from __future__ import annotations

import csv
from collections.abc import Iterator
from copy import deepcopy
from pathlib import Path

from pydantic import ValidationError

from ..schemas import DealInput


def deal_from_row(row: dict[str, str], profile: dict) -> DealInput:
    def get(key: str) -> str:
        return (row.get(key) or "").strip()

    def num(key: str) -> float | None:
        return float(get(key).replace(",", "").replace("$", "")) if get(key) else None

    units = int(num("units") or 1)
    if num("rent") is None or num("price") is None:
        raise ValueError("rent and price are required")
    ptype = get("property_type") or ("single_family" if units == 1 else
                                      "multi_2_4" if units <= 4 else "multi_5_plus")
    data = deepcopy(profile)
    data["property"] = {
        "address": get("address"), "zip_code": get("zip_code").zfill(5), "property_type": ptype,
        "year_built": int(num("year_built") or 0), "sqft": num("sqft") or 0,
        "hoa_monthly": num("hoa_monthly") or 0,
        "units": [{"beds": int(num("beds") or 2), "baths": num("baths") or 1,
                   "rent": num("rent") / units}] * units,
    }
    data["purchase"] = {**data.get("purchase", {}), "price": num("price")}
    if num("market_value"):
        data["purchase"]["market_value"] = num("market_value")
    ops = data.setdefault("operations", {})
    for key, line in (("property_tax_annual", "property_tax"), ("insurance_annual", "insurance")):
        if num(key) is not None:
            ops[key] = num(key)
            ops["known"] = sorted({*ops.get("known", []), line})
    if num("rehab_budget"):
        data["rehab"] = {**data.get("rehab", {}), "budget": num("rehab_budget"),
                         **({"arv": num("arv")} if num("arv") else {})}
    return DealInput.model_validate(data)


def from_csv(path: Path, profile: dict, column_mapping: dict[str, str] | None = None,
             ) -> Iterator[tuple[int, DealInput | str]]:
    """Yield (line number, deal) — or (line number, error message) for a bad row."""
    mapping = column_mapping or {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"{path} is empty")
        for line, raw in enumerate(reader, start=2):
            row = {ours: raw.get(theirs, "") for ours, theirs in mapping.items()}
            row = {**raw, **row}
            try:
                yield line, deal_from_row(row, profile)
            except (ValueError, ValidationError) as e:
                yield line, str(e).splitlines()[0] if isinstance(e, ValueError) else _first_error(e)


def _first_error(e: ValidationError) -> str:
    err = e.errors()[0]
    return f"{'.'.join(map(str, err['loc']))}: {err['msg']}"
