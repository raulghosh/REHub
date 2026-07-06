"""Enrich a Property with the geographic and risk context that gates decisions.

Real enrichment calls out to:
- Census geocoder → census tract (free, via Census.gov API)
- FEMA NFHL → flood zone (free, via FEMA API)
- School zone / tax history: manual or paywalled APIs (not yet wired)

For now, Phase 3 leaves these fields as None if not already in the CSV — the engine
degrades gracefully (uses defaults from Assumptions).
"""

from __future__ import annotations

from copy import deepcopy

from ..schemas import Property


def enrich(prop: Property) -> Property:
    """Return a copy of `prop` with geo/risk/tax fields populated.

    In Phase 3, this is a pass-through. Real enrichment will call APIs here.
    For now, if the field is already populated (from the CSV), keep it.
    Otherwise, leave it as None and the engine uses defaults.
    """
    # Make a copy to avoid mutating the original
    enriched = deepcopy(prop)

    # Placeholder: real enrichment would call APIs here
    # For now, just return the property as-is.
    # If the CSV had these fields, they're already populated.
    # Otherwise, they stay None.

    return enriched


def geocode_to_tract(address: str, city: str, state: str, zip_code: str) -> str:
    """Geocode an address to a Census tract (11-digit FIPS code).

    In Phase 3, this is stubbed. Real implementation would call Census.gov API.
    """
    # TODO: Call Census geocoder API
    # For now, return a placeholder
    return None


def fema_flood_zone(address: str, city: str, state: str, zip_code: str) -> str:
    """Look up FEMA flood zone for an address.

    In Phase 3, this is stubbed. Real implementation would call FEMA NFHL API or use
    a static GeoJSON lookup.
    """
    # TODO: Call FEMA NFHL API
    # For now, return a placeholder
    return None


def school_zone_score(address: str, city: str, state: str, zip_code: str) -> float:
    """Look up school zone score (0-10) for an address.

    In Phase 3, this is stubbed. Real implementation would call GreatSchools API
    or a similar service.
    """
    # TODO: Call GreatSchools API or similar
    # For now, return a placeholder
    return None
