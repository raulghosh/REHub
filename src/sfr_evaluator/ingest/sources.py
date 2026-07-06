"""Listing source adapters.

Each source (MLS export, Zillow, Redfin, a wholesaler's CSV blast) maps its own schema onto
our `Property` contract. Start with a CSV adapter; add API/scraper adapters behind the same
interface later so the rest of the pipeline never learns where a listing came from.
"""

from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path
from typing import Iterable, Optional

from ..schemas import Property, AssetType, ComponentAge


def from_csv(
    path: Path,
    source_name: str = "csv",
    column_mapping: Optional[dict[str, str]] = None,
) -> Iterable[Property]:
    """Yield Property records from a CSV export.

    column_mapping maps our schema field names to CSV column names:
    {
        "property_id": "id",
        "address": "full_address",
        "list_price": "asking_price",
        "beds": "bed_count",
        ...
    }

    If a mapping is not provided, assume the CSV column names match our schema.
    Missing/invalid fields are filled with defaults from the Property schema.
    """
    if column_mapping is None:
        column_mapping = {}

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"CSV file {path} is empty")

        for row in reader:
            try:
                prop = _row_to_property(row, source_name, column_mapping)
                if prop is not None:
                    yield prop
            except (ValueError, KeyError) as e:
                # Skip rows that can't be parsed; log if needed
                continue


def _row_to_property(
    row: dict[str, str],
    source_name: str,
    column_mapping: dict[str, str],
) -> Optional[Property]:
    """Convert a CSV row to a Property record."""

    def get_field(key: str, default=None):
        """Fetch a field from the row, respecting the column mapping."""
        csv_col = column_mapping.get(key, key)
        val = row.get(csv_col, "").strip()
        return val if val else default

    # Required fields
    property_id = get_field("property_id")
    if not property_id:
        return None  # Skip rows without an ID

    address = get_field("address", "")
    city = get_field("city", "")
    state = get_field("state", "")
    zip_code = get_field("zip_code", "")

    if not address or not city or not state:
        return None  # Skip incomplete addresses

    # Asset type (default to single family)
    asset_type_str = get_field("asset_type", "single_family").lower()
    if "townhouse" in asset_type_str or "townhome" in asset_type_str:
        asset_type = AssetType.TOWNHOUSE
    else:
        asset_type = AssetType.SINGLE_FAMILY

    # Numeric fields
    beds = _parse_float(get_field("beds", "0"))
    baths = _parse_float(get_field("baths", "0"))
    sqft = _parse_int(get_field("sqft", "0"))
    lot_sqft = _parse_int(get_field("lot_sqft"))
    year_built = _parse_int(get_field("year_built"))
    hoa_monthly = Decimal(get_field("hoa_monthly", "0"))
    list_price = Decimal(get_field("list_price", "0"))
    days_on_market = _parse_int(get_field("days_on_market"))
    price_cut_count = _parse_int(get_field("price_cut_count", "0"))

    # Component ages (optional)
    component_age = ComponentAge(
        roof=_parse_int(get_field("roof_age")),
        hvac=_parse_int(get_field("hvac_age")),
        water_heater=_parse_int(get_field("water_heater_age")),
        flooring=_parse_int(get_field("flooring_age")),
        electrical=_parse_int(get_field("electrical_age")),
        plumbing=_parse_int(get_field("plumbing_age")),
    )

    # Enriched fields (populated later by enrich.py)
    census_tract = get_field("census_tract")
    school_zone_score = _parse_float(get_field("school_zone_score"))
    fema_flood_zone = get_field("fema_flood_zone")
    annual_property_tax = _parse_decimal(get_field("annual_property_tax"))
    assessed_value = _parse_decimal(get_field("assessed_value"))

    return Property(
        property_id=property_id,
        source=source_name,
        address=address,
        city=city,
        state=state,
        zip_code=zip_code,
        asset_type=asset_type,
        beds=beds,
        baths=baths,
        sqft=sqft,
        lot_sqft=lot_sqft,
        year_built=year_built,
        hoa_monthly=hoa_monthly,
        list_price=list_price,
        days_on_market=days_on_market,
        price_cut_count=price_cut_count,
        component_age=component_age,
        census_tract=census_tract,
        school_zone_score=school_zone_score,
        fema_flood_zone=fema_flood_zone,
        annual_property_tax=annual_property_tax,
        assessed_value=assessed_value,
    )


def _parse_float(val: Optional[str]) -> float:
    """Parse a float, return 0 if empty/invalid."""
    if not val:
        return 0.0
    try:
        return float(val)
    except ValueError:
        return 0.0


def _parse_int(val: Optional[str]) -> Optional[int]:
    """Parse an int, return None if empty/invalid."""
    if not val:
        return None
    try:
        return int(val)
    except ValueError:
        return None


def _parse_decimal(val: Optional[str]) -> Optional[Decimal]:
    """Parse a Decimal, return None if empty/invalid."""
    if not val:
        return None
    try:
        return Decimal(val)
    except:
        return None
