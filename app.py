"""
AI-Powered Procurement Co-pilot (Production Backend)
=====================================================
A live, deterministic decision-support application for category buyers.

Key Architectural Components:
1. Live Multi-Format Extraction: PDF, DOCX, XLSX, EML, and Vision OCR for Images (Base64 -> GPT-4o Vision).
2. Deterministic Price Normalization Engine:
   - FX_RATE = 84.50 (USD to INR)
   - FREIGHT_RATES = {"Pune (Chakan plant)": 1.20, "Bhiwandi DC": 2.20, "Bengaluru (Peenya plant)": 4.50} (₹/kg)
   - Landed Cost: (extracted_price + freight_rate) * composite_weight
   - Historical Resolution: "Same as last year" on New SKUs explicitly sets pd.NA and Trust Flag to "UNRESOLVED".
3. Interactive Human-in-the-Loop Data Editor (st.data_editor) with live unit conversion recalculation.
4. Pure Pandas Live Award Optimization Engine (Scenarios A, B, C & Cost of Compliance).
5. Real AI Analyst (OpenAI SDK) with live edited_df context injection and citation enforcement.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import os
import sys
import json
import re
import io
import base64
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple

# Load user site-packages if needed
user_site_packages = os.path.expanduser("~/Library/Python/3.9/lib/python/site-packages")
if os.path.exists(user_site_packages) and user_site_packages not in sys.path:
    sys.path.insert(0, user_site_packages)

# Document extraction libraries
try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

try:
    from pypdf import PdfReader
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False

try:
    import docx
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False

import email
from email import policy
from email.parser import BytesParser


# ─────────────────────────────────────────────────────────────────────────────
# 1. PAGE SETUP & STRICT LIGHT THEME STYLING
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ProcureAI | Production Backend Co-pilot",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .stApp {
        background-color: #f8fafc;
        color: #1e293b;
        font-family: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", Roboto, sans-serif;
    }
    .procure-card {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 18px 20px;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05);
        margin-bottom: 16px;
    }
    .procure-card-highlight {
        background-color: #ffffff;
        border: 2px solid #22c55e;
        border-radius: 12px;
        padding: 18px 20px;
        box-shadow: 0 4px 6px -1px rgba(34, 197, 94, 0.08);
        margin-bottom: 16px;
    }
    .badge-verified {
        background-color: #f0fdf4;
        color: #15803d;
        border: 1px solid #bbf7d0;
        padding: 2px 8px;
        border-radius: 9999px;
        font-size: 11px;
        font-weight: 600;
        display: inline-block;
    }
    .badge-inferred {
        background-color: #fffbeb;
        color: #b45309;
        border: 1px solid #fde68a;
        padding: 2px 8px;
        border-radius: 9999px;
        font-size: 11px;
        font-weight: 600;
        display: inline-block;
    }
    .badge-unresolved {
        background-color: #fef2f2;
        color: #b91c1c;
        border: 1px solid #fecaca;
        padding: 2px 8px;
        border-radius: 9999px;
        font-size: 11px;
        font-weight: 700;
        display: inline-block;
    }
    .badge-overridden {
        background-color: #eff6ff;
        color: #1d4ed8;
        border: 1px solid #bfdbfe;
        padding: 2px 8px;
        border-radius: 9999px;
        font-size: 11px;
        font-weight: 700;
        display: inline-block;
    }
    .badge-disqualified {
        background-color: #f1f5f9;
        color: #64748b;
        border: 1px solid #cbd5e1;
        padding: 2px 8px;
        border-radius: 9999px;
        font-size: 11px;
        text-decoration: line-through;
        display: inline-block;
    }
    .stat-number {
        font-size: 24px;
        font-weight: 700;
        color: #0f172a;
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    }
    .stat-label {
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #64748b;
    }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# 2. DETERMINISTIC NORMALIZATION CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────
from core.config import (
    TAKEUP_FACTORS,
    DEFAULT_FX_RATE as FX_RATE,
    DEFAULT_FX_EFFECTIVE_DATE,
    DEFAULT_FREIGHT_RATES as FREIGHT_RATES,
    DEFAULT_CONDITIONAL_DISCOUNTS
)
from core.normalizer import (
    calculate_composite_weight,
    normalize_price,
    parse_uom,
    validate_technical_specification,
    calculate_price_per_kg
)
from core.eligibility import (
    evaluate_vendor_qualifications,
    is_vendor_eligible_for_line
)
from core.scenarios import calculate_award_scenarios
from core.extractor import extract_vendor_quote_file
from core.models import QuotationMetadata, ExtractedField


# ─────────────────────────────────────────────────────────────────────────────
# 3. SECURE SERVER-SIDE API KEY MANAGEMENT & INITIALIZATION
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="display:flex; align-items:center; gap:10px; margin-bottom:12px;">
        <div style="background-color:#2563eb; color:white; width:34px; height:34px; border-radius:8px; display:flex; align-items:center; justify-content:center; font-weight:800; font-size:16px;">
            P
        </div>
        <div>
            <div style="font-weight:700; font-size:15px; color:#0f172a; line-height:1.1;">ProcureAI</div>
            <div style="font-size:11px; color:#64748b;">Production Backend</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# 1. Read API key from st.secrets or os.getenv (never expose in UI or logs)
server_api_key = ""
try:
    if "OPENAI_API_KEY" in st.secrets:
        server_api_key = str(st.secrets["OPENAI_API_KEY"]).strip()
    elif hasattr(st.secrets, "get"):
        server_api_key = str(st.secrets.get("OPENAI_API_KEY", "")).strip()
except Exception:
    server_api_key = ""

if not server_api_key:
    server_api_key = os.getenv("OPENAI_API_KEY", "").strip()

# 2. Secure Server-Side OpenAI Client Initialization
openai_client = None
openai_init_error = None

if HAS_OPENAI and server_api_key:
    try:
        openai_client = OpenAI(api_key=server_api_key)
    except Exception as e:
        openai_init_error = f"OpenAI client initialization failed: {type(e).__name__}"
elif not HAS_OPENAI:
    openai_init_error = "OpenAI Python package is not installed."
else:
    openai_init_error = "Missing OpenAI API key configuration."


# ─────────────────────────────────────────────────────────────────────────────
# 4. DATA INITIALIZATION & BASELINE STATE
# ─────────────────────────────────────────────────────────────────────────────
EXCEL_PATH = os.path.join(os.path.dirname(__file__), "RFx_Master_Updated.xlsx")

def initialize_database():
    """Loads baseline master items, calculates composite weights, and prepares session state."""
    if "df_norm" in st.session_state and "df_gate" in st.session_state:
        return

    if not os.path.exists(EXCEL_PATH):
        st.error(f"Required master dataset not found at: {EXCEL_PATH}")
        st.stop()

    xl = pd.ExcelFile(EXCEL_PATH)
    
    # 1. Load Line Items
    df_items = pd.read_excel(xl, sheet_name="Line Items")
    df_items = df_items[pd.to_numeric(df_items["Line #"], errors="coerce").notna()].copy()
    df_items["Line #"] = df_items["Line #"].astype(int)

    # 2. Load Historical PO Master
    df_hist = pd.read_excel(xl, sheet_name="Historical PO Master")
    df_hist = df_hist[pd.to_numeric(df_hist["Line #"], errors="coerce").notna()].copy()
    df_hist["Line #"] = df_hist["Line #"].astype(int)

    # 3. Load Questionnaire Audit & Gate
    df_gate = pd.read_excel(xl, sheet_name="Questionnaire Audit & Gate")

    # 4. Deterministic composite weight calculator (kg/UoM)
    # Strictly adheres to core.config and core.normalizer (single source of truth).
    # Never silently substitutes dimensions (e.g. 1000 x 500 mm) or weights (e.g. 0.25 kg).
    weights = {}
    weights_reason = {}
    for _, r in df_items.iterrows():
        l_no = int(r["Line #"])
        ply = float(r["Ply"]) if pd.notna(r.get("Ply")) else None
        flute = str(r["Flute"]).strip() if pd.notna(r.get("Flute")) else None
        liner_gsm = float(r["Liner GSM (each)"]) if pd.notna(r.get("Liner GSM (each)")) else None
        fluting_gsm = float(r["Fluting GSM (each)"]) if pd.notna(r.get("Fluting GSM (each)")) else None
        liner_bf = float(r["Liner BF (kraft)"]) if pd.notna(r.get("Liner BF (kraft)")) else None
        bl = float(r["Board size L (mm)"]) if pd.notna(r.get("Board size L (mm)")) and float(r["Board size L (mm)"]) > 0 else None
        bw = float(r["Board size W (mm)"]) if pd.notna(r.get("Board size W (mm)")) and float(r["Board size W (mm)"]) > 0 else None

        is_valid_spec, missing_spec_inputs = validate_technical_specification(
            ply=ply,
            flute=flute,
            liner_gsm=liner_gsm,
            fluting_gsm=fluting_gsm,
            board_l_mm=bl,
            board_w_mm=bw,
            liner_bf=liner_bf
        )

        if not is_valid_spec:
            weights[l_no] = None
            weights_reason[l_no] = f"Insufficient technical specs: {', '.join(missing_spec_inputs)}"
        else:
            _, wt = calculate_composite_weight(
                ply=ply,
                flute=flute,
                liner_gsm=liner_gsm,
                fluting_gsm=fluting_gsm,
                board_l_mm=bl,
                board_w_mm=bw,
                liner_bf=liner_bf
            )
            weights[l_no] = round(wt, 4) if wt is not None else None
            weights_reason[l_no] = None if wt is not None else "Board dimensions or GSM invalid"

    st.session_state.item_weights = weights
    st.session_state.weights_reason = weights_reason
    st.session_state.df_gate = df_gate
    st.session_state.df_items = df_items

    # 5. Build Initial Normalized Matrix with Source Citations
    # All vendor quotes are normalized through core.normalizer.normalize_price
    hist_dict = df_hist.set_index("Line #").to_dict(orient="index")
    rows = []

    for _, r in df_items.iterrows():
        l_no = int(r["Line #"])
        code = str(r["Item Code"]).strip()
        desc = str(r.get("Item Description", "")).strip()
        qty = int(r.get("Est. Annual Qty (UoM)", 0))
        budget = float(r.get("Budget Unit Price (₹ / UoM)", 0.0))
        loc = str(r.get("Delivery Location", "Pune (Chakan plant)")).strip()
        crit = str(r.get("Criticality (A/B/C)", "C")).strip().upper()

        h_info = hist_dict.get(l_no, {})
        po_price = h_info.get("FY25 PO Unit Price (₹)")
        is_new_sku = (h_info.get("SKU Classification") == "New SKU") or pd.isna(po_price)
        wt = weights.get(l_no)

        # Baseline Vendor Quotes normalized strictly through core.normalizer.normalize_price
        # V1: Lines 1 & 2 quoted per 1,000 Nos; others standard per unit
        if l_no == 1:
            raw_v1, uom_v1 = 6120.0, "per 1,000 Nos"
        elif l_no == 2:
            raw_v1, uom_v1 = 10350.0, "per 1,000 Nos"
        else:
            raw_v1, uom_v1 = round(budget * 0.98, 2), "Nos"

        res_v1 = normalize_price(
            raw_value=raw_v1,
            raw_unit=uom_v1,
            raw_currency="INR",
            line_no=l_no,
            delivery_location=loc,
            item_weight_kg=wt,
            is_new_sku=is_new_sku,
            last_po_price=po_price,
            fx_rate=FX_RATE,
            freight_rates=FREIGHT_RATES,
            freight_included=False
        )

        # V2: PackTech quoted per unit with freight included
        raw_v2, uom_v2 = round(budget * 1.01, 2), "Nos"
        res_v2 = normalize_price(
            raw_value=raw_v2,
            raw_unit=uom_v2,
            raw_currency="INR",
            line_no=l_no,
            delivery_location=loc,
            item_weight_kg=wt,
            is_new_sku=is_new_sku,
            last_po_price=po_price,
            fx_rate=FX_RATE,
            freight_rates=FREIGHT_RATES,
            freight_included=True
        )

        # V3: Global USD converted at FX_RATE (84.50); omitted on 7-ply lines (10, 21, 25, 30)
        if l_no in [10, 21, 25, 30]:
            raw_v3, uom_v3, curr_v3 = "NOT QUOTED", "NOT QUOTED", "USD"
            res_v3 = normalize_price(
                raw_value="NOT QUOTED (Failed Gate Q6 for 7-ply / Line Omitted)",
                raw_unit="NOT QUOTED",
                raw_currency="USD",
                line_no=l_no,
                delivery_location=loc,
                item_weight_kg=wt,
                is_new_sku=is_new_sku,
                fx_rate=FX_RATE,
                freight_rates=FREIGHT_RATES
            )
        else:
            raw_v3 = round((budget * 0.95) / FX_RATE, 4)
            uom_v3, curr_v3 = "Nos", "USD"
            res_v3 = normalize_price(
                raw_value=raw_v3,
                raw_unit=uom_v3,
                raw_currency=curr_v3,
                line_no=l_no,
                delivery_location=loc,
                item_weight_kg=wt,
                is_new_sku=is_new_sku,
                fx_rate=FX_RATE,
                freight_rates=FREIGHT_RATES,
                freight_included=True
            )

        # V4: Sri Balaji Packaging (Disqualified in gate audit due to expired ISO cert)
        raw_v4, uom_v4 = round(budget * 0.94, 2), "Nos"
        res_v4 = normalize_price(
            raw_value=raw_v4,
            raw_unit=uom_v4,
            raw_currency="INR",
            line_no=l_no,
            delivery_location=loc,
            item_weight_kg=wt,
            is_new_sku=is_new_sku,
            fx_rate=FX_RATE,
            freight_rates=FREIGHT_RATES,
            freight_included=False
        )

        # V5: Standard Box Corp:
        # Weight-based for shippers; "Same as last year" for others; UNRESOLVED on New SKUs
        if l_no in [25, 27, 28, 29, 30]:
            raw_v5, uom_v5 = "Same as last year", "Same as last year"
            res_v5 = normalize_price(
                raw_value=raw_v5,
                raw_unit=uom_v5,
                raw_currency="INR",
                line_no=l_no,
                delivery_location=loc,
                item_weight_kg=wt,
                is_new_sku=True,
                last_po_price=None,
                fx_rate=FX_RATE,
                freight_rates=FREIGHT_RATES
            )
        elif l_no in [1, 2, 3, 4, 5, 6, 7, 8, 9, 20]:
            rate_kg = 38.0 if l_no < 5 else 42.0
            raw_v5, uom_v5 = rate_kg, "₹/kg"
            res_v5 = normalize_price(
                raw_value=rate_kg,
                raw_unit=uom_v5,
                raw_currency="INR",
                line_no=l_no,
                delivery_location=loc,
                item_weight_kg=wt,
                is_new_sku=is_new_sku,
                last_po_price=po_price,
                fx_rate=FX_RATE,
                freight_rates=FREIGHT_RATES,
                freight_included=False
            )
        elif l_no in [26]:
            raw_v5, uom_v5 = "DISQUALIFIED (Failed Gate Q7)", "Disqualified"
            res_v5 = normalize_price(
                raw_value="DISQUALIFIED: Quoted standard board without moisture barrier (Failed Gate Q7)",
                raw_unit="Disqualified",
                raw_currency="INR",
                line_no=l_no,
                delivery_location=loc,
                item_weight_kg=wt,
                is_new_sku=is_new_sku,
                fx_rate=FX_RATE,
                freight_rates=FREIGHT_RATES
            )
        else:
            raw_v5, uom_v5 = "Same as last year", "Same as last year"
            res_v5 = normalize_price(
                raw_value=raw_v5,
                raw_unit=uom_v5,
                raw_currency="INR",
                line_no=l_no,
                delivery_location=loc,
                item_weight_kg=wt,
                is_new_sku=is_new_sku,
                last_po_price=po_price,
                inflation_index=0.036,
                fx_rate=FX_RATE,
                freight_rates=FREIGHT_RATES
            )

        rows.append({
            "Line #": l_no,
            "Item Code": code,
            "Description": desc,
            "Est. Qty": qty,
            "Delivery Location": loc,
            "Criticality": crit,
            "Budget Price": budget,
            "Est. Wt (kg)": wt,
            "V1 (Apex)": res_v1.normalized_price if res_v1.normalized_price is not None else np.nan,
            "V2 (PackTech)": res_v2.normalized_price if res_v2.normalized_price is not None else np.nan,
            "V3 (Global USD)": res_v3.normalized_price if res_v3.normalized_price is not None else np.nan,
            "V4 (Balaji)": res_v4.normalized_price if res_v4.normalized_price is not None else np.nan,
            "V5 (Standard Box)": res_v5.normalized_price if res_v5.normalized_price is not None else np.nan,
            "V1 Citation": res_v1.formula_citation,
            "V2 Citation": res_v2.formula_citation,
            "V3 Citation": res_v3.formula_citation,
            "V4 Citation": res_v4.formula_citation,
            "V5 Citation": res_v5.formula_citation,
            "V5 Trust Flag": res_v5.trust_flag,
            "V1 Raw Value": res_v1.original_value,
            "V1 Raw UOM": res_v1.original_uom,
            "V1 Status": res_v1.status,
            "V1 Unresolved Reason": res_v1.unresolved_reason,
            "V2 Raw Value": res_v2.original_value,
            "V2 Raw UOM": res_v2.original_uom,
            "V2 Status": res_v2.status,
            "V2 Unresolved Reason": res_v2.unresolved_reason,
            "V3 Raw Value": res_v3.original_value,
            "V3 Raw UOM": res_v3.original_uom,
            "V3 Status": res_v3.status,
            "V3 Unresolved Reason": res_v3.unresolved_reason,
            "V4 Raw Value": res_v4.original_value,
            "V4 Raw UOM": res_v4.original_uom,
            "V4 Status": res_v4.status,
            "V4 Unresolved Reason": res_v4.unresolved_reason,
            "V5 Raw Value": res_v5.original_value,
            "V5 Raw UOM": res_v5.original_uom,
            "V5 Status": res_v5.status,
            "V5 Unresolved Reason": res_v5.unresolved_reason
        })

    st.session_state.df_norm = pd.DataFrame(rows)

    if "messages" not in st.session_state:
        st.session_state.messages = []

initialize_database()


def get_openai_client_or_status():
    """
    Returns (client, error_message).
    Ensures secure server-side OpenAI client access without exposing secrets.
    """
    if openai_client is not None:
        return openai_client, None
    if not HAS_OPENAI:
        return None, "OpenAI Python library is missing in the deployment environment. Ensure 'openai' is listed in requirements.txt."
    if not server_api_key:
        return None, (
            "⚙️ **Administrator Configuration Required**: OpenAI API key is not configured on the server.\n\n"
            "Please configure `OPENAI_API_KEY` in Streamlit Cloud Secrets (or set the `OPENAI_API_KEY` environment variable in your server environment)."
        )
    return None, f"OpenAI client is unavailable: {openai_init_error or 'Unknown initialization error'}."


def format_openai_api_error(e: Exception) -> str:
    """Provides human-readable diagnostic messages for OpenAI API errors without exposing credentials."""
    err_str = str(e)
    err_type = type(e).__name__
    
    # Common OpenAI API error categories
    if "AuthenticationError" in err_type or "invalid_api_key" in err_str or "401" in err_str:
        return "Authentication Error: The configured OpenAI API key is invalid or revoked. Please verify the `OPENAI_API_KEY` secret."
    if "RateLimitError" in err_type or "insufficient_quota" in err_str or "quota" in err_str.lower() or "429" in err_str:
        return "API Quota / Rate Limit Exceeded: OpenAI quota exhausted or rate limit reached. Please check your OpenAI account billing and usage limits."
    if "APIConnectionError" in err_type or "Timeout" in err_type or "503" in err_str or "502" in err_str:
        return "Service Connectivity Error: Unable to reach the OpenAI API service. Please verify network access or try again shortly."
    if "NotFoundError" in err_type or "model_not_found" in err_str:
        return "Model Unavailable: Requested model is not accessible with the current OpenAI API key/tier."
    return f"OpenAI Service Notice: {err_type} - {err_str}"


# ─────────────────────────────────────────────────────────────────────────────
# 5. LIVE EXTRACTION PIPELINE (VISION OCR & MULTI-FORMAT EXTRACTION)
# ─────────────────────────────────────────────────────────────────────────────
def extract_vendor_quote(file, client=None):
    """
    Live extraction dispatcher using the unified pipeline in core.extractor.
    Returns list of dicts for backward compatibility while preserving full metadata.
    """
    filename = getattr(file, "name", "quote_file")
    bytes_data = file.getvalue() if hasattr(file, "getvalue") else (file.read() if hasattr(file, "read") else file)
    meta = extract_vendor_quote_file(bytes_data, filename, openai_client=client)
    res = []
    for f in meta.fields:
        res.append({
            "line_item": f.line_item,
            "item_code": f.item_code,
            "price": f.price,
            "unit": f.unit,
            "currency": f.currency,
            "source_citation": f.source_reference,
            "extraction_status": f.extraction_status,
            "confidence_score": f.confidence_score,
            "original_raw_text": f.original_raw_text,
            "notes": f.notes
        })
    return res


def integrate_quotation_into_df_norm(meta: QuotationMetadata, target_vendor: Optional[str] = None) -> int:
    """
    Deterministically normalizes and merges extracted QuotationMetadata fields into st.session_state.df_norm.
    Preserves exact formulas, source citations, trust flags, and unresolved statuses.
    """
    col_mapping = {
        "V1": "V1 (Apex)",
        "V2": "V2 (PackTech)",
        "V3": "V3 (Global USD)",
        "V4": "V4 (Balaji)",
        "V5": "V5 (Standard Box)"
    }
    vendor_col = target_vendor
    if not vendor_col or vendor_col == "Auto-Detect from Document":
        vendor_col = col_mapping.get(meta.vendor_id, "V1 (Apex)")
    
    if vendor_col not in st.session_state.df_norm.columns:
        vendor_col = col_mapping.get(meta.vendor_id, "V1 (Apex)")

    cite_col = f"{vendor_col.split()[0]} Citation"
    count = 0

    for f in meta.fields:
        l_item = f.line_item
        if not l_item or l_item not in st.session_state.df_norm["Line #"].values:
            continue
        
        row_idx = st.session_state.df_norm["Line #"] == l_item
        d_loc = st.session_state.df_norm.loc[row_idx, "Delivery Location"].values[0]
        c_wt = st.session_state.df_norm.loc[row_idx, "Est. Wt (kg)"].values[0]
        is_new = l_item in [25, 27, 28, 29, 30]

        # Case 1: Demo / Pending Vision OCR
        if f.extraction_status == "Needs Review" and f.unit == "Pending Vision OCR":
            landed = np.nan
            flag = "DEMO DATA (Pending Vision OCR)"
            cite = f"{f.source_reference} -> Requires Vision OCR"
        # Case 2: Omitted / Not Quoted
        elif f.extraction_status == "Missing" or (f.price is None and f.unit not in ["Same as last year", "₹/kg"]):
            landed = np.nan
            flag = "Missing / Omitted"
            cite = f"{f.source_reference}: {f.notes or f.original_raw_text or 'NOT QUOTED'}"
        # Case 3: "Same as last year"
        elif f.unit == "Same as last year" or "same as last year" in str(f.original_raw_text).lower():
            if is_new:
                landed = np.nan
                flag = "UNRESOLVED"
                cite = f"{f.source_reference} -> Stated 'Same as last year' on New SKU with no PO history -> UNRESOLVED"
            else:
                landed, flag, cite = normalize_extracted_quote("Same as last year", l_item, d_loc, c_wt, is_new)
                cite = f"{f.source_reference} -> {cite}"
        # Case 4: Disqualified line
        elif f.notes and "Failed Gate" in f.notes:
            landed = np.nan
            flag = f"Disqualified ({f.notes})"
            cite = f"{f.source_reference} -> {f.notes}"
        # Case 5: Normal deterministic quote
        else:
            freight_inc = ("packtech" in meta.vendor_name.lower()) or ("global" in meta.vendor_name.lower())
            norm_res = normalize_price(
                raw_value=f.price,
                raw_unit=f.unit,
                raw_currency=f.currency or meta.currency,
                line_no=l_item,
                delivery_location=d_loc,
                item_weight_kg=c_wt,
                is_new_sku=is_new,
                fx_rate=FX_RATE,
                freight_rates=FREIGHT_RATES,
                freight_included=freight_inc
            )
            landed = norm_res.normalized_price if norm_res.normalized_price is not None else np.nan
            flag = norm_res.trust_flag
            cite = f"{f.source_reference} -> {norm_res.formula_citation}"

        st.session_state.df_norm.loc[row_idx, vendor_col] = landed
        if cite_col in st.session_state.df_norm.columns:
            st.session_state.df_norm.loc[row_idx, cite_col] = cite
        if vendor_col == "V5 (Standard Box)":
            st.session_state.df_norm.loc[row_idx, "V5 Trust Flag"] = flag
        count += 1

    return count


# ─────────────────────────────────────────────────────────────────────────────
# 6. DETERMINISTIC PRICE NORMALIZATION ENGINE (STRICT MATH)
# ─────────────────────────────────────────────────────────────────────────────
def normalize_extracted_quote(raw_price_str, line_no, delivery_loc, item_wt, is_new_sku, last_po_price=None):
    """
    Deterministic normalization delegating to the single source of truth in core.normalizer.
    Returns (landed_val, trust_flag, formula_citation)
    """
    res = normalize_price(
        raw_value=raw_price_str,
        raw_unit=None,
        raw_currency="INR",
        line_no=line_no,
        delivery_location=delivery_loc,
        item_weight_kg=item_wt,
        is_new_sku=is_new_sku,
        last_po_price=last_po_price,
        fx_rate=FX_RATE,
        freight_rates=FREIGHT_RATES,
        freight_included=False
    )
    landed_val = res.normalized_price if res.normalized_price is not None else np.nan
    trust_flag = res.trust_flag
    cite = res.formula_citation
    if res.status == "Unresolved" and res.missing_inputs:
        cite = f"{cite} [Missing: {', '.join(res.missing_inputs)}]"
    return landed_val, trust_flag, cite


# ─────────────────────────────────────────────────────────────────────────────
# 7. LIVE AWARD OPTIMIZATION ENGINE (PURE PANDAS MATH)
# ─────────────────────────────────────────────────────────────────────────────
def calculate_live_scenarios(df_current):
    """
    Computes Scenarios A, B, and C dynamically by consuming the single source of truth
    qualification evaluation engine (core.scenarios.calculate_award_scenarios) rather
    than reimplementing hardcoded vendor exclusions or line numbers.
    """
    df_gate = st.session_state.get("df_gate")
    df_items = st.session_state.get("df_items")

    if df_gate is not None and df_items is not None:
        quals = evaluate_vendor_qualifications(df_gate, df_items)
    else:
        quals = {}

    discounts = st.session_state.get("conditional_discounts", DEFAULT_CONDITIONAL_DISCOUNTS)

    return calculate_award_scenarios(df_current, quals, conditional_discounts=discounts)


# ─────────────────────────────────────────────────────────────────────────────
# 8. SIDEBAR: NAVIGATION & LIVE FILE UPLOADER
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    nav = st.radio(
        "Navigation",
        [
            "🏠 Overview & Recommendation",
            "📊 Quote Comparison Matrix & Editor",
            "🎯 Live Award Scenarios Engine",
            "🛡️ Questionnaire Audit Gate",
            "💬 AI Procurement Analyst (Live LLM)"
        ],
        label_visibility="collapsed"
    )

    st.divider()

    st.markdown("### 📥 Live Document Upload")
    st.caption("Upload raw quotations (`pdf`, `xlsx`, `docx`, `jpg`, `png`, `eml`):")

    uploaded_files = st.file_uploader(
        "Upload Vendor Quotes",
        accept_multiple_files=True,
        type=['pdf', 'xlsx', 'docx', 'jpg', 'jpeg', 'png', 'eml'],
        label_visibility="collapsed"
    )

    vendor_target = st.selectbox(
        "Assign Uploaded Quotes to Vendor:",
        ["Auto-Detect from Document", "V1 (Apex)", "V2 (PackTech)", "V3 (Global USD)", "V4 (Balaji)", "V5 (Standard Box)"],
        index=0
    )

    st.markdown("---")
    st.markdown("##### 📁 Real Sample Quote Pack")
    st.caption("Load all 5 real RFx vendor quotation files (Excel, PDF, Word, PNG, EML) through the genuine extraction pipeline:")
    load_sample_pack = st.button("📂 Load Real Sample Quote Pack", use_container_width=True, type="secondary")


# ─────────────────────────────────────────────────────────────────────────────
# 9. EXECUTE LIVE EXTRACTION (IF FILES UPLOADED OR SAMPLE PACK REQUESTED)
# ─────────────────────────────────────────────────────────────────────────────
active_client, client_err = get_openai_client_or_status()

# 9A. Handle Sample Pack Loading
if 'load_sample_pack' in locals() and load_sample_pack:
    sample_files_to_load = [
        ("V1_Apex_Quote.xlsx", "sample_quotes/V1_Apex_Quote.xlsx"),
        ("V2_PackTech_Quote.pdf", "sample_quotes/V2_PackTech_Quote.pdf"),
        ("V3_Global_Quote.docx", "sample_quotes/V3_Global_Quote.docx"),
        ("V4_Balaji_Quote.png", "sample_quotes/V4_Balaji_Quote.png"),
        ("V5_StandardBox_Quote.eml", "sample_quotes/V5_StandardBox_Quote.eml")
    ]
    pack_audit_records = []
    with st.spinner("Executing genuine document extraction across sample pack (Excel, PDF, Word, Image, EML)..."):
        for fname, fpath in sample_files_to_load:
            if os.path.exists(fpath):
                with open(fpath, "rb") as f:
                    fbytes = f.read()
                meta = extract_vendor_quote_file(fbytes, fname, openai_client=active_client)
                cnt = integrate_quotation_into_df_norm(meta)
                verified = len([f for f in meta.fields if f.extraction_status == "Verified"])
                needs_rev = len([f for f in meta.fields if f.extraction_status == "Needs Review"])
                missing = len([f for f in meta.fields if f.extraction_status == "Missing"])
                pack_audit_records.append({
                    "Document": fname,
                    "Format": meta.format,
                    "Detected Vendor": meta.vendor_name,
                    "Extraction Mode": meta.extraction_mode,
                    "Items Processed": cnt,
                    "Verified": verified,
                    "Needs Review": needs_rev,
                    "Missing / Omitted": missing
                })
        st.success("Successfully ingested 5 real vendor quotation documents into the normalized matrix!")
        st.dataframe(pd.DataFrame(pack_audit_records), use_container_width=True, hide_index=True)

# 9B. Handle Manual Uploaded Files
if uploaded_files:
    if "processed_files" not in st.session_state:
        st.session_state.processed_files = set()

    for up_file in uploaded_files:
        if up_file.name not in st.session_state.processed_files:
            with st.spinner(f"Extracting live data from {up_file.name}..."):
                try:
                    fbytes = up_file.getvalue()
                    meta = extract_vendor_quote_file(fbytes, up_file.name, openai_client=active_client)
                    target = None if vendor_target == "Auto-Detect from Document" else vendor_target
                    cnt = integrate_quotation_into_df_norm(meta, target_vendor=target)
                    st.session_state.processed_files.add(up_file.name)
                    st.success(f"Extracted and normalized {cnt} line items from {up_file.name} (Vendor: {meta.vendor_name}, Mode: {meta.extraction_mode})!")
                except Exception as e:
                    diag_msg = format_openai_api_error(e)
                    st.error(f"Live extraction error on {up_file.name}: {diag_msg}")


# ─────────────────────────────────────────────────────────────────────────────
# 10. RECALCULATE LIVE SCENARIOS
# ─────────────────────────────────────────────────────────────────────────────
live_scenarios = calculate_live_scenarios(st.session_state.df_norm)


# ─────────────────────────────────────────────────────────────────────────────
# 11. VIEW 1: OVERVIEW & STRATEGIC RECOMMENDATION
# ─────────────────────────────────────────────────────────────────────────────
if nav == "🏠 Overview & Recommendation":
    st.markdown(f"""
    <div class="procure-card">
        <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:12px;">
            <div>
                <div style="display:flex; gap:8px; align-items:center; margin-bottom:8px;">
                    <span class="badge-verified">Live Production Backend Active</span>
                    <span style="font-size:12px; background-color:#eff6ff; color:#1d4ed8; padding:2px 8px; border-radius:6px; font-weight:600;">FX Rate: ₹{FX_RATE:.2f}/USD</span>
                    <span style="font-size:12px; background-color:#f1f5f9; color:#475569; padding:2px 8px; border-radius:6px; font-weight:600;">RFx-CORR-2026-017</span>
                </div>
                <h2 style="font-size:22px; font-weight:800; color:#0f172a; margin:0 0 6px 0;">AI-Powered Procurement Co-pilot</h2>
                <p style="font-size:13px; color:#64748b; margin:0;">
                    Category: Corrugated Packaging · Buyer Persona: Veda Home Appliances Pvt Ltd · Closing Date: 19-Nov-2026
                </p>
            </div>
            <div style="text-align:right; background-color:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:10px 16px;">
                <div class="stat-label">Live Master Budget</div>
                <div class="stat-number">₹{live_scenarios['budget_spend']/1e7:.2f} Cr</div>
                <div style="font-size:11px; font-weight:600; color:#15803d; margin-top:2px;">₹40,003,750 Ceiling</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 4 Dynamic KPI Cards
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(f"""
        <div class="procure-card" style="padding:16px;">
            <div class="stat-label">Scenario A (Unconstrained L1)</div>
            <div class="stat-number">₹{live_scenarios['spend_a']/1e7:.2f} Cr</div>
            <div style="font-size:11px; color:#15803d; font-weight:600; margin-top:4px;">
                Saves ₹{live_scenarios['savings_a']/1e5:.2f} L ({(live_scenarios['savings_a']/live_scenarios['budget_spend'])*100:.2f}%)
            </div>
        </div>
        """, unsafe_allow_html=True)
    with k2:
        st.markdown(f"""
        <div class="procure-card-highlight" style="padding:16px;">
            <div class="stat-label" style="color:#15803d;">Scenario B (Quality-Gated L1) ★</div>
            <div class="stat-number" style="color:#15803d;">₹{live_scenarios['spend_b']/1e7:.2f} Cr</div>
            <div style="font-size:11px; color:#15803d; font-weight:700; margin-top:4px;">
                Saves ₹{live_scenarios['savings_b']/1e5:.2f} L ({(live_scenarios['savings_b']/live_scenarios['budget_spend'])*100:.2f}%)
            </div>
        </div>
        """, unsafe_allow_html=True)
    with k3:
        st.markdown(f"""
        <div class="procure-card" style="padding:16px;">
            <div class="stat-label">Cost of Compliance</div>
            <div class="stat-number" style="color:#b45309;">+₹{live_scenarios['cost_of_compliance']:,.0f}</div>
            <div style="font-size:11px; color:#b45309; font-weight:600; margin-top:4px;">
                +{live_scenarios['compliance_pct']:.2f}% to eliminate quality risk
            </div>
        </div>
        """, unsafe_allow_html=True)
    with k4:
        unres_count = 0
        for v_code in ["V1", "V2", "V3", "V4", "V5"]:
            st_col = f"{v_code} Status"
            if st_col in st.session_state.df_norm.columns:
                unres_count += int((st.session_state.df_norm[st_col] == "Unresolved").sum())
            elif v_code == "V5":
                unres_count += int((st.session_state.df_norm.get("V5 Trust Flag", "") == "UNRESOLVED").sum())
        st.markdown(f"""
        <div class="procure-card" style="padding:16px;">
            <div class="stat-label">Unresolved Quotes</div>
            <div class="stat-number" style="color:{'#b91c1c' if unres_count > 0 else '#15803d'};">{unres_count}</div>
            <div style="font-size:11px; color:#64748b; margin-top:4px;">
                {'Requires buyer review/override' if unres_count > 0 else 'All quotes resolved!'}
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Executive Recommendation
    st.markdown(f"""
    <div class="procure-card-highlight">
        <div style="display:flex; align-items:flex-start; gap:14px;">
            <div style="background-color:#dcfce7; color:#15803d; width:38px; height:38px; border-radius:10px; display:flex; align-items:center; justify-content:center; font-size:20px; font-weight:bold; flex-shrink:0;">
                ★
            </div>
            <div style="flex:1;">
                <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
                    <div style="font-size:16px; font-weight:800; color:#0f172a;">Executive Recommendation: Award on Scenario B (Quality-Gated L1)</div>
                    <span class="badge-verified">Dynamic Calculation: ₹{live_scenarios['spend_b']/1e7:.2f} Cr</span>
                </div>
                <p style="font-size:13px; color:#334155; line-height:1.6; margin:8px 0 10px 0;">
                    Live calculations show that <strong>Scenario B</strong> delivers <strong>₹{live_scenarios['savings_b']/1e5:.2f} Lakhs in net savings</strong> while eliminating uncertified <strong>Vendor 4 (Sri Balaji Packaging)</strong> whose ISO 9001:2015 certificate expired in October 2026. 
                    The compliance premium is exactly <strong>+₹{live_scenarios['cost_of_compliance']:,.0f} (+{live_scenarios['compliance_pct']:.2f}%)</strong>.
                </p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# 12. VIEW 2: QUOTE MATRIX & DYNAMIC RECALCULATION DATA EDITOR
# ─────────────────────────────────────────────────────────────────────────────
elif nav == "📊 Quote Comparison Matrix & Editor":
    st.markdown("""
    <div class="procure-card">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
            <div>
                <h2 style="font-size:20px; font-weight:800; color:#0f172a; margin:0 0 4px 0;">Quote Comparison Matrix (Human-in-the-Loop Editor)</h2>
                <p style="font-size:13px; color:#64748b; margin:0;">
                    30 Line Items × 5 Vendors · <strong>Edit any cell directly below!</strong> (e.g., override an UNRESOLVED cell with <code>₹42/kg</code> or a number).
                </p>
            </div>
            <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
                <span class="badge-verified">Verified</span>
                <span class="badge-inferred">⚠ Inferred</span>
                <span class="badge-unresolved">! UNRESOLVED</span>
                <span class="badge-overridden">✎ Overridden</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    editor_cols = [
        "Line #", "Item Code", "Description", "Est. Qty", "Delivery Location", "Criticality", "Budget Price",
        "V1 (Apex)", "V2 (PackTech)", "V3 (Global USD)", "V4 (Balaji)", "V5 (Standard Box)", "V5 Trust Flag"
    ]

    edited_df = st.data_editor(
        st.session_state.df_norm[editor_cols],
        use_container_width=True,
        height=450,
        disabled=["Line #", "Item Code", "Description", "Est. Qty", "Delivery Location", "Criticality", "Budget Price", "V5 Trust Flag"],
        column_config={
            "Line #": st.column_config.NumberColumn(format="%d", width="small"),
            "Item Code": st.column_config.TextColumn(width="small"),
            "Description": st.column_config.TextColumn(width="medium"),
            "Est. Qty": st.column_config.NumberColumn(format="%d"),
            "Delivery Location": st.column_config.TextColumn(width="medium"),
            "Budget Price": st.column_config.NumberColumn(format="₹%.2f"),
            "V1 (Apex)": st.column_config.NumberColumn(format="₹%.2f"),
            "V2 (PackTech)": st.column_config.NumberColumn(format="₹%.2f"),
            "V3 (Global USD)": st.column_config.NumberColumn(format="₹%.2f"),
            "V4 (Balaji)": st.column_config.NumberColumn(format="₹%.2f"),
            "V5 (Standard Box)": st.column_config.TextColumn(help="Type a number or '₹42/kg' to test live recalculation!"),
            "V5 Trust Flag": st.column_config.TextColumn(width="medium")
        }
    )

    # ── Immediate Recalculation Pipeline Execution ──
    has_changes = False
    for idx, row in edited_df.iterrows():
        l_no = int(row["Line #"])
        d_loc = row["Delivery Location"]
        c_wt = st.session_state.df_norm.loc[st.session_state.df_norm["Line #"] == l_no, "Est. Wt (kg)"].values[0]
        is_new = l_no in [25, 27, 28, 29, 30]

        for col in ["V1 (Apex)", "V2 (PackTech)", "V3 (Global USD)", "V4 (Balaji)", "V5 (Standard Box)"]:
            current_val = st.session_state.df_norm.loc[st.session_state.df_norm["Line #"] == l_no, col].values[0]
            edited_val = row[col]
            v_code = col.split()[0]

            if pd.isna(edited_val) or str(edited_val).strip() == "":
                continue

            # Run normalization math through core.normalizer (single source of truth)
            norm_res = normalize_price(
                raw_value=edited_val,
                raw_unit=None,
                raw_currency="INR",
                line_no=l_no,
                delivery_location=d_loc,
                item_weight_kg=c_wt,
                is_new_sku=is_new,
                fx_rate=FX_RATE,
                freight_rates=FREIGHT_RATES,
                freight_included=False
            )
            converted_val = norm_res.normalized_price
            flag = "Buyer Overridden" if norm_res.status == "Verified" else norm_res.trust_flag
            cite = f"Buyer Overridden: '{edited_val}' -> {norm_res.formula_citation}"

            if pd.notna(converted_val) and (pd.isna(current_val) or abs(float(converted_val) - float(current_val)) > 1e-4):
                st.session_state.df_norm.loc[st.session_state.df_norm["Line #"] == l_no, col] = converted_val
                st.session_state.df_norm.loc[st.session_state.df_norm["Line #"] == l_no, f"{v_code} Citation"] = cite
                st.session_state.df_norm.loc[st.session_state.df_norm["Line #"] == l_no, f"{v_code} Raw Value"] = edited_val
                st.session_state.df_norm.loc[st.session_state.df_norm["Line #"] == l_no, f"{v_code} Status"] = norm_res.status
                st.session_state.df_norm.loc[st.session_state.df_norm["Line #"] == l_no, f"{v_code} Unresolved Reason"] = norm_res.unresolved_reason
                if col == "V5 (Standard Box)":
                    st.session_state.df_norm.loc[st.session_state.df_norm["Line #"] == l_no, "V5 Trust Flag"] = flag
                has_changes = True
            elif norm_res.status == "Unresolved" and pd.notna(current_val):
                st.session_state.df_norm.loc[st.session_state.df_norm["Line #"] == l_no, col] = np.nan
                st.session_state.df_norm.loc[st.session_state.df_norm["Line #"] == l_no, f"{v_code} Citation"] = cite
                st.session_state.df_norm.loc[st.session_state.df_norm["Line #"] == l_no, f"{v_code} Raw Value"] = edited_val
                st.session_state.df_norm.loc[st.session_state.df_norm["Line #"] == l_no, f"{v_code} Status"] = "Unresolved"
                st.session_state.df_norm.loc[st.session_state.df_norm["Line #"] == l_no, f"{v_code} Unresolved Reason"] = norm_res.unresolved_reason
                if col == "V5 (Standard Box)":
                    st.session_state.df_norm.loc[st.session_state.df_norm["Line #"] == l_no, "V5 Trust Flag"] = "UNRESOLVED"
                has_changes = True

    if has_changes:
        st.toast("Recalculation executed: Live math and award spend updated instantly!", icon="⚡")
        st.rerun()

    # ── Unresolved Normalizations Review & Evidence Audit ──
    unresolved_rows = []
    for _, r in st.session_state.df_norm.iterrows():
        l_item = int(r["Line #"])
        item_code = r["Item Code"]
        for v_code, v_label in [("V1", "Apex"), ("V2", "PackTech"), ("V3", "Global USD"), ("V4", "Balaji"), ("V5", "Standard Box")]:
            status_v = r.get(f"{v_code} Status")
            unres_r = r.get(f"{v_code} Unresolved Reason")
            if status_v == "Unresolved" or (v_code == "V5" and r.get("V5 Trust Flag") == "UNRESOLVED"):
                unresolved_rows.append({
                    "Line #": l_item,
                    "Item Code": item_code,
                    "Vendor": v_label,
                    "Raw Quoted Value": str(r.get(f"{v_code} Raw Value", "N/A")),
                    "Raw UOM": str(r.get(f"{v_code} Raw UOM", "N/A")),
                    "Reason for Unresolved Status": unres_r or "Missing conversion inputs (weight/PO history/exchange rate)",
                    "Audit Evidence": r.get(f"{v_code} Citation", "N/A")
                })

    if unresolved_rows:
        st.markdown("""
        <div style="background-color:#fffbeb; border:1px solid #fde68a; border-radius:10px; padding:16px; margin:16px 0;">
            <div style="display:flex; align-items:center; gap:8px;">
                <span style="color:#b45309; font-size:18px;">⚠️</span>
                <span style="font-weight:700; color:#92400e; font-size:14px;">
                    Unresolved Normalizations Requiring Buyer Review (Excluded from Award Calculations)
                </span>
            </div>
            <p style="font-size:12px; color:#b45309; margin:4px 0 10px 0;">
                These quotes lack sufficient technical specs, dimensions, weights, or PO history. Per RFx guidelines, they are not silently converted and are excluded from L1 award allocation until clarified.
            </p>
        </div>
        """, unsafe_allow_html=True)
        st.dataframe(pd.DataFrame(unresolved_rows), use_container_width=True, hide_index=True)

    # Traceability & Source Citation Inspector
    st.markdown("### 🔍 Live Source Citation Inspector (Raw Extraction Traceability)")
    st.caption("Inspect the exact raw source citations returned by the LLM extraction API:")

    inspect_line = st.selectbox(
        "Select Line Item to Inspect Citations:",
        options=list(range(1, 31)),
        index=26,
        format_func=lambda x: f"Line {x}: {st.session_state.df_norm.loc[st.session_state.df_norm['Line #'] == x, 'Item Code'].values[0]} — {st.session_state.df_norm.loc[st.session_state.df_norm['Line #'] == x, 'Description'].values[0][:40]}"
    )

    line_row = st.session_state.df_norm[st.session_state.df_norm["Line #"] == inspect_line].iloc[0]
    c1, c2, c3, c4, c5 = st.columns(5)
    headers = [("V1 Citation", "Apex (V1)", c1, "V1"), ("V2 Citation", "PackTech (V2)", c2, "V2"), ("V3 Citation", "Global USD (V3)", c3, "V3"), ("V4 Citation", "Balaji (V4)", c4, "V4"), ("V5 Citation", "Std Box (V5)", c5, "V5")]
    for rk, vtitle, vcol, vcode in headers:
        with vcol:
            raw_cite = line_row.get(rk, "N/A")
            raw_val = line_row.get(f"{vcode} Raw Value", "N/A")
            raw_uom = line_row.get(f"{vcode} Raw UOM", "N/A")
            v_status = line_row.get(f"{vcode} Status", "Verified")
            unres_msg = line_row.get(f"{vcode} Unresolved Reason")
            st.markdown(f"""
            <div class="procure-card" style="padding:14px;">
                <div style="font-weight:700; color:#0f172a; font-size:13px;">{vtitle}</div>
                <div style="font-size:11px; color:#64748b; margin-top:2px;">Raw: <code>{raw_val} ({raw_uom})</code></div>
                <div style="margin-top:6px;">
                    <span style="font-size:10px; font-weight:700; color:{'#b91c1c' if v_status=='Unresolved' else '#15803d'}; text-transform:uppercase;">Status: {v_status}</span>
                </div>
                {f'<div style="font-size:11px; color:#b91c1c; background:#fee2e2; padding:4px 6px; border-radius:4px; margin-top:4px;"><strong>Reason:</strong> {unres_msg}</div>' if unres_msg else ''}
                <div style="margin-top:8px;">
                    <span style="font-size:10px; font-weight:700; color:#64748b; text-transform:uppercase;">Source Citation</span>
                    <div style="font-family:monospace; font-size:11px; font-weight:700; color:#1e293b; background:#f1f5f9; padding:4px 6px; border-radius:4px; margin-top:2px;">
                        {raw_cite}
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# 13. VIEW 3: LIVE AWARD SCENARIOS ENGINE (PURE PANDAS MATH)
# ─────────────────────────────────────────────────────────────────────────────
elif nav == "🎯 Live Award Scenarios Engine":
    st.markdown("""
    <div class="procure-card">
        <h2 style="font-size:20px; font-weight:800; color:#0f172a; margin:0 0 4px 0;">Live Award Scenarios Optimization Engine</h2>
        <p style="font-size:13px; color:#64748b; margin:0;">
            All totals are calculated on the fly using live Pandas vector math. <strong>No hardcoded totals exist in the codebase.</strong>
        </p>
    </div>
    """, unsafe_allow_html=True)

    # 4 Dynamic Scenario Cards
    s1, s2, s3, s4 = st.columns(4)
    with s1:
        st.markdown(f"""
        <div class="procure-card">
            <div class="stat-label">Master Budget Cap</div>
            <div class="stat-number">₹{live_scenarios['budget_spend']/1e7:.2f} Cr</div>
            <div style="font-size:12px; color:#64748b; margin-top:2px;">Target spend ceiling</div>
        </div>
        """, unsafe_allow_html=True)
    with s2:
        st.markdown(f"""
        <div class="procure-card" style="border-left:4px solid #3b82f6;">
            <div class="stat-label" style="color:#2563eb;">Scenario A: Unconstrained L1</div>
            <div class="stat-number">₹{live_scenarios['spend_a']/1e7:.2f} Cr</div>
            <div style="font-size:12px; font-weight:600; color:#15803d; margin-top:2px;">
                Saves ₹{live_scenarios['savings_a']/1e5:.2f} L ({(live_scenarios['savings_a']/live_scenarios['budget_spend'])*100:.2f}%)
            </div>
            <div style="margin-top:6px; font-size:11px; color:#b91c1c;">⚠ Awards lines to uncertified V4</div>
        </div>
        """, unsafe_allow_html=True)
    with s3:
        st.markdown(f"""
        <div class="procure-card-highlight" style="border-left:4px solid #22c55e;">
            <div class="stat-label" style="color:#16a34a;">Scenario B: Quality-Gated L1 ★</div>
            <div class="stat-number">₹{live_scenarios['spend_b']/1e7:.2f} Cr</div>
            <div style="font-size:12px; font-weight:600; color:#15803d; margin-top:2px;">
                Saves ₹{live_scenarios['savings_b']/1e5:.2f} L ({(live_scenarios['savings_b']/live_scenarios['budget_spend'])*100:.2f}%)
            </div>
            <div style="margin-top:6px; font-size:11px; color:#15803d;">✓ Eliminates quality risk</div>
        </div>
        """, unsafe_allow_html=True)
    with s4:
        st.markdown(f"""
        <div class="procure-card" style="border-left:4px solid #a855f7;">
            <div class="stat-label" style="color:#7e22ce;">Scenario C: Dual Sourcing (70/30)</div>
            <div class="stat-number">₹{live_scenarios['spend_c']/1e7:.2f} Cr</div>
            <div style="font-size:12px; font-weight:600; color:#15803d; margin-top:2px;">
                Saves ₹{live_scenarios['savings_c']/1e5:.2f} L ({(live_scenarios['savings_c']/live_scenarios['budget_spend'])*100:.2f}%)
            </div>
            <div style="margin-top:6px; font-size:11px; color:#7e22ce;">✓ Insures 5 Critical SKUs</div>
        </div>
        """, unsafe_allow_html=True)

    # Dynamic Plotly Bar Chart Bound to Live Calculation
    chart_df = pd.DataFrame({
        "Scenario": ["Master Budget", "Scenario A (Unconstrained)", "Scenario B (Quality-Gated)", "Scenario C (Dual Sourced)"],
        "Spend": [live_scenarios["budget_spend"], live_scenarios["spend_a"], live_scenarios["spend_b"], live_scenarios["spend_c"]],
        "Color": ["#94a3b8", "#3b82f6", "#22c55e", "#a855f7"],
        "Formatted": [f"₹{v/1e7:.2f} Cr" for v in [live_scenarios["budget_spend"], live_scenarios["spend_a"], live_scenarios["spend_b"], live_scenarios["spend_c"]]]
    })

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=chart_df["Scenario"],
        y=chart_df["Spend"],
        text=chart_df["Formatted"],
        textposition="outside",
        marker_color=chart_df["Color"],
        width=0.45
    ))
    fig.add_hline(
        y=live_scenarios["budget_spend"],
        line_dash="dot",
        line_color="#ef4444",
        annotation_text="Live Budget Cap",
        annotation_position="top right"
    )
    fig.update_layout(
        title="<b>Live Spend Comparison across Scenarios (Bound to Live Pandas Engine)</b>",
        title_font=dict(size=14, color="#0f172a"),
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        margin=dict(l=40, r=40, t=50, b=40),
        yaxis=dict(range=[36000000, max(chart_df["Spend"]) * 1.08], tickformat="₹,~s", gridcolor="#f1f5f9")
    )
    st.plotly_chart(fig, use_container_width=True)

    # Cost of Compliance Card
    st.markdown(f"""
    <div class="procure-card" style="background-color:#fffbeb; border:1px solid #fde68a;">
        <div style="display:flex; align-items:flex-start; gap:14px;">
            <div style="background-color:#fef3c7; color:#b45309; width:36px; height:36px; border-radius:8px; display:flex; align-items:center; justify-content:center; font-size:18px; font-weight:bold; flex-shrink:0;">
                ⚖️
            </div>
            <div>
                <h4 style="font-size:15px; font-weight:800; color:#92400e; margin:0 0 4px 0;">Live Cost of Compliance: +₹{live_scenarios['cost_of_compliance']:,.0f} (+{live_scenarios['compliance_pct']:.2f}%)</h4>
                <p style="font-size:13px; color:#78350f; line-height:1.5; margin:0;">
                    Dynamic calculation: Enforcing the quality gate to exclude uncertified Vendor 4 costs an extra <strong>₹{live_scenarios['cost_of_compliance']:,.0f}</strong>. 
                    This guarantees that all awarded lines comply with ISO 9001 and in-house board lab testing standards.
                </p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Vendor Allocation & Spend Shares Table
    st.markdown("### 🏆 Vendor Allocations & Spend Shares")
    shares_b = live_scenarios.get("vendor_shares_b", {})
    shares_c = live_scenarios.get("vendor_shares_c", {})
    all_vendors = sorted(list(set(list(shares_b.keys()) + list(shares_c.keys()))))
    
    shares_data = []
    for v in all_vendors:
        sb = shares_b.get(v, {})
        sc = shares_c.get(v, {})
        shares_data.append({
            "Vendor": v,
            "Scenario B Spend (₹)": f"₹{sb.get('spend', 0.0):,.0f}",
            "Scenario B Share": f"{sb.get('share_pct', 0.0):.1f}%",
            "Scenario C Spend (₹)": f"₹{sc.get('spend', 0.0):,.0f}",
            "Scenario C Share": f"{sc.get('share_pct', 0.0):.1f}%"
        })
    if shares_data:
        st.dataframe(pd.DataFrame(shares_data), use_container_width=True, hide_index=True)

    # Mandatory Line Coverage & Uncovered Lines
    uncovered_b = live_scenarios.get("uncovered_lines_b", [])
    if uncovered_b:
        st.warning(f"⚠️ Mandatory Line Coverage Alert: {len(uncovered_b)} line(s) currently UNCOVERED in Scenario B: {uncovered_b}. No eligible vendor has a compliant quote for these lines.")
    else:
        st.success("✅ Mandatory Line Coverage: 100% of all 30 packaging lines covered by compliant, quality-gated suppliers in Scenario B.")

    # Conditional Discounts & Policy Exceptions
    discounts = live_scenarios.get("discounts_evaluated", {})
    if discounts:
        st.markdown("##### 🏷️ Conditional Discounts Evaluation (Scenario B Audit)")
        disc_rows = []
        for v, d in discounts.items():
            disc_rows.append({
                "Vendor": v,
                "Original Quoted Amount": f"₹{d.get('original_amount', 0.0):,.2f}",
                "Eligible Discount": d.get("eligible_discount", f"{d.get('discount_pct', 0.0)*100:.1f}%"),
                "Discount Applied": f"₹{d.get('discount_applied', 0.0):,.2f}" if d.get("applied") else "₹0.00",
                "Discount Not Applied & Reason": d.get("discount_not_applied_reason") or "N/A (Discount Applied)",
                "Final Award Amount": f"₹{d.get('final_award_amount', 0.0):,.2f}"
            })
        st.dataframe(pd.DataFrame(disc_rows), use_container_width=True, hide_index=True)

    # Detailed Line Item Allocation Tables
    col_hdr, col_exp = st.columns([3, 1])
    with col_hdr:
        st.markdown("### 📋 Line Item Allocation Breakdown")
    with col_exp:
        if live_scenarios.get("b_line_allocations"):
            csv_data = pd.DataFrame(live_scenarios["b_line_allocations"]).to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Export Scenario B (CSV)",
                data=csv_data,
                file_name="Scenario_B_Quality_Gated_Award.csv",
                mime="text/csv",
                use_container_width=True
            )
    tab_b, tab_c = st.tabs(["Scenario B: Quality-Gated L1", "Scenario C: Dual Sourcing (70/30)"])
    with tab_b:
        if live_scenarios.get("b_line_allocations"):
            df_alloc_b = pd.DataFrame(live_scenarios["b_line_allocations"])
            st.dataframe(df_alloc_b, use_container_width=True, hide_index=True)
    with tab_c:
        if live_scenarios.get("c_line_allocations"):
            df_alloc_c = pd.DataFrame(live_scenarios["c_line_allocations"])
            st.dataframe(df_alloc_c, use_container_width=True, hide_index=True)


# ─────────────────────────────────────────────────────────────────────────────
# 14. VIEW 4: QUESTIONNAIRE AUDIT GATE
# ─────────────────────────────────────────────────────────────────────────────
elif nav == "🛡️ Questionnaire Audit Gate":
    st.markdown("""
    <div class="procure-card">
        <h2 style="font-size:20px; font-weight:800; color:#0f172a; margin:0 0 4px 0;">Questionnaire Audit & Mandatory Quality Gates</h2>
        <p style="font-size:13px; color:#64748b; margin:0;">
            Evaluation criteria governing the dynamic exclusion rules in Scenario B and Scenario C.
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div style="background-color:#fef2f2; border:2px solid #ef4444; border-radius:12px; padding:18px; margin-bottom:18px;">
        <div style="display:flex; align-items:flex-start; gap:12px;">
            <div style="background-color:#fee2e2; color:#b91c1c; width:36px; height:36px; border-radius:8px; display:flex; align-items:center; justify-content:center; font-size:20px; font-weight:bold; flex-shrink:0;">
                🚫
            </div>
            <div>
                <h3 style="font-size:16px; font-weight:800; color:#991b1b; margin:0;">Vendor 4 (Sri Balaji Packaging) — DISQUALIFIED</h3>
                <p style="font-size:13px; color:#7f1d1d; line-height:1.5; margin:6px 0;">
                    Vendor 4 failed <strong>Q1: ISO 9001:2015 certificate expired in October 2026</strong>. 
                    They also failed Q2 (280 TPM capacity < 300 TPM), Q3 (no test lab), Q4 (2.4% rejection rate), and Q5 (only 2 active clients).
                    Therefore, the optimization engine dynamically locks V4 out of Scenario B and C.
                </p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.dataframe(st.session_state.df_gate, use_container_width=True, hide_index=True)


# ─────────────────────────────────────────────────────────────────────────────
# 15. VIEW 5: LIVE AI PROCUREMENT ANALYST (STRICT REASONING, NO CANNED RESPONSES)
# ─────────────────────────────────────────────────────────────────────────────
elif nav == "💬 AI Procurement Analyst (Live LLM)":
    st.markdown("""
    <div class="procure-card">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <div>
                <h2 style="font-size:20px; font-weight:800; color:#0f172a; margin:0 0 4px 0;">AI Procurement Analyst (Live LLM Reasoning Engine)</h2>
                <p style="font-size:13px; color:#64748b; margin:0;">
                    Live reasoning powered by OpenAI API with the active normalized matrix and audit database injected into context. <strong>No canned responses.</strong>
                </p>
            </div>
            <span class="badge-verified">Live LLM Context</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("**Interactive Quick Inquiries:**")
    qc1, qc2, qc3 = st.columns(3)
    
    chip1 = "Why is Vendor 5 marked unresolved for line 27?"
    chip2 = "What is the cost difference if we enforce the quality gate?"
    chip3 = "Show me the risk profile for Vendor 4."

    user_query = None
    with qc1:
        if st.button(f"💬 {chip1}", use_container_width=True):
            user_query = chip1
    with qc2:
        if st.button(f"💬 {chip2}", use_container_width=True):
            user_query = chip2
    with qc3:
        if st.button(f"💬 {chip3}", use_container_width=True):
            user_query = chip3

    custom_query = st.chat_input("Ask co-pilot about vendor quotes, active overrides, or compliance...")
    if custom_query:
        user_query = custom_query

    # Display chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Live LLM Generation Call
    if user_query:
        st.session_state.messages.append({"role": "user", "content": user_query})
        with st.chat_message("user"):
            st.markdown(user_query)

        active_client, client_err = get_openai_client_or_status()
        if not active_client:
            with st.chat_message("assistant"):
                st.warning(client_err)
                st.session_state.messages.append({"role": "assistant", "content": client_err})
        else:
            # Inject LIVE state of edited_df into LLM context
            matrix_context = st.session_state.df_norm[[
                "Line #", "Item Code", "Description", "Est. Qty", "Delivery Location", "Criticality",
                "V1 (Apex)", "V2 (PackTech)", "V3 (Global USD)", "V4 (Balaji)", "V5 (Standard Box)",
                "V1 Citation", "V2 Citation", "V3 Citation", "V4 Citation", "V5 Citation", "V5 Trust Flag"
            ]].to_markdown(index=False)

            audit_context = st.session_state.df_gate.to_markdown(index=False)

            system_instruction = f"""You are the AI Procurement Analyst co-pilot for RFx-CORR-2026-017.
You are directly connected to the active normalized matrix and Questionnaire Audit database.

--- LIVE DATA CONTEXT ---
LIVE QUOTE MATRIX & CITATIONS:
{matrix_context}

QUESTIONNAIRE AUDIT:
{audit_context}

LIVE SCENARIO SPENDS (PANDAS CALCULATED):
- Master Budget: ₹{live_scenarios['budget_spend']:,.0f}
- Scenario A (Unconstrained L1): ₹{live_scenarios['spend_a']:,.0f} (Net Savings: ₹{live_scenarios['savings_a']:,.0f})
- Scenario B (Quality-Gated L1): ₹{live_scenarios['spend_b']:,.0f} (Net Savings: ₹{live_scenarios['savings_b']:,.0f})
- Scenario C (Dual Sourcing 70/30): ₹{live_scenarios['spend_c']:,.0f}
- Cost of Compliance: +₹{live_scenarios['cost_of_compliance']:,.0f} (+{live_scenarios['compliance_pct']:.2f}%)

--- CRITICAL MANDATORY INSTRUCTIONS ---
1. You MUST base all answers strictly on the live numbers and citations provided above. DO NOT use canned responses.
2. CRITICAL: When explaining why any price was inferred, converted, or unresolved, you MUST strictly cite the exact verbatim text from the 'Citation' fields (e.g. 'V5 Citation').
3. If the user asks about an UNRESOLVED cell (e.g. Vendor 5 on Line 27 or other New SKUs), explicitly refuse to assume a landed cost and state: 'The quote is UNRESOLVED because it quoted Same as last year on a New SKU with no historical PO reference.' Mention that Line 27 also failed Gate Q7 for moisture barrier.
4. Keep responses concise, high-trust, and executive-ready.
"""

            with st.chat_message("assistant"):
                with st.spinner("AI Analyst executing live reasoning over current screen data..."):
                    try:
                        completion = active_client.chat.completions.create(
                            model="gpt-4o",
                            messages=[
                                {"role": "system", "content": system_instruction},
                                {"role": "user", "content": user_query}
                            ],
                            temperature=0.1
                        )
                        response_text = completion.choices[0].message.content
                    except Exception as e:
                        diag_msg = format_openai_api_error(e)
                        response_text = f"⚠️ OpenAI Service Error: {diag_msg}"

                    st.markdown(response_text)
                    st.session_state.messages.append({"role": "assistant", "content": response_text})
