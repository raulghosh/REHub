"""Data contracts: what a retail investor enters (`DealInput`) and what the model returns.

Rates are fractions (0.06 == 6%). Money is float dollars: this is a forecast built on
estimates, not a ledger. Fields left as None are derived — from the zip code's market data
or from the property itself — and every derived value is reported back in
`Result.assumptions` with its source, so nothing is a silent default.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class PropertyType(str, Enum):
    SINGLE_FAMILY = "single_family"
    TOWNHOUSE = "townhouse"
    CONDO = "condo"                  # HOA owns roof, exterior and structure
    MULTI_2_4 = "multi_2_4"          # residential financing, 2-4 units
    MULTI_5_PLUS = "multi_5_plus"    # commercial financing, 5+ units


# --------------------------------------------------------------------------- #
# Inputs
# --------------------------------------------------------------------------- #

class Unit(BaseModel):
    beds: int = Field(3, ge=0, le=12)
    baths: float = Field(2, ge=0, le=12)
    rent: float = Field(ge=0, le=100_000, description="Market rent, $/month (after any rehab).")


class KnownRepair(BaseModel):
    """A specific item from the inspection, beyond normal wear (e.g. a roof at end of life).
    Normal wear is already in the age-based upkeep reserve."""
    description: str = Field("Repair", max_length=80)
    cost: float = Field(ge=0, le=10_000_000, description="Today's dollars.")
    year: int = Field(0, ge=0, le=40, description="0 = at purchase (negotiate a credit).")


class Property(BaseModel):
    address: str = Field("", max_length=200)
    zip_code: str = Field(pattern=r"^\d{5}$")
    state: str = Field("", max_length=2, description="Two-letter code; filled from zip data if blank.")
    property_type: PropertyType = PropertyType.SINGLE_FAMILY
    year_built: int = Field(ge=1700, le=2100)
    sqft: float = Field(gt=100, le=2_000_000, description="Total finished living area, all units.")
    stories: int = Field(1, ge=1, le=60, description="Above-ground floors; sizes the roof.")
    units: list[Unit] = Field(min_length=1, max_length=500)
    hoa_monthly: float = Field(0, ge=0, le=100_000)
    hoa_history: list[float] = Field(default_factory=list, max_length=30,
                                     description="Past monthly dues, oldest first, one per year.")
    hoa_reserve_funded_pct: float | None = Field(None, ge=0, le=3, description="From the reserve study.")
    hoa_special_assessment: float = Field(0, ge=0, description="Approved or expected, total $ for this property.")
    hoa_assessment_year: int = Field(1, ge=0, le=40)


ComponentKey = Literal["roof", "hvac", "water_heater", "appliances", "flooring", "interior_paint",
                       "exterior", "windows", "electrical", "plumbing", "kitchen_bath"]


class ComponentAge(BaseModel):
    """A component whose age you know (inspection report, seller disclosure, permits)."""
    key: ComponentKey
    age: float = Field(ge=0, le=200)
    cost: float | None = Field(None, ge=0, description="Replacement cost today; default from the catalog.")
    life: float | None = Field(None, gt=0, le=150, description="Useful life in years; default from the catalog.")


class Components(BaseModel):
    roof_material: Literal["asphalt_3tab", "architectural", "metal", "tile", "slate", "flat"] = "architectural"
    roof_pitch: Literal["low", "medium", "steep"] = "medium"
    known_ages: list[ComponentAge] = Field(default_factory=list, max_length=20)


class Occupancy(BaseModel):
    """House hacking: live in one unit (or the whole house) first, then rent it."""
    owner_occupied: bool = False
    months: int = Field(12, ge=1, le=480, description="How long you live there.")
    rent_saved: float | None = Field(None, ge=0, description="Housing cost you avoid, $/mo. Default: that unit's rent.")


class Purchase(BaseModel):
    price: float = Field(gt=0, le=1e9, description="Asking price or your offer.")
    market_value: float | None = Field(None, gt=0, description="Appraisal/comps. Default: zip $/sqft x sqft.")
    closing_costs_pct: float = Field(0.015, ge=0, le=0.2,
                                     description="Title, escrow, recording, transfer tax, attorney.")
    inspection_costs: float | None = Field(None, ge=0, description="Home, sewer scope, termite. Default by units.")
    other_costs: float = Field(0, ge=0, description="Survey, HOA transfer, travel, etc.")
    seller_credits: float = Field(0, ge=0)
    known_repairs: list[KnownRepair] = Field(default_factory=list, max_length=50)
    inspection_done: bool = Field(False, description="Inspected already: enter its findings as known "
                                  "repairs; no expected surprises are added.")
    bargaining: Literal["auto", "buyers", "balanced", "sellers", "as_is"] = Field(
        "auto", description="Who pays for what the inspection finds. auto: as-is for a fixer-upper, "
                            "else from the zip's days on market.")


class Rehab(BaseModel):
    """Distressed / value-add: buy, renovate, rent, optionally refinance (BRRRR)."""
    budget: float = Field(ge=0, le=1e8)
    months: int = Field(3, ge=0, le=24, description="No rent while renovating.")
    contingency_pct: float = Field(0.15, ge=0, le=1, description="Allowance for overruns.")
    arv: float | None = Field(None, gt=0, description="After-repair value. Default: zip $/sqft x sqft.")
    effective_age_after: float | None = Field(None, ge=0, le=300,
                                                 description="Default: scaled down by rehab size.")
    holding_utilities_monthly: float = Field(250, ge=0)
    refinance: bool = False
    refi_month: int | None = Field(None, ge=1, le=240, description="Default: rehab + 6 months seasoning.")
    refi_ltv: float = Field(0.75, gt=0, le=1)
    refi_rate: float | None = Field(None, ge=0, le=0.3, description="Default: purchase loan rate.")
    refi_term_years: int = Field(30, ge=1, le=40)
    refi_cost_pct: float = Field(0.02, ge=0, le=0.1)


class Loan(BaseModel):
    type: Literal["conventional", "dscr", "commercial", "fha"] | None = Field(
        None, description="Default: conventional for 1-4 units, commercial for 5+.")
    credit_score: int = Field(740, ge=300, le=850)
    down_payment_pct: float = Field(0.25, ge=0, le=1, description="1.0 = all-cash purchase.")
    rate: float | None = Field(None, ge=0, le=0.3,
                               description="Your quote. Blank: priced from the weekly market rate.")
    base_rate: float | None = Field(None, ge=0, le=0.3, description="Override the weekly 30-yr market rate.")
    term_years: int | None = Field(None, ge=1, le=40, description="Amortization. Default 30 (commercial 25).")
    balloon_years: int | None = Field(None, ge=1, le=40, description="Commercial: refinance due. Default 10.")
    points_pct: float = Field(0, ge=0, le=0.1)
    lender_fees: float | None = Field(None, ge=0, description="Origination, underwriting, appraisal.")
    pmi_rate: float | None = Field(None, ge=0, le=0.05,
                                   description="Annual % of loan. Blank: by credit score and down payment.")


class Management(BaseModel):
    mode: Literal["self", "pm"] = "pm"
    pm_fee_pct: float = Field(0.09, ge=0, le=0.5, description="% of rent collected.")
    leasing_fee_pct: float = Field(0.75, ge=0, le=3, description="x one month's rent, per new lease.")
    renewal_fee: float = Field(200, ge=0)
    maintenance_markup_pct: float = Field(0.10, ge=0, le=1, description="PM markup on vendor work.")
    diy_pct: float = Field(0.25, ge=0, le=1, description="Self-managed: share of repair/turnover jobs you do.")
    hours_per_unit_month: float = Field(2, ge=0, le=200)
    hourly_value: float = Field(0, ge=0, le=10_000, description="$/hr for your time; 0 = not counted.")


class Operations(BaseModel):
    other_income_monthly: float = Field(0, ge=0, description="Laundry, parking, pet rent, storage.")
    vacancy_pct: float | None = Field(None, ge=0, le=1)
    credit_loss_pct: float = Field(0.01, ge=0, le=1, description="Unpaid rent, separate from vacancy.")
    lease_up_months: float = Field(1, ge=0, le=12, description="Vacant months before the first tenant.")
    avg_tenancy_years: float | None = Field(None, gt=0, le=30)
    turnover_cost: float | None = Field(None, ge=0, description="Per move-out per unit, today's $.")
    property_tax_annual: float | None = Field(None, ge=0, description="After reassessment at purchase.")
    property_tax_rate: float | None = Field(None, ge=0, le=0.1, description="Effective rate on price.")
    insurance_annual: float | None = Field(None, ge=0, description="Landlord (DP-3) policy quote.")
    flood_insurance_annual: float = Field(0, ge=0, description="Required in FEMA flood zones A/V.")
    utilities_monthly: float | None = Field(None, ge=0, description="Landlord-paid utilities.")
    other_expenses_annual: float | None = Field(None, ge=0, description="Accounting, licenses, pest, lawn.")
    replacement_cost_psf: float = Field(160, gt=0, le=2000,
                                        description="Rebuild cost (NAHB 2024 avg ~$162); drives upkeep & insurance.")
    upkeep_pct_override: float | None = Field(None, ge=0, le=0.2,
                                                 description="Replace the age-based upkeep curve.")
    known: list[str] = Field(default_factory=list, max_length=20,
                             description="Lines that are quotes/actuals (no estimate allowance): "
                                         "property_tax, insurance, hoa, utilities, other, closing, inspection.")
    compliance: dict[str, bool] = Field(default_factory=dict,
                                        description="Turn checklist items on/off; unset = on when it applies.")


class Growth(BaseModel):
    """Each line grows with its own long-run index, not one blanket inflation rate."""
    general_inflation: float = Field(0.025, ge=-0.1, le=0.3, description="CPI-U: admin/other costs, tax brackets.")
    rent: float = Field(0.03, ge=-0.2, le=0.3, description="CPI rent of primary residence.")
    appreciation: float | None = Field(None, ge=-0.2, le=0.3, description="Default: zip-adjusted long run.")
    property_tax: float | None = Field(None, ge=-0.2, le=0.3, description="Default: = appreciation.")
    insurance: float | None = Field(None, ge=-0.2, le=0.5, description="Default: zip trend, else 5%.")
    maintenance: float = Field(0.035, ge=-0.2, le=0.3, description="Construction labor + materials.")
    hoa: float | None = Field(None, ge=-0.2, le=0.3, description="Default: your HOA's own history, else "
                                                                 "its cost mix (insurance + upkeep).")
    utilities: float = Field(0.035, ge=-0.2, le=0.3)


class TaxProfile(BaseModel):
    filing_status: Literal["single", "mfj"] = "mfj"
    household_income: float = Field(150_000, ge=0, le=1e9, description="MAGI before this property.")
    income_growth: float | None = Field(None, ge=-0.2, le=0.3, description="Default: general inflation.")
    state_rate: float = Field(0.05, ge=0, le=0.2, description="Marginal state income tax rate.")
    real_estate_professional: bool = Field(False, description="REPS + material participation.")
    active_participation: bool = Field(True, description="Unlocks the $25k passive-loss allowance.")
    land_pct: float | None = Field(None, ge=0, le=1, description="Non-depreciable share. Use assessor split.")
    cost_seg_pct: float = Field(0, ge=0, le=0.6, description="Share of building reclassified to 5-15 yr.")
    bonus_depreciation_pct: float = Field(1.0, ge=0, le=1, description="100% for property acquired after 1/19/2025.")
    exchange_1031: bool = Field(False, description="Defer the gain into a replacement property.")


class Exit(BaseModel):
    hold_years: int = Field(10, ge=1, le=40)
    selling_cost_pct: float = Field(0.07, ge=0, le=0.2, description="Commissions + seller closing costs.")


class Targets(BaseModel):
    """Your buy box. The max offer is the highest price meeting every target, then
    discounted by the margin of safety."""
    margin_of_safety_pct: float = Field(0.10, ge=0, le=0.9)
    estimate_allowance_pct: float = Field(0.10, ge=0, le=1, description="Added to every estimated expense.")
    min_cash_on_cash: float | None = Field(0.06, ge=-1, le=1)
    min_monthly_cash_flow_per_unit: float | None = Field(100, ge=-100_000, le=100_000)
    min_dscr: float | None = Field(1.20, ge=0, le=10)
    min_irr: float | None = Field(0.10, ge=-1, le=1, description="After-tax IRR.")


class DealInput(BaseModel):
    property: Property
    purchase: Purchase
    rehab: Rehab | None = None
    components: Components = Field(default_factory=Components)
    occupancy: Occupancy = Field(default_factory=Occupancy)
    loan: Loan = Field(default_factory=Loan)
    management: Management = Field(default_factory=Management)
    operations: Operations = Field(default_factory=Operations)
    growth: Growth = Field(default_factory=Growth)
    tax: TaxProfile = Field(default_factory=TaxProfile)
    exit: Exit = Field(default_factory=Exit)
    targets: Targets = Field(default_factory=Targets)

    @model_validator(mode="after")
    def _default_loan_type(self) -> DealInput:
        if self.loan.type is None:
            self.loan.type = "commercial" if self.property.property_type is PropertyType.MULTI_5_PLUS else "conventional"
        return self


# --------------------------------------------------------------------------- #
# Outputs
# --------------------------------------------------------------------------- #

class Assumption(BaseModel):
    label: str
    value: str
    source: str


class YearRow(BaseModel):
    year: int
    gross_rent: float
    other_income: float
    vacancy_loss: float
    egi: float
    property_tax: float
    insurance: float
    hoa: float
    utilities: float
    other: float
    management: float
    leasing: float
    upkeep: float          # age-based repairs + capex reserve
    turnover: float
    known_repairs: float   # one-time items: inspection repairs, component replacements, assessments
    compliance: float      # recurring regulatory costs
    owner_time: float      # non-cash; only when you value your time
    holding: float         # rehab-period utilities
    opex: float
    noi: float
    debt_service: float    # P&I + PMI
    interest: float
    principal: float
    pmi: float
    refi_cash_out: float
    housing_saved: float = 0   # house hack: rent you don't pay elsewhere while living there
    cash_flow: float       # before tax
    taxable_income: float = 0
    tax: float = 0         # incremental tax; negative = savings
    suspended_losses: float = 0
    cash_flow_after_tax: float = 0
    loan_balance: float
    value: float
    equity: float


class Acquisition(BaseModel):
    price: float
    down_payment: float
    loan_amount: float
    closing_costs: float
    lender_costs: float
    inspections: float
    other_costs: float
    seller_credits: float
    rehab: float
    repairs_at_purchase: float
    compliance_costs: float = 0
    inspection_risk: float = 0     # expected cost of inspection findings that falls on you
    total_cash_needed: float
    lender_reserves: float  # liquidity lenders expect (6 months PITI), not a cost


class Sale(BaseModel):
    year: int
    price: float
    selling_costs: float
    loan_payoff: float
    proceeds_before_tax: float
    adjusted_basis: float
    gain: float
    depreciation_recapture: float
    capital_gain: float
    suspended_losses_released: float
    tax: float
    proceeds_after_tax: float
    deferred_tax: float      # 1031 only


class Metrics(BaseModel):
    market_value: float
    cap_rate: float               # stabilized NOI / market value
    cap_rate_on_cost: float       # stabilized NOI / all-in cost
    cash_on_cash: float | None  # None when no cash is left in the deal
    monthly_cash_flow: float
    monthly_cash_flow_per_unit: float
    dscr: float | None
    break_even_occupancy: float
    gross_rent_multiplier: float
    rent_to_price: float          # monthly rent / (price + rehab); the "1% rule"
    expense_ratio: float          # opex / effective gross income
    upkeep_pct_of_value: float
    upkeep_pct_of_rent: float
    irr_before_tax: float | None
    irr_after_tax: float | None
    equity_multiple: float
    cash_left_in_deal: float
    house_hack_monthly: float | None = None   # your net monthly cost (or income) while living there


class ReturnBreakdown(BaseModel):
    operating_cash_flow: float
    principal_paydown: float
    appreciation: float
    equity_at_purchase: float
    transaction_costs: float
    taxes: float
    total: float


class TargetCheck(BaseModel):
    name: str
    threshold: float
    value: float | None
    passed: bool
    max_price: float | None    # highest price that still meets this target


class Offer(BaseModel):
    price: float
    market_value: float
    investment_value: float | None
    limited_by: str
    margin_of_safety_pct: float
    max_offer: float | None
    margin_at_price: float | None   # 1 - price / investment value
    verdict: Literal["buy", "negotiate", "pass"]
    summary: str
    rule_70: float | None = None    # distressed: 70% of ARV minus rehab
    walk_away: float | None = None  # above this price the verdict is pass (min of investment value, ceiling)
    targets: list[TargetCheck]


class Financing(BaseModel):
    loan_type: str
    base_rate: float
    base_as_of: str
    rate: float
    rate_steps: list[Assumption]       # how the rate was built
    mortgage_insurance: float          # annual % (PMI or FHA MIP)
    mortgage_insurance_note: str
    max_ltv: float | None
    eligible: bool
    notes: list[str]


class DownPaymentOption(BaseModel):
    down_pct: float
    eligible: bool
    note: str
    rate: float | None = None
    mortgage_insurance: float | None = None
    cash_needed: float | None = None
    monthly_cash_flow: float | None = None
    cash_on_cash: float | None = None
    irr_after_tax: float | None = None


class ExitYear(BaseModel):
    year: int
    value: float
    loan_balance: float
    profit_if_sold: float       # after selling costs and all taxes, net of cash invested
    irr_if_sold: float | None
    multiple_if_sold: float
    wealth_if_kept: float       # equity + after-tax cash collected - cash invested (no sale)


class ComponentRow(BaseModel):
    name: str
    age: float | None           # None: unknown, handled by the age-based curve
    life: float
    cost_today: float
    next_replacement_year: int | None   # 0 = needed at purchase


class ComplianceRow(BaseModel):
    key: str
    label: str
    included: bool
    one_time: float
    annual: float
    note: str


class InspectionRow(BaseModel):
    key: str
    label: str
    probability: float
    cost: float
    note: str


class InspectionRisk(BaseModel):
    done: bool
    market: str                  # buyer's / balanced / seller's market, or as-is sale
    basis: str                   # why that market
    buyer_share: float           # share of the repair cost you typically end up paying
    p_any: float                 # chance the inspection finds at least one of these
    expected_cost: float         # sum(probability x cost), whoever pays
    expected_to_you: float       # x your share; 0 once inspected
    bad_case: float              # the costliest single finding, your share
    rows: list[InspectionRow]


class Scenario(BaseModel):
    name: str
    monthly_cash_flow: float
    cash_on_cash: float | None
    irr_after_tax: float | None


class MarketInfo(BaseModel):
    zip: str
    city: str
    state: str
    metro: str
    sales_12m: int | None
    median_price: float | None
    median_dom: float | None
    ppsf: float | None           # for this property type
    list_ppsf: float | None
    appreciation_trend: float | None
    appreciation_vs_us: float | None
    trend_years: str
    rent_by_beds: dict[int, float] = Field(default_factory=dict)
    tax_rate: float | None = None
    rental_vacancy: float | None = None
    median_year_built: float | None = None
    median_income: float | None = None
    as_of: str
    sources: list[str]


class Result(BaseModel):
    offer: Offer
    metrics: Metrics
    returns: ReturnBreakdown
    financing: Financing
    down_payment_options: list[DownPaymentOption]
    exit_timeline: list[ExitYear]
    components: list[ComponentRow]
    compliance: list[ComplianceRow]
    inspection: InspectionRisk
    acquisition: Acquisition
    stabilized: YearRow
    years: list[YearRow]
    sale: Sale
    management: list[Scenario]
    stress: list[Scenario]
    assumptions: list[Assumption]
    market: MarketInfo | None
    warnings: list[str]
