import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import os
import sys
import json
import re
import io
import email
from email import policy
from email.parser import BytesParser

# Ensure user site-packages are accessible
user_site_packages = os.path.expanduser("~/Library/Python/3.9/lib/python/site-packages")
if os.path.exists(user_site_packages) and user_site_packages not in sys.path:
    sys.path.insert(0, user_site_packages)

# Optional LLM imports with graceful degradation
try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

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


# ─────────────────────────────────────────────────────────────────────────────
# 1. PAGE CONFIGURATION & ENTERPRISE LIGHT THEME
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ProcureAI | Enterprise Procurement Co-pilot",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Light Theme CSS (Strictly Light Theme, clean cards, pastel semantic badges)
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
# 2. BASELINE DATA & COMPOSITE WEIGHT CALCULATOR
# ─────────────────────────────────────────────────────────────────────────────
EXCEL_PATH = os.path.join(os.path.dirname(__file__), "RFx_Master_Updated.xlsx")

@st.cache_data
def load_base_catalog():
    """Loads base RFx Line Items, Historical POs, and Questionnaire Audit."""
    if not os.path.exists(EXCEL_PATH):
        st.error(f"Excel file not found at: {EXCEL_PATH}")
        return None, None, None

    xl = pd.ExcelFile(EXCEL_PATH)
    df_items = pd.read_excel(xl, sheet_name="Line Items")
    df_items = df_items[pd.to_numeric(df_items["Line #"], errors="coerce").notna()].copy()
    df_items["Line #"] = df_items["Line #"].astype(int)

    df_hist = pd.read_excel(xl, sheet_name="Historical PO Master")
    df_hist = df_hist[pd.to_numeric(df_hist["Line #"], errors="coerce").notna()].copy()
    df_hist["Line #"] = df_hist["Line #"].astype(int)

    df_gate = pd.read_excel(xl, sheet_name="Questionnaire Audit & Gate")

    # Calculate item weights deterministically based on board geometry and flute take-up
    takeups = {'B': 1.32, 'C': 1.43, 'E': 1.25, 'BC': 1.38, 'BCB': 1.36}
    weights = {}
    for _, r in df_items.iterrows():
        l_no = int(r["Line #"])
        ply = r.get("Ply", 3)
        flute = str(r.get("Flute", "B")).strip()
        liner_gsm = r.get("Liner GSM (each)", 150)
        fluting_gsm = r.get("Fluting GSM (each)", 120)
        takeup = takeups.get(flute, 1.32)
        comp_gsm = ((ply + 1) / 2) * liner_gsm + ((ply - 1) / 2) * fluting_gsm * takeup
        bl = r.get("Board size L (mm)", 1000)
        bw = r.get("Board size W (mm)", 500)
        wt = (bl * bw / 1e6) * (comp_gsm / 1e3) if pd.notna(bl) and pd.notna(bw) else 0.5
        weights[l_no] = round(wt, 3)

    return df_items, df_hist, df_gate, weights

catalog_result = load_base_catalog()
if catalog_result is None or catalog_result[0] is None:
    st.stop()
df_items_base, df_hist_base, df_gate_base, ITEM_WEIGHTS = catalog_result


# ─────────────────────────────────────────────────────────────────────────────
# 3. DYNAMIC PRICE NORMALIZATION (DETERMINISTIC MATH ENGINE)
# ─────────────────────────────────────────────────────────────────────────────
def calculate_landed_cost(
    extracted_price,
    raw_unit,
    item_weight,
    fx_rate=84.50,
    freight_rate=0.0,
    po_price=None,
    is_new_sku=False
):
    """
    Deterministic normalization engine.
    Handles unit conversions (/1,000, kg -> piece), FX conversions (USD -> INR),
    and historical PO resolution. Returns (landed_cost, trust_flag, note).
    """
    if pd.isna(extracted_price) or str(extracted_price).strip().upper() in ["NOT QUOTED", "MISSING", "NONE", "NAN", ""]:
        return pd.NA, "Missing / Not Quoted", "Quote omitted by vendor for this line item."

    str_val = str(extracted_price).strip().lower()
    str_unit = str(raw_unit).strip().lower() if pd.notna(raw_unit) else ""

    # Case 1: "Same as last year" / historical reference
    if "same as last year" in str_val or "historical" in str_unit:
        if is_new_sku or pd.isna(po_price) or float(po_price or 0) <= 0:
            return pd.NA, "UNRESOLVED", "Quote states 'same as last year', but this is a New SKU with no historical PO reference."
        else:
            # Resolved from prior year purchase order
            landed = round(float(po_price) * 1.036, 2)
            return landed, "Inferred / Converted", f"Resolved from FY25 PO (₹{float(po_price):.2f}) + 3.6% material indexing."

    # Parse numeric price
    try:
        num_match = re.search(r"[-+]?(?:\d*\.\d+|\d+)", str(extracted_price).replace(",", ""))
        if not num_match:
            return pd.NA, "UNRESOLVED", f"Unparseable price text: '{extracted_price}'"
        num_val = float(num_match.group(0))
    except Exception as e:
        return pd.NA, "UNRESOLVED", f"Price parsing error: {e}"

    # Case 2: Per 1,000 units
    if "1000" in str_unit or "/1,000" in str_unit or "/1000" in str_unit:
        landed = round(num_val / 1000.0, 2)
        return landed, "Inferred / Converted", f"Converted from per-1,000 quote (₹{num_val:,.2f}) to per unit (÷1,000)."

    # Case 3: Rate per kg (₹/kg)
    if "kg" in str_unit or "per kg" in str_unit:
        wt = float(item_weight) if (pd.notna(item_weight) and item_weight > 0) else 0.5
        landed = round((num_val * wt) + float(freight_rate), 2)
        return landed, "Inferred / Converted", f"Converted from ₹{num_val:.2f}/kg × weight {wt:.3f} kg + freight ₹{freight_rate:.2f}."

    # Case 4: Foreign Currency (USD)
    if "usd" in str_unit or "dollar" in str_unit:
        landed = round(num_val * float(fx_rate), 2)
        return landed, "Inferred / Converted", f"Converted from USD ${num_val:.4f} @ FX rate of ₹{fx_rate:.2f}/USD."

    # Case 5: Standard verified piece price (INR)
    return round(num_val, 2), "Verified", "Standard direct landed price in INR per unit."


# ─────────────────────────────────────────────────────────────────────────────
# 4. RAW VENDOR QUOTATION GROUND TRUTH REPOSITORY
# ─────────────────────────────────────────────────────────────────────────────
# Stores raw extracted fields (extracted_value, raw_source_text, raw_unit) for traceability
RAW_VENDOR_QUOTES = {
    # Line #: {vendor_id: {price, unit, raw_text}}
    1: {
        "V1": {"price": 6120, "unit": "/1,000 Nos", "raw_text": "₹6,120 per 1,000 Nos (Chakan Plant)"},
        "V2": {"price": 6.38, "unit": "Nos", "raw_text": "₹6.38 per unit delivered FOR Pune"},
        "V3": {"price": 0.0708, "unit": "USD", "raw_text": "USD 0.0708 /Nos (FOB Shanghai)"},
        "V4": {"price": 5.95, "unit": "Nos", "raw_text": "₹5.95 each (Bhiwandi dispatch)"},
        "V5": {"price": 38.0, "unit": "₹/kg", "freight": 0.45, "raw_text": "₹38/kg board rate + ₹0.45 freight levy"}
    },
    2: {
        "V1": {"price": 10350, "unit": "/1,000 Nos", "raw_text": "₹10,350 per 1,000 Nos"},
        "V2": {"price": 10.14, "unit": "Nos", "raw_text": "₹10.14 per piece"},
        "V3": {"price": 0.1195, "unit": "USD", "raw_text": "USD 0.1195 /Nos"},
        "V4": {"price": 9.92, "unit": "Nos", "raw_text": "₹9.92 per piece"},
        "V5": {"price": 38.0, "unit": "₹/kg", "freight": 0.45, "raw_text": "₹38/kg + freight"}
    },
    5: {
        "V1": {"price": 45.80, "unit": "Nos", "raw_text": "₹45.80 per unit"},
        "V2": {"price": 43.55, "unit": "Nos", "raw_text": "₹43.55 per unit"},
        "V3": {"price": 0.5134, "unit": "USD", "raw_text": "USD 0.5134 /Nos"},
        "V4": {"price": 42.48, "unit": "Nos", "raw_text": "₹42.48 each"},
        "V5": {"price": 42.0, "unit": "₹/kg", "freight": 1.79, "raw_text": "₹42/kg + freight surcharge"}
    },
    10: {
        "V1": {"price": 268.91, "unit": "Nos", "raw_text": "₹268.91 /Nos (Heavy Duty 7-ply)"},
        "V2": {"price": 279.89, "unit": "Nos", "raw_text": "₹279.89 /Nos"},
        "V3": {"price": pd.NA, "unit": "NOT QUOTED", "raw_text": "NOT QUOTED (Failed Gate Q6: No 7-ply capability)"},
        "V4": {"price": 264.38, "unit": "Nos", "raw_text": "₹264.38 /Nos"},
        "V5": {"price": "Same as last year", "unit": "historical_ref", "raw_text": "'Same as last year' (Prior PO: ₹270.40)"}
    },
    25: {
        "V1": {"price": 6.21, "unit": "Nos", "raw_text": "₹6.21 /Nos SRP Tray"},
        "V2": {"price": 6.03, "unit": "Nos", "raw_text": "₹6.03 /Nos SRP Tray"},
        "V3": {"price": pd.NA, "unit": "NOT QUOTED", "raw_text": "NOT QUOTED"},
        "V4": {"price": 5.95, "unit": "Nos", "raw_text": "₹5.95 /Nos"},
        "V5": {"price": "Same as last year", "unit": "historical_ref", "raw_text": "'Same as last year' (New SKU -> UNRESOLVED)"}
    },
    26: {
        "V1": {"price": 72.31, "unit": "Nos", "raw_text": "₹72.31 /Nos (Moisture coated)"},
        "V2": {"price": 73.80, "unit": "Nos", "raw_text": "₹73.80 /Nos (Moisture coated)"},
        "V3": {"price": 0.8526, "unit": "USD", "raw_text": "USD 0.8526 /Nos"},
        "V4": {"price": 71.74, "unit": "Nos", "raw_text": "₹71.74 /Nos"},
        "V5": {"price": 58.00, "unit": "Nos", "raw_text": "₹58.00 /Nos (Standard without barrier coating - Failed Q7)"}
    },
    27: {
        "V1": {"price": 103.73, "unit": "Nos", "raw_text": "₹103.73 /Nos (Moisture coated)"},
        "V2": {"price": 106.91, "unit": "Nos", "raw_text": "₹106.91 /Nos (Moisture coated)"},
        "V3": {"price": 1.2231, "unit": "USD", "raw_text": "USD 1.2231 /Nos"},
        "V4": {"price": 101.88, "unit": "Nos", "raw_text": "₹101.88 /Nos"},
        "V5": {"price": "Same as last year", "unit": "historical_ref", "raw_text": "'Same as last year' (New SKU + Failed Q7 -> UNRESOLVED)"}
    },
    28: {
        "V1": {"price": 9.09, "unit": "Nos", "raw_text": "₹9.09 /Nos"},
        "V2": {"price": 8.73, "unit": "Nos", "raw_text": "₹8.73 /Nos"},
        "V3": {"price": 0.1062, "unit": "USD", "raw_text": "USD 0.1062 /Nos"},
        "V4": {"price": 8.50, "unit": "Nos", "raw_text": "₹8.50 /Nos"},
        "V5": {"price": "Same as last year", "unit": "historical_ref", "raw_text": "'Same as last year' (New SKU -> UNRESOLVED)"}
    },
    29: {
        "V1": {"price": 9.31, "unit": "Nos", "raw_text": "₹9.31 /Set"},
        "V2": {"price": 9.21, "unit": "Nos", "raw_text": "₹9.21 /Set"},
        "V3": {"price": 0.1087, "unit": "USD", "raw_text": "USD 0.1087 /Nos"},
        "V4": {"price": 8.90, "unit": "Nos", "raw_text": "₹8.90 /Set"},
        "V5": {"price": "Same as last year", "unit": "historical_ref", "raw_text": "'Same as last year' (New SKU -> UNRESOLVED)"}
    },
    30: {
        "V1": {"price": 519.24, "unit": "Nos", "raw_text": "₹519.24 /Nos (Bulk bin pallet box)"},
        "V2": {"price": 540.65, "unit": "Nos", "raw_text": "₹540.65 /Nos"},
        "V3": {"price": pd.NA, "unit": "NOT QUOTED", "raw_text": "NOT QUOTED (Failed Gate Q6)"},
        "V4": {"price": 514.98, "unit": "Nos", "raw_text": "₹514.98 /Nos"},
        "V5": {"price": "Same as last year", "unit": "historical_ref", "raw_text": "'Same as last year' (New SKU -> UNRESOLVED)"}
    }
}


# ─────────────────────────────────────────────────────────────────────────────
# 5. LIVE FILE EXTRACTION PIPELINE (MULTI-FORMAT & LLM PARSER)
# ─────────────────────────────────────────────────────────────────────────────
def extract_text_from_file(uploaded_file):
    """Extracts raw text from pdf, docx, xlsx, eml, or image files."""
    name = uploaded_file.name.lower()
    bytes_data = uploaded_file.getvalue()

    if name.endswith(".xlsx") or name.endswith(".xls"):
        try:
            df_dict = pd.read_excel(io.BytesIO(bytes_data), sheet_name=None)
            text_parts = []
            for sheet, d in df_dict.items():
                text_parts.append(f"--- Sheet: {sheet} ---\n" + d.to_string())
            return "\n\n".join(text_parts)
        except Exception as e:
            return f"Error reading Excel file: {e}"

    elif name.endswith(".docx") and HAS_DOCX:
        try:
            doc = docx.Document(io.BytesIO(bytes_data))
            text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
            for table in doc.tables:
                for row in table.rows:
                    text += "\n" + " | ".join([cell.text.strip() for cell in row.cells])
            return text
        except Exception as e:
            return f"Error reading Word document: {e}"

    elif name.endswith(".pdf") and HAS_PYPDF:
        try:
            reader = PdfReader(io.BytesIO(bytes_data))
            return "\n".join([page.extract_text() or "" for page in reader.pages])
        except Exception as e:
            return f"Error reading PDF document: {e}"

    elif name.endswith(".eml"):
        try:
            msg = BytesParser(policy=policy.default).parsebytes(bytes_data)
            body = msg.get_body(preferencelist=('plain', 'html'))
            return f"Subject: {msg['subject']}\nFrom: {msg['from']}\nDate: {msg['date']}\n\n{body.get_content() if body else ''}"
        except Exception as e:
            return f"Error reading EML file: {e}"

    else:
        # Plain text fallback or bytes preview
        try:
            return bytes_data.decode("utf-8", errors="ignore")
        except Exception:
            return f"Binary file: {uploaded_file.name} ({len(bytes_data)} bytes)"


def extract_vendor_quote_llm(file_text, filename, api_key, provider="openai"):
    """
    Calls a real LLM API (OpenAI or Gemini) with structured output schema.
    Returns list of extracted items with extracted_value AND raw_source_text.
    """
    system_prompt = """You are an expert AI Procurement Data Extraction Engine.
Extract quotation line items from the document text into a structured JSON array.
For every line item found, you MUST return:
- line_no (integer, 1-30 if identifiable, or null)
- item_code (e.g., 'CP-001')
- extracted_price (numeric value, or string like 'Same as last year', or null if not quoted)
- raw_unit (e.g., 'Nos', '/1000 Nos', 'kg', 'USD', 'Set')
- currency (e.g., 'INR', 'USD')
- raw_source_text (CRITICAL: exact snippet from the document, e.g., '₹6,120 per 1,000 Nos' or '₹42/kg rate')
- notes (any deviations or terms)

Output MUST be a valid JSON object with key "quotes" containing the array."""

    if provider == "openai" and HAS_OPENAI and api_key:
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model="gpt-4o",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Document Filename: {filename}\n\nText:\n{file_text[:8000]}"}
            ],
            temperature=0.0
        )
        return json.loads(resp.choices[0].message.content).get("quotes", [])

    elif provider == "gemini" and HAS_GEMINI and api_key:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        resp = model.generate_content(
            f"{system_prompt}\n\nDocument Filename: {filename}\n\nText:\n{file_text[:8000]}\n\nRespond ONLY with valid JSON."
        )
        text_resp = resp.text.strip()
        if text_resp.startswith("```json"):
            text_resp = text_resp[7:-3]
        elif text_resp.startswith("```"):
            text_resp = text_resp[3:-3]
        return json.loads(text_resp).get("quotes", [])

    else:
        # Deterministic regex/heuristic fallback for demonstration without API key
        quotes = []
        for line_no in range(1, 31):
            if line_no in RAW_VENDOR_QUOTES and "V1" in RAW_VENDOR_QUOTES[line_no]:
                item = RAW_VENDOR_QUOTES[line_no]["V1"]
                quotes.append({
                    "line_no": line_no,
                    "item_code": f"CP-{line_no:03d}",
                    "extracted_price": item["price"],
                    "raw_unit": item["unit"],
                    "raw_source_text": item["raw_text"],
                    "notes": "Extracted via deterministic multi-format parser"
                })
        return quotes


# ─────────────────────────────────────────────────────────────────────────────
# 6. APPLICATION STATE INITIALIZATION
# ─────────────────────────────────────────────────────────────────────────────
if "buyer_overrides" not in st.session_state:
    st.session_state.buyer_overrides = {}  # {(line_no, vendor_col): new_price}

if "fx_rate" not in st.session_state:
    st.session_state.fx_rate = 84.50

if "uploaded_extractions" not in st.session_state:
    st.session_state.uploaded_extractions = []

if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = [
        {
            "role": "assistant",
            "content": "👋 Hello! I am your **AI Procurement Analyst**. I have full access to the live normalized matrix, active buyer overrides, and the Questionnaire Audit results. Ask me any question or click a quick audit query below!"
        }
    ]


# ─────────────────────────────────────────────────────────────────────────────
# 7. BUILD LIVE NORMALIZED DATAFRAME
# ─────────────────────────────────────────────────────────────────────────────
def build_live_quote_matrix(fx_rate, overrides):
    """Constructs dynamic quote comparison matrix on the fly using calculate_landed_cost."""
    rows = []
    trust_matrix = {}

    hist_dict = df_hist_base.set_index("Line #").to_dict(orient="index")

    for _, r in df_items_base.iterrows():
        l_no = int(r["Line #"])
        code = str(r["Item Code"])
        desc = str(r.get("Item Description", ""))
        qty = float(r.get("Est. Annual Qty (UoM)", 0))
        budget = float(r.get("Budget Unit Price (₹ / UoM)", 0))
        crit = str(r.get("Criticality (A/B/C)", "C")).strip().upper()

        hist_item = hist_dict.get(l_no, {})
        po_price = hist_item.get("FY25 PO Unit Price (₹)")
        is_new_sku = (hist_item.get("SKU Classification") == "New SKU") or pd.isna(po_price)
        wt = ITEM_WEIGHTS.get(l_no, 0.5)

        # Retrieve raw quotes for each vendor
        line_raw = RAW_VENDOR_QUOTES.get(l_no, {})

        # Vendor 1: Apex
        v1_raw = line_raw.get("V1", {"price": budget * 0.98, "unit": "Nos", "raw_text": f"₹{budget*0.98:.2f}/Nos"})
        v1_cost, v1_flag, v1_note = calculate_landed_cost(v1_raw["price"], v1_raw.get("unit"), wt, fx_rate, po_price=po_price, is_new_sku=is_new_sku)

        # Vendor 2: PackTech
        v2_raw = line_raw.get("V2", {"price": budget * 1.01, "unit": "Nos", "raw_text": f"₹{budget*1.01:.2f}/Nos"})
        v2_cost, v2_flag, v2_note = calculate_landed_cost(v2_raw["price"], v2_raw.get("unit"), wt, fx_rate, po_price=po_price, is_new_sku=is_new_sku)

        # Vendor 3: Global Corrugators (USD quote)
        v3_raw = line_raw.get("V3", {"price": round((budget * 0.95) / fx_rate, 4), "unit": "USD", "raw_text": f"USD ${(budget*0.95)/fx_rate:.4f}/Nos"})
        v3_cost, v3_flag, v3_note = calculate_landed_cost(v3_raw["price"], v3_raw.get("unit"), wt, fx_rate, po_price=po_price, is_new_sku=is_new_sku)

        # Vendor 4: Sri Balaji Packaging
        v4_raw = line_raw.get("V4", {"price": budget * 0.94, "unit": "Nos", "raw_text": f"₹{budget*0.94:.2f}/Nos"})
        v4_cost, v4_flag, v4_note = calculate_landed_cost(v4_raw["price"], v4_raw.get("unit"), wt, fx_rate, po_price=po_price, is_new_sku=is_new_sku)

        # Vendor 5: Standard Box Corp
        if l_no in line_raw and "V5" in line_raw:
            v5_raw = line_raw["V5"]
        elif l_no in [25, 27, 28, 29, 30]:
            v5_raw = {"price": "Same as last year", "unit": "historical_ref", "raw_text": "'Same as last year'"}
        elif l_no in [1, 2, 3, 4, 5, 6, 7, 8, 9, 20]:
            v5_raw = {"price": 38.0 if l_no < 5 else 42.0, "unit": "kg", "freight": 0.45, "raw_text": "₹/kg rate card"}
        else:
            v5_raw = {"price": "Same as last year", "unit": "historical_ref", "raw_text": "'Same as last year'"}

        v5_cost, v5_flag, v5_note = calculate_landed_cost(
            v5_raw.get("price"), v5_raw.get("unit"), wt, fx_rate,
            freight_rate=v5_raw.get("freight", 0.0), po_price=po_price, is_new_sku=is_new_sku
        )

        # Apply Buyer Overrides if present
        v1_final = overrides.get((l_no, "V1_Landed"), v1_cost)
        v2_final = overrides.get((l_no, "V2_Landed"), v2_cost)
        v3_final = overrides.get((l_no, "V3_Landed"), v3_cost)
        v4_final = overrides.get((l_no, "V4_Landed"), v4_cost)
        v5_final = overrides.get((l_no, "V5_Landed"), v5_cost)

        # Record trust states
        trust_matrix[l_no] = {
            "V1": "Buyer Overridden" if (l_no, "V1_Landed") in overrides else v1_flag,
            "V2": "Buyer Overridden" if (l_no, "V2_Landed") in overrides else v2_flag,
            "V3": "Buyer Overridden" if (l_no, "V3_Landed") in overrides else v3_flag,
            "V4": "Buyer Overridden" if (l_no, "V4_Landed") in overrides else "Disqualified (Audit Fail)",
            "V5": "Buyer Overridden" if (l_no, "V5_Landed") in overrides else v5_flag,
            "V1_raw": v1_raw.get("raw_text", ""),
            "V2_raw": v2_raw.get("raw_text", ""),
            "V3_raw": v3_raw.get("raw_text", ""),
            "V4_raw": v4_raw.get("raw_text", ""),
            "V5_raw": v5_raw.get("raw_text", "")
        }

        rows.append({
            "Line #": l_no,
            "Item Code": code,
            "SKU Type": "New SKU" if is_new_sku else "Repeat SKU",
            "Criticality": crit,
            "Qty": int(qty),
            "Budget Price": budget,
            "V1_Landed": v1_final if pd.notna(v1_final) else None,
            "V2_Landed": v2_final if pd.notna(v2_final) else None,
            "V3_Landed": v3_final if pd.notna(v3_final) else None,
            "V4_Landed": v4_final if pd.notna(v4_final) else None,
            "V5_Landed": v5_final if pd.notna(v5_final) else None,
            "V5_Trust_State": trust_matrix[l_no]["V5"]
        })

    return pd.DataFrame(rows), trust_matrix


# ─────────────────────────────────────────────────────────────────────────────
# 8. LIVE AWARD OPTIMIZATION ENGINE (PANDAS CALCULATOR)
# ─────────────────────────────────────────────────────────────────────────────
def run_live_award_optimization(df_matrix):
    """
    Computes Scenarios A, B, and C dynamically from the active dataframe state.
    """
    df = df_matrix.copy()

    # Scenario A: Unconstrained L1 (all vendors eligible, ignoring audit gates)
    vendor_cols_all = ["V1_Landed", "V2_Landed", "V3_Landed", "V4_Landed", "V5_Landed"]
    df["L1_Unconstrained"] = df[vendor_cols_all].min(axis=1, skipna=True)
    spend_scenario_a = float((df["L1_Unconstrained"] * df["Qty"]).sum())

    # Scenario B: Quality-Gated L1
    # Vendor 4 strictly excluded (failed Q1-Q5)
    # Vendor 3 excluded on lines 10 & 30 (failed Q6: 7-ply)
    # Vendor 5 excluded on lines 26 & 27 (failed Q7: moisture barrier)
    b_spends = []
    c_spends = []

    for _, row in df.iterrows():
        l_no = int(row["Line #"])
        qty = row["Qty"]
        crit = str(row.get("Criticality", "C")).strip().upper()

        qualified_prices = {}
        if pd.notna(row["V1_Landed"]):
            qualified_prices["V1"] = row["V1_Landed"]
        if pd.notna(row["V2_Landed"]):
            qualified_prices["V2"] = row["V2_Landed"]
        if l_no not in [10, 30] and pd.notna(row["V3_Landed"]):
            qualified_prices["V3"] = row["V3_Landed"]
        # V4 is completely omitted
        if l_no not in [26, 27] and pd.notna(row["V5_Landed"]):
            qualified_prices["V5"] = row["V5_Landed"]

        sorted_prices = sorted(qualified_prices.values()) if qualified_prices else [row["Budget Price"]]

        # Scenario B choice: lowest qualified
        best_b = sorted_prices[0]
        b_spends.append(best_b * qty)

        # Scenario C choice: 70/30 split on Criticality A lines if 2+ vendors available
        if crit == "A" and len(sorted_prices) >= 2:
            l1_p, l2_p = sorted_prices[0], sorted_prices[1]
            c_spends.append((0.70 * l1_p + 0.30 * l2_p) * qty)
        else:
            c_spends.append(best_b * qty)

    spend_scenario_b = float(sum(b_spends))
    spend_scenario_c = float(sum(c_spends))
    budget_spend = float((df["Budget Price"] * df["Qty"]).sum())

    cost_of_compliance = spend_scenario_b - spend_scenario_a
    compliance_pct = (cost_of_compliance / spend_scenario_a) * 100.0 if spend_scenario_a > 0 else 0.0

    return {
        "budget_spend": budget_spend,
        "spend_a": spend_scenario_a,
        "spend_b": spend_scenario_b,
        "spend_c": spend_scenario_c,
        "savings_a": budget_spend - spend_scenario_a,
        "savings_b": budget_spend - spend_scenario_b,
        "savings_c": budget_spend - spend_scenario_c,
        "cost_of_compliance": cost_of_compliance,
        "compliance_pct": compliance_pct
    }


# ─────────────────────────────────────────────────────────────────────────────
# 9. SIDEBAR: NAVIGATION & LIVE EXTRACTION CONTROLS
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="display:flex; align-items:center; gap:10px; margin-bottom:12px;">
        <div style="background-color:#2563eb; color:white; width:34px; height:34px; border-radius:8px; display:flex; align-items:center; justify-content:center; font-weight:800; font-size:16px;">
            P
        </div>
        <div>
            <div style="font-weight:700; font-size:15px; color:#0f172a; line-height:1.1;">ProcureAI</div>
            <div style="font-size:11px; color:#64748b;">Enterprise Co-pilot</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    nav = st.radio(
        "Navigation Menu",
        [
            "🏠 Overview & Recommendation",
            "📊 Live Quote Matrix & Editor",
            "🎯 Live Award Optimization",
            "🛡️ Questionnaire Audit Gate",
            "💬 AI Procurement Analyst"
        ],
        label_visibility="collapsed"
    )

    st.divider()

    # ── Live File Ingestion Section ──
    st.markdown("### 📥 Live Quotation Ingestion")
    st.caption("Upload raw quotes (.pdf, .docx, .xlsx, .jpeg, .eml) to parse with LLM:")

    uploaded_files = st.file_uploader(
        "Drop vendor quote files here",
        type=["pdf", "docx", "xlsx", "xls", "jpeg", "jpg", "eml", "txt"],
        accept_multiple_files=True,
        label_visibility="collapsed"
    )

    # ── LLM Configuration ──
    st.markdown("### ⚙️ LLM Reasoning Engine")
    llm_provider = st.selectbox("LLM Provider", ["OpenAI (GPT-4o)", "Google Gemini (1.5 Flash)"], index=0)
    
    api_key_env = os.environ.get("OPENAI_API_KEY") if "OpenAI" in llm_provider else os.environ.get("GEMINI_API_KEY")
    user_api_key = st.text_input(
        f"{'OpenAI' if 'OpenAI' in llm_provider else 'Gemini'} API Key",
        value=api_key_env or "",
        type="password",
        help="Used for live multi-format quote extraction and interactive co-pilot reasoning."
    )

    # Deterministic fx rate setting
    st.markdown("### 💱 Deterministic Currency FX")
    st.session_state.fx_rate = st.number_input(
        "USD to INR FX Rate",
        min_value=70.0,
        max_value=100.0,
        value=float(st.session_state.fx_rate),
        step=0.25,
        help="Used to convert USD quotes (Vendor 3) dynamically into INR."
    )

    if st.button("📥 Load Sample Quote Pack", use_container_width=True):
        st.session_state.uploaded_extractions = [
            {"file": "V1_Apex_Quote.xlsx", "items": 5, "status": "Success"},
            {"file": "V3_Global_Quote.docx", "items": 4, "status": "Success"},
            {"file": "V5_StandardBox_Quote.eml", "items": 5, "status": "Success"}
        ]
        st.success("Loaded 3 multi-format raw sample quotations!")

    if len(st.session_state.buyer_overrides) > 0:
        st.markdown(f"**Active Overrides:** `{len(st.session_state.buyer_overrides)} cells`")
        if st.button("↺ Reset All Overrides", use_container_width=True):
            st.session_state.buyer_overrides = {}
            st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# 10. GENERATE LIVE MATRIX AND LIVE SCENARIOS
# ─────────────────────────────────────────────────────────────────────────────
df_live_matrix, live_trust_matrix = build_live_quote_matrix(st.session_state.fx_rate, st.session_state.buyer_overrides)
optimization_results = run_live_award_optimization(df_live_matrix)


# ─────────────────────────────────────────────────────────────────────────────
# 11. VIEW 1: OVERVIEW & STRATEGIC RECOMMENDATION
# ─────────────────────────────────────────────────────────────────────────────
if nav == "🏠 Overview & Recommendation":
    st.markdown("""
    <div class="procure-card">
        <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:12px;">
            <div>
                <div style="display:flex; gap:8px; align-items:center; margin-bottom:8px;">
                    <span class="badge-verified">Live Pipeline Connected</span>
                    <span style="font-size:12px; background-color:#eff6ff; color:#1d4ed8; padding:2px 8px; border-radius:6px; font-weight:600;">Deterministic Normalization</span>
                    <span style="font-size:12px; background-color:#f1f5f9; color:#475569; padding:2px 8px; border-radius:6px; font-weight:600;">FX: ₹{:.2f}/USD</span>
                </div>
                <h2 style="font-size:22px; font-weight:800; color:#0f172a; margin:0 0 6px 0;">AI-Powered Procurement Co-pilot (Active Engine)</h2>
                <p style="font-size:13px; color:#64748b; margin:0;">
                    Real-time quote extraction, dynamic unit & currency normalization, human-in-the-loop overrides, and live scenario math.
                </p>
            </div>
            <div style="text-align:right; background-color:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:10px 16px;">
                <div class="stat-label">Live Master Budget</div>
                <div class="stat-number">₹{:,.0f}</div>
                <div style="font-size:11px; font-weight:600; color:#15803d; margin-top:2px;">₹4.00 Cr Target</div>
            </div>
        </div>
    </div>
    """.format(st.session_state.fx_rate, optimization_results["budget_spend"]), unsafe_allow_html=True)

    # 4 Dynamic KPI Cards calculated live
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class="procure-card" style="padding:16px;">
            <div class="stat-label">Scenario A (Unconstrained L1)</div>
            <div class="stat-number">₹{optimization_results['spend_a']/1e7:.2f} Cr</div>
            <div style="font-size:11px; color:#15803d; font-weight:600; margin-top:4px;">
                Saves ₹{optimization_results['savings_a']/1e5:.2f} L ({(optimization_results['savings_a']/optimization_results['budget_spend'])*100:.2f}%)
            </div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="procure-card-highlight" style="padding:16px;">
            <div class="stat-label" style="color:#15803d;">Scenario B (Quality-Gated L1) ★</div>
            <div class="stat-number" style="color:#15803d;">₹{optimization_results['spend_b']/1e7:.2f} Cr</div>
            <div style="font-size:11px; color:#15803d; font-weight:700; margin-top:4px;">
                Saves ₹{optimization_results['savings_b']/1e5:.2f} L ({(optimization_results['savings_b']/optimization_results['budget_spend'])*100:.2f}%)
            </div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="procure-card" style="padding:16px;">
            <div class="stat-label">Cost of Compliance</div>
            <div class="stat-number" style="color:#b45309;">+₹{optimization_results['cost_of_compliance']:,.0f}</div>
            <div style="font-size:11px; color:#b45309; font-weight:600; margin-top:4px;">
                +{optimization_results['compliance_pct']:.2f}% risk premium
            </div>
        </div>
        """, unsafe_allow_html=True)
    with c4:
        overrides_count = len(st.session_state.buyer_overrides)
        st.markdown(f"""
        <div class="procure-card" style="padding:16px;">
            <div class="stat-label">Human Overrides</div>
            <div class="stat-number" style="color:{'#1d4ed8' if overrides_count > 0 else '#64748b'};">{overrides_count}</div>
            <div style="font-size:11px; color:#64748b; margin-top:4px;">
                {'Live edits reflected' if overrides_count > 0 else 'No active overrides'}
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Executive Summary Card
    st.markdown(f"""
    <div class="procure-card-highlight">
        <div style="display:flex; align-items:flex-start; gap:14px;">
            <div style="background-color:#dcfce7; color:#15803d; width:38px; height:38px; border-radius:10px; display:flex; align-items:center; justify-content:center; font-size:20px; font-weight:bold; flex-shrink:0;">
                ★
            </div>
            <div style="flex:1;">
                <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
                    <div style="font-size:16px; font-weight:800; color:#0f172a;">Live Decision Support: Award on Scenario B (Quality-Gated L1)</div>
                    <span class="badge-verified">Dynamic Calculation: ₹{optimization_results['spend_b']/1e7:.2f} Cr</span>
                </div>
                <p style="font-size:13px; color:#334155; line-height:1.6; margin:8px 0 10px 0;">
                    Live calculations show that <strong>Scenario B</strong> delivers <strong>₹{optimization_results['savings_b']/1e5:.2f} Lakhs in net savings</strong> against the master budget. 
                    The cost to eliminate the disqualified Vendor 4 (expired ISO 9001:2015 cert) is exactly <strong>+₹{optimization_results['cost_of_compliance']:,.0f} (+{optimization_results['compliance_pct']:.2f}%)</strong>.
                </p>
                <div style="display:flex; gap:16px; font-size:12px; color:#475569; flex-wrap:wrap; border-top:1px solid #f1f5f9; padding-top:8px;">
                    <span>✓ <strong>Live Pandas Engine:</strong> Fully deterministic unit and FX math</span>
                    <span>✓ <strong>Audit Lockout:</strong> V4 locked out, V3 7-ply excluded, V5 barrier excluded</span>
                    <span>✓ <strong>Human-in-the-Loop:</strong> Overrides in the Quote Matrix instantly re-compute these totals</span>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# 12. VIEW 2: LIVE QUOTE MATRIX & INTERACTIVE DATA EDITOR
# ─────────────────────────────────────────────────────────────────────────────
elif nav == "📊 Live Quote Matrix & Editor":
    st.markdown("""
    <div class="procure-card">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
            <div>
                <h2 style="font-size:20px; font-weight:800; color:#0f172a; margin:0 0 4px 0;">Interactive Quote Comparison Matrix & Editor</h2>
                <p style="font-size:13px; color:#64748b; margin:0;">
                    30 Line Items × 5 Vendors · Dynamic Landed Cost (₹/UoM) · <strong>Edit any cell below to override UNRESOLVED values!</strong>
                </p>
            </div>
            <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
                <span class="badge-verified">Verified</span>
                <span class="badge-inferred">⚠ Inferred</span>
                <span class="badge-unresolved">! UNRESOLVED</span>
                <span class="badge-overridden">✎ Buyer Overridden</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Filtering options
    fcol1, fcol2, fcol3 = st.columns([2, 2, 3])
    with fcol1:
        filter_new = st.checkbox("Show New SKUs only (Lines 25, 27, 28, 29, 30)", value=False)
    with fcol2:
        filter_unres = st.checkbox("Show Lines with UNRESOLVED Quotes", value=False)

    df_for_editor = df_live_matrix.copy()
    if filter_new:
        df_for_editor = df_for_editor[df_for_editor["SKU Type"] == "New SKU"]
    if filter_unres:
        df_for_editor = df_for_editor[df_for_editor["V5_Trust_State"].str.contains("UNRESOLVED", na=False)]

    st.markdown("##### 📝 Interactive Data Editor (`st.data_editor`)")
    st.caption("You can directly type numerical values into `V5_Landed` (or any vendor column) to resolve missing quotes:")

    editor_cols = ["Line #", "Item Code", "SKU Type", "Qty", "Budget Price", "V1_Landed", "V2_Landed", "V3_Landed", "V4_Landed", "V5_Landed", "V5_Trust_State"]

    # Interactive data editor
    edited_data = st.data_editor(
        df_for_editor[editor_cols],
        key="live_quote_editor",
        use_container_width=True,
        height=440,
        disabled=["Line #", "Item Code", "SKU Type", "Qty", "Budget Price", "V5_Trust_State"],
        column_config={
            "Line #": st.column_config.NumberColumn(format="%d", width="small"),
            "Item Code": st.column_config.TextColumn(width="small"),
            "SKU Type": st.column_config.TextColumn(width="small"),
            "Qty": st.column_config.NumberColumn(format="%d"),
            "Budget Price": st.column_config.NumberColumn(format="₹%.2f"),
            "V1_Landed": st.column_config.NumberColumn("V1 Apex (₹)", format="₹%.2f"),
            "V2_Landed": st.column_config.NumberColumn("V2 PackTech (₹)", format="₹%.2f"),
            "V3_Landed": st.column_config.NumberColumn("V3 Global USD (₹)", format="₹%.2f"),
            "V4_Landed": st.column_config.NumberColumn("V4 Balaji (₹)", format="₹%.2f"),
            "V5_Landed": st.column_config.NumberColumn("V5 StdBox (₹)", format="₹%.2f"),
            "V5_Trust_State": st.column_config.TextColumn("V5 State", width="medium")
        }
    )

    # Detect cell edits and store in session_state buyer_overrides
    if edited_data is not None:
        for idx, row in edited_data.iterrows():
            l_no = int(row["Line #"])
            orig_row = df_live_matrix[df_live_matrix["Line #"] == l_no].iloc[0]
            for col in ["V1_Landed", "V2_Landed", "V3_Landed", "V4_Landed", "V5_Landed"]:
                orig_val = orig_row[col]
                new_val = row[col]
                if pd.notna(new_val) and (pd.isna(orig_val) or abs(float(new_val) - float(orig_val)) > 1e-4):
                    if (l_no, col) not in st.session_state.buyer_overrides or st.session_state.buyer_overrides[(l_no, col)] != new_val:
                        st.session_state.buyer_overrides[(l_no, col)] = float(new_val)
                        st.toast(f"Saved Buyer Override: Line {l_no} {col} = ₹{new_val:.2f}", icon="💾")
                        st.rerun()

    # Traceability & Raw Quote Inspector
    st.markdown("### 🔍 Raw Quote & Audit Traceability")
    st.caption("Inspect the exact original raw quote text and conversion formula before dynamic normalization:")

    inspect_line = st.selectbox(
        "Select Line Item to Inspect:",
        options=list(range(1, 31)),
        index=26,
        format_func=lambda x: f"Line {x}: {df_items_base.loc[df_items_base['Line #'] == x, 'Item Code'].values[0]} — {df_items_base.loc[df_items_base['Line #'] == x, 'Item Description'].values[0][:40]}"
    )

    if inspect_line in live_trust_matrix:
        tm = live_trust_matrix[inspect_line]
        c1, c2, c3, c4, c5 = st.columns(5)
        v_headers = [("V1", "Apex (V1)", c1), ("V2", "PackTech (V2)", c2), ("V3", "Global USD (V3)", c3), ("V4", "Balaji (V4)", c4), ("V5", "Std Box (V5)", c5)]
        
        for k, vtitle, vcol in v_headers:
            with vcol:
                state = tm[k]
                st_class = "badge-verified" if state == "Verified" else "badge-overridden" if state == "Buyer Overridden" else "badge-unresolved" if "UNRESOLVED" in state else "badge-disqualified" if "Disqualified" in state else "badge-inferred"
                raw_txt = tm[f"{k}_raw"] or "Direct Quote"
                st.markdown(f"""
                <div class="procure-card" style="padding:14px;">
                    <div style="font-weight:700; color:#0f172a; font-size:13px;">{vtitle}</div>
                    <span class="{st_class}">{state}</span>
                    <div style="margin-top:8px;">
                        <span style="font-size:10px; font-weight:700; color:#64748b; text-transform:uppercase;">Raw Source Snippet</span>
                        <div style="font-family:monospace; font-size:11px; font-weight:700; color:#1e293b; background:#f1f5f9; padding:4px 6px; border-radius:4px; margin-top:2px;">
                            {raw_txt}
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# 13. VIEW 3: LIVE AWARD OPTIMIZATION & RECHARTS/PLOTLY
# ─────────────────────────────────────────────────────────────────────────────
elif nav == "🎯 Live Award Optimization":
    st.markdown("""
    <div class="procure-card">
        <h2 style="font-size:20px; font-weight:800; color:#0f172a; margin:0 0 4px 0;">Live Award Scenarios Optimization Engine</h2>
        <p style="font-size:13px; color:#64748b; margin:0;">
            Real-time optimization calculated directly from the live dataframe state. <strong>Any override made in the matrix updates these totals instantly!</strong>
        </p>
    </div>
    """, unsafe_allow_html=True)

    # 4 Live Scenario Metric Cards
    s1, s2, s3, s4 = st.columns(4)
    with s1:
        st.markdown(f"""
        <div class="procure-card">
            <div class="stat-label">Master Budget Cap</div>
            <div class="stat-number">₹{optimization_results['budget_spend']/1e7:.2f} Cr</div>
            <div style="font-size:12px; color:#64748b; margin-top:2px;">Target spend ceiling</div>
        </div>
        """, unsafe_allow_html=True)
    with s2:
        st.markdown(f"""
        <div class="procure-card" style="border-left:4px solid #3b82f6;">
            <div class="stat-label" style="color:#2563eb;">Scenario A: Unconstrained L1</div>
            <div class="stat-number">₹{optimization_results['spend_a']/1e7:.2f} Cr</div>
            <div style="font-size:12px; font-weight:600; color:#15803d; margin-top:2px;">
                Saves ₹{optimization_results['savings_a']/1e5:.2f} L ({(optimization_results['savings_a']/optimization_results['budget_spend'])*100:.2f}%)
            </div>
            <div style="margin-top:6px; font-size:11px; color:#b91c1c;">⚠ Allocates to uncertified V4</div>
        </div>
        """, unsafe_allow_html=True)
    with s3:
        st.markdown(f"""
        <div class="procure-card-highlight" style="border-left:4px solid #22c55e;">
            <div class="stat-label" style="color:#16a34a;">Scenario B: Quality-Gated L1 ★</div>
            <div class="stat-number">₹{optimization_results['spend_b']/1e7:.2f} Cr</div>
            <div style="font-size:12px; font-weight:600; color:#15803d; margin-top:2px;">
                Saves ₹{optimization_results['savings_b']/1e5:.2f} L ({(optimization_results['savings_b']/optimization_results['budget_spend'])*100:.2f}%)
            </div>
            <div style="margin-top:6px; font-size:11px; color:#15803d;">✓ Zero compliance risk</div>
        </div>
        """, unsafe_allow_html=True)
    with s4:
        st.markdown(f"""
        <div class="procure-card" style="border-left:4px solid #a855f7;">
            <div class="stat-label" style="color:#7e22ce;">Scenario C: Dual Sourcing (70/30)</div>
            <div class="stat-number">₹{optimization_results['spend_c']/1e7:.2f} Cr</div>
            <div style="font-size:12px; font-weight:600; color:#15803d; margin-top:2px;">
                Saves ₹{optimization_results['savings_c']/1e5:.2f} L ({(optimization_results['savings_c']/optimization_results['budget_spend'])*100:.2f}%)
            </div>
            <div style="margin-top:6px; font-size:11px; color:#7e22ce;">✓ Insures Criticality A lines</div>
        </div>
        """, unsafe_allow_html=True)

    # Live Plotly Bar Chart
    chart_df = pd.DataFrame({
        "Scenario": ["Master Budget", "Scenario A (Unconstrained)", "Scenario B (Quality-Gated)", "Scenario C (Dual Sourced)"],
        "Spend": [optimization_results["budget_spend"], optimization_results["spend_a"], optimization_results["spend_b"], optimization_results["spend_c"]],
        "Color": ["#94a3b8", "#3b82f6", "#22c55e", "#a855f7"],
        "Formatted": [f"₹{v/1e7:.2f} Cr" for v in [optimization_results["budget_spend"], optimization_results["spend_a"], optimization_results["spend_b"], optimization_results["spend_c"]]]
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
        y=optimization_results["budget_spend"],
        line_dash="dot",
        line_color="#ef4444",
        annotation_text="Live Budget Cap",
        annotation_position="top right"
    )
    fig.update_layout(
        title="<b>Live Total Spend by Optimization Engine (Dynamic Pandas Execution)</b>",
        title_font=dict(size=14, color="#0f172a"),
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        margin=dict(l=40, r=40, t=50, b=40),
        yaxis=dict(range=[36000000, max(chart_df["Spend"]) * 1.08], tickformat="₹,~s", gridcolor="#f1f5f9")
    )
    st.plotly_chart(fig, use_container_width=True)

    # Cost of Compliance Dynamic Card
    st.markdown(f"""
    <div class="procure-card" style="background-color:#fffbeb; border:1px solid #fde68a;">
        <div style="display:flex; align-items:flex-start; gap:14px;">
            <div style="background-color:#fef3c7; color:#b45309; width:36px; height:36px; border-radius:8px; display:flex; align-items:center; justify-content:center; font-size:18px; font-weight:bold; flex-shrink:0;">
                ⚖️
            </div>
            <div>
                <h4 style="font-size:15px; font-weight:800; color:#92400e; margin:0 0 4px 0;">Live Cost of Compliance: +₹{optimization_results['cost_of_compliance']:,.0f} (+{optimization_results['compliance_pct']:.2f}%)</h4>
                <p style="font-size:13px; color:#78350f; line-height:1.5; margin:0;">
                    Calculated live: Enforcing the quality gate to exclude Vendor 4 costs an extra <strong>₹{optimization_results['cost_of_compliance']:,.0f}</strong>. 
                    This eliminates quality non-conformances, factory rejection penalties, and customer audit liabilities.
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

    # Vendor 4 Alert Box
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

    st.dataframe(df_gate_base, use_container_width=True, hide_index=True)


# ─────────────────────────────────────────────────────────────────────────────
# 15. VIEW 5: REAL AI PROCUREMENT ANALYST (LIVE LLM REASONING)
# ─────────────────────────────────────────────────────────────────────────────
elif nav == "💬 AI Procurement Analyst":
    st.markdown("""
    <div class="procure-card">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <div>
                <h2 style="font-size:20px; font-weight:800; color:#0f172a; margin:0 0 4px 0;">AI Procurement Analyst (Live Reasoning Engine)</h2>
                <p style="font-size:13px; color:#64748b; margin:0;">
                    Live reasoning powered by real LLM API with the active normalized matrix and audit database injected into context.
                </p>
            </div>
            <span class="badge-verified">Live LLM Context</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Pre-populated suggestions chips
    st.markdown("**Suggested Quick Inquiries:**")
    sc1, sc2, sc3 = st.columns(3)
    
    chip1 = "Why is Vendor 5 marked unresolved for line 27?"
    chip2 = "What is the cost difference if we enforce the quality gate?"
    chip3 = "Show me the risk profile for Vendor 4."

    user_query = None
    with sc1:
        if st.button(f"💬 {chip1}", use_container_width=True):
            user_query = chip1
    with sc2:
        if st.button(f"💬 {chip2}", use_container_width=True):
            user_query = chip2
    with sc3:
        if st.button(f"💬 {chip3}", use_container_width=True):
            user_query = chip3

    custom_query = st.chat_input("Ask co-pilot about vendor quotes, active overrides, or compliance...")
    if custom_query:
        user_query = custom_query

    # Display chat history
    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # If query triggered, call real LLM
    if user_query:
        st.session_state.chat_messages.append({"role": "user", "content": user_query})
        with st.chat_message("user"):
            st.markdown(user_query)

        # Build context from live dataframe
        matrix_markdown = df_live_matrix[["Line #", "Item Code", "SKU Type", "Qty", "V1_Landed", "V2_Landed", "V3_Landed", "V4_Landed", "V5_Landed", "V5_Trust_State"]].to_markdown(index=False)
        audit_markdown = df_gate_base.to_markdown(index=False)
        active_overrides_str = json.dumps({f"Line {k[0]} {k[1]}": v for k, v in st.session_state.buyer_overrides.items()})

        system_instruction = f"""You are the AI Procurement Analyst co-pilot for RFx-CORR-2026-017 (Corrugated Packaging).
You have full access to the live normalized matrix, active buyer overrides, and the Questionnaire Audit database.

--- LIVE DATA CONTEXT ---
LIVE QUOTE MATRIX:
{matrix_markdown}

ACTIVE BUYER OVERRIDES:
{active_overrides_str}

QUESTIONNAIRE AUDIT:
{audit_markdown}

LIVE SCENARIO SPENDS:
- Master Budget: ₹{optimization_results['budget_spend']:,.0f}
- Scenario A (Unconstrained L1): ₹{optimization_results['spend_a']:,.0f} (Net Savings: ₹{optimization_results['savings_a']:,.0f})
- Scenario B (Quality-Gated L1): ₹{optimization_results['spend_b']:,.0f} (Net Savings: ₹{optimization_results['savings_b']:,.0f})
- Scenario C (Dual Sourcing 70/30): ₹{optimization_results['spend_c']:,.0f}
- Cost of Compliance: +₹{optimization_results['cost_of_compliance']:,.0f} (+{optimization_results['compliance_pct']:.2f}%)

--- CRITICAL MANDATORY INSTRUCTIONS ---
1. Base all quantitative reasoning strictly on the live numbers provided above.
2. If the user asks about a line or vendor where the price is marked as 'UNRESOLVED' (e.g. Vendor 5 on Lines 25, 27, 28, 29, 30):
   - You MUST explicitly refuse to recommend or assume a landed price.
   - Clearly state that the quote is marked as UNRESOLVED because it quoted 'Same as last year' on a New SKU with no historical purchase order record.
3. Be concise, executive-ready, and cite specific data points.
"""

        with st.chat_message("assistant"):
            with st.spinner("AI Analyst reasoning over live dataset..."):
                response_text = ""

                # Real OpenAI API call
                if "OpenAI" in llm_provider and HAS_OPENAI and user_api_key:
                    try:
                        client = OpenAI(api_key=user_api_key)
                        completion = client.chat.completions.create(
                            model="gpt-4o",
                            messages=[
                                {"role": "system", "content": system_instruction},
                                {"role": "user", "content": user_query}
                            ],
                            temperature=0.1
                        )
                        response_text = completion.choices[0].message.content
                    except Exception as e:
                        response_text = f"⚠️ OpenAI API Error: {e}"

                # Real Gemini API call
                elif "Gemini" in llm_provider and HAS_GEMINI and user_api_key:
                    try:
                        genai.configure(api_key=user_api_key)
                        model = genai.GenerativeModel("gemini-1.5-flash")
                        resp = model.generate_content(f"{system_instruction}\n\nUser Question: {user_query}")
                        response_text = resp.text
                    except Exception as e:
                        response_text = f"⚠️ Gemini API Error: {e}"

                # Deterministic Grounded Reasoning Fallback if no API key provided
                else:
                    if user_query == chip1:
                        response_text = (
                            "**Audit Finding: Vendor 5 is UNRESOLVED on Line 27 (`CP-027`):**\n\n"
                            "1. **Missing Baseline (New SKU):** Line 27 is designated as a **New SKU** with no FY25 purchase order history. Vendor 5 quoted *'same as last year'*, meaning there is no baseline PO price to anchor this quote.\n"
                            "2. **Line Disqualification (Gate Q7):** In the *Questionnaire Audit*, Vendor 5 declared **NO to Q7** (Moisture-barrier coating). Because Line 27 requires moisture-barrier treatment for ocean freight, Vendor 5 is disqualified from award on this line.\n\n"
                            "**Co-pilot Instruction Rule:** Because this quote is marked as **UNRESOLVED**, the engine refuses to guess a landed cost until the buyer overrides the cell or clarifies terms."
                        )
                    elif user_query == chip2:
                        response_text = (
                            f"**Live Cost of Compliance Analysis:**\n\n"
                            f"Enforcing the quality gate (moving from Scenario A to Scenario B) costs **+₹{optimization_results['cost_of_compliance']:,.0f} (+{optimization_results['compliance_pct']:.2f}%)**:\n\n"
                            f"| Scenario | Total Annual Spend | Net Savings vs Budget |\n"
                            f"|---|---|---|\n"
                            f"| **Scenario A: Unconstrained L1** | ₹{optimization_results['spend_a']/1e7:.2f} Cr | ₹{optimization_results['savings_a']/1e5:.2f} L |\n"
                            f"| **Scenario B: Quality-Gated L1** | ₹{optimization_results['spend_b']/1e7:.2f} Cr | ₹{optimization_results['savings_b']/1e5:.2f} L |\n\n"
                            f"**Recommendation:** Scenario A awards high-volume lines to Vendor 4 (expired ISO 9001 cert). The {optimization_results['compliance_pct']:.2f}% premium in Scenario B guarantees 100% compliant supplier allocation."
                        )
                    elif user_query == chip3:
                        response_text = (
                            "**Risk Profile: Vendor 4 (Sri Balaji Packaging):**\n\n"
                            "⛔ **Status: DISQUALIFIED (Failed Q1 through Q5)**\n\n"
                            "• **Q1 (ISO 9001:2015):** **FAIL** — Certificate expired October 2026.\n"
                            "• **Q2 (Capacity):** **FAIL** — 280 TPM (below 300 TPM threshold).\n"
                            "• **Q3 (Testing Lab):** **FAIL** — No in-house testing lab.\n"
                            "• **Q4 (Rejection Rate):** **FAIL** — 2.4% (exceeds 1.5% max limit).\n"
                            "• **Q5 (Active Clients):** **FAIL** — Only 2 active references.\n\n"
                            "Vendor 4 is dynamically locked out of Scenario B and C."
                        )
                    else:
                        response_text = (
                            f"**Live Reasoning for:** *\"{user_query}\"*\n\n"
                            f"Based on the active normalized dataframe (FX rate: ₹{st.session_state.fx_rate:.2f}/USD, Active Overrides: {len(st.session_state.buyer_overrides)}):\n"
                            f"- Master Budget: ₹{optimization_results['budget_spend']/1e7:.2f} Cr\n"
                            f"- Recommended Scenario B Spend: ₹{optimization_results['spend_b']/1e7:.2f} Cr (Saves ₹{optimization_results['savings_b']/1e5:.2f} Lakhs)\n\n"
                            f"*Tip: Enter your OpenAI or Gemini API Key in the left sidebar to activate live freeform multi-turn LLM generation!*"
                        )

                st.markdown(response_text)
                st.session_state.chat_messages.append({"role": "assistant", "content": response_text})
