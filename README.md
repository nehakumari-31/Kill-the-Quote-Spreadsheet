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
   - **Cost of Compliance** card showing the +₹2,74,585 (+0.73%) premium to eliminate quality risk.
4. **Vendor Eligibility Gate:**
   - Full questionnaire audit matrix from `Questionnaire Audit & Gate`.
   - Dedicated red alert box for **Vendor 4 (Sri Balaji Packaging)** highlighting expired ISO 9001:2015 certificate and low capacity.
   - Partial gate callouts for Vendor 3 (7-ply capability) and Vendor 5 (moisture-barrier).
5. **AI Procurement Analyst (Interactive Co-pilot):**
   - Interactive chat interface with 3 pre-populated query chips citing ground truth data:
     - *"Why is Vendor 5 marked unresolved for line 27?"*
     - *"What is the cost difference if we enforce the quality gate?"*
     - *"Show me the risk profile for Vendor 4."*
   - Freeform chat prompt for buyer ad-hoc questions.

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
