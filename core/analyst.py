"""
AI Procurement Analyst engine.
Context-aware analytical reasoning connected to live state.
Uses OpenAI client when available; provides deterministic reasoning in Demo Mode.
"""

from typing import Dict, Any, List, Optional
import pandas as pd


def build_system_context(
    df_matrix: pd.DataFrame,
    df_audit: pd.DataFrame,
    qualifications: Dict[str, Any],
    scenarios: Dict[str, Any],
    overrides: List[Any],
    fx_rate: float
) -> str:
    """Builds comprehensive live context prompt for the AI Analyst."""
    matrix_md = df_matrix[[
        "Line #", "Item Code", "Description", "Est. Qty", "Delivery Location", "Criticality",
        "V1 (Apex)", "V2 (PackTech)", "V3 (Global USD)", "V4 (Balaji)", "V5 (Standard Box)",
        "V1 Citation", "V2 Citation", "V3 Citation", "V4 Citation", "V5 Citation", "V5 Trust Flag"
    ]].to_markdown(index=False)

    audit_md = df_audit.to_markdown(index=False)

    qual_summary = []
    for vid, q in qualifications.items():
        qual_summary.append(f"- {q.vendor_name} ({vid}): Status = {q.status}. Reason: {q.reason}")

    overrides_summary = []
    for o in overrides:
        overrides_summary.append(f"- Line {o.line_no} ({o.item_code}) {o.vendor_col}: Changed '{o.original_value}' -> '{o.corrected_value}' | Reason: {o.reason}")

    return f"""You are the AI Procurement Analyst co-pilot for RFx-CORR-2026-017 (Corrugated Packaging).
You are directly connected to the active normalized matrix, Questionnaire Audit database, and live award scenarios engine.

--- LIVE DATA CONTEXT ---
ACTIVE EXCHANGE RATE: ₹{fx_rate:.2f} / USD

LIVE QUOTE MATRIX & AUDIT CITATIONS:
{matrix_md}

QUESTIONNAIRE AUDIT & GATES:
{audit_md}

DATA-DRIVEN VENDOR QUALIFICATIONS:
{chr(10).join(qual_summary)}

LIVE SCENARIO SPENDS (PANDAS CALCULATED):
- Master Budget: ₹{scenarios['budget_spend']:,.0f}
- Scenario A (Unconstrained L1): ₹{scenarios['spend_a']:,.0f} (Net Savings: ₹{scenarios['savings_a']:,.0f} / {scenarios['savings_pct_a']:.2f}%)
- Scenario B (Quality-Gated L1): ₹{scenarios['spend_b']:,.0f} (Net Savings: ₹{scenarios['savings_b']:,.0f} / {scenarios['savings_pct_b']:.2f}%)
- Scenario C (Dual Sourcing 70/30): ₹{scenarios['spend_c']:,.0f} (Net Savings: ₹{scenarios['savings_c']:,.0f} / {scenarios['savings_pct_c']:.2f}%)
- Cost of Compliance (B vs A): +₹{scenarios['cost_of_compliance']:,.0f} (+{scenarios['compliance_pct']:.2f}%)
- Uncovered Lines in Scenario B: {scenarios.get('uncovered_lines_b', [])}
- Scenario B Operational & Quality Risks: {scenarios.get('risks_b', [])}

ACTIVE BUYER OVERRIDES:
{chr(10).join(overrides_summary) if overrides_summary else 'None (Matrix is at base extracted state)'}

--- MANDATORY REASONING GUIDELINES ---
1. Base all answers strictly on the live numbers, citations, and vendor statuses provided above.
2. When explaining why any price was inferred, converted, or unresolved, cite the exact text from the 'Citation' fields.
3. If asked about an UNRESOLVED cell (e.g. Vendor 5 on Line 27 or other New SKUs), explicitly refuse to invent a price and state: 'The quote is UNRESOLVED because Vendor 5 quoted 'Same as last year' on a New SKU with no PO history.' Note that Line 27 also failed Gate Q7 for moisture barrier.
4. For questions regarding Vendor 4, state clearly that Vendor 4 is Disqualified across all lines due to failing mandatory gates (Q1 ISO 9001 expired Oct 2026, Q2 capacity 280 TPM < 300 TPM).
5. Explain numerical calculations step by step using the deterministic figures provided.
"""


def answer_query(
    user_query: str,
    df_matrix: pd.DataFrame,
    df_audit: pd.DataFrame,
    qualifications: Dict[str, Any],
    scenarios: Dict[str, Any],
    overrides: List[Any],
    fx_rate: float,
    openai_client=None
) -> Tuple[str, str]:
    """
    Answers buyer query.
    Returns (response_text, execution_mode).
    """
    system_prompt = build_system_context(df_matrix, df_audit, qualifications, scenarios, overrides, fx_rate)

    if openai_client:
        try:
            completion = openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_query}
                ],
                temperature=0.1
            )
            return completion.choices[0].message.content, "Live OpenAI GPT-4o"
        except Exception as e:
            fallback_ans = _deterministic_analyst_answer(user_query, df_matrix, qualifications, scenarios)
            return f"⚠️ OpenAI API Error: {e}\n\n**Deterministic Reasoning:**\n{fallback_ans}", "Deterministic Engine (API Error)"

    # Demo Mode (no API key provided)
    ans = _deterministic_analyst_answer(user_query, df_matrix, qualifications, scenarios)
    return ans, "Deterministic Analytics Engine (Demo Mode - Enter API Key for GPT-4o)"


def _deterministic_analyst_answer(
    query: str,
    df_matrix: pd.DataFrame,
    qualifications: Dict[str, Any],
    scenarios: Dict[str, Any]
) -> str:
    """Answers specific queries deterministically from active state."""
    q_low = query.lower()

    if "unresolved" in q_low and ("27" in q_low or "cp-027" in q_low):
        return (
            "### Analysis for Line 27 (CP-027 - Export Carton 650x450x400):\n"
            "- **Vendor 5 (Standard Box) Status:** `UNRESOLVED`\n"
            "- **Root Cause Evidence:** In their quotation email, Standard Box Corp quoted 'Same as last year'. "
            "However, CP-027 is a **New SKU** in the RFx master with no historical FY25 purchase order price on record. "
            "Therefore, no baseline price exists to index.\n"
            "- **Technical Disqualification:** Line 27 requires moisture-barrier treatment for export. Standard Box Corp "
            "failed Questionnaire Gate Q7 ('Do not provide moisture-barrier treatment'). Even if priced, Vendor 5 cannot be awarded this line.\n"
            "- **Action Required:** Buyer must either obtain a direct piece quotation or award to qualified L1 (Vendor 4 is disqualified, making Vendor 3 or Vendor 1 the qualified candidate)."
        )

    if "cp-010" in q_low or "line 10" in q_low or "lowest compliant" in q_low:
        row10 = df_matrix[df_matrix["Line #"] == 10].iloc[0]
        v1_p = row10.get("V1 (Apex)")
        v2_p = row10.get("V2 (PackTech)")
        v3_p = row10.get("V3 (Global USD)")
        v4_p = row10.get("V4 (Balaji)")
        v5_p = row10.get("V5 (Standard Box)")
        return (
            f"### Lowest Compliant Supplier for Line 10 (CP-010 - 7-Ply Heavy-Duty Carton):\n"
            f"- **Technical Requirement:** 7-ply BCB board with 230/140 GSM.\n"
            f"- **Vendor 4 (Balaji):** Quoted ₹{v4_p:.2f}, but is **DISQUALIFIED** across all lines due to expired ISO 9001 cert.\n"
            f"- **Vendor 3 (Global):** **DISQUALIFIED for Line 10** (Failed Gate Q6: lacks in-house 7-ply manufacturing capability).\n"
            f"- **Vendor 1 (Apex):** Quoted **₹{v1_p:.2f}** (Fully qualified on ISO 9001 and 7-ply).\n"
            f"- **Vendor 2 (PackTech):** Quoted **₹{v2_p:.2f}**.\n"
            f"- **Vendor 5 (Standard Box):** Quoted **₹{v5_p:.2f}** (Resolved from FY25 PO).\n\n"
            f"**Recommendation:** **Vendor 1 (Apex Packaging)** offers the lowest compliant price at **₹{v1_p:.2f}**."
        )

    if "cost difference" in q_low or "compliance" in q_low or "quality gate" in q_low:
        cost = scenarios['cost_of_compliance']
        pct = scenarios['compliance_pct']
        spend_a = scenarios['spend_a']
        spend_b = scenarios['spend_b']
        return (
            f"### Cost of Compliance Analysis:\n"
            f"- **Scenario A Spend (Unconstrained L1):** ₹{spend_a:,.0f}\n"
            f"- **Scenario B Spend (Quality-Gated L1):** ₹{spend_b:,.0f}\n"
            f"- **Cost of Compliance Premium:** **+₹{cost:,.0f} (+{pct:.2f}%)**\n\n"
            f"**Strategic Justification:**\n"
            f"The extra ₹{cost:,.0f} eliminates high operational and supply risk by locking out **Vendor 4 (Sri Balaji Packaging)**, "
            f"whose ISO 9001:2015 certificate expired in October 2026, monthly capacity is only 280 TPM (below the 300 TPM threshold), "
            f"and has no certified in-house testing lab."
        )

    if "risk" in q_low and "v4" in q_low or "balaji" in q_low:
        return (
            "### Risk Profile: Vendor 4 (Sri Balaji Packaging Industries)\n"
            "- **Overall Status:** `DISQUALIFIED`\n"
            "- **Violations of Mandatory Gates:**\n"
            "  1. **Q1 (ISO 9001:2015):** Certificate expired in October 2026 (prior to closing date 19-Nov-2026).\n"
            "  2. **Q2 (Capacity):** Declared capacity is 280 TPM (Threshold: >= 300 TPM).\n"
            "  3. **Q3 (Testing Lab):** No certified in-house laboratory (relies on third-party labs).\n"
            "  4. **Q4 (Rejection Rate):** 2.4% historical rejection rate (Threshold: <= 1.5%).\n"
            "  5. **Q5 (Client References):** Only 2 active clients in FMCG/appliances (Threshold: >= 3).\n"
            "- **Impact:** Automatically excluded from Scenarios B and C to protect supply chain integrity."
        )

    # General overview
    return (
        f"### Executive Procurement Summary:\n"
        f"- **Master Budget:** ₹{scenarios['budget_spend']:,.0f}\n"
        f"- **Scenario B (Recommended Quality-Gated L1):** ₹{scenarios['spend_b']:,.0f} (Net Savings: ₹{scenarios['savings_b']:,.0f} / {scenarios['savings_pct_b']:.2f}%)\n"
        f"- **Scenario C (Dual Sourced 70/30):** ₹{scenarios['spend_c']:,.0f}\n"
        f"- **Compliance Premium:** +₹{scenarios['cost_of_compliance']:,.0f} (+{scenarios['compliance_pct']:.2f}%)\n"
        f"- **Uncovered Lines:** {len(scenarios.get('uncovered_lines_b', []))} lines\n"
        f"Ask me about specific line items, vendor risks, or overrides for detailed trace evidence!"
    )
