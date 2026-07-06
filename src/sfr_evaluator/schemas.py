"""Core data contracts for the SFR/townhouse evaluation pipeline.

Everything downstream is a pure function over these models. Keep money as Decimal,
keep rates as fractions (0.06 == 6%), and keep all tunable assumptions in `Assumptions`
so nothing is hard-coded in the engine.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# Inputs: the property as it comes off a listing, then enriched.
# --------------------------------------------------------------------------- #

class AssetType(str, Enum):
    SINGLE_FAMILY = "single_family"
    TOWNHOUSE = "townhouse"


class ComponentAge(BaseModel):
    """Age (years) of a major component, for capex replacement clocks.

    `None` means unknown -> the engine assumes mid-life (conservative) rather than new.
    """
    roof: Optional[int] = None
    hvac: Optional[int] = None
    water_heater: Optional[int] = None
    flooring: Optional[int] = None
    electrical: Optional[int] = None
    plumbing: Optional[int] = None


class Property(BaseModel):
    """A candidate property. Geographic/risk fields are populated by `ingest.enrich`."""
    property_id: str
    source: str = Field(description="Origin feed, e.g. 'mls', 'zillow', 'wholesaler_x'.")
    address: str
    city: str
    state: str
    zip_code: str

    asset_type: AssetType
    beds: float
    baths: float
    sqft: int
    lot_sqft: Optional[int] = None
    year_built: Optional[int] = None
    hoa_monthly: Decimal = Decimal(0)

    list_price: Decimal
    days_on_market: Optional[int] = None
    price_cut_count: int = 0

    component_age: ComponentAge = Field(default_factory=ComponentAge)

    # Enriched (Phase 3).
    census_tract: Optional[str] = None
    school_zone_score: Optional[float] = None  # 0-10
    fema_flood_zone: Optional[str] = None       # e.g. "X", "AE"
    annual_property_tax: Optional[Decimal] = None
    assessed_value: Optional[Decimal] = None


# --------------------------------------------------------------------------- #
# Rents: a triangulated estimate, never a single number.
# --------------------------------------------------------------------------- #

class RentEstimate(BaseModel):
    """Triangulated monthly rent. The band, not the point, drives sensitivity."""
    point: Decimal
    low: Decimal
    high: Decimal
    signals: dict[str, Decimal] = Field(
        default_factory=dict,
        description="Per-source estimates, e.g. {'comps': 2100, 'psf': 2050, 'haircut': 1980}.",
    )
    divergence_flag: bool = Field(
        default=False,
        description="True when signals disagree beyond threshold — review manually.",
    )


# --------------------------------------------------------------------------- #
# Assumptions: every knob the engine uses. No magic numbers in the math.
# --------------------------------------------------------------------------- #

class Assumptions(BaseModel):
    # Operating
    physical_vacancy: float = 0.05          # submarket-driven
    credit_loss: float = 0.01               # tenant-quality-driven (kept separate)
    mgmt_fee: float = 0.08                  # of effective gross income
    maintenance_pct: float = 0.05           # of EGI, ongoing (separate from capex reserve)
    insurance_annual: Decimal = Decimal(1800)
    other_opex_annual: Decimal = Decimal(600)

    # CapEx reserve (sinking fund); component lifespans in years.
    roof_life: int = 25
    roof_cost: Decimal = Decimal(12000)
    hvac_life: int = 18
    hvac_cost: Decimal = Decimal(7000)
    water_heater_life: int = 12
    water_heater_cost: Decimal = Decimal(1500)
    flooring_life: int = 20
    flooring_cost: Decimal = Decimal(5000)
    electrical_life: int = 50
    electrical_cost: Decimal = Decimal(8000)
    plumbing_life: int = 50
    plumbing_cost: Decimal = Decimal(6000)

    # Acquisition / disposition
    closing_cost_pct: float = 0.03          # of purchase price
    rehab_budget: Decimal = Decimal(0)
    selling_cost_pct: float = 0.07          # of exit price

    # Growth
    rent_growth: float = 0.03
    expense_growth: float = 0.03
    hold_years: int = 5

    # Exit — exit cap must reflect a spread over entry, never equal it.
    exit_cap_rate: Optional[float] = None   # if None, derive as entry_cap + spread
    exit_cap_spread_bps: int = 75

    # Taxes — post-sale reassessment.
    reassess_on_sale: bool = True
    assessment_ratio: float = 1.0           # assessed / market
    millage_rate: float = 0.012             # effective property tax rate on assessed value

    # Debt
    ltv: float = 0.75
    interest_rate: float = 0.07
    amort_years: int = 30
    stress_rate_bps: int = 100              # DSCR tested at rate + this

    # Gates / hurdles
    min_rent_to_price: float = 0.008        # 0.8% / month
    min_cash_on_cash: float = 0.06
    min_dscr: float = 1.25
    min_yoc_exit_spread_bps: int = 150
    min_levered_irr: float = 0.15


# --------------------------------------------------------------------------- #
# Outputs: the underwriting result and the gate verdicts.
# --------------------------------------------------------------------------- #

class GateResult(BaseModel):
    name: str
    value: float
    threshold: float
    passed: bool
    note: str = ""


class UnderwritingResult(BaseModel):
    property_id: str
    rent: RentEstimate

    # Year-0 economics
    all_in_basis: Decimal                   # price + closing + rehab
    going_in_noi: Decimal
    going_in_cap_rate: float
    yield_on_cost: float

    # Levered returns
    cash_on_cash: float
    dscr: float
    dscr_stressed: float
    levered_irr: float
    equity_multiple: float
    break_even_occupancy: float

    # Exit
    exit_cap_rate: float
    exit_value: Decimal

    gates: list[GateResult] = Field(default_factory=list)

    @property
    def passed_all_gates(self) -> bool:
        return all(g.passed for g in self.gates)
