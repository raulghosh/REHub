"""Tests for Phase 2: rent triangulation."""

from decimal import Decimal
import pytest

from sfr_evaluator.rents.triangulate import (
    from_signals,
    from_comps,
    from_submarket_psf,
    from_asking_with_haircut,
)


def test_triangulate_signals():
    """Test blending three rent signals."""
    comps = Decimal("2150")
    psf = Decimal("2200")
    haircut = Decimal("2100")

    result = from_signals(comps, psf, haircut)

    # Point should be median (2150)
    assert result.point == Decimal("2150")
    assert result.low == Decimal("2100")
    assert result.high == Decimal("2200")
    assert result.divergence_flag is False
    assert "comps" in result.signals


def test_triangulate_with_divergence():
    """Test divergence flag when signals diverge >10%."""
    comps = Decimal("2000")
    psf = Decimal("2200")
    haircut = Decimal("2400")

    result = from_signals(comps, psf, haircut)

    # Range: 2000-2400 = 400; median ~2200; spread = 400/2200 ~ 18% > 10%
    assert result.divergence_flag is True
    assert result.low == Decimal("2000")
    assert result.high == Decimal("2400")


def test_from_comps():
    """Test rent estimation from comparable leases."""
    comps = [Decimal("2100"), Decimal("2150"), Decimal("2200")]
    estimate = from_comps(comps)

    # Average should be 2150
    assert estimate == Decimal("2150")


def test_from_comps_with_adjustment():
    """Test comps with market adjustment."""
    comps = [Decimal("2000"), Decimal("2000"), Decimal("2000")]
    estimate = from_comps(comps, adjustment=1.10)  # 10% appreciation

    # Allow for small floating-point error
    assert abs(estimate - Decimal("2200")) < Decimal("0.01")


def test_from_submarket_psf():
    """Test rent estimation from submarket $/sqft."""
    submarket_psf = Decimal("1.35")  # $1.35/sqft/month
    sqft = 1600

    estimate = from_submarket_psf(submarket_psf, sqft)

    # $1.35/sqft/month * 1600 sqft = $2160/month
    assert estimate == Decimal("2160")


def test_haircut_model():
    """Test conservative haircut on asking rents."""
    asking = Decimal("2300")
    estimate = from_asking_with_haircut(asking, haircut=0.05)

    # 2300 * 0.95 = 2185, allow for floating-point error
    assert abs(estimate - Decimal("2185")) < Decimal("0.01")


def test_no_divergence_tight_signals():
    """Test that tight signals don't flag divergence."""
    comps = Decimal("2200")
    psf = Decimal("2210")
    haircut = Decimal("2205")

    result = from_signals(comps, psf, haircut)

    # Spread: (2210 - 2200) / 2205 ~ 0.4% < 10%
    assert result.divergence_flag is False
