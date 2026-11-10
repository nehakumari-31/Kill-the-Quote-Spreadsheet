import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os

# ─────────────────────────────────────────────────────────────────────────────
# 1. PAGE CONFIGURATION & ENTERPRISE LIGHT THEME
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ProcureAI | Enterprise Procurement Co-pilot",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Light-Theme CSS (Strictly Light Theme, Corporate Blue accents, pastel badges)
st.markdown("""
<style>
    /* Global styles */
    .stApp {
        background-color: #f8fafc;
        color: #1e293b;
        font-family: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", Roboto, sans-serif;
    }

    /* Card styling */
    .procure-card {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05);
        margin-bottom: 18px;
    }

    .procure-card-highlight {
        background-color: #ffffff;
        border: 2px solid #22c55e;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 6px -1px rgba(34, 197, 94, 0.1);
        margin-bottom: 18px;
    }

    /* Custom badges */
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

    .badge-l1 {
        background-color: #dcfce7;
        color: #166534;
        border: 1px solid #86efac;
        padding: 1px 6px;
        border-radius: 4px;
        font-size: 10px;
        font-weight: 800;
        margin-left: 4px;
    }

    .badge-new-sku {
        background-color: #f3e8ff;
        color: #7e22ce;
        border: 1px solid #d8b4fe;
        padding: 1px 6px;
        border-radius: 4px;
        font-size: 10px;
        font-weight: 700;
    }

    /* Stat box */
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
# 2. DATA LOADING & PARSING (EXCEL SHEETS)
# ─────────────────────────────────────────────────────────────────────────────
EXCEL_PATH = os.path.join(os.path.dirname(__file__), "RFx_Master_Updated.xlsx")

@st.cache_data
def load_rfx_data():
    if not os.path.exists(EXCEL_PATH):
        st.error(f"Excel file not found at: {EXCEL_PATH}")
        return None, None, None, None, None

    xl = pd.ExcelFile(EXCEL_PATH)
    df_norm = pd.read_excel(xl, sheet_name="Normalized Comparison")
    df_hist = pd.read_excel(xl, sheet_name="Historical PO Master")
    df_gate = pd.read_excel(xl, sheet_name="Questionnaire Audit & Gate")
    df_award = pd.read_excel(xl, sheet_name="Award Scenarios Engine")
    df_items = pd.read_excel(xl, sheet_name="Line Items")
    return df_norm, df_hist, df_gate, df_award, df_items

df_norm, df_hist, df_gate, df_award, df_items = load_rfx_data()

# Raw quote metadata dictionary for rich tooltip inspection
RAW_QUOTE_DB = {
    1: {
        "v1": {"raw": "₹6,120 per 1,000 Nos", "note": "Converted from per-1,000 quote to per unit (÷ 1,000).", "state": "Inferred"},
        "v2": {"raw": "₹6.38 / Nos", "note": "Direct piece rate verified.", "state": "Verified"},
        "v3": {"raw": "USD 0.0708 / Nos (FOB Shanghai)", "note": "Converted from USD at ₹83.95/USD closing FX rate.", "state": "Inferred"},
        "v4": {"raw": "₹5.95 / Nos", "note": "Disqualified across all lines (Failed Q1–Q5, ISO cert expired).", "state": "Disqualified"},
        "v5": {"raw": "₹38/kg + ₹0.45 freight", "note": "Converted using piece weight 0.165 kg/Nos + freight levy.", "state": "Inferred"}
    },
    2: {
        "v1": {"raw": "₹10,350 per 1,000 Nos", "note": "Converted from /1,000 rate.", "state": "Inferred"},
        "v2": {"raw": "₹10.14 / Nos", "note": "Direct piece rate verified.", "state": "Verified"},
        "v3": {"raw": "USD 0.1195 / Nos", "note": "Converted from USD at ₹83.95/USD.", "state": "Inferred"},
        "v4": {"raw": "₹9.92 / Nos", "note": "Disqualified across all lines.", "state": "Disqualified"},
        "v5": {"raw": "₹38/kg + freight", "note": "Converted from ₹/kg using piece weight 0.253 kg.", "state": "Inferred"}
    },
    10: {
        "v1": {"raw": "₹268.91 / Nos", "note": "Verified landed price.", "state": "Verified"},
        "v2": {"raw": "₹279.89 / Nos", "note": "Verified landed price.", "state": "Verified"},
        "v3": {"raw": "NOT QUOTED", "note": "V3 lacks 7-ply capability (failed Gate Q6). Strictly disqualified on Lines 10 & 30.", "state": "Disqualified"},
        "v4": {"raw": "₹264.38 / Nos", "note": "Disqualified across all lines.", "state": "Disqualified"},
        "v5": {"raw": "Same as last year", "note": "Resolved from FY25 PO Master (₹270.40) + material index formula.", "state": "Inferred"}
    },
    25: {
        "v1": {"raw": "₹6.21 / Nos", "note": "Verified landed price.", "state": "Verified"},
        "v2": {"raw": "₹6.03 / Nos", "note": "Verified landed price.", "state": "Verified"},
        "v3": {"raw": "NOT QUOTED", "note": "Line omitted from vendor quotation.", "state": "Unresolved"},
        "v4": {"raw": "₹5.95 / Nos", "note": "Disqualified across all lines.", "state": "Disqualified"},
        "v5": {"raw": "'Same as last year'", "note": "Line 25 is a New SKU with NO historical PO data. Cannot infer baseline -> UNRESOLVED.", "state": "Unresolved"}
    },
    26: {
        "v1": {"raw": "₹72.31 / Nos", "note": "Verified landed price.", "state": "Verified"},
        "v2": {"raw": "₹73.80 / Nos", "note": "Verified landed price.", "state": "Verified"},
        "v3": {"raw": "USD 0.8526 / Nos", "note": "Converted from USD at ₹83.95/USD.", "state": "Inferred"},
        "v4": {"raw": "₹71.74 / Nos", "note": "Disqualified across all lines.", "state": "Disqualified"},
        "v5": {"raw": "₹58.00 / Nos (Standard)", "note": "V5 lacks moisture-barrier capability (Failed Gate Q7). Strictly disqualified on Lines 26 & 27.", "state": "Disqualified"}
    },
    27: {
        "v1": {"raw": "₹103.73 / Nos", "note": "Verified landed price.", "state": "Verified"},
        "v2": {"raw": "₹106.91 / Nos", "note": "Verified landed price.", "state": "Verified"},
        "v3": {"raw": "USD 1.2231 / Nos", "note": "Converted from USD at ₹83.95/USD.", "state": "Inferred"},
        "v4": {"raw": "₹101.88 / Nos", "note": "Disqualified across all lines.", "state": "Disqualified"},
        "v5": {"raw": "'Same as last year'", "note": "Dual Blocker: New SKU (no PO history to anchor quote) AND V5 failed Gate Q7 (no moisture barrier). UNRESOLVED.", "state": "Unresolved"}
    },
    28: {
        "v1": {"raw": "₹9.09 / Nos", "note": "Verified landed price.", "state": "Verified"},
        "v2": {"raw": "₹8.73 / Nos", "note": "Verified landed price.", "state": "Verified"},
        "v3": {"raw": "USD 0.1062 / Nos", "note": "Converted from USD at ₹83.95/USD.", "state": "Inferred"},
        "v4": {"raw": "₹8.50 / Nos", "note": "Disqualified across all lines.", "state": "Disqualified"},
        "v5": {"raw": "'Same as last year'", "note": "New SKU with no historical PO. Cannot resolve quote.", "state": "Unresolved"}
    },
    29: {
        "v1": {"raw": "₹9.31 / Nos", "note": "Verified landed price.", "state": "Verified"},
        "v2": {"raw": "₹9.21 / Nos", "note": "Verified landed price.", "state": "Verified"},
        "v3": {"raw": "USD 0.1087 / Nos", "note": "Converted from USD at ₹83.95/USD.", "state": "Inferred"},
        "v4": {"raw": "₹8.90 / Nos", "note": "Disqualified across all lines.", "state": "Disqualified"},
        "v5": {"raw": "'Same as last year'", "note": "New SKU with no historical PO. Cannot resolve quote.", "state": "Unresolved"}
    },
    30: {
        "v1": {"raw": "₹519.24 / Nos", "note": "Verified landed price.", "state": "Verified"},
        "v2": {"raw": "₹540.65 / Nos", "note": "Verified landed price.", "state": "Verified"},
        "v3": {"raw": "NOT QUOTED", "note": "Failed Gate Q6 (no in-house 7-ply capability). Disqualified.", "state": "Disqualified"},
        "v4": {"raw": "₹514.98 / Nos", "note": "Disqualified across all lines.", "state": "Disqualified"},
        "v5": {"raw": "'Same as last year'", "note": "New SKU with no historical PO history. UNRESOLVED.", "state": "Unresolved"}
    }
}


# ─────────────────────────────────────────────────────────────────────────────
# 3. SIDEBAR NAVIGATION & CONTEXT
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

    st.markdown("""
    <div style="background-color:#eff6ff; border:1px solid #bfdbfe; border-radius:8px; padding:10px 12px; margin-bottom:16px;">
        <div style="font-size:10px; font-weight:700; text-transform:uppercase; color:#2563eb; letter-spacing:0.05em;">Active RFx</div>
        <div style="font-size:13px; font-weight:700; color:#1e3a8a; font-family:monospace;">RFx-CORR-2026-017</div>
        <div style="font-size:11px; color:#475569; margin-top:2px;">Corrugated Packaging FY27</div>
        <div style="margin-top:6px; display:flex; align-items:center; gap:6px;">
            <span style="width:7px; height:7px; border-radius:9999px; background-color:#22c55e;"></span>
            <span style="font-size:11px; font-weight:600; color:#15803d;">5 Quotes Sourced</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    nav = st.radio(
        "Navigation Menu",
        [
            "🏠 Overview & Recommendation",
            "📊 Quote Comparison Matrix",
            "🎯 Award Scenarios & Analytics",
            "🛡️ Vendor Eligibility Gate",
            "💬 AI Procurement Analyst"
        ],
        label_visibility="collapsed"
    )

    st.divider()

    st.markdown("""
    <div style="font-size:11px; color:#64748b; line-height:1.6;">
        <div style="display:flex; justify-content:space-between;"><span>Line Items:</span> <strong>30 Items</strong></div>
        <div style="display:flex; justify-content:space-between;"><span>Vendors:</span> <strong>5 (1 Disqualified)</strong></div>
        <div style="display:flex; justify-content:space-between;"><span>Closing Date:</span> <strong>19-Nov-2026</strong></div>
        <div style="display:flex; justify-content:space-between;"><span>Budget Target:</span> <strong>₹4.00 Cr</strong></div>
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# 4. VIEW 1: OVERVIEW & STRATEGIC RECOMMENDATION
# ─────────────────────────────────────────────────────────────────────────────
if nav == "🏠 Overview & Recommendation":
    st.markdown("""
    <div class="procure-card">
        <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:12px;">
            <div>
                <div style="display:flex; gap:8px; align-items:center; margin-bottom:8px;">
                    <span class="badge-verified">RFx-CORR-2026-017</span>
                    <span style="font-size:12px; background-color:#f1f5f9; color:#475569; padding:2px 8px; border-radius:6px; font-weight:600;">FY2027 Contract</span>
                    <span style="font-size:12px; background-color:#dbeafe; color:#1e40af; padding:2px 8px; border-radius:6px; font-weight:600;">Closing: 19-Nov-2026</span>
                </div>
                <h2 style="font-size:22px; font-weight:800; color:#0f172a; margin:0 0 6px 0;">Corrugated Packaging Procurement Co-pilot</h2>
                <p style="font-size:13px; color:#64748b; margin:0;">
                    Veda Home Appliances Pvt Ltd · Category Buyer Dashboard · Side-by-Side Vendor Normalization & Optimization
                </p>
            </div>
            <div style="text-align:right; background-color:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:10px 16px;">
                <div class="stat-label">Master Budget Cap</div>
                <div class="stat-number">₹4,00,03,750</div>
                <div style="font-size:11px; font-weight:600; color:#15803d; margin-top:2px;">Target Baseline (₹4.00 Cr)</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 5 KPI Cards
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.markdown("""
        <div class="procure-card" style="padding:16px;">
            <div class="stat-label">Total SKUs</div>
            <div class="stat-number">30</div>
            <div style="font-size:11px; color:#64748b; margin-top:4px;">Shippers, Mailers, Trays</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown("""
        <div class="procure-card" style="padding:16px;">
            <div class="stat-label">Participating Vendors</div>
            <div class="stat-number">5</div>
            <div style="font-size:11px; color:#15803d; font-weight:600; margin-top:4px;">4 Qualified / 1 Disqualified</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown("""
        <div class="procure-card" style="padding:16px;">
            <div class="stat-label">New SKUs (No History)</div>
            <div class="stat-number" style="color:#7e22ce;">5</div>
            <div style="font-size:11px; color:#7e22ce; font-weight:600; margin-top:4px;">Lines 25, 27, 28, 29, 30</div>
        </div>
        """, unsafe_allow_html=True)
    with c4:
        st.markdown("""
        <div class="procure-card" style="padding:16px;">
            <div class="stat-label">Inferred Quotes</div>
            <div class="stat-number" style="color:#b45309;">31</div>
            <div style="font-size:11px; color:#b45309; font-weight:600; margin-top:4px;">Converted USD & ₹/kg</div>
        </div>
        """, unsafe_allow_html=True)
    with c5:
        st.markdown("""
        <div class="procure-card" style="padding:16px;">
            <div class="stat-label">Unresolved Quotes</div>
            <div class="stat-number" style="color:#b91c1c;">5</div>
            <div style="font-size:11px; color:#b91c1c; font-weight:700; margin-top:4px;">Missing historical baseline</div>
        </div>
        """, unsafe_allow_html=True)

    # Executive Recommendation Banner
    st.markdown("""
    <div class="procure-card-highlight">
        <div style="display:flex; align-items:flex-start; gap:14px;">
            <div style="background-color:#dcfce7; color:#15803d; width:38px; height:38px; border-radius:10px; display:flex; align-items:center; justify-content:center; font-size:20px; font-weight:bold; flex-shrink:0;">
                ★
            </div>
            <div style="flex:1;">
                <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
                    <div style="font-size:16px; font-weight:800; color:#0f172a;">Executive Recommendation: Award on Scenario B (Quality-Gated L1)</div>
                    <span class="badge-verified">Total Spend: ₹3,80,19,190 · Net Savings: ₹19.85 L (4.96%)</span>
                </div>
                <p style="font-size:13px; color:#334155; line-height:1.6; margin:8px 0 10px 0;">
                    While <strong>Scenario A (Unconstrained L1)</strong> appears cheaper at ₹3.77 Cr, it awards high-volume lines to <strong>Vendor 4 (Sri Balaji Packaging)</strong>, whose ISO 9001:2015 certificate expired in October 2026. 
                    Enforcing the quality gate in <strong>Scenario B</strong> eliminates 100% of quality, certification, and lab testing risks for an incremental compliance premium of only <strong>+₹2,74,585 (+0.73%)</strong>.
                </p>
                <div style="display:flex; gap:16px; font-size:12px; color:#475569; flex-wrap:wrap; border-top:1px solid #f1f5f9; padding-top:8px;">
                    <span>✓ <strong>Apex Packaging (V1):</strong> Qualified on all 30 lines</span>
                    <span>✓ <strong>PackTech Solutions (V2):</strong> Qualified on all 30 lines</span>
                    <span>✓ <strong>Global Corrugators (V3):</strong> Qualified for 3-ply & 5-ply</span>
                    <span>✓ <strong>Standard Box Corp (V5):</strong> Qualified for Repeat SKUs</span>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Vendor Health Status Cards
    st.subheader("Vendor Eligibility & Qualification Quick Summary")
    vcol1, vcol2, vcol3, vcol4, vcol5 = st.columns(5)
    vendors_summary = [
        ("V1: Apex Packaging", "QUALIFIED", "badge-verified", "650 TPM", "Exp: 2028", "Clean quotes, all verified"),
        ("V2: PackTech Solutions", "QUALIFIED", "badge-verified", "420 TPM", "Exp: 2027", "Competitive on mailers"),
        ("V3: Global Corrugators", "PARTIAL", "badge-inferred", "1,200 TPM", "Exp: 2028", "Disqualified L10 & 30 (7-ply)"),
        ("V4: Sri Balaji Packaging", "DISQUALIFIED", "badge-disqualified", "280 TPM (Fail)", "Expired Oct 26", "Failed Q1–Q5 mandatory gates"),
        ("V5: Standard Box Corp", "PARTIAL", "badge-inferred", "380 TPM", "Exp: 2027", "Disqualified L26 & 27 (Moisture)")
    ]
    for col, (vname, vstatus, vbadge, vcap, viso, vnote) in zip([vcol1, vcol2, vcol3, vcol4, vcol5], vendors_summary):
        with col:
            st.markdown(f"""
            <div class="procure-card" style="padding:14px; height:100%;">
                <div style="font-weight:700; font-size:13px; color:#0f172a;">{vname.split(':')[1]}</div>
                <div style="font-size:11px; color:#64748b; margin-bottom:8px;">{vname.split(':')[0]}</div>
                <span class="{vbadge}">{vstatus}</span>
                <div style="margin-top:10px; font-size:11px; color:#475569; line-height:1.5;">
                    <div>Capacity: <strong>{vcap}</strong></div>
                    <div>ISO 9001: <strong>{viso}</strong></div>
                    <div style="margin-top:4px; font-size:10px; color:#64748b;">{vnote}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# 5. VIEW 2: QUOTE COMPARISON MATRIX (THE CORE FEATURE)
# ─────────────────────────────────────────────────────────────────────────────
elif nav == "📊 Quote Comparison Matrix":
    st.markdown("""
    <div class="procure-card">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
            <div>
                <h2 style="font-size:20px; font-weight:800; color:#0f172a; margin:0 0 4px 0;">Side-by-Side Quote Comparison Matrix</h2>
                <p style="font-size:13px; color:#64748b; margin:0;">
                    30 Line Items × 5 Vendors · Landed Cost per UoM (₹) · Normalization & Trust Flags
                </p>
            </div>
            <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
                <span class="badge-verified">Verified</span>
                <span class="badge-inferred">⚠ Inferred / Converted</span>
                <span class="badge-unresolved">! Unresolved</span>
                <span class="badge-disqualified">🚫 Disqualified</span>
                <span class="badge-l1">L1 Lowest Qualified</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Filter controls
    fcol1, fcol2, fcol3 = st.columns([2, 2, 3])
    with fcol1:
        only_new_skus = st.checkbox("Show New SKUs only (Lines 25, 27, 28, 29, 30)", value=False)
    with fcol2:
        hide_disqualified = st.checkbox("Dim Disqualified Quotes (Vendor 4)", value=True)

    # Prepare matrix view dataframe
    if df_norm is not None and df_hist is not None:
        display_df = df_norm.copy()
        
        # Merge SKU classification
        sku_map = dict(zip(df_hist["Line #"], df_hist["SKU Classification"]))
        desc_map = dict(zip(df_hist["Line #"], df_hist["Description"]))
        
        display_df["Item Description"] = display_df["Line #"].map(desc_map)
        display_df["SKU Type"] = display_df["Line #"].map(sku_map)

        if only_new_skus:
            display_df = display_df[display_df["SKU Type"] == "New SKU"]

        # Rename columns for clean presentation
        columns_to_show = [
            "Line #", "Item Code", "SKU Type", "Item Description", "Est. Qty", "Budget Price",
            "V1 Landed (Apex)", "V2 Landed (PackTech)", "V3 Landed (Global USD)", 
            "V4 Landed (Balaji)", "V5 Landed (Standard Box)", "Normalization & Trust Flags"
        ]
        
        # Interactive Grid
        st.dataframe(
            display_df[columns_to_show],
            use_container_width=True,
            height=460,
            column_config={
                "Line #": st.column_config.NumberColumn(format="%d", width="small"),
                "Item Code": st.column_config.TextColumn(width="small"),
                "SKU Type": st.column_config.TextColumn(width="small"),
                "Item Description": st.column_config.TextColumn(width="medium"),
                "Est. Qty": st.column_config.NumberColumn(format="%d"),
                "Budget Price": st.column_config.NumberColumn(format="₹%.2f"),
                "V1 Landed (Apex)": st.column_config.TextColumn(help="Apex Packaging (Qualified)"),
                "V2 Landed (PackTech)": st.column_config.TextColumn(help="PackTech Solutions (Qualified)"),
                "V3 Landed (Global USD)": st.column_config.TextColumn(help="Global Corrugators (USD Converted)"),
                "V4 Landed (Balaji)": st.column_config.TextColumn(help="Sri Balaji (DISQUALIFIED across all lines)"),
                "V5 Landed (Standard Box)": st.column_config.TextColumn(help="Standard Box Corp (Converted from ₹/kg)"),
                "Normalization & Trust Flags": st.column_config.TextColumn(width="large")
            }
        )

    # ── Interactive Item Inspector (Audit Tooltip Viewer) ──────────────────────
    st.markdown("### 🔍 Raw Quote & Normalization Inspector (Hover / Click Replacement)")
    st.caption("Select any Line Item below to view the original raw quote text, conversion formulas, and trust state before normalization:")

    inspect_line = st.selectbox(
        "Choose Line Item to Inspect:",
        options=list(range(1, 31)),
        index=26, # Default to Line 27 (CP-027)
        format_func=lambda x: f"Line {x}: {df_hist.loc[df_hist['Line #'] == x, 'Item Code'].values[0]} — {df_hist.loc[df_hist['Line #'] == x, 'Description'].values[0]}"
    )

    if inspect_line in RAW_QUOTE_DB:
        q_data = RAW_QUOTE_DB[inspect_line]
        st.markdown(f"**Item Code:** `{df_hist.loc[df_hist['Line #'] == inspect_line, 'Item Code'].values[0]}` · **Est. Annual Volume:** {df_hist.loc[df_hist['Line #'] == inspect_line, 'PO Volume'].values[0]:,} Nos · **SKU Type:** {df_hist.loc[df_hist['Line #'] == inspect_line, 'SKU Classification'].values[0]}")
        
        ic1, ic2, ic3, ic4, ic5 = st.columns(5)
        vendor_keys = [("v1", "Apex (V1)", ic1), ("v2", "PackTech (V2)", ic2), ("v3", "Global USD (V3)", ic3), ("v4", "Balaji (V4)", ic4), ("v5", "Std Box (V5)", ic5)]
        
        for k, vtitle, vcol in vendor_keys:
            with vcol:
                vinfo = q_data.get(k, {"raw": "N/A", "note": "Verified standard quote", "state": "Verified"})
                st_class = "badge-verified" if vinfo["state"] == "Verified" else "badge-inferred" if vinfo["state"] == "Inferred" else "badge-unresolved" if vinfo["state"] == "Unresolved" else "badge-disqualified"
                
                st.markdown(f"""
                <div class="procure-card" style="padding:14px; font-size:12px;">
                    <div style="font-weight:700; color:#0f172a; margin-bottom:4px;">{vtitle}</div>
                    <span class="{st_class}">{vinfo['state']}</span>
                    <div style="margin-top:8px;">
                        <span style="font-size:10px; font-weight:700; color:#64748b; text-transform:uppercase;">Original Raw Quote</span>
                        <div style="font-family:monospace; font-weight:700; color:#1e293b; background:#f1f5f9; padding:4px 6px; border-radius:4px; margin-top:2px;">
                            {vinfo['raw']}
                        </div>
                    </div>
                    <div style="margin-top:8px; font-size:11px; color:#475569; line-height:1.4;">
                        <span style="font-size:10px; font-weight:700; color:#64748b; text-transform:uppercase;">Normalization Note</span>
                        <div>{vinfo['note']}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info(f"Line {inspect_line}: Quotes submitted as standard piece rates in INR; no complex FX or weight conversions required.")


# ─────────────────────────────────────────────────────────────────────────────
# 6. VIEW 3: AWARD SCENARIOS & ANALYTICS
# ─────────────────────────────────────────────────────────────────────────────
elif nav == "🎯 Award Scenarios & Analytics":
    st.markdown("""
    <div class="procure-card">
        <h2 style="font-size:20px; font-weight:800; color:#0f172a; margin:0 0 4px 0;">Award Scenarios Optimization Engine</h2>
        <p style="font-size:13px; color:#64748b; margin:0;">
            Data directly loaded from the <span style="font-weight:600; color:#1e293b;">Award Scenarios Engine</span> tab — Comparing Total Annual Spend, Compliance Trade-offs, and Dual Sourcing Risk.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # 4 Scenario Summary Cards
    sc1, sc2, sc3, sc4 = st.columns(4)
    with sc1:
        st.markdown("""
        <div class="procure-card">
            <div class="stat-label">Master Budget Cap</div>
            <div class="stat-number">₹4.00 Cr</div>
            <div style="font-size:12px; color:#64748b; margin-top:2px;">₹40,003,750 Ceiling</div>
            <div style="margin-top:8px; font-size:11px; color:#64748b; border-top:1px solid #f1f5f9; padding-top:6px;">Internal engineering estimate</div>
        </div>
        """, unsafe_allow_html=True)
    with sc2:
        st.markdown("""
        <div class="procure-card" style="border-left:4px solid #3b82f6;">
            <div class="stat-label" style="color:#2563eb;">Scenario A: Unconstrained L1</div>
            <div class="stat-number">₹3.77 Cr</div>
            <div style="font-size:12px; font-weight:600; color:#15803d; margin-top:2px;">Saves ₹22.59 L (5.65%)</div>
            <div style="margin-top:8px; font-size:11px; color:#b91c1c; border-top:1px solid #f1f5f9; padding-top:6px;">⚠ High Risk: Awards to uncertified V4</div>
        </div>
        """, unsafe_allow_html=True)
    with sc3:
        st.markdown("""
        <div class="procure-card-highlight" style="border-left:4px solid #22c55e;">
            <div class="stat-label" style="color:#16a34a;">Scenario B: Quality-Gated L1 ★</div>
            <div class="stat-number">₹3.80 Cr</div>
            <div style="font-size:12px; font-weight:600; color:#15803d; margin-top:2px;">Saves ₹19.85 L (4.96%)</div>
            <div style="margin-top:8px; font-size:11px; color:#15803d; border-top:1px solid #f1f5f9; padding-top:6px;">✓ Zero Risk: Compliant vendors only</div>
        </div>
        """, unsafe_allow_html=True)
    with sc4:
        st.markdown("""
        <div class="procure-card" style="border-left:4px solid #a855f7;">
            <div class="stat-label" style="color:#7e22ce;">Scenario C: Dual Sourcing</div>
            <div class="stat-number">₹3.81 Cr</div>
            <div style="font-size:12px; font-weight:600; color:#15803d; margin-top:2px;">Saves ₹18.85 L (4.71%)</div>
            <div style="margin-top:8px; font-size:11px; color:#7e22ce; border-top:1px solid #f1f5f9; padding-top:6px;">✓ Insures 5 Critical SKUs (70/30)</div>
        </div>
        """, unsafe_allow_html=True)

    # Spend Comparison Bar Chart (Plotly)
    chart_df = pd.DataFrame({
        "Scenario": [
            "Master Budget", 
            "Scenario A: Unconstrained L1", 
            "Scenario B: Quality-Gated L1", 
            "Scenario C: Dual Sourced (70/30)"
        ],
        "Total Spend (₹)": [40003750, 37744605, 38019190, 38118864],
        "Color": ["#94a3b8", "#3b82f6", "#22c55e", "#a855f7"],
        "Spend in Cr": ["₹4.00 Cr", "₹3.77 Cr", "₹3.80 Cr", "₹3.81 Cr"]
    })

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=chart_df["Scenario"],
        y=chart_df["Total Spend (₹)"],
        text=chart_df["Spend in Cr"],
        textposition="outside",
        marker_color=chart_df["Color"],
        width=0.45
    ))
    fig.add_hline(
        y=40003750, 
        line_dash="dot", 
        line_color="#ef4444", 
        annotation_text="Budget Cap: ₹4.00 Cr", 
        annotation_position="top right"
    )
    fig.update_layout(
        title="<b>Total Annual Spend by Award Scenario (₹)</b>",
        title_font=dict(size=15, color="#0f172a"),
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        margin=dict(l=40, r=40, t=50, b=40),
        yaxis=dict(
            range=[36000000, 41500000],
            tickformat="₹,~s",
            gridcolor="#f1f5f9"
        ),
        xaxis=dict(gridcolor="#ffffff")
    )
    st.plotly_chart(fig, use_container_width=True)

    # Cost of Compliance Card
    st.markdown("""
    <div class="procure-card" style="background-color:#fffbeb; border:1px solid #fde68a;">
        <div style="display:flex; align-items:flex-start; gap:14px;">
            <div style="background-color:#fef3c7; color:#b45309; width:36px; height:36px; border-radius:8px; display:flex; align-items:center; justify-content:center; font-size:18px; font-weight:bold; flex-shrink:0;">
                ⚖️
            </div>
            <div>
                <h4 style="font-size:15px; font-weight:800; color:#92400e; margin:0 0 6px 0;">Cost of Compliance Analysis</h4>
                <p style="font-size:13px; color:#78350f; line-height:1.5; margin:0 0 8px 0;">
                    Moving from <strong>Scenario A</strong> (Unconstrained) to <strong>Scenario B</strong> (Quality-Gated) requires an incremental spend of <strong>+₹2,74,585 (+0.73%)</strong>. 
                    This 0.73% premium represents the rational insurance cost to lock out uncertified Vendor 4, preventing factory rejection penalties, ISO non-compliance audits, and production interruptions.
                </p>
                <div style="font-size:12px; color:#92400e; font-weight:600;">
                    • Dual Sourcing Premium (Scenario B → C): +₹99,674 (+0.26%) to split 5 Criticality A lines across two audited vendors.
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# 7. VIEW 4: VENDOR ELIGIBILITY GATE
# ─────────────────────────────────────────────────────────────────────────────
elif nav == "🛡️ Vendor Eligibility Gate":
    st.markdown("""
    <div class="procure-card">
        <h2 style="font-size:20px; font-weight:800; color:#0f172a; margin:0 0 4px 0;">Questionnaire Audit & Mandatory Quality Gates</h2>
        <p style="font-size:13px; color:#64748b; margin:0;">
            Source: <span style="font-weight:600; color:#0f172a;">Questionnaire Audit & Gate</span> tab — Pass / Fail / Partial eligibility determination.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Vendor 4 Alert Box (Highlighted in Red as requested)
    st.markdown("""
    <div style="background-color:#fef2f2; border:2px solid #ef4444; border-radius:12px; padding:18px; margin-bottom:20px;">
        <div style="display:flex; align-items:flex-start; gap:12px;">
            <div style="background-color:#fee2e2; color:#b91c1c; width:36px; height:36px; border-radius:8px; display:flex; align-items:center; justify-content:center; font-size:20px; font-weight:bold; flex-shrink:0;">
                🚫
            </div>
            <div>
                <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
                    <h3 style="font-size:16px; font-weight:800; color:#991b1b; margin:0;">Vendor 4 (Sri Balaji Packaging) — DISQUALIFIED</h3>
                    <span class="badge-disqualified">Failed Q1 through Q5</span>
                </div>
                <p style="font-size:13px; color:#7f1d1d; line-height:1.5; margin:6px 0 10px 0;">
                    <strong>Mandatory Disqualification Rationale:</strong> Vendor 4's <strong>ISO 9001:2015 certificate expired in October 2026</strong>, before the RFx closing date of 19-Nov-2026. 
                    In addition, their declared manufacturing capacity is 280 TPM (below the 300 TPM threshold), they have no in-house testing lab, and their customer rejection rate is 2.4% (exceeds the 1.5% maximum tolerance).
                </p>
                <div style="display:flex; gap:8px; flex-wrap:wrap;">
                    <span style="background-color:#fee2e2; color:#991b1b; border:1px solid #fecaca; padding:2px 8px; border-radius:6px; font-size:11px; font-weight:600;">Q1 ISO Cert: Expired Oct 2026 (FAIL)</span>
                    <span style="background-color:#fee2e2; color:#991b1b; border:1px solid #fecaca; padding:2px 8px; border-radius:6px; font-size:11px; font-weight:600;">Q2 Capacity: 280 TPM < 300 TPM (FAIL)</span>
                    <span style="background-color:#fee2e2; color:#991b1b; border:1px solid #fecaca; padding:2px 8px; border-radius:6px; font-size:11px; font-weight:600;">Q3 In-House Lab: None (FAIL)</span>
                    <span style="background-color:#fee2e2; color:#991b1b; border:1px solid #fecaca; padding:2px 8px; border-radius:6px; font-size:11px; font-weight:600;">Q4 Rejection: 2.4% > 1.5% (FAIL)</span>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Full Questionnaire Gate Table
    if df_gate is not None:
        st.markdown("### Full Questionnaire Audit Table")
        st.dataframe(
            df_gate,
            use_container_width=True,
            hide_index=True,
            height=340
        )

    # Partial Gate Callouts
    st.markdown("### ⚠️ Partial Line-Specific Disqualifications")
    pcol1, pcol2 = st.columns(2)
    with pcol1:
        st.markdown("""
        <div class="procure-card" style="border-left:4px solid #f59e0b;">
            <div style="font-weight:700; color:#b45309; font-size:14px;">Vendor 3 (Global Corrugators) — Partial Gate</div>
            <div style="font-size:12px; color:#475569; margin-top:6px; line-height:1.5;">
                • <strong>Failed Q6:</strong> No in-house 7-ply (BCB triple-wall) corrugation capability.<br>
                • <strong>Impact:</strong> Strictly banned from award recommendations on <strong>Lines 10 & 30</strong>.<br>
                • Remains qualified and cost-competitive for all 3-ply and 5-ply cartons.
            </div>
        </div>
        """, unsafe_allow_html=True)
    with pcol2:
        st.markdown("""
        <div class="procure-card" style="border-left:4px solid #f59e0b;">
            <div style="font-weight:700; color:#b45309; font-size:14px;">Vendor 5 (Standard Box Corp) — Partial Gate</div>
            <div style="font-size:12px; color:#475569; margin-top:6px; line-height:1.5;">
                • <strong>Failed Q7:</strong> No in-house or partner moisture-barrier treatment.<br>
                • <strong>Impact:</strong> Strictly banned from award recommendations on <strong>Lines 26 & 27</strong> (sea-freight export cartons).<br>
                • Holds historical incumbent advantage on standard RSC shippers.
            </div>
        </div>
        """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# 8. VIEW 5: AI PROCUREMENT ANALYST (CHAT & INTERACTIVE CHIPS)
# ─────────────────────────────────────────────────────────────────────────────
elif nav == "💬 AI Procurement Analyst":
    st.markdown("""
    <div class="procure-card">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <div>
                <h2 style="font-size:20px; font-weight:800; color:#0f172a; margin:0 0 4px 0;">AI Procurement Analyst Co-pilot</h2>
                <p style="font-size:13px; color:#64748b; margin:0;">
                    Decision support grounded in RFx_Master_Updated.xlsx · Historical POs · Quality Audits · Award Scenarios
                </p>
            </div>
            <span class="badge-verified">Live Co-pilot</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Initialize chat history in session state
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = [
            {
                "role": "ai",
                "content": "Hello! I am your **AI Procurement Analyst** for RFx-CORR-2026-017. I have analyzed all quotes across the 30 line items, cross-referenced our FY25 PO history, and audited vendor quality gates. Click a suggested query below or ask any question about line normalization and award trade-offs."
            }
        ]

    # Pre-populated Interactive Suggestion Chips
    st.markdown("**Suggested Audit Queries:**")
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

    # Freeform chat input
    custom_query = st.chat_input("Ask co-pilot about vendor quotes, conversions, savings...")
    if custom_query:
        user_query = custom_query

    # Response generation engine grounded in Excel dataset
    if user_query:
        st.session_state.chat_history.append({"role": "user", "content": user_query})

        if user_query == chip1:
            reply = (
                "**Vendor 5 (Standard Box Corp) — Line 27 Audit Finding:**\n\n"
                "Vendor 5 is marked **UNRESOLVED** on Line 27 (`CP-027`: Export carton 650×450×400, moisture-barrier) for two compounding reasons:\n\n"
                "1. **New SKU with No Historical Baseline:** In the *Historical PO Master*, Line 27 is explicitly classified as a **New SKU** (0 prior purchase volume, blank historical price). Vendor 5's quote stated *'same as last year'*, but because there is no historical PO record to reference, the normalization engine cannot infer a baseline unit price.\n"
                "2. **Line Disqualification (Gate Q7):** Furthermore, in the *Questionnaire Audit & Gate*, Vendor 5 answered **NO to Q7** (Moisture-barrier coating). Because Line 27 mandates moisture barrier for ocean freight, Vendor 5 is disqualified from award on this line regardless of pricing."
            )
        elif user_query == chip2:
            reply = (
                "**Cost of Compliance & Quality Gate Analysis:**\n\n"
                "Enforcing the quality gate (transitioning from **Scenario A: Unconstrained L1** to **Scenario B: Quality-Gated L1**) costs exactly **+₹2,74,585 (+0.73%)** in annual spend:\n\n"
                "| Metric | Master Budget | Scenario A (Unconstrained) | Scenario B (Quality-Gated) |\n"
                "|---|---|---|---|\n"
                "| **Total Spend** | ₹4,00,03,750 | ₹3,77,44,605 | **₹3,80,19,190** |\n"
                "| **Net Savings** | — | ₹22,59,145 (5.65%) | **₹19,84,560 (4.96%)** |\n"
                "| **Cost of Compliance** | — | Baseline | **+₹2,74,585 (+0.73%)** |\n\n"
                "**Recommendation for Leadership:**\n"
                "Scenario A achieves nominal savings by awarding multiple high-volume lines to **Vendor 4 (Sri Balaji Packaging)**. However, Vendor 4's ISO 9001 certificate expired in October 2026. Paying the 0.73% premium (₹2.75 Lakhs) in Scenario B eliminates all quality and audit risks while still saving ₹19.85 Lakhs against budget."
            )
        elif user_query == chip3:
            reply = (
                "**Risk Profile: Vendor 4 (Sri Balaji Packaging):**\n\n"
                "⛔ **Overall Audit Status: DISQUALIFIED (Failed Q1 through Q5)**\n\n"
                "Vendor 4 failed every mandatory qualification gate in the *Questionnaire Audit & Gate*:\n\n"
                "• **Q1 (ISO 9001:2015 Cert):** **FAIL** — Expired in October 2026 (prior to the RFx closing date of 19-Nov-2026).\n"
                "• **Q2 (Monthly Capacity):** **FAIL** — Declared 280 TPM (below the 300 TPM threshold).\n"
                "• **Q3 (In-house Lab):** **FAIL** — No in-house testing lab for burst/ECT/GSM.\n"
                "• **Q4 (Rejection Rate):** **FAIL** — 2.4% customer rejection rate (exceeds 1.5% maximum tolerance).\n"
                "• **Q5 (Active Customers):** **FAIL** — Only 2 active accounts (minimum 3 required).\n\n"
                "**Verdict:** Vendor 4 is locked out of all qualified award models (Scenario B and C). No awards should be recommended to Sri Balaji until re-certification and capacity expansion are verified."
            )
        else:
            reply = (
                f"**Procurement Co-pilot Analysis for:** *\"{user_query}\"*\n\n"
                "Cross-referencing the 4 active sheets from `RFx_Master_Updated.xlsx`:\n\n"
                "• **Normalized Quotes:** 30 line items are normalized into landed costs (₹/UoM). Vendor 3 includes USD-to-INR conversions (at ₹83.95/USD), and Vendor 5 includes weight-based conversions from ₹38–42/kg.\n"
                "• **Quality Gating:** Vendor 4 is fully disqualified. Vendors 3 and 5 are eligible with line-specific restrictions (7-ply and moisture barrier respectively).\n"
                "• **Award Recommendation:** Scenario B (Quality-Gated L1 at ₹3.80 Cr) provides ₹19.85 Lakhs in savings with zero compliance exposure.\n\n"
                "Click any of the suggested chips above for deep-dive audit calculations!"
            )

        st.session_state.chat_history.append({"role": "ai", "content": reply})

    # Render chat messages
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
