"""
Pytest test suite for Fix 2: Data-Driven Supplier Qualification.

Verifies:
1. Derivation of qualification from actual questionnaire responses without hardcoded vendor names.
2. 7-ply BCB manufacturing requirement applied only to relevant lines (Lines 10, 30).
3. Moisture-barrier requirement applied only to relevant lines (Lines 26, 27).
4. Missing mandatory evidence (Q1-Q5) treated as 'Pending Review', not compliant.
5. Supplier-wide requirements kept separate from line-specific requirements.
6. Stored reason and source evidence for every qualification decision.
7. Award engine consumes qualification results and never recommends an ineligible or pending supplier.
8. Changing a questionnaire response dynamically changes qualification results and recalculates award eligibility.
9. Line-specific failure does not incorrectly disqualify unrelated lines.
10. All four qualification statuses supported: Eligible, Conditionally Eligible, Disqualified, Pending Review.
"""

import os
import pytest
import pandas as pd

from core.eligibility import (
    evaluate_vendor_qualifications,
    is_vendor_eligible_for_line,
    _extract_vendor_id
)
from core.scenarios import calculate_award_scenarios
from core.models import VendorQualification

EXCEL_PATH = os.path.join(os.path.dirname(__file__), "..", "RFx_Master_Updated.xlsx")


@pytest.fixture(scope="module")
def rfx_base_data():
    """Loads base sheets from RFx_Master_Updated.xlsx."""
    xl = pd.ExcelFile(EXCEL_PATH)
    df_items = pd.read_excel(xl, sheet_name="Line Items")
    df_items = df_items[pd.to_numeric(df_items["Line #"], errors="coerce").notna()].copy()
    df_items["Line #"] = df_items["Line #"].astype(int)

    df_gate = pd.read_excel(xl, sheet_name="Questionnaire Audit & Gate")
    df_norm = pd.read_excel(xl, sheet_name="Normalized Comparison")
    df_norm = df_norm[pd.to_numeric(df_norm["Line #"], errors="coerce").notna()].copy()
    df_norm["Line #"] = df_norm["Line #"].astype(int)

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

    return {
        "items": df_items,
        "gate": df_gate,
        "norm": df_norm,
        "matrix": matrix_df
    }


# 1. Four supported qualification statuses
def test_all_four_supported_statuses_exist(rfx_base_data):
    df_items = rfx_base_data["items"]
    df_gate = rfx_base_data["gate"].copy()

    # Base gives Eligible (V1, V2), Conditionally Eligible (V3, V5), and Disqualified (V4)
    quals = evaluate_vendor_qualifications(df_gate, df_items)
    statuses = {q.status for q in quals.values()}
    assert "Eligible" in statuses
    assert "Conditionally Eligible" in statuses
    assert "Disqualified" in statuses

    # Create Pending Review by introducing pending ISO certificate for V1
    v1_col = [c for c in df_gate.columns if "V1" in c][0]
    df_gate_pending = df_gate.copy()
    for idx, row in df_gate_pending.iterrows():
        if "iso" in str(row["Question / Gate Criteria"]).lower():
            df_gate_pending.at[idx, v1_col] = "Pending Certificate Copy Verification"

    quals_pending = evaluate_vendor_qualifications(df_gate_pending, df_items)
    assert quals_pending["V1"].status == "Pending Review"
    assert "Pending Review" in {q.status for q in quals_pending.values()}


# 2. Derive qualification from questionnaire responses without hardcoded vendor exclusions
def test_derive_qualification_dynamically_without_hardcoded_vendor_names(rfx_base_data):
    df_items = rfx_base_data["items"]
    df_gate = rfx_base_data["gate"]

    # Introduce a new unknown vendor "V9: Super Packaging"
    df_gate_dynamic = df_gate.copy()
    df_gate_dynamic["V9: Super Packaging"] = [
        "Pass (Exp: 2029)",       # Q1
        "500 TPM (Pass)",         # Q2
        "Yes",                    # Q3
        "0.6% (Pass)",            # Q4
        "8 (Pass)",               # Q5
        "Yes",                    # Q6
        "Yes",                    # Q7
        "QUALIFIED"               # Decision row
    ]

    quals = evaluate_vendor_qualifications(df_gate_dynamic, df_items)
    assert "V9" in quals, "Dynamic vendor V9 should be evaluated"
    assert quals["V9"].status == "Eligible"
    assert quals["V9"].passed_mandatory_gates is True
    assert len(quals["V9"].banned_lines) == 0


# 3. 7-ply BCB manufacturing requirement applied only to relevant lines
def test_7ply_requirement_applied_only_to_relevant_lines(rfx_base_data):
    df_items = rfx_base_data["items"]
    df_gate = rfx_base_data["gate"]

    quals = evaluate_vendor_qualifications(df_gate, df_items)

    # V3 failed Q6 (7-ply capability)
    v3_qual = quals["V3"]
    assert v3_qual.status == "Conditionally Eligible"
    # Lines 10 and 30 are 7-ply BCB
    assert 10 in v3_qual.banned_lines
    assert 30 in v3_qual.banned_lines
    assert not is_vendor_eligible_for_line("V3", 10, quals)
    assert not is_vendor_eligible_for_line("V3", 30, quals)

    # All standard lines (e.g. Lines 1 to 9, 11 to 25) must NOT be banned for V3
    unrelated_lines = [l for l in range(1, 31) if l not in [10, 30]]
    for l in unrelated_lines:
        assert l not in v3_qual.banned_lines
        assert is_vendor_eligible_for_line("V3", l, quals)


# 4. Moisture barrier requirement applied only to relevant lines
def test_moisture_barrier_requirement_applied_only_to_relevant_lines(rfx_base_data):
    df_items = rfx_base_data["items"]
    df_gate = rfx_base_data["gate"]

    quals = evaluate_vendor_qualifications(df_gate, df_items)

    # V5 failed Q7 (Moisture barrier)
    v5_qual = quals["V5"]
    assert v5_qual.status == "Conditionally Eligible"
    # Lines 26 and 27 require moisture barrier
    assert 26 in v5_qual.banned_lines
    assert 27 in v5_qual.banned_lines
    assert not is_vendor_eligible_for_line("V5", 26, quals)
    assert not is_vendor_eligible_for_line("V5", 27, quals)

    # Other lines (Lines 1 to 25, 28 to 30) must NOT be banned for V5
    unrelated_lines = [l for l in range(1, 31) if l not in [26, 27]]
    for l in unrelated_lines:
        assert l not in v5_qual.banned_lines
        assert is_vendor_eligible_for_line("V5", l, quals)


# 5. Missing mandatory evidence treated as Pending Review
def test_missing_mandatory_evidence_treated_as_pending_review(rfx_base_data):
    df_items = rfx_base_data["items"]
    df_gate = rfx_base_data["gate"].copy()
    v2_col = [c for c in df_gate.columns if "V2" in c][0]

    # Clear Q1 (ISO cert) to blank/missing for V2
    for idx, row in df_gate.iterrows():
        if "iso" in str(row["Question / Gate Criteria"]).lower():
            df_gate.at[idx, v2_col] = "Awaited / Under Audit Review"

    quals = evaluate_vendor_qualifications(df_gate, df_items)
    assert quals["V2"].status == "Pending Review"
    assert quals["V2"].passed_mandatory_gates is False
    assert any("Q1" in p for p in quals["V2"].pending_gates)

    # Vendor with Pending Review must NOT be eligible for awards
    assert not is_vendor_eligible_for_line("V2", 1, quals)
    assert not is_vendor_eligible_for_line("V2", 10, quals)


# 6. Supplier-wide requirements kept separate from line-specific requirements
def test_separation_of_supplier_wide_and_line_specific_requirements(rfx_base_data):
    df_items = rfx_base_data["items"]
    df_gate = rfx_base_data["gate"]

    quals = evaluate_vendor_qualifications(df_gate, df_items)

    # V4 failed general supplier-wide gates (Q1 expired ISO cert, Q2 capacity 280, etc.)
    assert quals["V4"].status == "Disqualified"
    assert len(quals["V4"].failed_general_gates) >= 4
    # Banned on ALL 30 lines
    assert len(quals["V4"].banned_lines) == 30

    # V3 passed general supplier-wide gates, but failed line-specific capability Q6
    assert quals["V3"].status == "Conditionally Eligible"
    assert len(quals["V3"].failed_general_gates) == 0
    # Banned only on lines 10 and 30
    assert quals["V3"].banned_lines == [10, 30]


# 7. Store reason and source evidence for every qualification decision
def test_store_reason_and_evidence(rfx_base_data):
    df_items = rfx_base_data["items"]
    df_gate = rfx_base_data["gate"]

    quals = evaluate_vendor_qualifications(df_gate, df_items)

    for vid, q in quals.items():
        assert isinstance(q.reason, str) and len(q.reason) > 0, f"Vendor {vid} missing reason"
        assert isinstance(q.evidence, dict) and len(q.evidence) >= 7, f"Vendor {vid} missing evidence dict"
        assert "Q1_ISO" in q.evidence
        assert "Q2_Capacity" in q.evidence
        assert "Q3_Lab" in q.evidence
        assert "Q4_Rejection" in q.evidence
        assert "Q5_Customers" in q.evidence
        assert "Q6_7Ply" in q.evidence
        assert "Q7_Moisture" in q.evidence


# 8. Award engine consumes qualification results and never recommends ineligible/pending suppliers
def test_award_engine_consumes_qualification_results(rfx_base_data):
    matrix_df = rfx_base_data["matrix"]
    df_items = rfx_base_data["items"]
    df_gate = rfx_base_data["gate"]

    quals = evaluate_vendor_qualifications(df_gate, df_items)
    scenarios = calculate_award_scenarios(matrix_df, quals)

    # In Scenario B, V4 must NEVER be awarded any line
    for alloc in scenarios["b_line_allocations"]:
        awarded_vendor = alloc["Awarded Vendor"]
        assert "V4" not in awarded_vendor, f"Ineligible vendor V4 was awarded line {alloc['Line #']}"
        # On lines 10 and 30, V3 must NEVER be awarded
        if alloc["Line #"] in [10, 30]:
            assert "V3" not in awarded_vendor, f"V3 was awarded line {alloc['Line #']}"
        # On lines 26 and 27, V5 must NEVER be awarded
        if alloc["Line #"] in [26, 27]:
            assert "V5" not in awarded_vendor, f"V5 was awarded line {alloc['Line #']}"


# 9. Changing a questionnaire response changes qualification and recalculates award eligibility
def test_changing_questionnaire_recalculates_award_eligibility(rfx_base_data):
    matrix_df = rfx_base_data["matrix"]
    df_items = rfx_base_data["items"]
    df_gate = rfx_base_data["gate"].copy()
    v4_col = [c for c in df_gate.columns if "V4" in c][0]

    # Baseline: V4 is disqualified, Spend B is higher
    base_quals = evaluate_vendor_qualifications(df_gate, df_items)
    base_scenarios = calculate_award_scenarios(matrix_df, base_quals)
    assert base_quals["V4"].status == "Disqualified"

    # Now simulate V4 rectifying its ISO certificate and all quality gates
    for idx, row in df_gate.iterrows():
        c_name = str(row["Question / Gate Criteria"]).lower()
        if "iso" in c_name:
            df_gate.at[idx, v4_col] = "Pass (Exp: 2028)"
        elif "capacity" in c_name:
            df_gate.at[idx, v4_col] = "450 TPM (Pass)"
        elif "lab" in c_name:
            df_gate.at[idx, v4_col] = "Yes"
        elif "rejection" in c_name:
            df_gate.at[idx, v4_col] = "0.7% (Pass)"
        elif "customers" in c_name:
            df_gate.at[idx, v4_col] = "6 (Pass)"
        elif "7-ply" in c_name:
            df_gate.at[idx, v4_col] = "Yes"
        elif "moisture" in c_name:
            df_gate.at[idx, v4_col] = "Yes"

    new_quals = evaluate_vendor_qualifications(df_gate, df_items)
    assert new_quals["V4"].status == "Eligible"

    # Recalculate award scenarios with new qualifications
    new_scenarios = calculate_award_scenarios(matrix_df, new_quals)

    # Since V4 is now eligible and offers competitive pricing on multiple lines,
    # Scenario B spend should drop (higher savings)
    assert new_scenarios["spend_b"] < base_scenarios["spend_b"], "Spend B should decrease when V4 becomes qualified"
    assert new_scenarios["savings_b"] > base_scenarios["savings_b"], "Savings B should increase when V4 becomes qualified"


# 10. Line-specific failure does not incorrectly disqualify unrelated lines
def test_line_specific_failure_does_not_disqualify_unrelated_lines(rfx_base_data):
    matrix_df = rfx_base_data["matrix"]
    df_items = rfx_base_data["items"]
    df_gate = rfx_base_data["gate"]

    quals = evaluate_vendor_qualifications(df_gate, df_items)
    scenarios = calculate_award_scenarios(matrix_df, quals)

    # V3 is disqualified for Line 10 (7-ply), but is L1 on several standard shipper lines
    # Check that V3 CAN win eligible standard lines
    v3_allocs = [a for a in scenarios["b_line_allocations"] if "V3" in a["Awarded Vendor"]]
    assert len(v3_allocs) > 0, "V3 should still be awarded standard lines where it is L1"
    for a in v3_allocs:
        assert a["Line #"] not in [10, 30], f"V3 should not be awarded banned line {a['Line #']}"
