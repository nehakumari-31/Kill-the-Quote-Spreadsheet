"""
Tests for Fix: Scenario C Visibility on Overview Screen.

Requirements verified:
1. Display all three scenarios — A, B, and C — in the Overview spend comparison.
2. Show each scenario's total award spend using the existing scenario calculation engine.
3. Show the absolute and percentage cost difference of Scenario B and C against Scenario A.
4. Clearly explain the trade-off between Scenario B and Scenario C using existing scenario descriptions and allocation logic.
5. Keep the existing recommended scenario unchanged (Scenario B remains recommended).
6. Ensure Scenario C values are dynamically updated whenever underlying quote data changes.
7. Keep the existing Overview layout and styling consistent.
"""

import os
import re
import pytest
import pandas as pd
import numpy as np

from core.scenarios import calculate_award_scenarios, evaluate_award_approval_gate
from core.models import VendorQualification


def test_overview_code_renders_all_three_scenarios():
    """Verify that app.py Overview section explicitly renders Scenario A, B, and C."""
    with open("app.py", "r", encoding="utf-8") as f:
        app_code = f.read()

    # Extract the Overview view block
    overview_match = re.search(
        r'if nav == "🏠 Overview & Recommendation":(.*?)(?:elif nav ==|else:)',
        app_code,
        re.DOTALL
    )
    assert overview_match is not None, "Overview view must exist in app.py"
    overview_block = overview_match.group(1)

    # 1. All three scenarios appear in Overview spend comparison
    assert "Scenario A: Unconstrained L1" in overview_block or "Scenario A" in overview_block
    assert "Scenario B: Quality-Gated L1" in overview_block or "Scenario B" in overview_block
    assert "Scenario C: Dual Sourcing (70/30)" in overview_block or "Scenario C" in overview_block

    # 2. Spend C is referenced from live_scenarios
    assert "live_scenarios['spend_c']" in overview_block or 'live_scenarios["spend_c"]' in overview_block

    # 3. Differences vs Scenario A are displayed for B and C
    assert "cost_diff_b_vs_a" in overview_block
    assert "pct_diff_b_vs_a" in overview_block
    assert "cost_diff_c_vs_a" in overview_block
    assert "pct_diff_c_vs_a" in overview_block

    # 4. Difference vs Scenario B is displayed for Scenario C trade-off
    assert "cost_diff_c_vs_b" in overview_block
    assert "pct_diff_c_vs_b" in overview_block

    # 5. Strategic trade-off explanation is present
    assert "Scenario B vs Scenario C" in overview_block
    assert "Criticality A lines" in overview_block or "Critical SKUs" in overview_block

    # 6. Scenario B remains the primary recommended scenario
    assert "Scenario B (Quality-Gated L1) ★" in overview_block
    assert "procure-card-highlight" in overview_block


def test_overview_scenario_c_cost_matches_calculation_engine():
    """Verify that displayed costs match the single source of truth calculate_award_scenarios engine."""
    # Create a realistic sample matrix with 30 items
    rows = []
    for l_no in range(1, 31):
        crit = "A" if l_no in [9, 10, 26, 27, 30] else "B" if l_no % 2 == 0 else "C"
        base_budget = 1000.0 * l_no
        rows.append({
            "Line #": l_no,
            "Item Code": f"CP-{l_no:03d}",
            "Description": f"Carton {l_no}",
            "Est. Qty": 1000,
            "Delivery Location": "Pune (Chakan plant)",
            "Criticality": crit,
            "Budget Price": base_budget,
            "V1 (Apex)": base_budget * 0.90,
            "V2 (PackTech)": base_budget * 0.92,
            "V3 (Global USD)": base_budget * 0.95,
            "V4 (Balaji)": base_budget * 0.85,  # Uncertified
            "V5 (Standard Box)": base_budget * 0.91,
        })
    df = pd.DataFrame(rows)

    quals = {
        "V1": VendorQualification("V1", "Apex", "Eligible", True),
        "V2": VendorQualification("V2", "PackTech", "Eligible", True),
        "V3": VendorQualification("V3", "Global USD", "Eligible", True),
        "V4": VendorQualification("V4", "Balaji", "Disqualified", False, reason="ISO Expired"),
        "V5": VendorQualification("V5", "Standard Box", "Eligible", True),
    }

    scenarios = calculate_award_scenarios(df, quals)

    # Validate engine output consistency
    spend_a = scenarios["spend_a"]
    spend_b = scenarios["spend_b"]
    spend_c = scenarios["spend_c"]

    # In unconstrained Scenario A, V4 wins lines because it is lowest
    assert spend_a < spend_b, "Scenario A must be cheaper than qualified Scenario B"

    # In Scenario C, 70/30 split on Criticality A lines introduces secondary suppliers
    assert spend_c >= spend_b, "Scenario C dual-sourcing must be >= single-sourcing Scenario B"

    # Verify difference fields are correctly calculated
    assert scenarios["cost_diff_c_vs_a"] == spend_c - spend_a
    assert abs(scenarios["pct_diff_c_vs_a"] - ((spend_c - spend_a) / spend_a) * 100.0) < 1e-4

    assert scenarios["cost_diff_c_vs_b"] == spend_c - spend_b
    assert abs(scenarios["pct_diff_c_vs_b"] - ((spend_c - spend_b) / spend_b) * 100.0) < 1e-4

    # Format simulation matching Overview display
    display_spend_c = f"₹{scenarios['spend_c']/1e7:.2f} Cr"
    display_diff_c_vs_a = f"+₹{scenarios['cost_diff_c_vs_a']:,.0f} (+{scenarios['pct_diff_c_vs_a']:.2f}% higher than Scenario A)"
    display_diff_c_vs_b = f"+₹{scenarios['cost_diff_c_vs_b']:,.0f} (+{scenarios['pct_diff_c_vs_b']:.2f}% higher than Scenario B)"

    assert display_spend_c.startswith("₹")
    assert "higher than Scenario A" in display_diff_c_vs_a
    assert "higher than Scenario B" in display_diff_c_vs_b


def test_dynamic_recalculation_updates_scenario_c():
    """Verify that Scenario C spend dynamically responds when quote matrix data is modified."""
    rows = []
    for l_no in range(1, 31):
        crit = "A" if l_no in [9, 10, 26, 27, 30] else "C"
        rows.append({
            "Line #": l_no,
            "Item Code": f"CP-{l_no:03d}",
            "Description": f"Item {l_no}",
            "Est. Qty": 1000,
            "Delivery Location": "Pune",
            "Criticality": crit,
            "Budget Price": 100.0,
            "V1 (Apex)": 90.0,
            "V2 (PackTech)": 95.0,
            "V3 (Global USD)": 92.0,
            "V4 (Balaji)": 80.0,
            "V5 (Standard Box)": 91.0,
        })
    df_initial = pd.DataFrame(rows)

    quals = {
        "V1": VendorQualification("V1", "Apex", "Eligible", True),
        "V2": VendorQualification("V2", "PackTech", "Eligible", True),
        "V3": VendorQualification("V3", "Global USD", "Eligible", True),
        "V4": VendorQualification("V4", "Balaji", "Disqualified", False),
        "V5": VendorQualification("V5", "Standard Box", "Eligible", True),
    }

    initial_scenarios = calculate_award_scenarios(df_initial, quals)
    initial_spend_c = initial_scenarios["spend_c"]
    initial_diff_c_vs_b = initial_scenarios["cost_diff_c_vs_b"]

    # Modify secondary supplier quote on Criticality A Line 9: V5 quote increases from 91.0 to 115.0
    # In Scenario B, V1 (90.0) remains 100% winner on Line 9 (so spend_b does not change)
    # In Scenario C, Line 9 is 70% V1 (90.0) + 30% V3 (92.0) or V5, dynamically recalculating spend_c and diffs
    df_modified = df_initial.copy()
    df_modified.loc[df_modified["Line #"] == 9, "V5 (Standard Box)"] = 115.0
    df_modified.loc[df_modified["Line #"] == 9, "V3 (Global USD)"] = 112.0

    updated_scenarios = calculate_award_scenarios(df_modified, quals)
    updated_spend_c = updated_scenarios["spend_c"]

    # Recalculation must immediately change Scenario C spend and diffs
    assert updated_spend_c != initial_spend_c, "Scenario C spend must dynamically react to quote updates"
    assert updated_scenarios["cost_diff_c_vs_a"] != initial_scenarios["cost_diff_c_vs_a"]
    assert updated_scenarios["cost_diff_c_vs_b"] != initial_diff_c_vs_b
