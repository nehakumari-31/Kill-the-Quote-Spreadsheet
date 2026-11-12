"""
AI Procurement Analyst engine.
Context-aware analytical reasoning connected to live state.
Uses OpenAI client when available; provides deterministic reasoning in Demo Mode.
"""

from typing import Dict, Any, List, Optional, Tuple
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
    cols_to_include = [
        c for c in [
            "Line #", "Item Code", "Description", "Est. Qty", "Delivery Location", "Criticality",
            "V1 (Apex)", "V2 (PackTech)", "V3 (Global USD)", "V4 (Balaji)", "V5 (Standard Box)",
            "V1 Citation", "V2 Citation", "V3 Citation", "V4 Citation", "V5 Citation", "V5 Trust Flag"
        ] if c in df_matrix.columns
    ]
    matrix_md = df_matrix[cols_to_include].to_markdown(index=False)

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
    Uses OpenAI client when available; otherwise executes deterministic analytical reasoning.
    Clearly distinguishes confirmed facts, unresolved data, and missing data.
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
                temperature=0.0
            )
            return completion.choices[0].message.content, "Live OpenAI GPT-4o"
        except Exception as e:
            fallback_ans = _deterministic_analyst_answer(user_query, df_matrix, qualifications, scenarios, overrides)
            return f"⚠️ OpenAI API is unavailable: {e}\n\n**Deterministic Reasoning from Live State:**\n\n{fallback_ans}", "Deterministic Engine (API Unavailable)"

    # Deterministic Engine Mode (no API key configured)
    ans = _deterministic_analyst_answer(user_query, df_matrix, qualifications, scenarios, overrides)
    return ans, "Deterministic Analytics Engine (Live State Connected)"


def _deterministic_analyst_answer(
    query: str,
    df_matrix: pd.DataFrame,
    qualifications: Dict[str, Any],
    scenarios: Dict[str, Any],
    overrides: Optional[List[Any]] = None
) -> str:
    """
    Answers buyer queries dynamically using deterministic functions on the live state.
    Distinguishes confirmed facts, unresolved data, missing data, and disqualifications.
    """
    import re
    q_low = query.lower()

    # 1. Line-Specific Inquiries (e.g. Line 10, Line 27, CP-010, etc.)
    line_match = re.search(r"\b(?:line\s*|cp-0*)(\d{1,2})\b", q_low)
    if line_match:
        target_line = int(line_match.group(1))
        matching_rows = df_matrix[df_matrix["Line #"] == target_line]
        if not matching_rows.empty:
            row = matching_rows.iloc[0]
            code = str(row.get("Item Code", f"CP-{target_line:03d}"))
            desc = str(row.get("Description", ""))
            qty = row.get("Est. Qty", 0)
            budget = row.get("Budget Price", 0.0)
            loc = row.get("Delivery Location", "Pune")
            crit = row.get("Criticality", "C")

            vendor_cols = [c for c in ["V1 (Apex)", "V2 (PackTech)", "V3 (Global USD)", "V4 (Balaji)", "V5 (Standard Box)"] if c in df_matrix.columns]
            
            facts = []
            unresolved = []
            missing = []
            disqualified = []
            eligible_quotes = []

            for vc in vendor_cols:
                vid = vc.split()[0]
                val = row.get(vc)
                cite = row.get(f"{vid} Citation", "No citation")
                qual = qualifications.get(vid)

                is_globally_dq = qual and qual.status in ["Disqualified", "Pending Review"]
                is_line_banned = qual and target_line in qual.banned_lines
                is_unresolved = ("unresolved" in str(cite).lower()) or (vid == "V5" and "unresolved" in str(row.get("V5 Trust Flag", "")).lower())

                if is_unresolved:
                    unresolved.append(f"- **{vc}:** `UNRESOLVED` — Citation: {cite}")

                if is_globally_dq:
                    disqualified.append(f"- **{vc}:** Quoted ₹{val:.2f} if applicable, but **DISQUALIFIED globally** ({qual.reason})")
                elif is_line_banned:
                    restr = qual.line_restrictions.get(target_line, "Technical capability constraint")
                    disqualified.append(f"- **{vc}:** **DISQUALIFIED for Line {target_line}** ({restr})")
                elif pd.isna(val) or val is None:
                    if not is_unresolved:
                        missing.append(f"- **{vc}:** `MISSING / NOT QUOTED` — Citation: {cite}")
                else:
                    if not is_unresolved:
                        facts.append(f"- **{vc}:** **₹{float(val):.2f}** (Confirmed Fact — Citation: {cite})")
                        eligible_quotes.append((vc, float(val)))

            # Sort eligible
            eligible_quotes.sort(key=lambda x: x[1])

            out = [f"### Line {target_line} ({code} — {desc}) Analysis\n"]
            out.append(f"- **Technical Specs:** Annual Qty: {qty:,} | Location: {loc} | Criticality: {crit} | Budget: ₹{budget:.2f}")
            
            if facts:
                out.append("\n**Confirmed Quotations:**\n" + "\n".join(facts))
            if unresolved:
                out.append("\n**Unresolved Items (Missing Baseline / Ambiguous):**\n" + "\n".join(unresolved))
            if missing:
                out.append("\n**Missing / Not Quoted:**\n" + "\n".join(missing))
            if disqualified:
                out.append("\n**Disqualified / Ineligible Vendors:**\n" + "\n".join(disqualified))

            if eligible_quotes:
                best_v, best_p = eligible_quotes[0]
                out.append(f"\n**Award Engine Outcome:** Lowest compliant eligible supplier is **{best_v}** at **₹{best_p:.2f}**.")
            else:
                out.append(f"\n⚠️ **Award Engine Alert:** Mandatory Line {target_line} is **UNCOVERED**. No compliant eligible vendor has a valid quote.")

            return "\n".join(out)

    # 2. Cost of Compliance & Savings Inquiries
    if any(k in q_low for k in ["cost difference", "compliance", "quality gate", "savings", "scenario"]):
        cost = scenarios["cost_of_compliance"]
        pct = scenarios["compliance_pct"]
        spend_a = scenarios["spend_a"]
        spend_b = scenarios["spend_b"]
        spend_c = scenarios["spend_c"]
        budget = scenarios["budget_spend"]
        sav_b = scenarios["savings_b"]
        sav_pct_b = scenarios["savings_pct_b"]
        uncovered = scenarios.get("uncovered_lines_b", [])

        out = [
            "### Live Award Scenarios & Cost of Compliance Breakdown\n",
            f"- **Master Budget Spend:** **₹{budget:,.0f}**",
            f"- **Scenario A (Unconstrained L1):** **₹{spend_a:,.0f}** (Saves ₹{scenarios['savings_a']:,.0f} / {scenarios['savings_pct_a']:.2f}%)",
            f"- **Scenario B (Quality-Gated L1):** **₹{spend_b:,.0f}** (Saves ₹{sav_b:,.0f} / {sav_pct_b:.2f}%)",
            f"- **Scenario C (Dual Sourcing 70/30):** **₹{spend_c:,.0f}** (Saves ₹{scenarios['savings_c']:,.0f} / {scenarios['savings_pct_c']:.2f}%)",
            f"- **Cost of Compliance (B vs A):** **+₹{cost:,.0f} (+{pct:.2f}%)**",
            f"- **Uncovered Lines in Scenario B:** {uncovered if uncovered else 'None (100% Mandatory Coverage Achieved)'}\n",
            f"**Strategic Fact:** The compliance premium of ₹{cost:,.0f} is required to enforce mandatory RFx quality gates "
            "(excluding uncertified Vendor 4 due to expired ISO 9001 and inadequate 280 TPM capacity). All figures are computed dynamically."
        ]
        return "\n".join(out)

    # 3. Vendor-Specific Risk Inquiries (e.g. V4, Balaji, V3, V5, etc.)
    for vid, vname in [("V4", "balaji"), ("V3", "global"), ("V5", "standard"), ("V1", "apex"), ("V2", "packtech")]:
        if vid.lower() in q_low or vname in q_low:
            qual = qualifications.get(vid)
            if qual:
                shares = scenarios.get("vendor_shares_b", {}).get(qual.vendor_name, {})
                spend_val = shares.get("spend", 0.0)
                share_pct = shares.get("share_pct", 0.0)

                out = [f"### Risk & Qualification Profile: {qual.vendor_name} ({vid})\n"]
                out.append(f"- **Qualification Status:** `{qual.status}`")
                out.append(f"- **Award Eligibility:** {'Eligible for award' if qual.passed_mandatory_gates else 'INELIGIBLE across all lines'}")
                out.append(f"- **Audit Assessment Reason:** {qual.reason}")

                if qual.failed_general_gates:
                    out.append("\n**Failed Mandatory Gates:**\n" + "\n".join([f"  - {g}" for g in qual.failed_general_gates]))
                if qual.pending_gates:
                    out.append("\n**Pending Review Gates:**\n" + "\n".join([f"  - {g}" for g in qual.pending_gates]))
                if qual.banned_lines:
                    out.append(f"\n**Restricted / Banned Line Items:** {qual.banned_lines}")
                    for l, r in qual.line_restrictions.items():
                        out.append(f"  - Line {l}: {r}")

                out.append(f"\n**Scenario B Award Allocation:** ₹{spend_val:,.0f} ({share_pct:.1f}% of total portfolio)")
                return "\n".join(out)

    # 4. General Executive Overview (Computed from active state)
    return (
        f"### Executive Procurement Analysis (Live State Connected)\n"
        f"- **Master Budget Ceiling:** ₹{scenarios['budget_spend']:,.0f}\n"
        f"- **Recommended Scenario B Spend:** ₹{scenarios['spend_b']:,.0f} (Net Savings: ₹{scenarios['savings_b']:,.0f} / {scenarios['savings_pct_b']:.2f}%)\n"
        f"- **Scenario C Spend (Dual-Sourced):** ₹{scenarios['spend_c']:,.0f}\n"
        f"- **Cost of Compliance Premium:** +₹{scenarios['cost_of_compliance']:,.0f} (+{scenarios['compliance_pct']:.2f}%)\n"
        f"- **Uncovered Mandatory Lines:** {len(scenarios.get('uncovered_lines_b', []))} lines\n"
        f"- **Active Buyer Overrides:** {len(overrides) if overrides else 0} overridden cells\n\n"
        f"Ask me about any specific Line # (e.g. 'Line 10' or 'Line 27'), vendor risks (e.g. 'Vendor 4'), "
        f"or cost of compliance for verified trace evidence."
    )
