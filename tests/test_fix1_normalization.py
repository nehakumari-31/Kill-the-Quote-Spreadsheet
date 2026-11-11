"""
Pytest test suite for Fix 1: Procurement Price Normalization and RFx Assumptions.

Verifies:
1. BCB factor equals 1.45.
2. All other flute factors match the RFx source (B=1.32, C=1.43, E=1.25, BC=1.38).
3. Per-1,000 conversion.
4. Per-kg conversion with known and missing weight.
5. Foreign currency conversion.
6. Freight included versus extra.
7. GST included versus excluded.
8. Conditional discount on a split award.
9. Unsupported UOM.
10. Missing conversion data.
"""

import os
import pytest
import pandas as pd
import openpyxl

from core.config import (
    TAKEUP_FACTORS,
    DEFAULT_FX_RATE,
    DEFAULT_FX_EFFECTIVE_DATE,
    DEFAULT_FREIGHT_RATES
)
from core.normalizer import (
    calculate_composite_weight,
    normalize_price,
    parse_uom
)
from core.models import NormalizationResult

EXCEL_PATH = os.path.join(os.path.dirname(__file__), "..", "RFx_Master_Updated.xlsx")


# 1. BCB factor equals 1.45
def test_1_bcb_factor_equals_1_45():
    # Verify in Python constant source of truth
    assert "BCB" in TAKEUP_FACTORS, "BCB must be in TAKEUP_FACTORS"
    assert TAKEUP_FACTORS["BCB"] == 1.45, f"Expected BCB takeup 1.45, got {TAKEUP_FACTORS['BCB']}"

    # Verify in Excel source workbook
    wb = openpyxl.load_workbook(EXCEL_PATH, data_only=True)
    ws_assump = wb["Assumptions"]
    # Look for BCB row in Assumptions sheet
    bcb_found = False
    for r in range(4, ws_assump.max_row + 1):
        flute_val = ws_assump.cell(r, 1).value
        if flute_val and str(flute_val).strip() == "BCB":
            takeup_val = ws_assump.cell(r, 2).value
            assert float(takeup_val) == 1.45, f"Expected Excel BCB takeup 1.45, got {takeup_val}"
            bcb_found = True
            break
    assert bcb_found, "BCB flute not found in Assumptions sheet"

    # Verify composite weight calculation with BCB factor
    # Line 10: 7-ply, 230 liner, 140 fluting, 3035x1200 board
    # Comp GSM = ((7+1)/2)*230 + ((7-1)/2)*140*1.45 = 920 + 609 = 1529.0
    gsm, wt = calculate_composite_weight(
        ply=7, flute="BCB", liner_gsm=230, fluting_gsm=140, board_l_mm=3035, board_w_mm=1200
    )
    assert gsm == 1529.0
    # Area = 3.035 * 1.2 = 3.642 sqm. Wt = 3.642 * 1.529 = 5.5686 kg
    assert wt == pytest.approx(5.5686, rel=1e-3)


# 2. All other flute factors match the RFx source
def test_2_all_other_flute_factors_match_rfx_source():
    wb = openpyxl.load_workbook(EXCEL_PATH, data_only=True)
    ws_assump = wb["Assumptions"]
    excel_factors = {}
    for r in range(5, 10):
        f = ws_assump.cell(r, 1).value
        v = ws_assump.cell(r, 2).value
        if f and v:
            excel_factors[str(f).strip()] = float(v)

    # Expected standard RFx factors
    expected = {
        "B": 1.32,
        "C": 1.43,
        "E": 1.25,
        "BC": 1.38,
        "BCB": 1.45
    }
    assert TAKEUP_FACTORS == expected, f"Config TAKEUP_FACTORS mismatch: {TAKEUP_FACTORS}"
    for flute, factor in expected.items():
        assert excel_factors.get(flute) == factor, f"Mismatch for flute {flute} in workbook: {excel_factors.get(flute)}"


# 3. Per-1,000 conversion
def test_3_per_1000_conversion():
    # Quoted Rs 6,120 per 1,000 Nos -> 6.12 per piece
    res = normalize_price(
        raw_value=6120.0,
        raw_unit="per 1,000 Nos",
        raw_currency="INR"
    )
    assert isinstance(res, NormalizationResult)
    assert res.normalized_price == 6.12
    assert res.status == "Verified"
    assert res.trust_flag == "Inferred (/1000 to piece)"
    assert res.original_value == 6120.0
    assert "÷ 1,000" in res.formula_citation
    assert res.applied_formula == "Price / 1000"

    # Also test string input with comma
    res_str = normalize_price(
        raw_value="10,350",
        raw_unit="per 1000",
        raw_currency="INR"
    )
    assert res_str.normalized_price == 10.35
    assert res_str.status == "Verified"


# 4. Per-kg conversion with known and missing weight
def test_4_per_kg_conversion_known_and_missing_weight():
    # A. Known weight: rate Rs 38.00/kg, delivery Pune (freight 1.20/kg), weight 0.1661 kg
    # Landed = (38.00 + 1.20) * 0.1661 = 39.20 * 0.1661 = 6.51
    res_known = normalize_price(
        raw_value=38.0,
        raw_unit="₹/kg",
        delivery_location="Pune (Chakan plant)",
        item_weight_kg=0.1661,
        freight_rates={"Pune (Chakan plant)": 1.20},
        freight_included=False
    )
    assert res_known.normalized_price == 6.51
    assert res_known.status == "Verified"
    assert res_known.trust_flag == "Inferred (kg to piece)"
    assert res_known.original_value == 38.0
    assert res_known.freight_treatment == "Extra"
    assert "0.1661" in res_known.formula_citation

    # B. Missing weight (None): MUST set normalized price to None and status to Unresolved
    res_missing_none = normalize_price(
        raw_value=38.0,
        raw_unit="₹/kg",
        item_weight_kg=None
    )
    assert res_missing_none.normalized_price is None
    assert res_missing_none.status == "Unresolved"
    assert res_missing_none.trust_flag == "UNRESOLVED"
    assert "Item weight basis (kg/UoM)" in res_missing_none.missing_inputs
    assert "Weight missing" in res_missing_none.formula_citation
    assert "Buyer review required" in res_missing_none.unresolved_reason

    # C. Missing weight (0 or negative): MUST NOT use any invented weight (e.g. 0.25 kg)
    res_missing_zero = normalize_price(
        raw_value=38.0,
        raw_unit="₹/kg",
        item_weight_kg=0.0
    )
    assert res_missing_zero.normalized_price is None
    assert res_missing_zero.status == "Unresolved"
    assert "Item weight basis (kg/UoM)" in res_missing_zero.missing_inputs


# 5. Foreign currency conversion
def test_5_foreign_currency_conversion():
    # Quoted USD 0.1000 at explicit exchange rate 84.50 with effective date 19-Nov-2026
    res_usd = normalize_price(
        raw_value=0.10,
        raw_unit="Nos",
        raw_currency="USD",
        fx_rate=84.50,
        fx_effective_date="19-Nov-2026"
    )
    assert res_usd.normalized_price == 8.45
    assert res_usd.status == "Verified"
    assert res_usd.trust_flag == "Inferred (USD to INR)"
    assert res_usd.original_currency == "USD"
    assert res_usd.exchange_rate == 84.50
    assert res_usd.exchange_rate_date == "19-Nov-2026"
    assert "84.50" in res_usd.formula_citation

    # Foreign currency with missing exchange rate -> MUST be Unresolved
    res_missing_fx = normalize_price(
        raw_value=0.10,
        raw_unit="Nos",
        raw_currency="EUR",
        fx_rate=None
    )
    assert res_missing_fx.normalized_price is None
    assert res_missing_fx.status == "Unresolved"
    assert "Configured exchange rate (FX Rate)" in res_missing_fx.missing_inputs
    assert "Buyer review required" in res_missing_fx.unresolved_reason


# 6. Freight included versus extra
def test_6_freight_included_versus_extra():
    # Base rate Rs 40.00/kg, Bhiwandi DC (freight 2.20/kg), weight 0.50 kg
    # A. Freight Extra: (40.00 + 2.20) * 0.50 = 21.10
    res_extra = normalize_price(
        raw_value=40.0,
        raw_unit="₹/kg",
        delivery_location="Bhiwandi DC",
        item_weight_kg=0.5,
        freight_rates={"Bhiwandi DC": 2.20},
        freight_included=False
    )
    assert res_extra.normalized_price == 21.10
    assert res_extra.freight_treatment == "Extra"
    assert "freight" in res_extra.formula_citation

    # B. Freight Included: 40.00 * 0.50 = 20.00 (freight not added)
    res_incl = normalize_price(
        raw_value=40.0,
        raw_unit="₹/kg",
        delivery_location="Bhiwandi DC",
        item_weight_kg=0.5,
        freight_rates={"Bhiwandi DC": 2.20},
        freight_included=True
    )
    assert res_incl.normalized_price == 20.00
    assert res_incl.freight_treatment == "Included"
    assert "freight" not in res_incl.formula_citation


# 7. GST included versus excluded
def test_7_gst_included_versus_excluded():
    # RFx requires basic price excluding GST.
    # A. Quote specifies GST 18% extra (default): base price 100.0 is used directly (not double-taxed)
    res_excl = normalize_price(
        raw_value=100.0,
        raw_unit="Nos",
        gst_included=False,
        gst_rate=0.18
    )
    assert res_excl.normalized_price == 100.0
    assert "GST 18% extra" in res_excl.tax_treatment

    # B. Quote specifies GST included (118.0 including 18% GST):
    # GST must be backed out: 118.0 / 1.18 = 100.0
    res_incl = normalize_price(
        raw_value=118.0,
        raw_unit="Nos",
        gst_included=True,
        gst_rate=0.18
    )
    assert res_incl.normalized_price == 100.0
    assert "GST 18% included in quote; backed out" in res_incl.tax_treatment
    assert "GST Excluded" in res_incl.formula_citation


# 8. Conditional discount on a split award
def test_8_conditional_discount_on_split_award():
    # Condition: 5% discount if vendor wins 100% of all lines.
    # In a split award, condition is NOT met -> discount must NOT be applied.
    res_split = normalize_price(
        raw_value=100.0,
        raw_unit="Nos",
        discount_pct=0.05,
        discount_condition="All-lines award (100% share)",
        condition_met=False  # split award
    )
    assert res_split.normalized_price == 100.0
    assert res_split.applied_discount == 0.0
    assert "NOT applied" in res_split.formula_citation or res_split.applied_discount == 0.0

    # In a full award, condition IS met -> 5% discount applied (100 -> 95)
    res_full = normalize_price(
        raw_value=100.0,
        raw_unit="Nos",
        discount_pct=0.05,
        discount_condition="All-lines award (100% share)",
        condition_met=True
    )
    assert res_full.normalized_price == 95.0
    assert res_full.applied_discount == 0.05
    assert "discount" in res_full.formula_citation


# 9. Unsupported UOM
def test_9_unsupported_uom():
    # A. Unsupported arbitrary unit
    res_lumpsum = normalize_price(
        raw_value=50000.0,
        raw_unit="Lump Sum",
        target_uom="Nos"
    )
    assert res_lumpsum.normalized_price is None
    assert res_lumpsum.status == "Unresolved"
    assert "Valid standard unit of measure" in res_lumpsum.missing_inputs[0]

    # B. Non-interchangeable: Quoted per Running Metre for a Nos line
    res_rm = normalize_price(
        raw_value=25.0,
        raw_unit="Running Metre",
        target_uom="Nos"
    )
    assert res_rm.normalized_price is None
    assert res_rm.status == "Unresolved"
    assert "running metre" in res_rm.unresolved_reason.lower()

    # C. Non-interchangeable: Quoted per Set for a Nos line
    res_set = normalize_price(
        raw_value=50.0,
        raw_unit="Set",
        target_uom="Nos"
    )
    assert res_set.normalized_price is None
    assert res_set.status == "Unresolved"
    assert "Set" in res_set.missing_inputs[0]


# 10. Missing conversion data
def test_10_missing_conversion_data():
    # A. Missing area for Sqm quote
    res_sqm = normalize_price(
        raw_value=45.0,
        raw_unit="Sqm",
        item_area_sqm=None
    )
    assert res_sqm.normalized_price is None
    assert res_sqm.status == "Unresolved"
    assert "Item area basis (sqm/UoM)" in res_sqm.missing_inputs
    assert "Buyer review required" in res_sqm.unresolved_reason

    # B. Missing delivery location / freight rate when freight is extra
    res_freight = normalize_price(
        raw_value=40.0,
        raw_unit="₹/kg",
        item_weight_kg=0.25,
        delivery_location="Unknown City Plant",
        freight_included=False,
        freight_rates={"Pune (Chakan plant)": 1.20}
    )
    assert res_freight.normalized_price is None
    assert res_freight.status == "Unresolved"
    assert any("Freight rate for delivery location" in m for m in res_freight.missing_inputs)

    # C. New SKU quoting 'Same as last year'
    res_new_sku = normalize_price(
        raw_value="Same as last year",
        is_new_sku=True,
        last_po_price=None
    )
    assert res_new_sku.normalized_price is None
    assert res_new_sku.status == "Unresolved"
    assert "FY25 Historical PO Price" in res_new_sku.missing_inputs
    assert "Buyer review required" in res_new_sku.unresolved_reason


# 11. Technical specification validation and no silent substitution
def test_11_validate_technical_specification_and_no_silent_defaults():
    from core.normalizer import validate_technical_specification, calculate_price_per_kg

    # Valid specification
    is_valid, missing = validate_technical_specification(
        ply=3, flute="B", liner_gsm=150, fluting_gsm=120, board_l_mm=1035, board_w_mm=350, liner_bf=18
    )
    assert is_valid is True
    assert len(missing) == 0

    # Missing dimensions: must NOT silently default to 1000x500
    is_valid_no_dim, missing_no_dim = validate_technical_specification(
        ply=3, flute="B", liner_gsm=150, fluting_gsm=120, board_l_mm=None, board_w_mm=None
    )
    assert is_valid_no_dim is False
    assert "Board Length (mm)" in missing_no_dim
    assert "Board Width (mm)" in missing_no_dim

    # Missing GSM / flute: must NOT silently default to 150/120/B
    is_valid_no_gsm, missing_no_gsm = validate_technical_specification(
        ply=None, flute=None, liner_gsm=None, fluting_gsm=None
    )
    assert is_valid_no_gsm is False
    assert "Ply" in missing_no_gsm
    assert any("Flute" in m for m in missing_no_gsm)
    assert "Liner GSM" in missing_no_gsm
    assert "Fluting GSM" in missing_no_gsm

    # calculate_composite_weight with missing dimensions must return None for weight
    gsm, wt = calculate_composite_weight(
        ply=3, flute="B", liner_gsm=150, fluting_gsm=120, board_l_mm=None, board_w_mm=None
    )
    assert gsm is not None
    assert wt is None, "Weight must be None when board dimensions are missing; cannot invent 1000x500"


# 12. Price per kg calculation strictly excludes unresolved items
def test_12_price_per_kg_excludes_unresolved_items():
    from core.normalizer import calculate_price_per_kg

    # Valid price and weight
    pkg, status = calculate_price_per_kg(landed_piece_price=10.0, item_weight_kg=0.25)
    assert pkg == 40.0
    assert status == "Valid"

    # Missing weight -> must be None and flagged Unresolved (no default 0.25 kg)
    pkg_no_wt, status_no_wt = calculate_price_per_kg(landed_piece_price=10.0, item_weight_kg=None)
    assert pkg_no_wt is None
    assert "Unresolved" in status_no_wt

    # Missing/unresolved price -> must be None and flagged Unresolved
    pkg_no_p, status_no_p = calculate_price_per_kg(landed_piece_price=None, item_weight_kg=0.25)
    assert pkg_no_p is None
    assert "Unresolved" in status_no_p


# 13. Traceability of raw vendor quote and UOM even when normalization fails
def test_13_preserves_raw_quote_and_uom_on_unresolved_failure():
    # Per-kg quote on missing weight
    res = normalize_price(
        raw_value=42.0,
        raw_unit="₹/kg",
        item_weight_kg=None
    )
    assert res.normalized_price is None
    assert res.status == "Unresolved"
    assert res.original_value == 42.0, "Original vendor quoted price must be preserved"
    assert res.original_uom == "₹/kg", "Original vendor quoted UOM must be preserved"
    assert "Item weight basis (kg/UoM)" in res.missing_inputs
    assert len(res.unresolved_reason) > 0, "Reason for unresolved normalization must be explained"


# 14. App initialization and matrix preserves raw values and excludes unresolved from awards
def test_14_app_initialization_no_conflicting_legacy_logic():
    import streamlit as st
    import app
    assert "df_norm" in st.session_state
    df_norm = st.session_state.df_norm
    assert len(df_norm) == 30

    # Traceability columns present
    assert "V1 Raw Value" in df_norm.columns
    assert "V1 Raw UOM" in df_norm.columns
    assert "V5 Raw Value" in df_norm.columns
    assert "V5 Raw UOM" in df_norm.columns
    assert "V5 Status" in df_norm.columns
    assert "V5 Unresolved Reason" in df_norm.columns

    # Verify that Line 27 (New SKU) is Unresolved with preserved raw quote
    line27 = df_norm[df_norm["Line #"] == 27].iloc[0]
    assert line27["V5 Status"] == "Unresolved"
    assert pd.isna(line27["V5 (Standard Box)"])
    assert "Same as last year" in str(line27["V5 Raw Value"])
    assert line27["V5 Unresolved Reason"] is not None
    assert "New SKU" in line27["V5 Citation"] or "UNRESOLVED" in line27["V5 Citation"]


# 15. Unresolved weight items excluded from award calculations and price-per-kg comparisons
def test_15_unresolved_weight_items_excluded_from_awards_and_price_per_kg():
    import numpy as np
    from core.scenarios import calculate_award_scenarios
    from core.eligibility import VendorQualification
    from core.normalizer import calculate_price_per_kg

    # Create test matrix where Line 1 has an unresolved quote for Vendor 1
    # Vendor 1 quoted ₹38/kg but item weight is missing (None) -> normalized price is None / NaN
    dummy_df = pd.DataFrame([{
        "Line #": 1,
        "Item Code": "CP-001",
        "Description": "Test Box",
        "Est. Qty": 1000,
        "Delivery Location": "Pune (Chakan plant)",
        "Criticality": "C",
        "Budget Price": 10.0,
        "Est. Wt (kg)": None,  # Weight cannot be calculated due to missing dimensions
        "V1 (Apex)": np.nan,   # Unresolved due to missing weight
        "V2 (PackTech)": 9.50,  # Valid quote
        "V1 Citation": "Weight missing -> UNRESOLVED",
        "V2 Citation": "₹9.50 per unit"
    }])

    dummy_quals = {
        "V1": VendorQualification(vendor_id="V1", vendor_name="Apex", status="Eligible", passed_mandatory_gates=True),
        "V2": VendorQualification(vendor_id="V2", vendor_name="PackTech", status="Eligible", passed_mandatory_gates=True)
    }

    scenarios = calculate_award_scenarios(dummy_df, dummy_quals)

    # V1 must NOT be awarded Line 1 because the quote is unresolved
    line_b = scenarios["b_line_allocations"][0]
    assert line_b["Awarded Vendor"] == "V2 (PackTech)"
    assert line_b["Landed Price (₹)"] == 9.50

    # Effective price-per-kg calculation must exclude unresolved item
    pkg_v1, status_v1 = calculate_price_per_kg(landed_piece_price=line_b["Landed Price (₹)"], item_weight_kg=None)
    assert pkg_v1 is None
    assert "Unresolved" in status_v1



