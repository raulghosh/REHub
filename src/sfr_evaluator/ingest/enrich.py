"""Enrich a Property with the geographic and risk context that gates decisions.

Geocode -> census tract; FEMA flood zone; school-zone score; tax history & assessed value;
DOM and price-cut history. A property with two price cuts in 45 days is a negotiation, not
just a comp — we keep that signal.

Phase 3. Stubbed.
"""

from __future__ import annotations

from ..schemas import Property


def enrich(prop: Property) -> Property:
    """Return a copy of `prop` with geo/risk/tax fields populated."""
    raise NotImplementedError("Phase 3: enrichment not yet implemented.")
