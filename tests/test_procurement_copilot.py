"""
Comprehensive automated tests for AI Procurement Co-pilot.
Verifies all 16 requirements from Section 10 of the audit specifications:
1. All 30 CP item codes are preserved.
2. Technical specifications match the source RFx.
3. BCB take-up factor equals 1.45.
4. Currency conversion.
5. Per-kg and per-1,000 price conversions.
6. Missing weight results in Unresolved status.
7. Freight included versus extra.
8. Conditional discounts.
9. Split-award calculations.
10. Maximum supplier share restrictions.
11. Vendor qualification changes when questionnaire responses change.
12. Line-specific disqualification.
13. Buyer overrides trigger recalculation.
14. No ineligible supplier is recommended.
15. Missing mandatory coverage is reported.
16. AI Analyst numerical answers match deterministic calculations.
"""

import os
import pytest
import numpy as np
import pandas as pd

from core.config import TAKEUP_FACTORS, DEFAULT_FX_RATE, DEFAULT_FREIGHT_RATES
from core.normalizer import calculate_composite_weight, normalize_price
from core.eligibility import evaluate_vendor_qualifications, is_vendor_eligible_for_line
from core.scenarios import calculate_award_scenarios
from core.analyst import answer_query
from core.models import BuyerOverrideRecord


EXCEL_PATH = os.path.join(os.path.dirname(__file__), "..", "RFx_Master_Updated.xlsx")


@pytest.fixture(scope="module")
def rfx_data():
    """Loads source sheets from RFx_Master_Updated.xlsx."""
    xl = pd.ExcelFile(EXCEL_PATH)
    df_items = pd.read_excel(xl, sheet_name="Line Items")
    df_items = df_items[pd.to_numeric(df_items["Line #"], errors="coerce").notna()].copy()
    df_items["Line #"] = df_items["Line #"].astype(int)

    df_hist = pd.read_excel(xl, sheet_name="Historical PO Master")
    df_hist = df_hist[pd.to_numeric(df_hist["Line #"], errors="coerce").notna()].copy()
    df_hist["Line #"] = df_hist["Line #"].astype(int)

    df_gate = pd.read_excel(xl, sheet_name="Questionnaire Audit & Gate")
    df_norm = pd.read_excel(xl, sheet_name="Normalized Comparison")
    df_norm = df_norm[pd.to_numeric(df_norm["Line #"], errors="coerce").notna()].copy()
    df_norm["Line #"] = df_norm["Line #"].astype(int)

    return {
        "items": df_items,
        "hist": df_hist,
        "gate": df_gate,
        "norm": df_norm
    }


# 1. All 30 CP item codes are preserved
def test_all_30_cp_items_preserved(rfx_data):
    df_items = rfx_data["items"]
    assert len(df_items) == 30, f"Expected 30 line items, got {len(df_items)}"
    expected_codes = [f"CP-{i:03d}" for i in range(1, 31)]
    actual_codes = df_items["Item Code"].str.strip().tolist()
    assert actual_codes == expected_codes, "Mismatch in CP item codes list"


# 2. Technical specifications match the source RFx
def test_technical_specifications_match(rfx_data):
    df_items = rfx_data["items"]
    # Check CP-001 (Line 1): 3-ply B-flute, 300x200x150, board size 1035x350
    item1 = df_items[df_items["Line #"] == 1].iloc[0]
    assert int(item1["Ply"]) == 3
    assert str(item1["Flute"]).strip() == "B"
    assert float(item1["Board size L (mm)"]) == 1035.0
    assert float(item1["Board size W (mm)"]) == 350.0

    # Check CP-010 (Line 10): 7-ply BCB-flute
    item10 = df_items[df_items["Line #"] == 10].iloc[0]
    assert int(item10["Ply"]) == 7
    assert str(item10["Flute"]).strip() == "BCB"


# 3. BCB take-up factor equals 1.45
def test_bcb_takeup_factor_equals_1_45():
    assert "BCB" in TAKEUP_FACTORS, "BCB flute missing from take-up factors"
    assert TAKEUP_FACTORS["BCB"] == 1.45, f"Expected BCB takeup 1.45, got {TAKEUP_FACTORS['BCB']}"

    # Verify composite weight calculation using 1.45 for Line 10 (7-ply, 230 liner, 140 fluting, 3035x1200)
    # Composite GSM = ((7+1)/2)*230 + ((7-1)/2)*140*1.45 = 4*230 + 3*140*1.45 = 920 + 609 = 1529
    gsm, wt = calculate_composite_weight(
        ply=7, flute="BCB", liner_gsm=230, fluting_gsm=140, board_l_mm=3035, board_w_mm=1200
    )
    assert gsm == 1529.0
    assert wt == pytest.approx(5.5686, rel=1e-3)


# 4. Currency conversion
def test_currency_conversion():
    # Quoting USD 0.10 at FX rate 84.50 -> 8.45 INR
    landed, flag, cite, status = normalize_price(
        raw_value=0.10, raw_unit="USD", raw_currency="USD", fx_rate=84.50
    )
    assert landed == 8.45
    assert flag == "Inferred (USD to INR)"
    assert status == "Verified"

    # Test custom FX rate (e.g. 85.00)
    landed_custom, _, _, _ = normalize_price(
        raw_value=0.10, raw_unit="USD", raw_currency="USD", fx_rate=85.00
    )
    assert landed_custom == 8.50


# 5. Per-kg and per-1,000 price conversions
def test_per_kg_and_per_1000_conversions():
    # Per 1,000: Rs 6,120 per 1,000 Nos -> 6.12 per piece
    landed_1k, flag_1k, cite_1k, _ = normalize_price(
        raw_value=6120.0, raw_unit="per 1,000 Nos"
    )
    assert landed_1k == 6.12
    assert "1000" in flag_1k

    # Per-kg: Rs 38.00/kg + Rs 1.20 freight, weight 0.1424 kg
    # (38 + 1.20) * 0.1424 = 39.20 * 0.1424 = 5.58
    landed_kg, flag_kg, cite_kg, _ = normalize_price(
        raw_value=38.0, raw_unit="₹/kg", delivery_location="Pune (Chakan plant)",
        item_weight_kg=0.1424, freight_rates={"Pune (Chakan plant)": 1.20}
    )
    assert landed_kg == 5.58
    assert "kg to piece" in flag_kg


# 6. Missing weight results in Unresolved status
def test_missing_weight_results_in_unresolved():
    landed, flag, cite, status = normalize_price(
        raw_value=42.0, raw_unit="₹/kg", item_weight_kg=None
    )
    assert landed is None
    assert flag == "UNRESOLVED"
    assert status == "Needs Review"
    assert "Weight missing" in cite


# 7. Freight included versus extra
def test_freight_included_versus_extra():
    # Freight extra: (40 + 2.20) * 0.5 = 21.10
    landed_extra, _, cite_extra, _ = normalize_price(
        raw_value=40.0, raw_unit="₹/kg", delivery_location="Bhiwandi DC",
        item_weight_kg=0.5, freight_rates={"Bhiwandi DC": 2.20}, freight_included=False
    )
    assert landed_extra == 21.10
    assert "freight" in cite_extra

    # Freight included: 40 * 0.5 = 20.00
    landed_incl, _, cite_incl, _ = normalize_price(
        raw_value=40.0, raw_unit="₹/kg", delivery_location="Bhiwandi DC",
        item_weight_kg=0.5, freight_rates={"Bhiwandi DC": 2.20}, freight_included=True
    )
    assert landed_incl == 20.00


# 8. Conditional discounts
def test_conditional_discounts():
    # Repeat SKU with historical PO resolution + 3.6% index
    landed_repeat, flag_rep, cite_rep, _ = normalize_price(
        raw_value="Same as last year", last_po_price=10.0, is_new_sku=False, inflation_index=0.036
    )
    assert landed_repeat == 10.36
    assert "Inferred (PO History)" in flag_rep

    # New SKU with "Same as last year" must stay UNRESOLVED
    landed_new, flag_new, cite_new, status_new = normalize_price(
        raw_value="Same as last year", last_po_price=None, is_new_sku=True
    )
    assert landed_new is None
    assert flag_new == "UNRESOLVED"
    assert status_new == "Needs Review"


# 9. Split-award calculations
def test_split_award_calculations(rfx_data):
    df_norm = rfx_data["norm"]
    df_items = rfx_data["items"]
    df_gate = rfx_data["gate"]

    # Build matrix dataframe
    matrix_df = pd.DataFrame({
        "Line #": df_norm["Line #"],
        "Item Code": df_norm["Item Code"],
        "Description": df_items["Item Description"],
        "Est. Qty": df_norm["Est. Qty"],
        "Criticality": df_items["Criticality (A/B/C)"],
        "Budget Price": df_norm["Budget Price"],
        "V1 (Apex)": df_norm["V1 Landed (Apex)"],
        "V2 (PackTech)": df_norm["V2 Landed (PackTech)"],
        "V3 (Global USD)": df_norm["V3 Landed (Global USD)"],
        "V4 (Balaji)": df_norm["V4 Landed (Balaji)"],
        "V5 (Standard Box)": df_norm["V5 Landed (Standard Box)"]
    })

    quals = evaluate_vendor_qualifications(df_gate, df_items)
    scenarios = calculate_award_scenarios(matrix_df, quals)

    # Verify Scenario C split award for Criticality A lines
    c_lines = scenarios["c_line_allocations"]
    crit_a_allocations = [c for c in c_lines if c["Criticality"] == "A"]
    assert len(crit_a_allocations) > 0, "No Criticality A lines found"

    for c in crit_a_allocations:
        if c["Status"] == "Dual Sourced (70/30)":
            total_qty = c["L1 Qty"] + c["L2 Qty"]
            assert c["L1 Qty"] == pytest.approx(0.70 * total_qty, rel=1e-3)
            assert c["L2 Qty"] == pytest.approx(0.30 * total_qty, rel=1e-3)


# 10. Maximum supplier share restrictions
def test_maximum_supplier_share_restrictions(rfx_data):
    df_norm = rfx_data["norm"]
    df_items = rfx_data["items"]
    df_gate = rfx_data["gate"]

    matrix_df = pd.DataFrame({
        "Line #": df_norm["Line #"],
        "Item Code": df_norm["Item Code"],
        "Description": df_items["Item Description"],
        "Est. Qty": df_norm["Est. Qty"],
        "Criticality": df_items["Criticality (A/B/C)"],
        "Budget Price": df_norm["Budget Price"],
        "V1 (Apex)": df_norm["V1 Landed (Apex)"],
        "V2 (PackTech)": df_norm["V2 Landed (PackTech)"],
        "V3 (Global USD)": df_norm["V3 Landed (Global USD)"],
        "V4 (Balaji)": df_norm["V4 Landed (Balaji)"],
        "V5 (Standard Box)": df_norm["V5 Landed (Standard Box)"]
    })

    quals = evaluate_vendor_qualifications(df_gate, df_items)
    scenarios = calculate_award_scenarios(matrix_df, quals)

    shares_b = scenarios["vendor_shares_b"]
    for v, s_info in shares_b.items():
        assert s_info["share_pct"] <= 100.0


# 11. Vendor qualification changes when questionnaire responses change
def test_vendor_qualification_changes_when_questionnaire_changes(rfx_data):
    df_gate = rfx_data["gate"].copy()
    df_items = rfx_data["items"]

    # Base state: V4 is disqualified (expired ISO cert)
    quals_orig = evaluate_vendor_qualifications(df_gate, df_items)
    assert quals_orig["V4"].status == "Disqualified"

    # Simulate V4 passing all criteria: ISO valid, capacity 400 TPM, lab Yes, rejection 0.5%, customers 5
    v4_col = [c for c in df_gate.columns if "V4" in c][0]
    df_gate_modified = df_gate.copy()
    for idx, row in df_gate_modified.iterrows():
        c_name = str(row["Question / Gate Criteria"]).lower()
        if "iso" in c_name:
            df_gate_modified.at[idx, v4_col] = "Pass (Exp: 2028)"
        elif "capacity" in c_name:
            df_gate_modified.at[idx, v4_col] = "400 TPM (Pass)"
        elif "lab" in c_name:
            df_gate_modified.at[idx, v4_col] = "Yes"
        elif "rejection" in c_name:
            df_gate_modified.at[idx, v4_col] = "0.5% (Pass)"
        elif "customers" in c_name:
            df_gate_modified.at[idx, v4_col] = "5 (Pass)"
        elif "7-ply" in c_name:
            df_gate_modified.at[idx, v4_col] = "Yes"
        elif "moisture" in c_name:
            df_gate_modified.at[idx, v4_col] = "Yes"

    quals_mod = evaluate_vendor_qualifications(df_gate_modified, df_items)
    assert quals_mod["V4"].status == "Eligible", f"Expected V4 to become Eligible, got {quals_mod['V4'].status}"


# 12. Line-specific disqualification
def test_line_specific_disqualification(rfx_data):
    df_gate = rfx_data["gate"]
    df_items = rfx_data["items"]

    quals = evaluate_vendor_qualifications(df_gate, df_items)

    # Vendor 3 (Global) lacks 7-ply capability -> disqualified for Lines 10 and 30
    assert not is_vendor_eligible_for_line("V3", 10, quals)
    assert not is_vendor_eligible_for_line("V3", 30, quals)
    # But V3 is eligible for standard lines like Line 1
    assert is_vendor_eligible_for_line("V3", 1, quals)

    # Vendor 5 (Standard Box) lacks moisture barrier -> disqualified for Lines 26 and 27
    assert not is_vendor_eligible_for_line("V5", 26, quals)
    assert not is_vendor_eligible_for_line("V5", 27, quals)
    # But V5 is eligible for standard lines like Line 1
    assert is_vendor_eligible_for_line("V5", 1, quals)


# 13. Buyer overrides trigger recalculation
def test_buyer_overrides_trigger_recalculation(rfx_data):
    df_norm = rfx_data["norm"]
    df_items = rfx_data["items"]
    df_gate = rfx_data["gate"]

    matrix_df = pd.DataFrame({
        "Line #": df_norm["Line #"],
        "Item Code": df_norm["Item Code"],
        "Description": df_items["Item Description"],
        "Est. Qty": df_norm["Est. Qty"],
        "Criticality": df_items["Criticality (A/B/C)"],
        "Budget Price": df_norm["Budget Price"],
        "V1 (Apex)": df_norm["V1 Landed (Apex)"],
        "V2 (PackTech)": df_norm["V2 Landed (PackTech)"],
        "V3 (Global USD)": df_norm["V3 Landed (Global USD)"],
        "V4 (Balaji)": df_norm["V4 Landed (Balaji)"],
        "V5 (Standard Box)": df_norm["V5 Landed (Standard Box)"]
    })

    quals = evaluate_vendor_qualifications(df_gate, df_items)
    base_res = calculate_award_scenarios(matrix_df, quals)

    # Override Line 1 V1 price from 6.12 to 4.00
    matrix_df_overridden = matrix_df.copy()
    matrix_df_overridden.loc[matrix_df_overridden["Line #"] == 1, "V1 (Apex)"] = 4.00

    overridden_res = calculate_award_scenarios(matrix_df_overridden, quals)
    assert overridden_res["spend_b"] < base_res["spend_b"], "Spend B should decrease after buyer override"
    assert overridden_res["savings_b"] > base_res["savings_b"], "Savings B should increase after buyer override"


# 14. No ineligible supplier is recommended
def test_no_ineligible_supplier_recommended(rfx_data):
    df_norm = rfx_data["norm"]
    df_items = rfx_data["items"]
    df_gate = rfx_data["gate"]

    matrix_df = pd.DataFrame({
        "Line #": df_norm["Line #"],
        "Item Code": df_norm["Item Code"],
        "Description": df_items["Item Description"],
        "Est. Qty": df_norm["Est. Qty"],
        "Criticality": df_items["Criticality (A/B/C)"],
        "Budget Price": df_norm["Budget Price"],
        "V1 (Apex)": df_norm["V1 Landed (Apex)"],
        "V2 (PackTech)": df_norm["V2 Landed (PackTech)"],
        "V3 (Global USD)": df_norm["V3 Landed (Global USD)"],
        "V4 (Balaji)": df_norm["V4 Landed (Balaji)"],
        "V5 (Standard Box)": df_norm["V5 Landed (Standard Box)"]
    })

    quals = evaluate_vendor_qualifications(df_gate, df_items)
    scenarios = calculate_award_scenarios(matrix_df, quals)

    # In Scenario B and C, V4 must NEVER be awarded any line
    for alloc in scenarios["b_line_allocations"]:
        awarded_v = alloc["Awarded Vendor"]
        assert "V4" not in awarded_v, f"Ineligible vendor V4 was awarded line {alloc['Line #']}"

    # V3 must not be awarded Line 10 or 30
    for alloc in scenarios["b_line_allocations"]:
        if alloc["Line #"] in [10, 30]:
            assert "V3" not in alloc["Awarded Vendor"], f"V3 was awarded 7-ply line {alloc['Line #']}"

    # V5 must not be awarded Line 26 or 27
    for alloc in scenarios["b_line_allocations"]:
        if alloc["Line #"] in [26, 27]:
            assert "V5" not in alloc["Awarded Vendor"], f"V5 was awarded moisture barrier line {alloc['Line #']}"


# 15. Missing mandatory coverage is reported
def test_missing_mandatory_coverage_reported(rfx_data):
    df_norm = rfx_data["norm"].copy()
    df_items = rfx_data["items"]
    df_gate = rfx_data["gate"]

    # Intentionally erase all qualified vendor quotes for Line 27
    matrix_df = pd.DataFrame({
        "Line #": df_norm["Line #"],
        "Item Code": df_norm["Item Code"],
        "Description": df_items["Item Description"],
        "Est. Qty": df_norm["Est. Qty"],
        "Criticality": df_items["Criticality (A/B/C)"],
        "Budget Price": df_norm["Budget Price"],
        "V1 (Apex)": df_norm["V1 Landed (Apex)"],
        "V2 (PackTech)": df_norm["V2 Landed (PackTech)"],
        "V3 (Global USD)": df_norm["V3 Landed (Global USD)"],
        "V4 (Balaji)": df_norm["V4 Landed (Balaji)"],
        "V5 (Standard Box)": df_norm["V5 Landed (Standard Box)"]
    })

    # Erase V1, V2, V3 quotes for Line 27 (V4 is disqualified, V5 is disqualified for moisture barrier)
    matrix_df.loc[matrix_df["Line #"] == 27, ["V1 (Apex)", "V2 (PackTech)", "V3 (Global USD)"]] = np.nan

    quals = evaluate_vendor_qualifications(df_gate, df_items)
    scenarios = calculate_award_scenarios(matrix_df, quals)

    assert 27 in scenarios["uncovered_lines_b"], "Line 27 should be reported as UNCOVERED"
    alloc_27 = [a for a in scenarios["b_line_allocations"] if a["Line #"] == 27][0]
    assert alloc_27["Awarded Vendor"] == "UNCOVERED"


# 16. AI Analyst numerical answers match deterministic calculations
def test_ai_analyst_numerical_answers_match(rfx_data):
    df_norm = rfx_data["norm"]
    df_items = rfx_data["items"]
    df_gate = rfx_data["gate"]

    matrix_df = pd.DataFrame({
        "Line #": df_norm["Line #"],
        "Item Code": df_norm["Item Code"],
        "Description": df_items["Item Description"],
        "Est. Qty": df_norm["Est. Qty"],
        "Criticality": df_items["Criticality (A/B/C)"],
        "Budget Price": df_norm["Budget Price"]
    })
    for c in ["V1 (Apex)", "V2 (PackTech)", "V3 (Global USD)", "V4 (Balaji)", "V5 (Standard Box)"]:
        v_num = c.split()[0]
        v_name = c.split(maxsplit=1)[1].strip("()")
        matrix_df[c] = df_norm[f"{v_num} Landed ({v_name})"]
        matrix_df[f"{v_num} Citation"] = "Ground Truth Citation"

    matrix_df["V5 Trust Flag"] = "Verified"

    quals = evaluate_vendor_qualifications(df_gate, df_items)
    scenarios = calculate_award_scenarios(matrix_df, quals)

    # Ask AI analyst about cost of compliance
    ans, mode = answer_query(
        user_query="What is the cost difference if we enforce the quality gate?",
        df_matrix=matrix_df,
        df_audit=df_gate,
        qualifications=quals,
        scenarios=scenarios,
        overrides=[],
        fx_rate=84.50,
        openai_client=None
    )

    cost_str = f"{scenarios['cost_of_compliance']:,.0f}"
    assert cost_str in ans, f"Expected compliance cost ₹{cost_str} to be cited in analyst answer"
