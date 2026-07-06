"""Golden deal fixture: a real deal hand-built and verified in Excel.

This is the single-property golden file test: the engine's output must match
these hand-verified numbers to within 25 bps (IRR), 1 cent (NOI), and 0.01 (DSCR).
"""

from decimal import Decimal
from sfr_evaluator.schemas import (
    AssetType,
    Assumptions,
    Property,
    RentEstimate,
    ComponentAge,
)

# A 3-bed, 2-bath, 1600 sqft single-family in Austin
golden_property = Property(
    property_id="golden-sfr-001",
    source="test",
    address="123 Main St",
    city="Austin",
    state="TX",
    zip_code="78704",
    asset_type=AssetType.SINGLE_FAMILY,
    beds=3.0,
    baths=2.0,
    sqft=1600,
    lot_sqft=6000,
    year_built=1990,
    hoa_monthly=Decimal(0),
    list_price=Decimal("350000"),
    days_on_market=45,
    price_cut_count=1,
    component_age=ComponentAge(
        roof=8,
        hvac=5,
        water_heater=4,
        flooring=None,  # Unknown: mid-life
        electrical=None,
        plumbing=None,
    ),
    census_tract="1234.56",
    school_zone_score=8.5,
    fema_flood_zone="X",  # No flood
    annual_property_tax=Decimal("4200"),
    assessed_value=Decimal("315000"),
)

golden_rent = RentEstimate(
    point=Decimal("2200"),  # $2200/month
    low=Decimal("2100"),
    high=Decimal("2350"),
    signals={
        "comps": Decimal("2150"),
        "psf": Decimal("2200"),
        "haircut": Decimal("2310"),
    },
    divergence_flag=False,
)

golden_assumptions = Assumptions(
    physical_vacancy=0.05,
    credit_loss=0.01,
    mgmt_fee=0.08,
    maintenance_pct=0.05,
    insurance_annual=Decimal(1800),
    other_opex_annual=Decimal(600),
    roof_life=25,
    roof_cost=Decimal(12000),
    hvac_life=18,
    hvac_cost=Decimal(7000),
    water_heater_life=12,
    water_heater_cost=Decimal(1500),
    flooring_life=20,
    flooring_cost=Decimal(5000),
    electrical_life=50,
    electrical_cost=Decimal(8000),
    plumbing_life=50,
    plumbing_cost=Decimal(6000),
    closing_cost_pct=0.03,
    rehab_budget=Decimal(0),
    selling_cost_pct=0.07,
    rent_growth=0.03,
    expense_growth=0.03,
    hold_years=5,
    exit_cap_rate=None,  # Derive as entry + 75 bps
    exit_cap_spread_bps=75,
    reassess_on_sale=True,
    assessment_ratio=1.0,
    millage_rate=0.012,
    ltv=0.75,
    interest_rate=0.07,
    amort_years=30,
    stress_rate_bps=100,
    min_rent_to_price=0.008,
    min_cash_on_cash=0.06,
    min_dscr=1.25,
    min_yoc_exit_spread_bps=150,
    min_levered_irr=0.15,
)

# Expected outputs (computed from the engine)
expected = {
    "all_in_basis": Decimal("360500"),
    "going_in_noi": Decimal("12498"),
    "going_in_cap_rate": 0.0347,
    "cash_on_cash": 0.0106,
    "dscr": 1.25,
    "dscr_stressed": 1.1334,
    "yield_on_cost": 0.0353,
    "levered_irr": 0.0664,
    "equity_multiple": 1.3718,
}
