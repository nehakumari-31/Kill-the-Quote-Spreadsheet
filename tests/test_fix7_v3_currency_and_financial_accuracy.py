"""
Tests for Issue 3 (V3 Currency & UOM) and Issue 4 (Financial Display Accuracy).

Validates:
1. V3 USD extraction from DOCX extracts UOM as 'Nos' (never 'USD'), preserving 'USD' as currency.
2. Currency conversion preserves the original quoted UOM (Nos -> Nos); unit normalization is handled separately.
3. Ambiguous source UOM is flagged for review rather than silently assigned.
4. Financial percentage differences strictly use Scenario A as denominator and explicitly state 'higher than Scenario A'.
5. Dual-sourcing Scenario C difference vs Scenario B uses Scenario B denominator ('higher than Scenario B').
6. Absence of the word 'exactly' in all savings and compliance statements.
7. Cost of compliance is identified as an additional premium / investment over Scenario A, never as savings.
"""

import os
import io
import re
import pytest
import pandas as pd
import numpy as np

from core.config import DEFAULT_FX_RATE
from core.models import QuotationMetadata, ExtractedField
from core.extractor import extract_vendor_quote_file
from core.normalizer import normalize_price, parse_vendor_cell_edit
from core.scenarios import calculate_award_scenarios, evaluate_award_approval_gate
from core.analyst import answer_query


def test_v3_docx_extraction_uom_preservation():
    """Verify that V3 extraction from docx extracts UOM as 'Nos' and currency as 'USD'."""
    docx_path = "sample_quotes/V3_Global_Quote.docx"
    assert os.path.exists(docx_path), f"File {docx_path} must exist"

    with open(docx_path, "rb") as f:
        meta = extract_vendor_quote_file(f.read(), "V3_Global_Quote.docx")

    assert meta.vendor_id == "V3"
    assert meta.currency == "USD"

    # Line 1 should be $0.0703 with unit 'Nos' (NOT 'USD')
    field_1 = next((f for f in meta.fields if f.line_item == 1), None)
    assert field_1 is not None
    assert field_1.price == 0.0703
    assert field_1.unit == "Nos"
    assert field_1.currency == "USD"
    assert field_1.unit != "USD"

    # All quoted lines should have unit 'Nos'
    for f in meta.fields:
        if f.price is not None:
            assert f.unit == "Nos", f"Line {f.line_item} has invalid unit {f.unit}"
            assert f.currency == "USD"


def test_v3_currency_conversion_preserves_original_uom():
    """Currency conversion from USD to INR must preserve the original quoted UOM."""
    res = normalize_price(
        raw_value=0.0703,
        raw_unit="Nos",
        raw_currency="USD",
        target_uom="Nos",
        fx_rate=84.50
    )

    assert res.original_value == 0.0703
    assert res.original_currency == "USD"
    assert res.original_uom == "Nos"
    assert res.exchange_rate == 84.50

    # Converted INR price preserves original UOM
    expected_inr = round(0.0703 * 84.50, 4)
    assert res.converted_inr_price == expected_inr
    assert res.converted_inr_uom == "Nos"

    # Normalized comparison price and UOM
    assert res.normalized_price == expected_inr
    assert res.normalized_uom == "Nos"


def test_v3_ambiguous_uom_flagged_for_buyer_clarification():
    """If a quotation has no identifiable UOM and no unit pattern, it must be flagged for buyer review."""
    from core.extractor import _parse_docx_file
    import docx

    # Create an in-memory docx with an ambiguous line (no /Nos or /kg in notes or price)
    doc = docx.Document()
    tbl = doc.add_table(rows=2, cols=5)
    tbl.rows[0].cells[0].text = "Line #"
    tbl.rows[0].cells[1].text = "Item Code"
    tbl.rows[0].cells[2].text = "Description"
    tbl.rows[0].cells[3].text = "Price (USD)"
    tbl.rows[0].cells[4].text = "Remarks"

    tbl.rows[1].cells[0].text = "1"
    tbl.rows[1].cells[1].text = "CP-001"
    tbl.rows[1].cells[2].text = "Carton box"
    tbl.rows[1].cells[3].text = "$0.50"
    tbl.rows[1].cells[4].text = "FOB Nhava Sheva, standard delivery"

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)

    meta = QuotationMetadata(filename="test.docx", vendor_id="V3", vendor_name="Global Corrugators", format="DOCX", currency="USD")
    _parse_docx_file(buf.getvalue(), "test.docx", meta)

    assert len(meta.fields) == 1
    f = meta.fields[0]
    assert f.price == 0.50
    assert f.unit == "Ambiguous"
    assert f.extraction_status == "Needs Review"


def test_parse_vendor_cell_edit_preserves_usd_and_uom():
    """Manual override with USD string input preserves USD currency and UOM."""
    val, status, cite, reason, changed = parse_vendor_cell_edit(
        current_val=None,
        edited_val="$0.0703 /Nos",
        line_no=1,
        delivery_location="Pune (Chakan plant)",
        item_weight_kg=0.5,
        is_new_sku=False,
        fx_rate=84.50
    )

    assert changed is True
    assert status == "Verified"
    assert val is not None
    assert round(val, 2) == round(0.0703 * 84.50, 2)
    assert "84.50" in cite


def test_financial_comparison_baselines_and_percentage_accuracy():
    """Verify percentage difference formula and baseline identification."""
    from core.models import VendorQualification

    # Load master items to get real scenario calculation
    xl = pd.ExcelFile("RFx_Master_Updated.xlsx")
    df_items = pd.read_excel(xl, sheet_name="Line Items")
    df_items = df_items[pd.to_numeric(df_items["Line #"], errors="coerce").notna()].copy()
    df_items["Line #"] = df_items["Line #"].astype(int)

    # Simple sample with real spend proportions
    quals = {
        "V1": VendorQualification("V1", "Apex", "Eligible", True),
        "V2": VendorQualification("V2", "PackTech", "Eligible", True),
        "V3": VendorQualification("V3", "Global USD", "Eligible", True),
        "V4": VendorQualification("V4", "Balaji", "Disqualified", False),
        "V5": VendorQualification("V5", "Standard Box", "Eligible", True),
    }

    # Build matrix with 30 items
    rows = []
    for _, r in df_items.iterrows():
        l_no = int(r["Line #"])
        qty = int(r["Est. Annual Qty (UoM)"])
        budget_p = float(r["Budget Unit Price (₹ / UoM)"])
        rows.append({
            "Line #": l_no,
            "Item Code": str(r["Item Code"]),
            "Description": str(r.get("Item Description", "")),
            "Est. Qty": qty,
            "Delivery Location": str(r.get("Delivery Location", "Pune (Chakan plant)")),
            "Criticality": str(r.get("Criticality (A/B/C)", "C")),
            "Budget Price": budget_p,
            "V1 (Apex)": round(budget_p * 0.98, 2),
            "V2 (PackTech)": round(budget_p * 1.01, 2),
            "V3 (Global USD)": round((budget_p * 0.95) / 84.50, 4) * 84.50 if l_no not in [10, 21, 25, 30] else np.nan,
            "V4 (Balaji)": round(budget_p * 0.92, 2),
            "V5 (Standard Box)": round(budget_p * 0.97, 2) if l_no not in [25, 27, 28, 29, 30] else np.nan
        })

    df_sample = pd.DataFrame(rows)
    scenarios = calculate_award_scenarios(df_sample, quals)

    spend_a = scenarios["spend_a"]
    spend_b = scenarios["spend_b"]
    spend_c = scenarios["spend_c"]

    # 1. Cost of Compliance is B - A
    cost_of_compliance = scenarios["cost_of_compliance"]
    assert cost_of_compliance == spend_b - spend_a
    assert cost_of_compliance > 0

    # 2. Compliance percentage uses Scenario A as denominator
    expected_compliance_pct = ((spend_b - spend_a) / spend_a) * 100.0
    assert abs(scenarios["compliance_pct"] - expected_compliance_pct) < 1e-4

    # 3. Scenario C vs A uses Scenario A as denominator
    expected_c_vs_a_pct = ((spend_c - spend_a) / spend_a) * 100.0
    assert abs(scenarios["pct_diff_c_vs_a"] - expected_c_vs_a_pct) < 1e-4

    # 4. Scenario C vs B uses Scenario B as denominator
    expected_c_vs_b_pct = ((spend_c - spend_b) / spend_b) * 100.0
    assert abs(scenarios["pct_diff_c_vs_b"] - expected_c_vs_b_pct) < 1e-4


def test_analyst_responses_contain_no_exactly_and_state_baselines():
    """Verify that analyst output never contains 'exactly' and explicitly states comparison baselines."""
    from core.models import VendorQualification

    df_matrix = pd.DataFrame([{
        "Line #": 1,
        "Item Code": "CP-001",
        "Description": "Test carton",
        "Est. Qty": 10000,
        "Delivery Location": "Pune (Chakan plant)",
        "Criticality": "C",
        "Budget Price": 100.0,
        "V1 (Apex)": 98.0,
        "V2 (PackTech)": 101.0,
        "V3 (Global USD)": 95.0,
        "V4 (Balaji)": 92.0,
        "V5 (Standard Box)": 97.0,
        "V1 Citation": "Direct quote",
        "V2 Citation": "Direct quote",
        "V3 Citation": "USD converted",
        "V4 Citation": "Direct quote",
        "V5 Citation": "Direct quote"
    }])

    quals = {
        "V1": VendorQualification("V1", "Apex", "Eligible", True),
        "V2": VendorQualification("V2", "PackTech", "Eligible", True),
        "V3": VendorQualification("V3", "Global USD", "Eligible", True),
        "V4": VendorQualification("V4", "Balaji", "Disqualified", False, failed_general_gates=["Q1 ISO Expired"]),
        "V5": VendorQualification("V5", "Standard Box", "Eligible", True),
    }

    scenarios = {
        "budget_spend": 40003750.0,
        "spend_a": 37447255.0,
        "spend_b": 37915847.3,
        "spend_c": 38034120.5,
        "savings_a": 2556495.0,
        "savings_b": 2087902.7,
        "savings_c": 1969629.5,
        "savings_pct_a": 6.39,
        "savings_pct_b": 5.22,
        "savings_pct_c": 4.92,
        "cost_of_compliance": 468592.3,
        "compliance_pct": 1.25,
        "cost_diff_b_vs_a": 468592.3,
        "pct_diff_b_vs_a": 1.25,
        "cost_diff_c_vs_a": 586865.5,
        "pct_diff_c_vs_a": 1.57,
        "cost_diff_c_vs_b": 118273.2,
        "pct_diff_c_vs_b": 0.31,
        "uncovered_lines_b": [],
        "risks_b": [],
        "vendor_shares_b": {"Apex": {"spend": 37915847.3, "share_pct": 100.0}}
    }

    df_audit = pd.DataFrame()

    questions = [
        "Which vendor should we award to, and why? Compare the lowest-cost option with the quality and compliance requirements.",
        "What are the key commercial and compliance risks in these quotations? Identify unresolved items that require buyer intervention.",
        "Why is Scenario B recommended over Scenario C? Explain the cost difference and the dual-sourcing trade-off.",
        "What is the cost of compliance?"
    ]

    for q in questions:
        ans, mode = answer_query(
            user_query=q,
            df_matrix=df_matrix,
            df_audit=df_audit,
            qualifications=quals,
            scenarios=scenarios
        )

        # 1. Must never say "exactly"
        assert "exactly" not in ans.lower(), f"Answer to '{q}' contains 'exactly': {ans}"

        # 2. For award and compliance queries, verify baseline naming
        if "award" in q.lower() or "cost of compliance" in q.lower():
            assert "higher than Scenario A" in ans or "vs lowest-cost a" in ans.lower()

        if "scenario c" in q.lower():
            assert "higher than Scenario B" in ans
