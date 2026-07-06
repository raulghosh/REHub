"""Tests for Phase 3: ingestion and enrichment."""

from decimal import Decimal
from pathlib import Path
import tempfile

import pytest

from sfr_evaluator.ingest.sources import from_csv
from sfr_evaluator.ingest.normalize import canonical_address, dedup
from sfr_evaluator.schemas import Property, AssetType


def test_csv_import():
    """Test CSV import with basic column mapping."""
    # Create a temporary CSV file
    csv_content = """id,address,city,state,zipcode,beds,baths,sqft,asking_price,type
prop-1,123 Main St,Austin,TX,78704,3,2,1600,350000,single_family
prop-2,456 Oak Ave,Austin,TX,78705,2,1,1200,250000,townhouse
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(csv_content)
        csv_path = Path(f.name)

    try:
        # Import with custom column mapping
        column_mapping = {
            "property_id": "id",
            "zip_code": "zipcode",
            "list_price": "asking_price",
            "asset_type": "type",
        }
        properties = list(from_csv(csv_path, source_name="test_csv", column_mapping=column_mapping))

        assert len(properties) == 2
        assert properties[0].property_id == "prop-1"
        assert properties[0].beds == 3.0
        assert properties[0].list_price == Decimal("350000")
        assert properties[0].asset_type == AssetType.SINGLE_FAMILY

        assert properties[1].asset_type == AssetType.TOWNHOUSE
    finally:
        csv_path.unlink()


def test_canonical_address():
    """Test address canonicalization."""
    # Test basic normalization
    result = canonical_address("123 Main St", "Austin", "TX", "78704")
    assert "STREET" in result
    assert "AUSTIN" in result
    assert "TX" in result
    assert "78704" in result

    # Test with abbreviations
    result = canonical_address("456 Oak Ave Apt 5", "Dallas", "TX", "75001")
    assert "AVENUE" in result
    assert "APT" in result


def test_canonical_address_dedup():
    """Test that different spellings of the same address canonicalize to the same value."""
    addr1 = canonical_address("123 Main St", "Austin", "TX", "78704")
    addr2 = canonical_address("123 Main Street", "Austin", "TX", "78704")

    assert addr1 == addr2, "Different address spellings should canonicalize to the same form"


def test_dedup():
    """Test deduplication logic."""
    # Create a list with duplicates at different prices
    props = [
        Property(
            property_id="prop-1",
            source="mls",
            address="123 Main St",
            city="Austin",
            state="TX",
            zip_code="78704",
            asset_type=AssetType.SINGLE_FAMILY,
            beds=3.0,
            baths=2.0,
            sqft=1600,
            list_price=Decimal("350000"),
        ),
        Property(
            property_id="prop-1-dup",
            source="zillow",
            address="123 Main Street",  # Different spelling
            city="Austin",
            state="TX",
            zip_code="78704",
            asset_type=AssetType.SINGLE_FAMILY,
            beds=3.0,
            baths=2.0,
            sqft=1600,
            list_price=Decimal("345000"),  # Lower price
        ),
    ]

    deduped = dedup(props)

    # Should have 1 property (the cheaper one)
    assert len(deduped) == 1
    assert deduped[0].property_id == "prop-1-dup"  # The cheaper one
    assert deduped[0].list_price == Decimal("345000")


def test_dedup_keeps_distinct_addresses():
    """Test that dedup doesn't collapse genuinely different properties."""
    props = [
        Property(
            property_id="prop-1",
            source="mls",
            address="123 Main St",
            city="Austin",
            state="TX",
            zip_code="78704",
            asset_type=AssetType.SINGLE_FAMILY,
            beds=3.0,
            baths=2.0,
            sqft=1600,
            list_price=Decimal("350000"),
        ),
        Property(
            property_id="prop-2",
            source="mls",
            address="456 Oak Ave",
            city="Austin",
            state="TX",
            zip_code="78705",
            asset_type=AssetType.SINGLE_FAMILY,
            beds=2.0,
            baths=1.0,
            sqft=1200,
            list_price=Decimal("250000"),
        ),
    ]

    deduped = dedup(props)

    # Should have 2 properties (different addresses)
    assert len(deduped) == 2
