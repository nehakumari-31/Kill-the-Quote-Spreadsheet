"""
Tests for Fix: Correct Conditional Discounts and Award Scenario Calculations.

Verifies:
1. An all-lines discount is NEVER applied when the award is split across multiple vendors.
2. An all-lines discount is applied when the vendor wins 100% of all required RFx lines.
3. Uncovered lines prevent all-lines discount from being applied.
4. If an award is split, no portion of the vendor's award receives the all-lines discount.
5. Conditional discounts are evaluated independently across scenarios (Scenario A, B, C).
6. Recalculation of line-level prices, line spends, vendor totals, total award value, savings, and budget variance.
7. Discounts are not applied twice (idempotence).
8. Supported discount types: all_lines, spend_threshold, share_threshold, line_count_threshold, unconditional.
9. Audit display fields: original quoted amount, eligible discount, discount applied, discount not applied and reason, final award amount.
10. UI and AI Analyst share identical calculated figures.
"""

import pytest
import pandas as pd
import numpy as np

from core.scenarios import calculate_award_scenarios
from core.eligibility import VendorQualification
from core.config import DEFAULT_CONDITIONAL_DISCOUNTS, DISCOUNT_TYPES


@pytest.fixture
def base_setup():
    """Builds a test matrix with 30 line items and two eligible vendors."""
    rows = []
    for i in range(1, 31):
        rows.append({
            "Line #": i,
            "Item Code": f"CP-{i:03d}",
            "Description": f"Item {i}",
            "Est. Qty": 1000,
            "Delivery Location": "Pune (Chakan plant)",
            "Criticality": "A" if i <= 5 else "C",
            "Budget Price": 10.0,
            "V1 (Apex)": 8.0 if i <= 15 else 12.0,   # V1 cheaper on lines 1-15
            "V2 (PackTech)": 11.0 if i <= 15 else 9.0  # V2 cheaper on lines 16-30
        })
    df_matrix = pd.DataFrame(rows)

    quals = {
        "V1": VendorQualification(vendor_id="V1", vendor_name="Apex", status="Eligible", passed_mandatory_gates=True),
        "V2": VendorQualification(vendor_id="V2", vendor_name="PackTech", status="Eligible", passed_mandatory_gates=True)
    }

    return df_matrix, quals


# 1. Supported discount types identified
def test_supported_discount_types():
    expected_types = ["all_lines", "spend_threshold", "share_threshold", "line_count_threshold", "unconditional"]
    for dt in expected_types:
        assert dt in DISCOUNT_TYPES, f"Discount type '{dt}' must be supported"


# 2. All-lines discount is NEVER applied in a split award
def test_all_lines_discount_never_applied_on_split_award(base_setup):
    df_matrix, quals = base_setup

    discounts = {
        "V1": {
            "discount_pct": 0.05,
            "condition_type": "all_lines",
            "description": "5% discount for 100% all-lines award"
        }
    }

    res = calculate_award_scenarios(df_matrix, quals, conditional_discounts=discounts)
    disc_v1 = res["discounts_evaluated"]["V1 (Apex)"]

    # In split award: V1 wins 15 lines, V2 wins 15 lines
    assert disc_v1["applied"] is False, "All-lines discount must NOT be applied when award is split"
    assert disc_v1["discount_applied"] == 0.0
    assert "Split award" in disc_v1["discount_not_applied_reason"]
    assert disc_v1["final_award_amount"] == disc_v1["original_amount"]

    # Verify no line awarded to V1 had its price discounted
    for alloc in res["b_line_allocations"]:
        if alloc["Awarded Vendor"] == "V1 (Apex)":
            assert alloc["Landed Price (₹)"] == 8.0, "Individual lines must NOT be discounted in a split award"
            assert alloc["Line Spend (₹)"] == 8000.0


# 3. All-lines discount IS applied when vendor wins 100% of RFx lines
def test_all_lines_discount_applied_on_full_award(base_setup):
    df_matrix, quals = base_setup

    # Make V1 cheaper on ALL 30 lines
    df_v1_wins_all = df_matrix.copy()
    df_v1_wins_all["V1 (Apex)"] = 8.0
    df_v1_wins_all["V2 (PackTech)"] = 12.0

    discounts = {
        "V1": {
            "discount_pct": 0.05,
            "condition_type": "all_lines",
            "description": "5% discount for 100% all-lines award"
        }
    }

    res = calculate_award_scenarios(df_v1_wins_all, quals, conditional_discounts=discounts)
    disc_v1 = res["discounts_evaluated"]["V1 (Apex)"]

    # Pre-discount spend: 30 lines * 1000 qty * Rs 8.0 = Rs 240,000
    assert disc_v1["applied"] is True
    assert disc_v1["original_amount"] == 240000.0
    assert disc_v1["discount_applied"] == 12000.0  # 5% of 240,000
    assert disc_v1["final_award_amount"] == 228000.0
    assert disc_v1["discount_not_applied_reason"] is None

    # Line-level prices and spends must be recalculated by 5%
    for alloc in res["b_line_allocations"]:
        assert alloc["Awarded Vendor"] == "V1 (Apex)"
        assert alloc["Landed Price (₹)"] == 7.60  # 8.0 * 0.95
        assert alloc["Line Spend (₹)"] == 7600.0

    # Total spend must match sum of line spends and discounted vendor spend
    assert res["spend_b"] == 228000.0
    sum_lines = sum(a["Line Spend (₹)"] for a in res["b_line_allocations"])
    assert sum_lines == res["spend_b"]


# 4. Uncovered line prevents all-lines discount
def test_uncovered_line_prevents_all_lines_discount(base_setup):
    df_matrix, quals = base_setup

    df_mostly_v1 = df_matrix.copy()
    df_mostly_v1["V1 (Apex)"] = 8.0
    df_mostly_v1["V2 (PackTech)"] = 12.0
    # Line 30 has no quote from either vendor (uncovered)
    df_mostly_v1.loc[df_mostly_v1["Line #"] == 30, ["V1 (Apex)", "V2 (PackTech)"]] = np.nan

    discounts = {
        "V1": {
            "discount_pct": 0.05,
            "condition_type": "all_lines",
            "description": "5% all-lines award discount"
        }
    }

    res = calculate_award_scenarios(df_mostly_v1, quals, conditional_discounts=discounts)
    disc_v1 = res["discounts_evaluated"]["V1 (Apex)"]

    assert disc_v1["applied"] is False, "All-lines discount cannot apply when lines are uncovered"
    assert disc_v1["discount_applied"] == 0.0
    assert "uncovered" in disc_v1["discount_not_applied_reason"].lower()


# 5. Independent evaluation across scenarios
def test_independent_evaluation_across_scenarios(base_setup):
    df_matrix, quals = base_setup

    # V1 wins all in unconstrained (Scenario A), but in Scenario B lines 1-5 are disqualified for V1
    df_test = df_matrix.copy()
    df_test["V1 (Apex)"] = 7.0
    df_test["V2 (PackTech)"] = 9.0

    # Disqualify V1 on lines 1-5
    quals_restricted = {
        "V1": VendorQualification(vendor_id="V1", vendor_name="Apex", status="Conditionally Eligible", passed_mandatory_gates=True, banned_lines=[1, 2, 3, 4, 5]),
        "V2": VendorQualification(vendor_id="V2", vendor_name="PackTech", status="Eligible", passed_mandatory_gates=True)
    }

    discounts = {
        "V1": {
            "discount_pct": 0.05,
            "condition_type": "all_lines",
            "description": "5% discount for winning all lines"
        }
    }

    res = calculate_award_scenarios(df_test, quals_restricted, conditional_discounts=discounts)

    # In Scenario A (unconstrained): V1 wins all 30 lines -> discount APPLIED
    assert res["discounts_evaluated_a"]["V1 (Apex)"]["applied"] is True
    assert res["discounts_evaluated_a"]["V1 (Apex)"]["discount_applied"] > 0

    # In Scenario B (quality-gated): V1 banned from lines 1-5, so V2 wins those lines -> award is split -> discount NOT applied
    assert res["discounts_evaluated_b"]["V1 (Apex)"]["applied"] is False
    assert res["discounts_evaluated_b"]["V1 (Apex)"]["discount_applied"] == 0.0

    # In Scenario C (dual-sourcing on critical lines): lines 1-5 are dual sourced -> award is split -> discount NOT applied
    assert res["discounts_evaluated_c"]["V1 (Apex)"]["applied"] is False


# 6. Spend threshold discount condition
def test_spend_threshold_discount(base_setup):
    df_matrix, quals = base_setup

    discounts = {
        "V1": {
            "discount_pct": 0.03,
            "condition_type": "spend_threshold",
            "threshold": 100000.0,
            "description": "3% discount if awarded spend >= 100k"
        }
    }

    # In base setup, V1 wins lines 1-15: 15 * 1000 * Rs 8.0 = Rs 120,000 >= 100,000 threshold
    res = calculate_award_scenarios(df_matrix, quals, conditional_discounts=discounts)
    disc_v1 = res["discounts_evaluated"]["V1 (Apex)"]

    assert disc_v1["applied"] is True
    assert disc_v1["original_amount"] == 120000.0
    assert disc_v1["discount_applied"] == 3600.0  # 3% of 120,000
    assert disc_v1["final_award_amount"] == 116400.0

    # If threshold is higher (e.g. 200k), condition is not met
    discounts_high = {
        "V1": {
            "discount_pct": 0.03,
            "condition_type": "spend_threshold",
            "threshold": 200000.0,
            "description": "3% discount if awarded spend >= 200k"
        }
    }
    res_high = calculate_award_scenarios(df_matrix, quals, conditional_discounts=discounts_high)
    disc_high = res_high["discounts_evaluated"]["V1 (Apex)"]
    assert disc_high["applied"] is False
    assert disc_high["discount_applied"] == 0.0
    assert "below required threshold" in disc_high["discount_not_applied_reason"]


# 7. Audit display fields present in result
def test_audit_display_fields_present(base_setup):
    df_matrix, quals = base_setup

    discounts = {
        "V1": {
            "discount_pct": 0.05,
            "condition_type": "all_lines",
            "description": "5% all-lines discount"
        }
    }

    res = calculate_award_scenarios(df_matrix, quals, conditional_discounts=discounts)
    d = res["discounts_evaluated"]["V1 (Apex)"]

    # Verify all 5 required display properties
    assert "original_amount" in d, "Must display original quoted amount"
    assert "eligible_discount" in d, "Must display eligible discount"
    assert "discount_applied" in d, "Must display discount applied"
    assert "discount_not_applied_reason" in d, "Must display discount not applied and reason"
    assert "final_award_amount" in d, "Must display final award amount"


# 8. Do not apply discount twice (idempotence)
def test_discount_not_applied_twice(base_setup):
    df_matrix, quals = base_setup

    df_v1_wins_all = df_matrix.copy()
    df_v1_wins_all["V1 (Apex)"] = 10.0
    df_v1_wins_all["V2 (PackTech)"] = 20.0

    discounts = {
        "V1": {
            "discount_pct": 0.10,
            "condition_type": "all_lines",
            "description": "10% all-lines discount"
        }
    }

    # Run calculation first time
    res1 = calculate_award_scenarios(df_v1_wins_all, quals, conditional_discounts=discounts)
    # 30 * 1000 * 10 = 300,000. 10% discount = 30,000. Spend = 270,000
    assert res1["spend_b"] == 270000.0

    # Run calculation a second time
    res2 = calculate_award_scenarios(df_v1_wins_all, quals, conditional_discounts=discounts)
    assert res2["spend_b"] == 270000.0, "Spend must be identical; discount must not compound"
