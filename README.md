# AI-Powered Procurement Co-pilot (Streamlit App)

An enterprise-grade **AI-Powered Procurement Co-pilot** designed for a category buyer, built using **Streamlit**, **Pandas**, and **Plotly**. Sourced directly from `RFx_Master_Updated.xlsx`.

---

## 🌟 Key Features

1. **Strict Enterprise Light Theme:** Clean white cards (`#ffffff`), subtle off-white background (`#f8fafc`), dark slate text (`#1e293b`), corporate blue accents (`#2563eb`), and pastel status badges.
2. **Quote Comparison Matrix (Core View):**
   - 30 packaging items across 5 vendors.
   - Sourced from `Normalized Comparison` and `Historical PO Master`.
   - Trust state badges: **Verified**, **Inferred / Converted** (⚠), **Unresolved** (!), and **Disqualified** (🚫).
   - Filter for "New SKUs only".
   - **Interactive Raw Quote Inspector**: Select any line item to inspect the exact raw quote text before normalization (e.g., `₹6,120 per 1,000 Nos`, `USD 0.0708 /Nos`, `₹38/kg + freight`).
3. **Award Scenarios & Spend Analytics:**
   - Plotly bar chart comparing total spend across Master Budget (₹4.00 Cr), Scenario A: Unconstrained L1 (₹3.77 Cr), Scenario B: Quality-Gated L1 (₹3.80 Cr), and Scenario C: Dual Sourced (₹3.81 Cr).
   - **Cost of Compliance** card showing the +₹468,592 (+1.25% higher than Scenario A) premium to eliminate quality risk.
4. **Centralized Award Approval Gate & Vendor Eligibility:**
   - Single source of truth gate (`evaluate_award_approval_gate`) integrated across Overview, Award Screen, and AI Analyst.
   - Dynamically counts unresolved lines from eligible bidders (Lines 25, 28, 29, 30 for Vendor 5 on New SKUs with no PO history).
   - Excludes genuinely disqualified/ineligible suppliers (Vendor 4 globally, Vendor 5 on Line 27 for moisture barrier).
   - Clear gate status display:
     - `Award on Scenario B — BLOCKED pending 4 unresolved lines.`
     - `Buyer clarification or documented override required before award approval.`
   - Smooth transition to `Award on Scenario B — Approval Ready` upon human-in-the-loop buyer overrides with audit logging.
   - Preserves core recommendation on Scenario B throughout.
5. **AI Procurement Analyst (Submission-Ready Co-Pilot):**
   - Interactive conversation interface with 3 demonstration questions immediately clickable (no typing required):
     - *"Which vendor should we award to, and why? Compare the lowest-cost option with the quality and compliance requirements."*
     - *"What are the key commercial and compliance risks in these quotations? Identify unresolved items that require buyer intervention."*
     - *"Why is Scenario B recommended over Scenario C? Explain the cost difference and the dual-sourcing trade-off."*
   - Displays questions and live generated answers in the conversation history with session persistence.
   - Dual-engine architecture: Live OpenAI GPT-4o when API key is provided, and deterministic analytical engine grounded in active matrix, audit gates, and award spends when offline. No canned outputs.
   - Freeform chat input for ad-hoc buyer inquiries.

---

## 🚀 How to Run Locally

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the Streamlit application
streamlit run app.py
```
App will open automatically at `http://localhost:8501`.

---

## ☁️ How to Deploy to Streamlit Community Cloud (Free)

1. **Push this folder to a GitHub repository:**
   ```bash
   git init
   git add .
   git commit -m "Deploy AI Procurement Co-pilot on Streamlit"
   git branch -M main
   git remote add origin https://github.com/<your-username>/<your-repo-name>.git
   git push -u origin main
   ```

2. **Go to [share.streamlit.io](https://share.streamlit.io/)**:
   - Click **"New app"**.
   - Select your GitHub repository, branch (`main`), and set Main file path to: `app.py`.
   - Click **"Deploy"**!

Your app will be live on a public URL within 2 minutes with light theme and data persistence.
