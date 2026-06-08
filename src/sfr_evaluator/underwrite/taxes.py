"""Property taxes with post-sale reassessment.

The seller's tax bill is stale. On acquisition, most jurisdictions reassess to (near) the
purchase price. Underwriting on the seller's basis is one of the most common ways a deal
that "pencils" actually loses money.

Phase 1. Stubbed.
"""

from __future__ import annotations

from decimal import Decimal

from ..schemas import Assumptions, Property


def annual_property_tax(prop: Property, purchase_price: Decimal, assumptions: Assumptions) -> Decimal:
    """Annual tax after reassessment.

    If assumptions.reassess_on_sale:
        assessed = purchase_price * assessment_ratio
        tax      = assessed * millage_rate
    else: fall back to prop.annual_property_tax (seller's bill).
    """
    raise NotImplementedError("Phase 1: reassessment model not yet implemented.")
