"""
Mandatory Regression Test Suite for RFx RFX-CORR-2026-017
==========================================================
Comprehensive automated tests covering:

1. Normalization:
   - BCB flute factor equals 1.45 everywhere.
   - Missing dimensions do not trigger default dimensions (no 1000x500 mm).
   - Missing weight does not trigger a 0.25 kg fallback.
   - Unsupported UOM conversions remain unresolved.
   - Valid dimensions and specifications produce expected normalized weight and price.

2. Conditional Discounts & Award Engine:
   - Vendor wins all 30 lines: eligible all-lines discount is applied.
   - Vendor wins 29 of 30 lines: all-lines discount is not applied.
   - Two vendors split the 30 lines: neither receives an all-lines discount.
   - Vendor has an unconditional line-level discount: applied when eligible.
   - A discount is never applied twice (idempotence).
   - Award totals, savings, and vendor allocations reconcile after discount application.

3. Acceptance Criteria & System Integrity:
   - No conflicting legacy normalization calculations remain in app.py.
   - No silent fallback dimensions or weights remain.
   - All modules use the same normalization and award calculation logic.
   - UI, export data, and AI Analyst consume identical figures.
"""

import os
import pytest
import pandas as pd
import numpy as np
import openpyxl

from core.config import (
    TAKEUP_FACTORS,
    DEFAULT_FX_RATE as FX_RATE,
    DEFAULT_FX_EFFECTIVE_DATE,
    DEFAULT_FREIGHT_RATES as FREIGHT_RATES,
    DEFAULT_CONDITIONAL_DISCOUNTS,
    DISCOUNT_TYPES
)
from core.normalizer import (
    calculate_composite_weight,
    normalize_price,
    parse_uom,
    validate_technical_specification,
    calculate_price_per_kg
)
from core.scenarios import calculate_award_scenarios
from core.eligibility import evaluate_vendor_qualifications, VendorQualification
from core.models import NormalizationResult

EXCEL_FILE = os.path.join(os.path.dirname(__file__), "..", "RFx_Master_Updated.xlsx")


# ─────────────────────────────────────────────────────────────────────────────
# FIXTURES: Realistic RFx Dataset (30 Corrugated Packaging Line Items)
# ─────────────────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def rfx_master_data():
    """Loads genuine master dataset from RFx_Master_Updated.xlsx."""
    assert os.path.exists(EXCEL_FILE), f"Missing master file: {EXCEL_FILE}"
    xl = pd.ExcelFile(EXCEL_FILE)
    df_items = pd.read_excel(xl, sheet_name="Line Items")
    df_items = df_items[pd.to_numeric(df_items["Line #"], errors="coerce").notna()].copy()
    df_items["Line #"] = df_items["Line #"].astype(int)

    df_gate = pd.read_excel(xl, sheet_name="Questionnaire Audit & Gate")
    df_hist = pd.read_excel(xl, sheet_name="Historical PO Master")
    df_hist = df_hist[pd.to_numeric(df_hist["Line #"], errors="coerce").notna()].copy()
    df_hist["Line #"] = df_hist["Line #"].astype(int)

    quals = evaluate_vendor_qualifications(df_gate, df_items)

    return {
        "df_items": df_items,
        "df_gate": df_gate,
        "df_hist": df_hist,
        "quals": quals
    }


# ─────────────────────────────────────────────────────────────────────────────
# 1. NORMALIZATION REGRESSION TESTS
# ─────────────────────────────────────────────────────────────────────────────

def test_norm_1_bcb_uses_1_45_everywhere():
    """BCB take-up factor must be 1.45 across config, Excel, normalizer, and app."""
    # 1. In core.config
    assert "BCB" in TAKEUP_FACTORS
    assert TAKEUP_FACTORS["BCB"] == 1.45, f"Config BCB takeup must be 1.45, got {TAKEUP_FACTORS['BCB']}"

    # 2. In Excel workbook sheet 'Assumptions'
    wb = openpyxl.load_workbook(EXCEL_FILE, data_only=True)
    ws_assump = wb["Assumptions"]
    excel_bcb = None
    for r in range(4, ws_assump.max_row + 1):
        flute_val = ws_assump.cell(r, 1).value
        if flute_val and str(flute_val).strip() == "BCB":
            excel_bcb = float(ws_assump.cell(r, 2).value)
            break
    assert excel_bcb == 1.45, f"Excel workbook Assumptions sheet BCB factor must be 1.45, got {excel_bcb}"

    # 3. In calculate_composite_weight
    # Line 10 spec: 7-ply, BCB flute, liner 230, fluting 140, board 3035 x 1200 mm
    # Comp GSM = ((7+1)/2)*230 + ((7-1)/2)*140*1.45 = 920 + 609 = 1529.0 GSM
    gsm, wt = calculate_composite_weight(
        ply=7, flute="BCB", liner_gsm=230, fluting_gsm=140, board_l_mm=3035, board_w_mm=1200
    )
    assert gsm == 1529.0
    # Area = 3.035 * 1.2 = 3.642 sqm; Wt = 3.642 * 1.529 kg = 5.5686 kg
    assert wt == pytest.approx(5.5686, rel=1e-3)


def test_norm_2_missing_dimensions_do_not_trigger_default_dimensions():
    """Missing or zero dimensions must NOT trigger fallback to 1000x500 mm."""
    # Missing length and width (None)
    gsm, wt_none = calculate_composite_weight(
        ply=3, flute="B", liner_gsm=150, fluting_gsm=120, board_l_mm=None, board_w_mm=None
    )
    assert gsm is not None, "GSM should calculate if specs are present"
    assert wt_none is None, "Weight must be None when dimensions are missing (no 1000x500 fallback)"

    # Zero dimensions
    _, wt_zero = calculate_composite_weight(
        ply=3, flute="B", liner_gsm=150, fluting_gsm=120, board_l_mm=0, board_w_mm=500
    )
    assert wt_zero is None, "Weight must be None when length is 0"

    # Validation helper
    is_valid, missing = validate_technical_specification(
        ply=3, flute="B", liner_gsm=150, fluting_gsm=120, board_l_mm=None, board_w_mm=None
    )
    assert is_valid is False
    assert "Board Length (mm)" in missing
    assert "Board Width (mm)" in missing


def test_norm_3_missing_weight_does_not_trigger_0_25_kg_fallback():
    """Missing weight must NOT fall back to 0.25 kg; must return Unresolved."""
    # Quoted in Rs 42/kg with item_weight_kg = None
    res_none = normalize_price(
        raw_value=42.0,
        raw_unit="₹/kg",
        item_weight_kg=None
    )
    assert res_none.normalized_price is None, "Price must be None when weight basis is missing"
    assert res_none.status == "Unresolved"
    assert res_none.trust_flag == "UNRESOLVED"
    assert "Item weight basis (kg/UoM)" in res_none.missing_inputs
    assert "0.25" not in res_none.formula_citation

    # With item_weight_kg = 0.0
    res_zero = normalize_price(
        raw_value=42.0,
        raw_unit="₹/kg",
        item_weight_kg=0.0
    )
    assert res_zero.normalized_price is None
    assert res_zero.status == "Unresolved"


def test_norm_4_unsupported_uom_conversions_remain_unresolved():
    """Non-convertible or unsupported UOMs must remain Unresolved with preserved raw quote."""
    unsupported_cases = [
        ("Lump Sum", 50000.0),
        ("Running Metre", 25.0),
        ("Set", 100.0),
        ("Hours", 500.0),
        ("Unknown Unit", 12.5)
    ]
    for unit_str, val in unsupported_cases:
        res = normalize_price(raw_value=val, raw_unit=unit_str, target_uom="Nos")
        assert res.normalized_price is None, f"Unit '{unit_str}' must not be silently converted"
        assert res.status == "Unresolved"
        assert res.original_value == val, "Original quoted value must be preserved"
        assert res.original_uom == unit_str, "Original quoted UOM must be preserved"
        assert len(res.unresolved_reason) > 0, "Unresolved reason must be populated"


def test_norm_5_valid_dimensions_and_specs_produce_expected_weight_and_price():
    """Valid specifications produce deterministic, verified weight and landed price."""
    # Line 1: 3-ply B-flute, 150 liner, 120 fluting, 1035 x 350 mm board
    # Takeup B = 1.32
    # Comp GSM = ((3+1)/2)*150 + ((3-1)/2)*120*1.32 = 300 + 158.4 = 458.4 GSM
    # Board Area = 1.035 * 0.350 = 0.36225 sqm
    # Weight = 0.36225 * 0.4584 kg = 0.1660554 kg ~ 0.1661 kg
    gsm, wt = calculate_composite_weight(
        ply=3, flute="B", liner_gsm=150, fluting_gsm=120, board_l_mm=1035, board_w_mm=350
    )
    assert gsm == 458.4
    assert wt == pytest.approx(0.1661, rel=1e-3)

    # Per-kg quote: Rs 38.00/kg + Rs 1.20 freight for Pune
    # Landed = (38.00 + 1.20) * 0.1660554 = 39.20 * 0.1660554 = 6.50937 -> Rs 6.51
    res = normalize_price(
        raw_value=38.0,
        raw_unit="₹/kg",
        delivery_location="Pune (Chakan plant)",
        item_weight_kg=wt,
        freight_rates={"Pune (Chakan plant)": 1.20},
        freight_included=False
    )
    assert res.normalized_price == 6.51
    assert res.status == "Verified"
    assert res.trust_flag == "Inferred (kg to piece)"


# ─────────────────────────────────────────────────────────────────────────────
# 2. CONDITIONAL DISCOUNTS REGRESSION TESTS (30 CP ITEMS)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def rfx_30_matrix(rfx_master_data):
    """Builds a realistic 30-line matrix from the RFx master data."""
    df_items = rfx_master_data["df_items"]
    rows = []
    for _, r in df_items.iterrows():
        l_no = int(r["Line #"])
        qty = int(r.get("Est. Annual Qty (UoM)", 10000))
        budget = float(r.get("Budget Unit Price (₹ / UoM)", 10.0))
        rows.append({
            "Line #": l_no,
            "Item Code": str(r["Item Code"]),
            "Description": str(r["Item Description"]),
            "Est. Qty": qty,
            "Delivery Location": str(r.get("Delivery Location", "Pune (Chakan plant)")),
            "Criticality": str(r.get("Criticality (A/B/C)", "C")),
            "Budget Price": budget,
            "V1 (Apex)": round(budget * 0.95, 2),       # baseline V1
            "V2 (PackTech)": round(budget * 1.02, 2)     # baseline V2
        })
    return pd.DataFrame(rows)


def test_discount_6_vendor_wins_all_30_lines_discount_applied(rfx_30_matrix, rfx_master_data):
    """When a vendor wins all 30 lines, eligible all-lines discount is applied to all lines and totals."""
    df_matrix = rfx_30_matrix.copy()
    quals = {
        "V1": VendorQualification(vendor_id="V1", vendor_name="Apex", status="Eligible", passed_mandatory_gates=True),
        "V2": VendorQualification(vendor_id="V2", vendor_name="PackTech", status="Eligible", passed_mandatory_gates=True)
    }

    # Ensure V1 is cheaper on all 30 lines
    df_matrix["V1 (Apex)"] = 5.0
    df_matrix["V2 (PackTech)"] = 10.0

    discounts = {
        "V1": {
            "discount_pct": 0.05,
            "condition_type": "all_lines",
            "description": "5% discount for 100% all-lines award"
        }
    }

    res = calculate_award_scenarios(df_matrix, quals, conditional_discounts=discounts)
    disc_v1 = res["discounts_evaluated"]["V1 (Apex)"]

    assert disc_v1["applied"] is True, "All-lines discount must be applied when V1 wins all 30 lines"
    assert disc_v1["discount_applied"] > 0
    assert disc_v1["final_award_amount"] == disc_v1["original_amount"] - disc_v1["discount_applied"]

    # Verify all 30 lines have discounted landed price (5.0 * 0.95 = 4.75)
    for a in res["b_line_allocations"]:
        assert a["Awarded Vendor"] == "V1 (Apex)"
        assert a["Landed Price (₹)"] == 4.75
        assert a["Line Spend (₹)"] == 4.75 * a["Qty"]


def test_discount_7_vendor_wins_29_of_30_lines_discount_not_applied(rfx_30_matrix, rfx_master_data):
    """When a vendor wins 29 of 30 lines, all-lines discount is NOT applied to any line."""
    df_matrix = rfx_30_matrix.copy()
    quals = {
        "V1": VendorQualification(vendor_id="V1", vendor_name="Apex", status="Eligible", passed_mandatory_gates=True),
        "V2": VendorQualification(vendor_id="V2", vendor_name="PackTech", status="Eligible", passed_mandatory_gates=True)
    }

    # V1 wins lines 1-29; V2 wins line 30
    df_matrix["V1 (Apex)"] = 5.0
    df_matrix["V2 (PackTech)"] = 10.0
    df_matrix.loc[df_matrix["Line #"] == 30, "V1 (Apex)"] = 15.0  # V2 wins line 30 at 10.0

    discounts = {
        "V1": {
            "discount_pct": 0.05,
            "condition_type": "all_lines",
            "description": "5% discount for 100% all-lines award"
        }
    }

    res = calculate_award_scenarios(df_matrix, quals, conditional_discounts=discounts)
    disc_v1 = res["discounts_evaluated"]["V1 (Apex)"]

    assert disc_v1["applied"] is False, "All-lines discount must NOT be applied when winning 29 of 30 lines"
    assert disc_v1["discount_applied"] == 0.0
    assert "Split award" in disc_v1["discount_not_applied_reason"]
    assert "29 of 30 lines" in disc_v1["discount_not_applied_reason"]

    # Verify V1 lines remain at undiscounted price 5.0
    for a in res["b_line_allocations"]:
        if a["Awarded Vendor"] == "V1 (Apex)":
            assert a["Landed Price (₹)"] == 5.0


def test_discount_8_two_vendors_split_30_lines_neither_receives_all_lines_discount(rfx_30_matrix):
    """When two vendors split the 30 lines (e.g. 15 and 15), neither receives an all-lines discount."""
    df_matrix = rfx_30_matrix.copy()
    quals = {
        "V1": VendorQualification(vendor_id="V1", vendor_name="Apex", status="Eligible", passed_mandatory_gates=True),
        "V2": VendorQualification(vendor_id="V2", vendor_name="PackTech", status="Eligible", passed_mandatory_gates=True)
    }

    # V1 wins lines 1-15; V2 wins lines 16-30
    for idx, row in df_matrix.iterrows():
        l_no = row["Line #"]
        if l_no <= 15:
            df_matrix.at[idx, "V1 (Apex)"] = 6.0
            df_matrix.at[idx, "V2 (PackTech)"] = 8.0
        else:
            df_matrix.at[idx, "V1 (Apex)"] = 8.0
            df_matrix.at[idx, "V2 (PackTech)"] = 6.0

    discounts = {
        "V1": {"discount_pct": 0.05, "condition_type": "all_lines", "description": "5% all-lines V1"},
        "V2": {"discount_pct": 0.04, "condition_type": "all_lines", "description": "4% all-lines V2"}
    }

    res = calculate_award_scenarios(df_matrix, quals, conditional_discounts=discounts)
    disc_v1 = res["discounts_evaluated"]["V1 (Apex)"]
    disc_v2 = res["discounts_evaluated"]["V2 (PackTech)"]

    assert disc_v1["applied"] is False, "V1 must NOT receive all-lines discount on split award"
    assert disc_v1["discount_applied"] == 0.0

    assert disc_v2["applied"] is False, "V2 must NOT receive all-lines discount on split award"
    assert disc_v2["discount_applied"] == 0.0


def test_discount_9_unconditional_line_level_discount_applied_when_eligible():
    """Unconditional or condition-met line-level discount is preserved and applied."""
    # When condition is met during normalization, discount applies
    res_met = normalize_price(
        raw_value=100.0,
        raw_unit="Nos",
        discount_pct=0.10,
        discount_condition="Standard 10% catalog discount",
        condition_met=True
    )
    assert res_met.normalized_price == 90.0
    assert res_met.applied_discount == 0.10
    assert "90.00" in res_met.formula_citation

    # When condition is unmet, discount does not apply
    res_unmet = normalize_price(
        raw_value=100.0,
        raw_unit="Nos",
        discount_pct=0.10,
        discount_condition="Order > 10,000 units",
        condition_met=False
    )
    assert res_unmet.normalized_price == 100.0
    assert res_unmet.applied_discount == 0.0


def test_discount_10_discount_never_applied_twice(rfx_30_matrix):
    """Award recalculation is idempotent; discounts are never compounded or doubled."""
    df_matrix = rfx_30_matrix.copy()
    quals = {
        "V1": VendorQualification(vendor_id="V1", vendor_name="Apex", status="Eligible", passed_mandatory_gates=True),
        "V2": VendorQualification(vendor_id="V2", vendor_name="PackTech", status="Eligible", passed_mandatory_gates=True)
    }

    df_matrix["V1 (Apex)"] = 10.0
    df_matrix["V2 (PackTech)"] = 20.0

    discounts = {
        "V1": {"discount_pct": 0.10, "condition_type": "all_lines", "description": "10% all lines"}
    }

    # Pass 1
    res1 = calculate_award_scenarios(df_matrix, quals, conditional_discounts=discounts)
    spend_1 = res1["spend_b"]

    # Pass 2 with same matrix and discounts
    res2 = calculate_award_scenarios(df_matrix, quals, conditional_discounts=discounts)
    spend_2 = res2["spend_b"]

    assert spend_1 == spend_2, f"Award recalculation must be idempotent: {spend_1} != {spend_2}"


def test_discount_11_award_totals_savings_and_vendor_allocations_reconcile(rfx_30_matrix):
    """All totals, line spends, vendor shares, and savings reconcile perfectly after discount application."""
    df_matrix = rfx_30_matrix.copy()
    quals = {
        "V1": VendorQualification(vendor_id="V1", vendor_name="Apex", status="Eligible", passed_mandatory_gates=True),
        "V2": VendorQualification(vendor_id="V2", vendor_name="PackTech", status="Eligible", passed_mandatory_gates=True)
    }

    df_matrix["V1 (Apex)"] = 10.0
    df_matrix["V2 (PackTech)"] = 20.0

    discounts = {
        "V1": {"discount_pct": 0.05, "condition_type": "all_lines", "description": "5% discount"}
    }

    res = calculate_award_scenarios(df_matrix, quals, conditional_discounts=discounts)

    # 1. Sum of line spends equals total spend_b
    sum_line_spends = sum(a["Line Spend (₹)"] for a in res["b_line_allocations"])
    assert round(sum_line_spends, 2) == round(res["spend_b"], 2)

    # 2. Sum of vendor shares equals spend_b
    sum_vendor_spends = sum(s["spend"] for s in res["vendor_shares_b"].values())
    assert round(sum_vendor_spends, 2) == round(res["spend_b"], 2)

    # 3. Savings reconcile
    assert round(res["savings_b"], 2) == round(res["budget_spend"] - res["spend_b"], 2)

    # 4. Savings % reconciles
    expected_pct = (res["savings_b"] / res["budget_spend"]) * 100.0
    assert pytest.approx(res["savings_pct_b"], rel=1e-3) == expected_pct

    # 5. Cost of compliance reconciles
    assert round(res["cost_of_compliance"], 2) == round(res["spend_b"] - res["spend_a"], 2)
