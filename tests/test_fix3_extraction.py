"""
Test Suite for Fix 3: Genuine Document Extraction & Evidence Ingestion
Tests real extraction across Excel, PDF, Word, Image, and Email formats against ground truth.
Verifies CP code mapping, source citations, missing/ambiguous value flags, and vision fallback rules.
"""

import os
import io
import pytest
import pandas as pd
import numpy as np

from core.extractor import (
    extract_vendor_quote_file,
    _parse_excel_file,
    _parse_pdf_file,
    _parse_docx_file,
    _parse_eml_file,
    _parse_image_fallback
)
from core.models import QuotationMetadata, ExtractedField
from core.normalizer import normalize_price
from core.config import DEFAULT_FX_RATE as FX_RATE, DEFAULT_FREIGHT_RATES as FREIGHT_RATES


SAMPLE_DIR = "sample_quotes"
GROUND_TRUTH_FILE = "RFx_Master_Updated.xlsx"


@pytest.fixture(scope="module")
def ground_truth():
    """Loads ground truth normalized comparison from the master RFx workbook."""
    assert os.path.exists(GROUND_TRUTH_FILE), f"Workbook not found at {GROUND_TRUTH_FILE}"
    df_gt = pd.read_excel(GROUND_TRUTH_FILE, sheet_name="Normalized Comparison")
    df_items = pd.read_excel(GROUND_TRUTH_FILE, sheet_name="Line Items")
    return {"comparison": df_gt, "items": df_items}


# ─────────────────────────────────────────────────────────────────────────────
# 1. EXCEL EXTRACTION (.xlsx) - V1 Apex
# ─────────────────────────────────────────────────────────────────────────────
def test_excel_extraction_v1_apex(ground_truth):
    """
    Verifies genuine Excel extraction from V1_Apex_Quote.xlsx:
    - Extracts all 30 CP line item codes (CP-001 through CP-030).
    - Accurately captures /1000 Nos unit on Lines 1 and 2.
    - Preserves exact sheet and cell source references.
    """
    fpath = os.path.join(SAMPLE_DIR, "V1_Apex_Quote.xlsx")
    assert os.path.exists(fpath)
    with open(fpath, "rb") as f:
        meta = extract_vendor_quote_file(f.read(), "V1_Apex_Quote.xlsx")

    assert meta.vendor_id == "V1"
    assert "Apex" in meta.vendor_name
    assert meta.format == "XLSX"
    assert len(meta.fields) == 30

    # Verify all 30 CP codes present
    codes = [f.item_code for f in meta.fields]
    expected_codes = [f"CP-{i:03d}" for i in range(1, 31)]
    assert codes == expected_codes

    # Line 1: 6120 per 1000 Nos
    f1 = meta.fields[0]
    assert f1.line_item == 1
    assert f1.price == 6120.0
    assert "1000" in f1.unit
    assert "Sheet" in f1.source_reference and "Cell" in f1.source_reference
    assert f1.extraction_status == "Verified"

    # Line 2: 10350 per 1000 Nos
    f2 = meta.fields[1]
    assert f2.line_item == 2
    assert f2.price == 10350.0
    assert "1000" in f2.unit

    # Check accuracy against ground truth landed price (normalized by 1000)
    df_gt = ground_truth["comparison"]
    for f in meta.fields:
        gt_landed = df_gt.loc[df_gt["Line #"] == f.line_item, "V1 Landed (Apex)"].values[0]
        actual_rate = f.price / 1000.0 if "1000" in f.unit else f.price
        assert abs(actual_rate - gt_landed) < 0.05, f"V1 Line {f.line_item} mismatch: {actual_rate} vs {gt_landed}"


# ─────────────────────────────────────────────────────────────────────────────
# 2. PDF EXTRACTION (.pdf) - V2 PackTech
# ─────────────────────────────────────────────────────────────────────────────
def test_pdf_extraction_v2_packtech(ground_truth):
    """
    Verifies genuine PDF extraction from V2_PackTech_Quote.pdf:
    - Extracts all 30 CP line items with exact rates.
    - Captures freight terms (Included) and payment terms.
    - Preserves source references to page numbers and table rows.
    """
    fpath = os.path.join(SAMPLE_DIR, "V2_PackTech_Quote.pdf")
    assert os.path.exists(fpath)
    with open(fpath, "rb") as f:
        meta = extract_vendor_quote_file(f.read(), "V2_PackTech_Quote.pdf")

    assert meta.vendor_id == "V2"
    assert "PackTech" in meta.vendor_name
    assert meta.format == "PDF"
    assert len(meta.fields) == 30

    # Line 1: Rs 6.38
    f1 = meta.fields[0]
    assert f1.line_item == 1
    assert f1.item_code == "CP-001"
    assert f1.price == 6.38
    assert f1.unit == "Nos"
    assert "Page 1" in f1.source_reference
    assert f1.extraction_status == "Verified"

    # Line 30: Rs 540.65
    f30 = meta.fields[29]
    assert f30.line_item == 30
    assert f30.item_code == "CP-030"
    assert f30.price == 540.65

    # Check accuracy against ground truth
    df_gt = ground_truth["comparison"]
    for f in meta.fields:
        gt_landed = df_gt.loc[df_gt["Line #"] == f.line_item, "V2 Landed (PackTech)"].values[0]
        assert abs(f.price - gt_landed) < 0.05, f"V2 Line {f.line_item} mismatch: {f.price} vs {gt_landed}"


# ─────────────────────────────────────────────────────────────────────────────
# 3. WORD EXTRACTION (.docx) - V3 Global USD & Omissions
# ─────────────────────────────────────────────────────────────────────────────
def test_docx_extraction_v3_global(ground_truth):
    """
    Verifies genuine Word doc extraction from V3_Global_Quote.docx:
    - Currency is detected as USD.
    - 26 items quoted, 4 omitted items (Lines 10, 21, 25, 30) marked as Missing / NOT QUOTED.
    - Preserves omission reasons and notes for review.
    """
    fpath = os.path.join(SAMPLE_DIR, "V3_Global_Quote.docx")
    assert os.path.exists(fpath)
    with open(fpath, "rb") as f:
        meta = extract_vendor_quote_file(f.read(), "V3_Global_Quote.docx")

    assert meta.vendor_id == "V3"
    assert meta.currency == "USD"
    assert len(meta.fields) == 30

    omitted_lines = [10, 21, 25, 30]
    for f in meta.fields:
        if f.line_item in omitted_lines:
            assert f.price is None, f"Omitted line {f.line_item} should have null price"
            assert f.extraction_status == "Missing"
            assert "NOT QUOTED" in str(f.notes) or "omitted" in str(f.notes).lower() or "Failed Gate Q6" in str(f.notes)
        else:
            assert f.price is not None, f"Quoted line {f.line_item} should have valid price"
            assert f.extraction_status == "Verified"

    # Line 1: USD $0.0703
    f1 = meta.fields[0]
    assert f1.line_item == 1
    assert f1.price == 0.0703
    # Converted at 84.50 FX rate = ~5.94 INR
    inr_val = round(f1.price * FX_RATE, 2)
    df_gt = ground_truth["comparison"]
    gt_l1 = df_gt.loc[df_gt["Line #"] == 1, "V3 Landed (Global USD)"].values[0]
    assert abs(inr_val - gt_l1) < 0.05


# ─────────────────────────────────────────────────────────────────────────────
# 4. EMAIL EXTRACTION (.eml) - V5 Standard Box Rate Cards & Unresolved
# ─────────────────────────────────────────────────────────────────────────────
def test_eml_extraction_v5_standardbox(ground_truth):
    """
    Verifies genuine Email extraction from V5_StandardBox_Quote.eml:
    - Shippers (Lines 1-4) quoted at ₹38.00/kg board weight.
    - Master cartons (Lines 5-9, 20) quoted at ₹42.00/kg board weight.
    - Repeat SKUs quoted as 'Same as last year'.
    - New SKUs (Lines 25, 28, 29, 30) flagged for review / Unresolved due to no prior PO.
    - Moisture barrier cartons (Lines 26, 27) flagged as non-compliant with Gate Q7.
    """
    fpath = os.path.join(SAMPLE_DIR, "V5_StandardBox_Quote.eml")
    assert os.path.exists(fpath)
    with open(fpath, "rb") as f:
        meta = extract_vendor_quote_file(f.read(), "V5_StandardBox_Quote.eml")

    assert meta.vendor_id == "V5"
    assert len(meta.fields) == 30

    # Shippers: Lines 1 to 4 at 38/kg
    for l_no in [1, 2, 3, 4]:
        f = meta.fields[l_no - 1]
        assert f.price == 38.0
        assert f.unit == "₹/kg"
        assert f.extraction_status == "Verified"

    # Master: Lines 5 to 9, 20 at 42/kg
    for l_no in [5, 6, 7, 8, 9, 20]:
        f = meta.fields[l_no - 1]
        assert f.price == 42.0
        assert f.unit == "₹/kg"
        assert f.extraction_status == "Verified"

    # Moisture barrier: Lines 26, 27 flagged
    for l_no in [26, 27]:
        f = meta.fields[l_no - 1]
        assert f.price is None
        assert f.extraction_status == "Needs Review"
        assert "Gate Q7" in str(f.notes)

    # New SKUs: Lines 25, 28, 29, 30 flagged
    for l_no in [25, 28, 29, 30]:
        f = meta.fields[l_no - 1]
        assert f.price is None
        assert f.extraction_status == "Needs Review"
        assert "UNRESOLVED" in str(f.notes)


# ─────────────────────────────────────────────────────────────────────────────
# 5. IMAGE EXTRACTION (.png) - V4 Balaji & Vision OCR Guardrails
# ─────────────────────────────────────────────────────────────────────────────
def test_image_extraction_fallback_no_fake_data():
    """
    Verifies that image parsing without an active Vision model does NOT create fake OCR numbers
    or filename-based mock dictionaries.
    Must clearly label output as Demo / Pending Vision OCR and mark all items for review.
    """
    fpath = os.path.join(SAMPLE_DIR, "V4_Balaji_Quote.png")
    assert os.path.exists(fpath)
    with open(fpath, "rb") as f:
        meta = extract_vendor_quote_file(f.read(), "V4_Balaji_Quote.png", openai_client=None)

    assert meta.vendor_id == "V4"
    assert "DEMO" in meta.extraction_mode or "PENDING VISION" in meta.extraction_mode
    assert len(meta.fields) == 30

    # All prices must be None when vision model is absent
    for f in meta.fields:
        assert f.price is None, f"Image field {f.item_code} should not invent prices without vision model"
        assert f.extraction_status == "Needs Review"
        assert "Vision" in f.unit or "Vision" in f.original_raw_text


# ─────────────────────────────────────────────────────────────────────────────
# 6. FIELD & FORMAT ACCURACY BENCHMARK
# ─────────────────────────────────────────────────────────────────────────────
def test_field_and_format_accuracy_report(ground_truth):
    """
    Computes and reports extraction accuracy across all 5 formats against ground truth.
    Logs verified, missing, and unresolved cases per format.
    """
    df_gt = ground_truth["comparison"]
    formats = {
        "XLSX (V1 Apex)": ("sample_quotes/V1_Apex_Quote.xlsx", 30),
        "PDF (V2 PackTech)": ("sample_quotes/V2_PackTech_Quote.pdf", 30),
        "DOCX (V3 Global)": ("sample_quotes/V3_Global_Quote.docx", 26),
        "EML (V5 Standard)": ("sample_quotes/V5_StandardBox_Quote.eml", 24),
        "PNG (V4 Balaji)": ("sample_quotes/V4_Balaji_Quote.png", 0)  # 0 prices without Vision API
    }

    report = {}
    for fmt_label, (fpath, expected_verified) in formats.items():
        with open(fpath, "rb") as f:
            meta = extract_vendor_quote_file(f.read(), os.path.basename(fpath))
        
        verified_cnt = len([f for f in meta.fields if f.extraction_status == "Verified"])
        missing_cnt = len([f for f in meta.fields if f.extraction_status == "Missing"])
        review_cnt = len([f for f in meta.fields if f.extraction_status == "Needs Review"])

        assert verified_cnt >= expected_verified, f"Format {fmt_label} verified count {verified_cnt} < {expected_verified}"
        assert len(meta.fields) == 30, f"Format {fmt_label} must map all 30 CP codes"

        report[fmt_label] = {
            "total_items": len(meta.fields),
            "verified": verified_cnt,
            "missing": missing_cnt,
            "needs_review": review_cnt,
            "mode": meta.extraction_mode
        }

    # Print summary table for visibility
    print("\n--- INGESTION ACCURACY BENCHMARK REPORT ---")
    for k, v in report.items():
        print(f"Format: {k:20} | Verified: {v['verified']:2}/30 | Missing: {v['missing']:2} | Needs Review: {v['needs_review']:2} | Mode: {v['mode']}")
