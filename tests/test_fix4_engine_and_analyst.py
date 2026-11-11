"""
Test Suite for Fix 4: Reliable Award Engine and Contextual AI Analyst
Tests:
- Supplier exclusions (disqualified and pending-review never awarded)
- Split awards (70/30 on Criticality A lines)
- Maximum supplier-share restrictions
- Uncovered mandatory lines marked explicitly
- Conditional discounts applied only when conditions are met
- Dynamic recalculation after buyer overrides
- Changed questionnaire responses altering qualification and award allocations
- AI Analyst numerical accuracy, facts vs unresolved vs missing distinction, and API unavailable handling
"""

import os
import pytest
import pandas as pd
import numpy as np

from core.scenarios import calculate_award_scenarios
from core.eligibility import evaluate_vendor_qualifications, is_vendor_eligible_for_line
from core.analyst import answer_query, build_system_context
from core.models import VendorQualification, BuyerOverrideRecord
from core.normalizer import normalize_price
from core.config import DEFAULT_FX_RATE as FX_RATE, DEFAULT_FREIGHT_RATES as FREIGHT_RATES


GROUND_TRUTH_FILE = "RFx_Master_Updated.xlsx"


@pytest.fixture(scope="module")
def rfx_state():
    """Loads base RFx data and builds standard matrix DataFrame."""
    df_items = pd.read_excel(GROUND_TRUTH_FILE, sheet_name="Line Items")
    df_items = df_items[df_items["Line #"].notna()].copy()
    df_gate = pd.read_excel(GROUND_TRUTH_FILE, sheet_name="Questionnaire Audit & Gate")
    df_gt = pd.read_excel(GROUND_TRUTH_FILE, sheet_name="Normalized Comparison")
    df_gt = df_gt[df_gt["Line #"].notna()].copy()

    matrix_df = pd.DataFrame({
        "Line #": df_gt["Line #"].astype(int),
        "Item Code": df_gt["Item Code"],
        "Description": df_items["Item Description"],
        "Est. Qty": df_gt["Est. Qty"],
        "Criticality": df_items["Criticality (A/B/C)"],
        "Budget Price": df_gt["Budget Price"],
        "V1 (Apex)": df_gt["V1 Landed (Apex)"],
        "V2 (PackTech)": df_gt["V2 Landed (PackTech)"],
        "V3 (Global USD)": df_gt["V3 Landed (Global USD)"],
        "V4 (Balaji)": df_gt["V4 Landed (Balaji)"],
        "V5 (Standard Box)": df_gt["V5 Landed (Standard Box)"]
    })

    # Citations
    for c in ["V1", "V2", "V3", "V4", "V5"]:
        matrix_df[f"{c} Citation"] = "Ground Truth Citation"
    matrix_df["V5 Trust Flag"] = "Verified"

    quals = evaluate_vendor_qualifications(df_gate, df_items)
    return {
        "matrix": matrix_df,
        "items": df_items,
        "gate": df_gate,
        "quals": quals
    }


# ─────────────────────────────────────────────────────────────────────────────
# 1. Supplier Exclusions (Never allocate to Disqualified or Pending-Review)
# ─────────────────────────────────────────────────────────────────────────────
def test_1_supplier_exclusions_strictly_enforced(rfx_state):
    matrix = rfx_state["matrix"].copy()
    quals = rfx_state["quals"]

    scenarios = calculate_award_scenarios(matrix, quals)

    # Disqualified supplier V4 must NEVER be awarded any line in Scenario B or C
    for alloc in scenarios["b_line_allocations"]:
        assert "V4" not in alloc["Awarded Vendor"], f"Disqualified V4 awarded line {alloc['Line #']}"
    for alloc in scenarios["c_line_allocations"]:
        assert "V4" not in alloc["L1 Vendor"], f"Disqualified V4 awarded L1 in line {alloc['Line #']}"
        assert "V4" not in alloc["L2 Vendor"], f"Disqualified V4 awarded L2 in line {alloc['Line #']}"

    # V3 (lacks 7-ply) must not be awarded Line 10 or 30
    for alloc in scenarios["b_line_allocations"]:
        if alloc["Line #"] in [10, 30]:
            assert "V3" not in alloc["Awarded Vendor"], f"V3 awarded 7-ply line {alloc['Line #']}"

    # V5 (lacks moisture barrier) must not be awarded Line 26 or 27
    for alloc in scenarios["b_line_allocations"]:
        if alloc["Line #"] in [26, 27]:
            assert "V5" not in alloc["Awarded Vendor"], f"V5 awarded moisture barrier line {alloc['Line #']}"


# ─────────────────────────────────────────────────────────────────────────────
# 2. Split Awards (70/30 Dual Sourcing on Criticality A lines)
# ─────────────────────────────────────────────────────────────────────────────
def test_2_split_awards_70_30_on_critical_lines(rfx_state):
    matrix = rfx_state["matrix"].copy()
    quals = rfx_state["quals"]

    scenarios = calculate_award_scenarios(matrix, quals)
    c_allocs = scenarios["c_line_allocations"]

    crit_a_lines = [a for a in c_allocs if a["Criticality"] == "A"]
    assert len(crit_a_lines) >= 5, "Expected 5 Criticality A lines (Lines 9, 10, 26, 27, 30)"

    for a in crit_a_lines:
        if a["Status"] == "Dual Sourced (70/30)":
            total_qty = a["L1 Qty"] + a["L2 Qty"]
            assert a["L1 Qty"] == pytest.approx(0.70 * total_qty, rel=1e-3)
            assert a["L2 Qty"] == pytest.approx(0.30 * total_qty, rel=1e-3)
            assert a["L1 Vendor"] != a["L2 Vendor"], "Dual sourcing requires two distinct suppliers"


# ─────────────────────────────────────────────────────────────────────────────
# 3. Maximum Supplier Share Restrictions
# ─────────────────────────────────────────────────────────────────────────────
def test_3_maximum_supplier_share_restrictions(rfx_state):
    matrix = rfx_state["matrix"].copy()
    quals = rfx_state["quals"]

    # Base allocation without share cap
    base_scenarios = calculate_award_scenarios(matrix, quals)
    base_shares = base_scenarios["vendor_shares_b"]

    # Enforce a strict 60% cap
    capped_scenarios = calculate_award_scenarios(matrix, quals, max_single_vendor_share=0.60)
    capped_shares = capped_scenarios["vendor_shares_b"]

    for v, s_info in capped_shares.items():
        # Every vendor's share must be <= 60% (or flagged if constrained)
        assert s_info["share_pct"] <= 60.5, f"Vendor {v} exceeded 60% cap: {s_info['share_pct']:.1f}%"


# ─────────────────────────────────────────────────────────────────────────────
# 4. Uncovered Mandatory Lines Explicitly Flagged
# ─────────────────────────────────────────────────────────────────────────────
def test_4_uncovered_mandatory_lines_explicitly_flagged(rfx_state):
    matrix = rfx_state["matrix"].copy()
    quals = rfx_state["quals"]

    # Erase all valid quotes for Line 10 (CP-010)
    # V1, V2, V5 are eligible for 7-ply; V3 lacks 7-ply; V4 is disqualified globally
    matrix.loc[matrix["Line #"] == 10, ["V1 (Apex)", "V2 (PackTech)", "V5 (Standard Box)"]] = np.nan

    scenarios = calculate_award_scenarios(matrix, quals)

    # Line 10 must be in uncovered_lines_b
    assert 10 in scenarios["uncovered_lines_b"], "Line 10 should be explicitly flagged as UNCOVERED"
    
    alloc_10 = next(a for a in scenarios["b_line_allocations"] if a["Line #"] == 10)
    assert alloc_10["Awarded Vendor"] == "UNCOVERED"
    assert "UNCOVERED" in alloc_10["Status"]
    assert any("Line 10" in r for r in scenarios["risks_b"])


# ─────────────────────────────────────────────────────────────────────────────
# 5. Conditional Discounts Applied Only When Conditions Satisfied
# ─────────────────────────────────────────────────────────────────────────────
def test_5_conditional_discounts_on_split_vs_full_award(rfx_state):
    matrix = rfx_state["matrix"].copy()
    quals = rfx_state["quals"]

    # Scenario B is naturally a split award between V1, V2, V3, V5
    # Define condition: V1 offers 5% discount IF awarded 100% of all lines
    discounts_spec = {
        "V1": {
            "discount_pct": 0.05,
            "condition_type": "all_lines",
            "description": "5% discount if awarded 100% of lines"
        }
    }

    split_res = calculate_award_scenarios(matrix, quals, conditional_discounts=discounts_spec)
    v1_disc_split = split_res["discounts_evaluated"].get("V1 (Apex)", {})
    
    # In split award: condition is NOT met -> discount NOT applied
    assert not v1_disc_split.get("applied"), "All-lines discount must NOT be applied in a split award"
    assert v1_disc_split.get("discount_amount") == 0.0

    # Now simulate V1 winning 100% of lines by making V1 cheaper across all lines
    matrix_v1_wins_all = matrix.copy()
    for col in ["V2 (PackTech)", "V3 (Global USD)", "V4 (Balaji)", "V5 (Standard Box)"]:
        matrix_v1_wins_all[col] = 9999.0

    full_res = calculate_award_scenarios(matrix_v1_wins_all, quals, conditional_discounts=discounts_spec)
    v1_disc_full = full_res["discounts_evaluated"].get("V1 (Apex)", {})
    
    # When V1 wins 100% of lines: condition IS met -> discount IS applied
    assert v1_disc_full.get("applied"), "All-lines discount MUST be applied when vendor wins 100% of lines"
    assert v1_disc_full.get("discount_amount") > 0.0


# ─────────────────────────────────────────────────────────────────────────────
# 6. Recalculate After Buyer Edits and Overrides
# ─────────────────────────────────────────────────────────────────────────────
def test_6_buyer_overrides_recalculate_award_spend(rfx_state):
    matrix = rfx_state["matrix"].copy()
    quals = rfx_state["quals"]

    base_scenarios = calculate_award_scenarios(matrix, quals)
    base_spend_b = base_scenarios["spend_b"]

    # Buyer overrides Line 1 V1 price from ~6.12 to 2.50
    matrix_overridden = matrix.copy()
    matrix_overridden.loc[matrix_overridden["Line #"] == 1, "V1 (Apex)"] = 2.50

    new_scenarios = calculate_award_scenarios(matrix_overridden, quals)
    assert new_scenarios["spend_b"] < base_spend_b, "Spend B must decrease after lower buyer override price"
    assert new_scenarios["savings_b"] > base_scenarios["savings_b"], "Savings B must increase"


# ─────────────────────────────────────────────────────────────────────────────
# 7. Changed Questionnaire Responses Alter Award Eligibility
# ─────────────────────────────────────────────────────────────────────────────
def test_7_questionnaire_change_recalculates_award(rfx_state):
    df_gate = rfx_state["gate"].copy()
    df_items = rfx_state["items"]
    matrix = rfx_state["matrix"].copy()

    # Base: V4 is disqualified
    quals_orig = evaluate_vendor_qualifications(df_gate, df_items)
    assert quals_orig["V4"].status == "Disqualified"

    # Make V4 compliant
    v4_col = next(c for c in df_gate.columns if "V4" in c)
    df_gate_fixed = df_gate.copy()
    for idx, row in df_gate_fixed.iterrows():
        c_name = str(row["Question / Gate Criteria"]).lower()
        if "iso" in c_name:
            df_gate_fixed.at[idx, v4_col] = "Pass (Exp: 2028)"
        elif "capacity" in c_name:
            df_gate_fixed.at[idx, v4_col] = "500 TPM (Pass)"
        elif "lab" in c_name:
            df_gate_fixed.at[idx, v4_col] = "Yes"
        elif "rejection" in c_name:
            df_gate_fixed.at[idx, v4_col] = "0.8% (Pass)"
        elif "customers" in c_name:
            df_gate_fixed.at[idx, v4_col] = "5 (Pass)"
        elif "7-ply" in c_name:
            df_gate_fixed.at[idx, v4_col] = "Yes"
        elif "moisture" in c_name:
            df_gate_fixed.at[idx, v4_col] = "Yes"

    quals_fixed = evaluate_vendor_qualifications(df_gate_fixed, df_items)
    assert quals_fixed["V4"].status == "Eligible"

    # Recalculate award scenarios: V4 can now be awarded lines
    new_scenarios = calculate_award_scenarios(matrix, quals_fixed)
    v4_allocs = [a for a in new_scenarios["b_line_allocations"] if "V4" in a["Awarded Vendor"]]
    assert len(v4_allocs) > 0, "Now-compliant V4 should win lines where they are lowest"


# ─────────────────────────────────────────────────────────────────────────────
# 8. AI Analyst Uses Deterministic Functions for Numerical Calculations
# ─────────────────────────────────────────────────────────────────────────────
def test_8_ai_analyst_uses_deterministic_calculations(rfx_state):
    matrix = rfx_state["matrix"]
    df_gate = rfx_state["gate"]
    quals = rfx_state["quals"]
    scenarios = calculate_award_scenarios(matrix, quals)

    # Ask about cost difference / compliance
    ans, mode = answer_query(
        user_query="What is the cost difference if we enforce the quality gate?",
        df_matrix=matrix,
        df_audit=df_gate,
        qualifications=quals,
        scenarios=scenarios,
        overrides=[],
        fx_rate=84.50,
        openai_client=None
    )

    cost_str = f"{scenarios['cost_of_compliance']:,.0f}"
    spend_b_str = f"{scenarios['spend_b']:,.0f}"
    
    assert cost_str in ans, f"Analyst must cite exact compliance cost ₹{cost_str}"
    assert spend_b_str in ans, f"Analyst must cite exact Scenario B spend ₹{spend_b_str}"


# ─────────────────────────────────────────────────────────────────────────────
# 9. AI Analyst Distinguishes Confirmed Facts, Unresolved, and Missing Data
# ─────────────────────────────────────────────────────────────────────────────
def test_9_ai_analyst_distinguishes_facts_unresolved_missing(rfx_state):
    matrix = rfx_state["matrix"].copy()
    df_gate = rfx_state["gate"]
    quals = rfx_state["quals"]
    scenarios = calculate_award_scenarios(matrix, quals)

    # Mark V5 Line 27 as UNRESOLVED
    matrix.loc[matrix["Line #"] == 27, "V5 Citation"] = "UNRESOLVED: Stated 'Same as last year' on New SKU"
    matrix.loc[matrix["Line #"] == 27, "V5 Trust Flag"] = "UNRESOLVED"
    matrix.loc[matrix["Line #"] == 27, "V5 (Standard Box)"] = np.nan

    ans, _ = answer_query(
        user_query="Analyze Line 27 quotes and explain vendor statuses",
        df_matrix=matrix,
        df_audit=df_gate,
        qualifications=quals,
        scenarios=scenarios,
        overrides=[],
        fx_rate=84.50,
        openai_client=None
    )

    # Must identify:
    # 1. Confirmed facts (e.g. V1, V2)
    assert "Confirmed" in ans or "Fact" in ans or "V1" in ans
    # 2. Unresolved data (V5)
    assert "UNRESOLVED" in ans
    # 3. Disqualified vendor (V4 expired ISO, V5 failed Q7)
    assert "DISQUALIFIED" in ans


# ─────────────────────────────────────────────────────────────────────────────
# 10. AI Analyst Explains Limitation When API Is Unavailable
# ─────────────────────────────────────────────────────────────────────────────
def test_10_ai_analyst_explains_limitations_when_api_unavailable(rfx_state):
    matrix = rfx_state["matrix"]
    df_gate = rfx_state["gate"]
    quals = rfx_state["quals"]
    scenarios = calculate_award_scenarios(matrix, quals)

    # Mock client that raises an error
    class MockFailingClient:
        class chat:
            class completions:
                @staticmethod
                def create(*args, **kwargs):
                    raise ConnectionError("Simulated OpenAI API Connection Failure (503 Service Unavailable)")

    failing_client = MockFailingClient()
    ans, mode = answer_query(
        user_query="What is the strategic recommendation?",
        df_matrix=matrix,
        df_audit=df_gate,
        qualifications=quals,
        scenarios=scenarios,
        overrides=[],
        fx_rate=84.50,
        openai_client=failing_client
    )

    # Must explain limitation without inventing fake LLM answers
    assert "unavailable" in ans.lower() or "error" in ans.lower()
    assert "deterministic" in ans.lower()
    # Must still provide mathematically accurate live numbers
    assert f"{scenarios['spend_b']:,.0f}" in ans
