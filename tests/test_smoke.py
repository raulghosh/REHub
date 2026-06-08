"""Smoke tests: the scaffold imports and the data contracts hold.

These pass today. Engine correctness tests arrive with Phase 1 (golden-file checks against
a hand-built Excel deal).
"""

from decimal import Decimal

from sfr_evaluator.schemas import (
    AssetType,
    Assumptions,
    Property,
    RentEstimate,
)


def test_property_contract():
    p = Property(
        property_id="demo-1",
        source="csv",
        address="123 Main St",
        city="Austin",
        state="TX",
        zip_code="78704",
        asset_type=AssetType.SINGLE_FAMILY,
        beds=3,
        baths=2,
        sqft=1600,
        list_price=Decimal("350000"),
    )
    assert p.asset_type is AssetType.SINGLE_FAMILY
    assert p.hoa_monthly == Decimal(0)  # default


def test_assumptions_defaults():
    a = Assumptions()
    # Vacancy and credit loss are modeled separately, not blended.
    assert a.physical_vacancy != a.credit_loss
    # Exit cap carries a spread over entry.
    assert a.exit_cap_spread_bps > 0
    # The development-spread gate exists.
    assert a.min_yoc_exit_spread_bps == 150


def test_rent_estimate_band():
    r = RentEstimate(point=Decimal("2000"), low=Decimal("1900"), high=Decimal("2150"))
    assert r.low <= r.point <= r.high
    assert r.divergence_flag is False
