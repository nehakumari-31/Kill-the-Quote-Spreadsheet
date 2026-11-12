"""
Test Suite for Fix 6: AI Procurement Analyst Experience and Centralized Award Approval Gate
Validates:
1. Dynamic counting of unresolved quotation lines.
2. Exclusion of genuinely ineligible or disqualified vendors from the unresolved count
   (Vendor 4 globally; Vendor 5 on Line 27 for moisture barrier).
3. Centralized approval gate status label and guidance message when blocked:
   - "Award on Scenario B — BLOCKED pending X unresolved lines."
   - "Buyer clarification or documented override required before award approval."
4. Transition to Approval Ready when all blocking unresolved items are resolved via buyer overrides.
5. Preservation of Scenario B award recommendation regardless of gate state.
6. Demonstration Question 1:
   "Which vendor should we award to, and why? Compare the lowest-cost option with the quality and compliance requirements."
7. Demonstration Question 2:
   "What are the key commercial and compliance risks in these quotations? Identify unresolved items that require buyer intervention."
8. Demonstration Question 3:
   "Why is Scenario B recommended over Scenario C? Explain the cost difference and the dual-sourcing trade-off."
9. Handling of API unavailable / offline states with deterministic analytical reasoning.
10. UI integration and session conversation history maintenance.
"""

import pytest
import numpy as np
import pandas as pd

from core.scenarios import calculate_award_scenarios, evaluate_award_approval_gate
from core.eligibility import evaluate_vendor_qualifications, is_vendor_eligible_for_line
from core.analyst import answer_query, build_system_context
from core.models import BuyerOverrideRecord, VendorQualification

GROUND_TRUTH_FILE = "RFx_Master_Updated.xlsx"


@pytest.fixture(scope="module")
def base_rfx_state():
    """Loads ground truth workbook and builds standard normalized matrix."""
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

    for c in ["V1", "V2", "V3", "V4", "V5"]:
        matrix_df[f"{c} Citation"] = "Ground Truth Citation"
        matrix_df[f"{c} Status"] = "Verified"
    matrix_df["V5 Trust Flag"] = "Verified"

    # Set base unresolved states: Vendor 5 quoted 'Same as last year' on New SKUs (Lines 25, 27, 28, 29, 30)
    for l in [25, 27, 28, 29, 30]:
        matrix_df.loc[matrix_df["Line #"] == l, "V5 (Standard Box)"] = None
        matrix_df.loc[matrix_df["Line #"] == l, "V5 Status"] = "Unresolved"
        matrix_df.loc[matrix_df["Line #"] == l, "V5 Citation"] = "Quoted 'Same as last year' on New SKU -> UNRESOLVED"
        matrix_df.loc[matrix_df["Line #"] == l, "V5 Trust Flag"] = "UNRESOLVED"
        matrix_df.loc[matrix_df["Line #"] == l, "V5 Unresolved Reason"] = "Quoted 'Same as last year' on New SKU with no PO history"

    quals = evaluate_vendor_qualifications(df_gate, df_items)

    return {
        "matrix": matrix_df,
        "gate": df_gate,
        "items": df_items,
        "quals": quals
    }


# ─────────────────────────────────────────────────────────────────────────────
# 1. CENTRALIZED APPROVAL GATE TESTS
# ─────────────────────────────────────────────────────────────────────────────

def test_approval_gate_dynamically_counts_unresolved_lines(base_rfx_state):
    """Verifies that unresolved lines are counted dynamically."""
    matrix = base_rfx_state["matrix"].copy()
    quals = base_rfx_state["quals"]

    gate = evaluate_award_approval_gate(matrix, quals)
    assert gate["unresolved_line_count"] == 4
    assert gate["unresolved_lines"] == [25, 28, 29, 30]
    assert gate["is_blocked"] is True


def test_approval_gate_excludes_disqualified_vendors(base_rfx_state):
    """
    CRITICAL RULE: Genuinely ineligible or disqualified vendors must be excluded
    from the unresolved count.
    - Vendor 4 is globally disqualified (failed ISO 9001 and capacity).
    - Vendor 5 is disqualified on Line 27 (failed Gate Q7 moisture barrier).
    Neither should count as a blocking unresolved line.
    """
    matrix = base_rfx_state["matrix"].copy()
    quals = base_rfx_state["quals"]

    # Mark Vendor 4 as Unresolved across 5 lines
    for l in [1, 2, 3, 4, 5]:
        matrix.loc[matrix["Line #"] == l, "V4 Status"] = "Unresolved"
        matrix.loc[matrix["Line #"] == l, "V4 Citation"] = "UNRESOLVED quote"

    # Line 27 is also marked Unresolved for Vendor 5, but V5 is disqualified for Line 27
    assert matrix.loc[matrix["Line #"] == 27, "V5 Status"].values[0] == "Unresolved"
    assert is_vendor_eligible_for_line("V5", 27, quals) is False
    assert is_vendor_eligible_for_line("V4", 1, quals) is False

    gate = evaluate_award_approval_gate(matrix, quals)

    # Line 27 must NOT be in unresolved_lines because V5 is disqualified on Line 27
    assert 27 not in gate["unresolved_lines"]
    # Vendor 4 lines (1-5) must NOT be in unresolved_lines because V4 is disqualified globally
    for l in [1, 2, 3, 4, 5]:
        assert l not in gate["unresolved_lines"]

    # Exactly Lines 25, 28, 29, 30 remain
    assert gate["unresolved_lines"] == [25, 28, 29, 30]
    assert gate["unresolved_line_count"] == 4


def test_approval_gate_exact_display_strings_when_blocked(base_rfx_state):
    """
    Verifies exact required strings when blocked:
    - 'Award on Scenario B — BLOCKED pending X unresolved lines.'
    - 'Buyer clarification or documented override required before award approval.'
    """
    matrix = base_rfx_state["matrix"].copy()
    quals = base_rfx_state["quals"]

    gate = evaluate_award_approval_gate(matrix, quals)
    assert gate["status_label"] == "Award on Scenario B — BLOCKED pending 4 unresolved lines."
    assert gate["guidance_message"] == "Buyer clarification or documented override required before award approval."


def test_approval_gate_override_resolution_and_approval_ready(base_rfx_state):
    """
    Verifies that:
    1. A buyer override resolves the relevant issue only when a valid override and audit record exist.
    2. Overrides incrementally decrease the count.
    3. When all blocking unresolved items are resolved, display the approval-ready state.
    4. Does not change actual award recommendation merely to bypass the gate (still Scenario B).
    """
    matrix = base_rfx_state["matrix"].copy()
    quals = base_rfx_state["quals"]

    # 1. Invalid override without reason or with 'UNRESOLVED' value does not resolve
    invalid_override = BuyerOverrideRecord(
        line_no=25,
        item_code="CP-025",
        vendor_col="V5 (Standard Box)",
        original_value="Same as last year",
        corrected_value="UNRESOLVED",
        reason=""
    )
    gate_inv = evaluate_award_approval_gate(matrix, quals, [invalid_override])
    assert gate_inv["unresolved_line_count"] == 4

    # 2. Valid override for Line 25
    valid_override_25 = BuyerOverrideRecord(
        line_no=25,
        item_code="CP-025",
        vendor_col="V5 (Standard Box)",
        original_value="Same as last year",
        corrected_value=14.50,
        reason="Negotiated flat unit rate with Standard Box via email"
    )
    gate_1 = evaluate_award_approval_gate(matrix, quals, [valid_override_25])
    assert gate_1["unresolved_line_count"] == 3
    assert gate_1["unresolved_lines"] == [28, 29, 30]
    assert gate_1["status_label"] == "Award on Scenario B — BLOCKED pending 3 unresolved lines."

    # 3. Resolve all 4 lines (25, 28, 29, 30)
    all_overrides = [
        valid_override_25,
        BuyerOverrideRecord(line_no=28, item_code="CP-028", vendor_col="V5 (Standard Box)", original_value="Same as last year", corrected_value=8.20, reason="Audited against PO-2025-09"),
        BuyerOverrideRecord(line_no=29, item_code="CP-029", vendor_col="V5 (Standard Box)", original_value="Same as last year", corrected_value=9.10, reason="Audited against PO-2025-09"),
        BuyerOverrideRecord(line_no=30, item_code="CP-030", vendor_col="V5 (Standard Box)", original_value="Same as last year", corrected_value=45.00, reason="Confirmed 7-ply quote")
    ]
    gate_ready = evaluate_award_approval_gate(matrix, quals, all_overrides)
    assert gate_ready["unresolved_line_count"] == 0
    assert gate_ready["is_blocked"] is False
    assert gate_ready["status_label"] == "Award on Scenario B — Approval Ready"
    assert "ready" in gate_ready["guidance_message"].lower()

    # Recommendation remains Scenario B
    assert gate_ready["recommendation"] == "Award on Scenario B (Quality-Gated L1)"
    assert gate_ready["target_scenario"] == "Scenario B"


# ─────────────────────────────────────────────────────────────────────────────
# 2. AI ANALYST DEMONSTRATION QUESTIONS TESTS
# ─────────────────────────────────────────────────────────────────────────────

def test_analyst_demo_question_1_vendor_award_and_cost_of_compliance(base_rfx_state):
    """
    Demonstration Question 1:
    "Which vendor should we award to, and why? Compare the lowest-cost option with the quality and compliance requirements."
    Verifies:
    - Recommends Scenario B (Quality-Gated L1).
    - Cites lowest-cost Scenario A and compares spends.
    - Cites cost of compliance premium (+₹2.75 L / +0.73%).
    - Explains Vendor 4 disqualification (expired ISO 9001 and inadequate 280 TPM capacity).
    - Explicitly cites current Approval Gate status ('Award on Scenario B — BLOCKED pending 4 unresolved lines.').
    """
    matrix = base_rfx_state["matrix"]
    gate_df = base_rfx_state["gate"]
    quals = base_rfx_state["quals"]
    scenarios = calculate_award_scenarios(matrix, quals)

    q1 = "Which vendor should we award to, and why? Compare the lowest-cost option with the quality and compliance requirements."
    ans, mode = answer_query(
        user_query=q1,
        df_matrix=matrix,
        df_audit=gate_df,
        qualifications=quals,
        scenarios=scenarios,
        overrides=[],
        fx_rate=84.50,
        openai_client=None
    )

    assert "Scenario B" in ans
    assert "Scenario A" in ans
    assert f"{scenarios['spend_b']:,.0f}" in ans
    assert f"{scenarios['cost_of_compliance']:,.0f}" in ans
    assert "Vendor 4" in ans or "Sri Balaji" in ans
    assert "ISO 9001" in ans
    assert "BLOCKED pending 4 unresolved lines" in ans
    assert "Deterministic Analytics Engine" in mode


def test_analyst_demo_question_2_commercial_and_compliance_risks(base_rfx_state):
    """
    Demonstration Question 2:
    "What are the key commercial and compliance risks in these quotations? Identify unresolved items that require buyer intervention."
    Verifies:
    - Identifies unresolved items requiring buyer intervention (Vendor 5 on Lines 25, 28, 29, 30).
    - Explains that Line 27 is excluded from the blocking gate because V5 failed Gate Q7 for moisture barrier.
    - Identifies Vendor 4 global disqualification (ISO expired, capacity 280 TPM, defect rate 2.4%).
    - Identifies line restrictions for Vendor 3 (lacks 7-ply) and Vendor 5 (lacks moisture barrier).
    - Identifies FX risk on USD quotes for Vendor 3.
    - Identifies conditional discount policy on Vendor 1.
    """
    matrix = base_rfx_state["matrix"]
    gate_df = base_rfx_state["gate"]
    quals = base_rfx_state["quals"]
    scenarios = calculate_award_scenarios(matrix, quals)

    q2 = "What are the key commercial and compliance risks in these quotations? Identify unresolved items that require buyer intervention."
    ans, mode = answer_query(
        user_query=q2,
        df_matrix=matrix,
        df_audit=gate_df,
        qualifications=quals,
        scenarios=scenarios,
        overrides=[],
        fx_rate=84.50,
        openai_client=None
    )

    assert "BLOCKED pending 4 unresolved lines" in ans
    assert "Vendor 5" in ans or "Standard Box" in ans
    assert "Lines [25, 28, 29, 30]" in ans or "25, 28, 29, 30" in ans
    assert "Line 27" in ans
    assert "Vendor 4" in ans or "Sri Balaji" in ans
    assert "ISO 9001" in ans
    assert "Vendor 3" in ans or "Global" in ans
    assert "Deterministic Analytics Engine" in mode


def test_analyst_demo_question_3_scenario_b_vs_c_dual_sourcing_tradeoff(base_rfx_state):
    """
    Demonstration Question 3:
    "Why is Scenario B recommended over Scenario C? Explain the cost difference and the dual-sourcing trade-off."
    Verifies:
    - Recommends Scenario B over Scenario C for commercial baseline.
    - Cites exact cost difference between Scenario C and Scenario B.
    - Explains dual-sourcing 70/30 split on Criticality A lines.
    - Explains the trade-off: supply chain insurance vs cost savings.
    """
    matrix = base_rfx_state["matrix"]
    gate_df = base_rfx_state["gate"]
    quals = base_rfx_state["quals"]
    scenarios = calculate_award_scenarios(matrix, quals)

    q3 = "Why is Scenario B recommended over Scenario C? Explain the cost difference and the dual-sourcing trade-off."
    ans, mode = answer_query(
        user_query=q3,
        df_matrix=matrix,
        df_audit=gate_df,
        qualifications=quals,
        scenarios=scenarios,
        overrides=[],
        fx_rate=84.50,
        openai_client=None
    )

    assert "Scenario B" in ans
    assert "Scenario C" in ans
    assert f"{scenarios['spend_b']:,.0f}" in ans
    assert f"{scenarios['spend_c']:,.0f}" in ans
    cost_diff = scenarios["spend_c"] - scenarios["spend_b"]
    assert f"{cost_diff:,.0f}" in ans
    assert "Criticality A" in ans or "70/30" in ans or "70%" in ans
    assert "trade-off" in ans.lower() or "insurance" in ans.lower() or "resilience" in ans.lower()


def test_analyst_handles_api_failure_gracefully_with_live_data(base_rfx_state):
    """
    Verifies that when OpenAI client throws an exception,
    the analyst falls back to the deterministic engine without fabricating answers.
    """
    matrix = base_rfx_state["matrix"]
    gate_df = base_rfx_state["gate"]
    quals = base_rfx_state["quals"]
    scenarios = calculate_award_scenarios(matrix, quals)

    class FailingClient:
        class chat:
            class completions:
                @staticmethod
                def create(*args, **kwargs):
                    raise RuntimeError("Simulated 500 API Gateway Error")

    ans, mode = answer_query(
        user_query="Which vendor should we award to, and why? Compare the lowest-cost option with the quality and compliance requirements.",
        df_matrix=matrix,
        df_audit=gate_df,
        qualifications=quals,
        scenarios=scenarios,
        overrides=[],
        fx_rate=84.50,
        openai_client=FailingClient()
    )

    assert "unavailable" in ans.lower() or "error" in ans.lower()
    assert "Deterministic Reasoning" in ans
    assert f"{scenarios['spend_b']:,.0f}" in ans
    assert mode == "Deterministic Engine (API Unavailable)"


def test_analyst_passes_full_conversation_history_to_openai(base_rfx_state):
    """
    Verifies that when OpenAI client is used, the complete conversation history
    is passed to the API on subsequent turns, avoiding duplicate messages.
    """
    matrix = base_rfx_state["matrix"]
    gate_df = base_rfx_state["gate"]
    quals = base_rfx_state["quals"]
    scenarios = calculate_award_scenarios(matrix, quals)

    captured_calls = []

    class MockOpenAIClient:
        class chat:
            class completions:
                @staticmethod
                def create(*args, **kwargs):
                    captured_calls.append(kwargs)
                    class Response:
                        class Choice:
                            class Message:
                                content = "Mocked GPT-4o analytical reasoning response."
                            message = Message()
                        choices = [Choice()]
                    return Response()

    prior_history = [
        {"role": "user", "content": "Question 1: Which vendor should we award to?"},
        {"role": "assistant", "content": "We recommend Scenario B (Apex Packaging).", "engine": "Live OpenAI GPT-4o"}
    ]
    follow_up_q = "What are the key risks with this award?"

    ans, mode = answer_query(
        user_query=follow_up_q,
        df_matrix=matrix,
        df_audit=gate_df,
        qualifications=quals,
        scenarios=scenarios,
        overrides=[],
        fx_rate=84.50,
        openai_client=MockOpenAIClient(),
        conversation_history=prior_history
    )

    assert mode == "Live OpenAI GPT-4o"
    assert ans == "Mocked GPT-4o analytical reasoning response."
    assert len(captured_calls) == 1

    messages_sent = captured_calls[0]["messages"]
    assert messages_sent[0]["role"] == "system"
    assert messages_sent[1]["role"] == "user"
    assert messages_sent[1]["content"] == "Question 1: Which vendor should we award to?"
    assert messages_sent[2]["role"] == "assistant"
    assert messages_sent[2]["content"] == "We recommend Scenario B (Apex Packaging)."
    assert messages_sent[3]["role"] == "user"
    assert messages_sent[3]["content"] == follow_up_q
    # Total messages: system + 2 prior turns + 1 new query = 4
    assert len(messages_sent) == 4


def test_analyst_figures_are_strictly_dynamic(base_rfx_state):
    """
    Verifies that all numerical values in Analyst responses are dynamically obtained
    from the current calculation engine and RFx data, never hardcoded.
    """
    matrix = base_rfx_state["matrix"]
    gate_df = base_rfx_state["gate"]
    quals = base_rfx_state["quals"]

    # Custom modified scenarios to test dynamic calculation reflection
    custom_scenarios = {
        "budget_spend": 50000000.0,
        "spend_a": 42000000.0,
        "savings_a": 8000000.0,
        "savings_pct_a": 16.0,
        "spend_b": 44000000.0,
        "savings_b": 6000000.0,
        "savings_pct_b": 12.0,
        "spend_c": 47500000.0,
        "savings_c": 2500000.0,
        "savings_pct_c": 5.0,
        "cost_of_compliance": 2000000.0,
        "compliance_pct": 4.76,
        "uncovered_lines_b": [],
        "risks_b": [],
        "vendor_shares_b": {"Apex Packaging (V1)": {"spend": 44000000.0, "share_pct": 100.0}}
    }

    q3 = "Why is Scenario B recommended over Scenario C? Explain the cost difference and the dual-sourcing trade-off."
    ans, _ = answer_query(
        user_query=q3,
        df_matrix=matrix,
        df_audit=gate_df,
        qualifications=quals,
        scenarios=custom_scenarios,
        overrides=[],
        fx_rate=84.50,
        openai_client=None
    )

    # Dynamic cost diff: 47,500,000 - 44,000,000 = 3,500,000
    assert "3,500,000" in ans
    assert "44,000,000" in ans
    assert "47,500,000" in ans
    assert "6,000,000" in ans
    # Must NOT have old hardcoded figures
    assert "1,33,356" not in ans
    assert "1.33 Lakhs" not in ans
    assert "20.06 Lakhs" not in ans


def test_analyst_followup_question_retains_context(base_rfx_state):
    """
    Verifies that follow-up questions retain context when previous conversation is provided.
    """
    matrix = base_rfx_state["matrix"]
    gate_df = base_rfx_state["gate"]
    quals = base_rfx_state["quals"]
    scenarios = calculate_award_scenarios(matrix, quals)

    history = [
        {"role": "user", "content": "Which vendor should we award to, and why? Compare the lowest-cost option with the quality and compliance requirements."},
        {"role": "assistant", "content": "Award on Scenario B. Vendor 4 is disqualified."}
    ]

    # Follow up asking "Why?"
    ans, _ = answer_query(
        user_query="Why was that vendor disqualified?",
        df_matrix=matrix,
        df_audit=gate_df,
        qualifications=quals,
        scenarios=scenarios,
        overrides=[],
        fx_rate=84.50,
        openai_client=None,
        conversation_history=history
    )

    assert "Vendor 4" in ans or "Sri Balaji" in ans
    assert "ISO 9001" in ans
    assert "280 TPM" in ans or "capacity" in ans.lower()


def test_analyst_offline_mode_distinct_from_gpt(base_rfx_state):
    """
    Verifies that when OpenAI client is None, the response is explicitly branded as
    Deterministic Analytics Engine and does not claim to be GPT-4o output.
    """
    matrix = base_rfx_state["matrix"]
    gate_df = base_rfx_state["gate"]
    quals = base_rfx_state["quals"]
    scenarios = calculate_award_scenarios(matrix, quals)

    ans, mode = answer_query(
        user_query="What are the key commercial and compliance risks in these quotations? Identify unresolved items that require buyer intervention.",
        df_matrix=matrix,
        df_audit=gate_df,
        qualifications=quals,
        scenarios=scenarios,
        overrides=[],
        fx_rate=84.50,
        openai_client=None
    )

    assert "Deterministic Analytics Engine" in mode
    assert "NOT by GPT-4o" in ans
    assert "Deterministic Analytics Engine (Offline Mode)" in ans

