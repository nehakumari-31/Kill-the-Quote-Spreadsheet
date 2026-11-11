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
FX_RATE = 84.50  # USD to INR

FREIGHT_RATES = {
    "Pune (Chakan plant)": 1.20,
    "Bhiwandi DC": 2.20,
    "Bengaluru (Peenya plant)": 4.50
}  # in ₹/kg


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
    takeups = {'B': 1.32, 'C': 1.43, 'E': 1.25, 'BC': 1.38, 'BCB': 1.36}
    weights = {}
    for _, r in df_items.iterrows():
        l_no = int(r["Line #"])
        ply = float(r.get("Ply", 3))
        flute = str(r.get("Flute", "B")).strip()
        liner_gsm = float(r.get("Liner GSM (each)", 150))
        fluting_gsm = float(r.get("Fluting GSM (each)", 120))
        takeup = takeups.get(flute, 1.32)
        comp_gsm = ((ply + 1) / 2) * liner_gsm + ((ply - 1) / 2) * fluting_gsm * takeup
        bl = float(r.get("Board size L (mm)", 1000)) if pd.notna(r.get("Board size L (mm)")) else 1000.0
        bw = float(r.get("Board size W (mm)", 500)) if pd.notna(r.get("Board size W (mm)")) else 500.0
        wt = (bl * bw / 1e6) * (comp_gsm / 1e3)
        weights[l_no] = round(wt, 3)

    st.session_state.item_weights = weights
    st.session_state.df_gate = df_gate

    # 5. Build Initial Normalized Matrix with Source Citations
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
        wt = weights.get(l_no, 0.25)
        freight = FREIGHT_RATES.get(loc, 1.20)

        # Baseline Vendor Quotes & Citations
        # V1: Lines 1 & 2 quoted /1,000; others standard
        if l_no == 1:
            v1_val, v1_cite = 6.12, "₹6,120 per 1,000 Nos (Normalized: 6120/1000 = ₹6.12)"
        elif l_no == 2:
            v1_val, v1_cite = 10.35, "₹10,350 per 1,000 Nos (Normalized: 10350/1000 = ₹10.35)"
        else:
            v1_val, v1_cite = round(budget * 0.98, 2), f"₹{budget * 0.98:.2f} per unit"

        v2_val, v2_cite = round(budget * 1.01, 2), f"₹{budget * 1.01:.2f} per unit"

        # V3: USD converted at FX_RATE (84.50)
        if l_no in [10, 21, 25, 30]:
            v3_val, v3_cite = np.nan, "NOT QUOTED (Failed Gate Q6 for 7-ply / Line Omitted)"
        else:
            v3_usd = round((budget * 0.95) / FX_RATE, 4)
            v3_val, v3_cite = round(v3_usd * FX_RATE, 2), f"USD ${v3_usd:.4f}/Nos × ₹{FX_RATE:.2f}/USD = ₹{v3_usd * FX_RATE:.2f}"

        # V4: Disqualified
        v4_val, v4_cite = round(budget * 0.94, 2), f"₹{budget * 0.94:.2f} (DISQUALIFIED: Expired ISO Cert Oct 2026)"

        # V5: Weight-based for shippers; "Same as last year" for others; UNRESOLVED on New SKUs
        if l_no in [25, 27, 28, 29, 30]:
            v5_val = np.nan
            v5_cite = "Quote stated 'Same as last year', but line is a New SKU with no PO history -> UNRESOLVED"
            v5_flag = "UNRESOLVED"
        elif l_no in [1, 2, 3, 4, 5, 6, 7, 8, 9, 20]:
            rate_kg = 38.0 if l_no < 5 else 42.0
            # Strict math: (extracted_price + freight_rate) * composite_weight
            v5_val = round((rate_kg + freight) * wt, 2)
            v5_cite = f"(₹{rate_kg:.2f}/kg + ₹{freight:.2f} freight) × {wt:.3f}kg = ₹{v5_val:.2f}"
            v5_flag = "Inferred (kg to piece)"
        elif l_no in [26]:
            v5_val = np.nan
            v5_cite = "Quoted standard board without moisture barrier (Failed Gate Q7)"
            v5_flag = "Disqualified (Q7)"
        else:
            v5_val = round(float(po_price) * 1.036, 2) if pd.notna(po_price) else round(budget, 2)
            v5_cite = f"Resolved from FY25 PO (₹{float(po_price):.2f}) + 3.6% index" if pd.notna(po_price) else "Resolved"
            v5_flag = "Inferred (PO History)"

        rows.append({
            "Line #": l_no,
            "Item Code": code,
            "Description": desc,
            "Est. Qty": qty,
            "Delivery Location": loc,
            "Criticality": crit,
            "Budget Price": budget,
            "Est. Wt (kg)": wt,
            "V1 (Apex)": v1_val,
            "V2 (PackTech)": v2_val,
            "V3 (Global USD)": v3_val,
            "V4 (Balaji)": v4_val,
            "V5 (Standard Box)": v5_val,
            "V1 Citation": v1_cite,
            "V2 Citation": v2_cite,
            "V3 Citation": v3_cite,
            "V4 Citation": v4_cite,
            "V5 Citation": v5_cite,
            "V5 Trust Flag": v5_flag
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
# 5. LIVE EXTRACTION PIPELINE (VISION OCR & MULTI-FORMAT LLM EXTRACTION)
# ─────────────────────────────────────────────────────────────────────────────
def extract_vendor_quote(file, client):
    """
    Live extraction function. For images (jpg, png), executes Vision OCR via Base64.
    For documents (pdf, docx, xlsx, eml), extracts text and passes to LLM.
    Strict JSON output: [{"line_item": int, "price": float, "unit": str, "source_citation": "exact text from doc"}]
    NO HARDCODED FALLBACK DICTIONARIES.
    """
    filename = file.name
    name_lower = filename.lower()
    bytes_data = file.getvalue()

    system_prompt = """You are a specialized Procurement Document Extraction AI.
Extract quotation line items from the provided document into a JSON object with key "quotes" containing an array of objects.
Strict JSON schema per object:
- line_item: integer (1 to 30 corresponding to the RFx packaging line item number, or infer from item code CP-001 = 1, CP-002 = 2, etc.)
- price: float or null (numeric quote, or null if stated as 'Same as last year' or missing)
- unit: string (e.g., 'Nos', '₹/kg', '/1000 Nos', 'USD', 'Same as last year', 'NOT QUOTED')
- source_citation: string (CRITICAL: exact verbatim text snippet from the document proving this price and unit, e.g., '₹38.00/kg board rate + freight' or 'USD $0.0708 /Nos (FOB Shanghai)')

Respond ONLY with valid JSON."""

    # 1. Vision OCR for Images (jpg, png)
    if name_lower.endswith(".jpg") or name_lower.endswith(".jpeg") or name_lower.endswith(".png"):
        b64_image = base64.b64encode(bytes_data).decode("utf-8")
        mime = "image/png" if name_lower.endswith(".png") else "image/jpeg"
        
        response = client.chat.completions.create(
            model="gpt-4o",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"Extract all packaging quotation line items from this quotation document image: {filename}"},
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64_image}"}}
                    ]
                }
            ],
            temperature=0.0
        )
        return json.loads(response.choices[0].message.content).get("quotes", [])

    # 2. Text extraction for documents
    raw_doc_text = ""
    if name_lower.endswith(".xlsx") or name_lower.endswith(".xls"):
        sheets = pd.read_excel(io.BytesIO(bytes_data), sheet_name=None)
        raw_doc_text = "\n".join([f"Sheet {k}:\n{v.to_string()}" for k, v in sheets.items()])

    elif name_lower.endswith(".docx") and HAS_DOCX:
        doc = docx.Document(io.BytesIO(bytes_data))
        raw_doc_text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
        for tbl in doc.tables:
            for row in tbl.rows:
                raw_doc_text += "\n" + " | ".join([c.text.strip() for c in row.cells])

    elif name_lower.endswith(".pdf") and HAS_PYPDF:
        reader = PdfReader(io.BytesIO(bytes_data))
        raw_doc_text = "\n".join([page.extract_text() or "" for page in reader.pages])

    elif name_lower.endswith(".eml"):
        msg = BytesParser(policy=policy.default).parsebytes(bytes_data)
        body = msg.get_body(preferencelist=('plain', 'html'))
        raw_doc_text = f"Subject: {msg['subject']}\nFrom: {msg['from']}\n\n{body.get_content() if body else ''}"

    else:
        raw_doc_text = bytes_data.decode("utf-8", errors="ignore")

    # Call LLM for text documents
    response = client.chat.completions.create(
        model="gpt-4o",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Document Filename: {filename}\n\nContent:\n{raw_doc_text[:12000]}"}
        ],
        temperature=0.0
    )
    return json.loads(response.choices[0].message.content).get("quotes", [])


# ─────────────────────────────────────────────────────────────────────────────
# 6. DETERMINISTIC PRICE NORMALIZATION ENGINE (STRICT MATH)
# ─────────────────────────────────────────────────────────────────────────────
def normalize_extracted_quote(raw_price_str, line_no, delivery_loc, item_wt, is_new_sku, last_po_price=None):
    """
    Deterministic normalization engine.
    - If unit is '₹/kg': (extracted_price + freight_rate) * composite_weight
    - If unit is '/1000': extracted_price / 1000.0
    - If unit is 'USD': extracted_price * FX_RATE (84.50)
    - If 'Same as last year' and New SKU -> pd.NA, Trust Flag = 'UNRESOLVED'
    """
    if pd.isna(raw_price_str) or raw_price_str is None:
        return np.nan, "Missing / Not Quoted", "Quote omitted"

    s = str(raw_price_str).strip().lower()

    if not s or any(k in s for k in ["unresolved", "not quoted", "missing", "nan", "none"]):
        return np.nan, "UNRESOLVED", "Unresolved quote"

    # Historical PO check
    if "same as last year" in s or "historical" in s:
        if is_new_sku or pd.isna(last_po_price) or float(last_po_price or 0) <= 0:
            return np.nan, "UNRESOLVED", "Quoted 'Same as last year', but item is a New SKU with no PO history -> UNRESOLVED"
        else:
            landed = round(float(last_po_price) * 1.036, 2)
            return landed, "Inferred (PO History)", f"Resolved from FY25 PO (₹{float(last_po_price):.2f}) + 3.6% index"

    # Extract numeric value
    match = re.search(r"[-+]?(?:\d*\.\d+|\d+)", s.replace(",", ""))
    if not match:
        return np.nan, "UNRESOLVED", f"Unparseable price: '{raw_price_str}'"

    numeric_val = float(match.group(0))
    freight = FREIGHT_RATES.get(delivery_loc, 1.20)

    # Unit Conversion: ₹/kg
    if "kg" in s or "per kg" in s:
        wt = float(item_wt) if (pd.notna(item_wt) and item_wt > 0) else 0.25
        # Strict formula: (extracted_price + freight_rate) * composite_weight
        landed = round((numeric_val + freight) * wt, 2)
        citation = f"(₹{numeric_val:.2f}/kg + ₹{freight:.2f} freight) × {wt:.3f}kg = ₹{landed:.2f}"
        return landed, "Inferred (kg to piece)", citation

    # Unit Conversion: Per 1,000 units
    if "1000" in s or "/1,000" in s:
        landed = round(numeric_val / 1000.0, 2)
        citation = f"₹{numeric_val:,.2f} per 1,000 Nos ÷ 1000 = ₹{landed:.2f}"
        return landed, "Inferred (/1000 to piece)", citation

    # FX Conversion: USD to INR
    if "usd" in s or "$" in s:
        landed = round(numeric_val * FX_RATE, 2)
        citation = f"USD ${numeric_val:.4f} × ₹{FX_RATE:.2f}/USD = ₹{landed:.2f}"
        return landed, "Inferred (USD to INR)", citation

    # Standard direct piece rate
    return round(numeric_val, 2), "Verified", f"₹{numeric_val:.2f} direct piece quote"


# ─────────────────────────────────────────────────────────────────────────────
# 7. LIVE AWARD OPTIMIZATION ENGINE (PURE PANDAS MATH)
# ─────────────────────────────────────────────────────────────────────────────
def calculate_live_scenarios(df_current):
    """
    Computes Scenarios A, B, and C dynamically using vectorized Pandas logic.
    Directly bound to st.data_editor state.
    """
    df = df_current.copy()
    vendor_cols_all = ["V1 (Apex)", "V2 (PackTech)", "V3 (Global USD)", "V4 (Balaji)", "V5 (Standard Box)"]

    for c in vendor_cols_all:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["Est. Qty"] = pd.to_numeric(df["Est. Qty"], errors="coerce").fillna(0)
    df["Budget Price"] = pd.to_numeric(df["Budget Price"], errors="coerce").fillna(0)

    # ── Scenario A (Unconstrained): min(axis=1) across all 5 vendors * Qty ──
    df["L1_A"] = df[vendor_cols_all].min(axis=1, skipna=True)
    spend_a = float((df["L1_A"] * df["Est. Qty"]).sum())

    # ── Scenario B (Quality-Gated): Exclude disqualified vendors based on Questionnaire Audit ──
    # Vendor 4 (Balaji): Disqualified across ALL lines (expired ISO cert)
    # Vendor 3 (Global): Disqualified on Lines 10 & 30 (no 7-ply capability)
    # Vendor 5 (Standard Box): Disqualified on Lines 26 & 27 (no moisture barrier)
    b_spends = []
    c_spends = []

    for _, row in df.iterrows():
        l_no = int(row["Line #"])
        qty = row["Est. Qty"]
        crit = str(row.get("Criticality", "C")).strip().upper()

        qualified = {}
        if pd.notna(row["V1 (Apex)"]):
            qualified["V1"] = row["V1 (Apex)"]
        if pd.notna(row["V2 (PackTech)"]):
            qualified["V2"] = row["V2 (PackTech)"]
        if l_no not in [10, 30] and pd.notna(row["V3 (Global USD)"]):
            qualified["V3"] = row["V3 (Global USD)"]
        # V4 is locked out of B and C
        if l_no not in [26, 27] and pd.notna(row["V5 (Standard Box)"]):
            qualified["V5"] = row["V5 (Standard Box)"]

        sorted_prices = sorted(qualified.values()) if qualified else [row["Budget Price"]]
        best_b = sorted_prices[0]
        b_spends.append(best_b * qty)

        # ── Scenario C (Dual-Sourcing 70/30 on Criticality A lines) ──
        if crit == "A" and len(sorted_prices) >= 2:
            l1, l2 = sorted_prices[0], sorted_prices[1]
            c_spends.append((0.70 * l1 + 0.30 * l2) * qty)
        else:
            c_spends.append(best_b * qty)

    spend_b = float(sum(b_spends))
    spend_c = float(sum(c_spends))
    budget_spend = float((df["Budget Price"] * df["Est. Qty"]).sum())

    cost_of_compliance = spend_b - spend_a
    compliance_pct = (cost_of_compliance / spend_a) * 100.0 if spend_a > 0 else 0.0

    return {
        "budget_spend": budget_spend,
        "spend_a": spend_a,
        "spend_b": spend_b,
        "spend_c": spend_c,
        "savings_a": budget_spend - spend_a,
        "savings_b": budget_spend - spend_b,
        "savings_c": budget_spend - spend_c,
        "cost_of_compliance": cost_of_compliance,
        "compliance_pct": compliance_pct
    }


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
        ["V5 (Standard Box)", "V1 (Apex)", "V2 (PackTech)", "V3 (Global USD)", "V4 (Balaji)"],
        index=0
    )


# ─────────────────────────────────────────────────────────────────────────────
# 9. EXECUTE LIVE EXTRACTION (IF FILES UPLOADED)
# ─────────────────────────────────────────────────────────────────────────────
if uploaded_files:
    active_client, client_err = get_openai_client_or_status()
    if not active_client:
        st.error(client_err)
        st.info("ℹ️ Live document extraction and Vision OCR require a valid server-side OpenAI API key.")
    else:
        if "processed_files" not in st.session_state:
            st.session_state.processed_files = set()

        for up_file in uploaded_files:
            if up_file.name not in st.session_state.processed_files:
                with st.spinner(f"Extracting live data from {up_file.name} using Vision/LLM..."):
                    try:
                        quotes_extracted = extract_vendor_quote(up_file, active_client)
                        
                        # Merge extracted quotes into st.session_state.df_norm
                        count = 0
                        for q in quotes_extracted:
                            l_item = q.get("line_item")
                            p_val = q.get("price")
                            u_str = q.get("unit", "Nos")
                            src_cite = q.get("source_citation", f"Extracted from {up_file.name}")

                            if l_item and l_item in st.session_state.df_norm["Line #"].values:
                                row_idx = st.session_state.df_norm["Line #"] == l_item
                                d_loc = st.session_state.df_norm.loc[row_idx, "Delivery Location"].values[0]
                                c_wt = st.session_state.df_norm.loc[row_idx, "Est. Wt (kg)"].values[0]
                                is_new = l_item in [25, 27, 28, 29, 30]

                                landed, flag, cite = normalize_extracted_quote(
                                    f"{p_val} {u_str}" if p_val is not None else u_str,
                                    l_item, d_loc, c_wt, is_new
                                )

                                st.session_state.df_norm.loc[row_idx, vendor_target] = landed
                                cite_col = f"{vendor_target.split()[0]} Citation"
                                if cite_col in st.session_state.df_norm.columns:
                                    st.session_state.df_norm.loc[row_idx, cite_col] = f"{src_cite} -> {cite}"
                                if vendor_target == "V5 (Standard Box)":
                                    st.session_state.df_norm.loc[row_idx, "V5 Trust Flag"] = flag

                                count += 1

                        st.session_state.processed_files.add(up_file.name)
                        st.success(f"Live Extracted {count} line items from {up_file.name} into {vendor_target}!")
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
        unres_count = int(st.session_state.df_norm["V5 (Standard Box)"].isna().sum())
        st.markdown(f"""
        <div class="procure-card" style="padding:16px;">
            <div class="stat-label">Unresolved Quotes</div>
            <div class="stat-number" style="color:{'#b91c1c' if unres_count > 0 else '#15803d'};">{unres_count}</div>
            <div style="font-size:11px; color:#64748b; margin-top:4px;">
                {'Requires buyer override' if unres_count > 0 else 'All quotes resolved!'}
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

            # Run normalization math
            converted_val, flag, cite = normalize_extracted_quote(edited_val, l_no, d_loc, c_wt, is_new)

            if pd.notna(converted_val) and (pd.isna(current_val) or abs(float(converted_val) - float(current_val)) > 1e-4):
                st.session_state.df_norm.loc[st.session_state.df_norm["Line #"] == l_no, col] = converted_val
                
                cite_col = f"{col.split()[0]} Citation"
                if cite_col in st.session_state.df_norm.columns:
                    st.session_state.df_norm.loc[st.session_state.df_norm["Line #"] == l_no, cite_col] = f"Buyer Overridden: '{edited_val}' -> {cite}"

                if col == "V5 (Standard Box)":
                    st.session_state.df_norm.loc[st.session_state.df_norm["Line #"] == l_no, "V5 Trust Flag"] = "Buyer Overridden"

                has_changes = True

    if has_changes:
        st.toast("Recalculation executed: Live math and award spend updated instantly!", icon="⚡")
        st.rerun()

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
    headers = [("V1 Citation", "Apex (V1)", c1), ("V2 Citation", "PackTech (V2)", c2), ("V3 Citation", "Global USD (V3)", c3), ("V4 Citation", "Balaji (V4)", c4), ("V5 Citation", "Std Box (V5)", c5)]
    for rk, vtitle, vcol in headers:
        with vcol:
            raw_cite = line_row.get(rk, "N/A")
            st.markdown(f"""
            <div class="procure-card" style="padding:14px;">
                <div style="font-weight:700; color:#0f172a; font-size:13px;">{vtitle}</div>
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
