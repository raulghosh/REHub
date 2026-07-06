"""Integration tests: end-to-end pipeline testing."""

import csv
import tempfile
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from sfr_evaluator.cli import cmd_screen
from sfr_evaluator.schemas import Assumptions


def test_cli_screen_integration():
    """Test the full screen command end-to-end."""
    # Create temporary files for input and output
    csv_content = """property_id,address,city,state,zip_code,beds,baths,sqft,list_price,asset_type
test-001,100 Test St,Austin,TX,78704,3,2,1600,350000,single_family
test-002,200 Test Ave,Austin,TX,78705,2,1,1200,280000,single_family
"""
    assumptions_data = {
        "physical_vacancy": 0.05,
        "credit_loss": 0.01,
        "mgmt_fee": 0.08,
        "maintenance_pct": 0.05,
        "insurance_annual": 1800,
        "other_opex_annual": 600,
        "roof_life": 25,
        "roof_cost": 12000,
        "hvac_life": 18,
        "hvac_cost": 7000,
        "water_heater_life": 12,
        "water_heater_cost": 1500,
        "flooring_life": 20,
        "flooring_cost": 5000,
        "electrical_life": 50,
        "electrical_cost": 8000,
        "plumbing_life": 50,
        "plumbing_cost": 6000,
        "closing_cost_pct": 0.03,
        "rehab_budget": 0,
        "selling_cost_pct": 0.07,
        "rent_growth": 0.03,
        "expense_growth": 0.03,
        "hold_years": 5,
        "exit_cap_rate": None,
        "exit_cap_spread_bps": 75,
        "reassess_on_sale": True,
        "assessment_ratio": 1.0,
        "millage_rate": 0.012,
        "ltv": 0.75,
        "interest_rate": 0.07,
        "amort_years": 30,
        "stress_rate_bps": 100,
        "min_rent_to_price": 0.008,
        "min_cash_on_cash": 0.06,
        "min_dscr": 1.25,
        "min_yoc_exit_spread_bps": 150,
        "min_levered_irr": 0.15,
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Write CSV
        csv_path = tmpdir / "listings.csv"
        with open(csv_path, "w") as f:
            f.write(csv_content)

        # Write assumptions
        assumptions_path = tmpdir / "assumptions.yaml"
        with open(assumptions_path, "w") as f:
            yaml.dump(assumptions_data, f)

        # Output file
        output_path = tmpdir / "queue.csv"

        # Create args object
        class Args:
            input = str(csv_path)
            assumptions = str(assumptions_path)
            out = str(output_path)
            rent_low = 0
            rent_mid = 2200
            rent_high = 0
            column_map = None
            command = "screen"

        args = Args()

        # Run screen command
        result = cmd_screen(args)
        assert result == 0, "Screen command should succeed"

        # Verify output file was created
        assert output_path.exists(), "Output CSV should be created"

        # Read and validate output
        with open(output_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 2, "Should have 2 properties in output"
        assert rows[0]["rank"] == "1", "First property should have rank 1"
        assert rows[0]["property_id"] in ["test-001", "test-002"]
        assert "levered_irr" in rows[0], "Output should have levered_irr"


def test_pipeline_with_different_rents():
    """Test that screening works with different rent assumptions."""
    csv_content = """property_id,address,city,state,zip_code,beds,baths,sqft,list_price
prop-high-rent,100 A St,Austin,TX,78704,3,2,1600,200000
"""
    assumptions_data = {
        "physical_vacancy": 0.05,
        "credit_loss": 0.01,
        "mgmt_fee": 0.08,
        "maintenance_pct": 0.05,
        "insurance_annual": 1800,
        "other_opex_annual": 600,
        "roof_life": 25,
        "roof_cost": 12000,
        "hvac_life": 18,
        "hvac_cost": 7000,
        "water_heater_life": 12,
        "water_heater_cost": 1500,
        "flooring_life": 20,
        "flooring_cost": 5000,
        "electrical_life": 50,
        "electrical_cost": 8000,
        "plumbing_life": 50,
        "plumbing_cost": 6000,
        "closing_cost_pct": 0.03,
        "rehab_budget": 0,
        "selling_cost_pct": 0.07,
        "rent_growth": 0.03,
        "expense_growth": 0.03,
        "hold_years": 5,
        "exit_cap_rate": None,
        "exit_cap_spread_bps": 75,
        "reassess_on_sale": True,
        "assessment_ratio": 1.0,
        "millage_rate": 0.012,
        "ltv": 0.75,
        "interest_rate": 0.07,
        "amort_years": 30,
        "stress_rate_bps": 100,
        "min_rent_to_price": 0.008,
        "min_cash_on_cash": 0.06,
        "min_dscr": 1.25,
        "min_yoc_exit_spread_bps": 150,
        "min_levered_irr": 0.15,
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        csv_path = tmpdir / "listings.csv"
        with open(csv_path, "w") as f:
            f.write(csv_content)

        assumptions_path = tmpdir / "assumptions.yaml"
        with open(assumptions_path, "w") as f:
            yaml.dump(assumptions_data, f)

        output_path = tmpdir / "queue.csv"

        class Args:
            input = str(csv_path)
            assumptions = str(assumptions_path)
            out = str(output_path)
            rent_low = 0
            rent_mid = 2000  # High rent to pass screening
            rent_high = 0
            column_map = None
            command = "screen"

        args = Args()
        result = cmd_screen(args)

        # Should still produce a result (even if it fails gates)
        assert result == 0
        assert output_path.exists()

        with open(output_path) as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 1
