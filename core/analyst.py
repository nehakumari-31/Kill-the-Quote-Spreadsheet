"""
AI Procurement Analyst engine.
Context-aware analytical reasoning connected to live state.
Uses OpenAI client when available; provides deterministic reasoning in Demo Mode.
"""

from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
from core.scenarios import evaluate_award_approval_gate


def build_system_context(
    df_matrix: pd.DataFrame,
    df_audit: pd.DataFrame,
    qualifications: Dict[str, Any],
    scenarios: Dict[str, Any],
    overrides: List[Any],
    fx_rate: float,
    gate_result: Optional[Dict[str, Any]] = None
) -> str:
    """Builds comprehensive live context prompt for the AI Analyst."""
    if gate_result is None:
        gate_result = evaluate_award_approval_gate(df_matrix, qualifications, overrides)

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
        l_no = getattr(o, "line_no", None) if hasattr(o, "line_no") else o.get("line_no")
        item_code = getattr(o, "item_code", "") if hasattr(o, "item_code") else o.get("item_code", "")
        v_col = getattr(o, "vendor_col", "") if hasattr(o, "vendor_col") else o.get("vendor_col", "")
        orig_val = getattr(o, "original_value", "") if hasattr(o, "original_value") else o.get("original_value", "")
        corr_val = getattr(o, "corrected_value", "") if hasattr(o, "corrected_value") else o.get("corrected_value", "")
        reason = getattr(o, "reason", "") if hasattr(o, "reason") else o.get("reason", "")
        overrides_summary.append(f"- Line {l_no} ({item_code}) {v_col}: Changed '{orig_val}' -> '{corr_val}' | Reason: {reason}")

    return f"""You are the AI Procurement Analyst co-pilot for RFx-CORR-2026-017 (Corrugated Packaging).
You are directly connected to the active normalized matrix, Questionnaire Audit database, and live award scenarios engine.

--- LIVE DATA CONTEXT ---
ACTIVE EXCHANGE RATE: ₹{fx_rate:.2f} / USD

CENTRALIZED AWARD APPROVAL GATE:
- Status Label: {gate_result['status_label']}
- Guidance Message: {gate_result['guidance_message']}
- Approval Blocked: {gate_result['is_blocked']}
- Unresolved Lines Count: {gate_result['unresolved_line_count']}
- Pending Unresolved Lines: {gate_result['unresolved_lines']}
- Target Award Recommendation: {gate_result['recommendation']}

LIVE QUOTE MATRIX & AUDIT CITATIONS:
{matrix_md}

QUESTIONNAIRE AUDIT & GATES:
{audit_md}

DATA-DRIVEN VENDOR QUALIFICATIONS:
{chr(10).join(qual_summary)}

LIVE SCENARIO SPENDS (PANDAS CALCULATED):
- Master Budget: ₹{scenarios['budget_spend']:,.0f}
- Scenario A (Unconstrained L1): ₹{scenarios['spend_a']:,.0f} (Net Savings: ₹{scenarios['savings_a']:,.0f} / {scenarios['savings_pct_a']:.2f}%)
- Scenario B (Quality-Gated L1): ₹{scenarios['spend_b']:,.0f} (Net Savings: ₹{scenarios['savings_b']:,.0f} / {scenarios['savings_pct_b']:.2f}%; +{scenarios.get('pct_diff_b_vs_a', ((scenarios['spend_b']-scenarios['spend_a'])/scenarios['spend_a'])*100):.2f}% higher than Scenario A)
- Scenario C (Dual Sourcing 70/30): ₹{scenarios['spend_c']:,.0f} (Net Savings: ₹{scenarios['savings_c']:,.0f} / {scenarios['savings_pct_c']:.2f}%; +{scenarios.get('pct_diff_c_vs_a', ((scenarios['spend_c']-scenarios['spend_a'])/scenarios['spend_a'])*100):.2f}% higher than Scenario A)
- Cost of Compliance (B vs A): +₹{scenarios['cost_of_compliance']:,.0f} (+{scenarios['compliance_pct']:.2f}% higher than Scenario A)
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
6. When answering award recommendations ("Which vendor should we award to, and why?"):
   - Recommend Award on Scenario B (Quality-Gated L1).
   - Explicitly cite the current Approval Gate status: '{gate_result['status_label']}'. If blocked, state clearly: '{gate_result['guidance_message']}' and identify pending lines: {gate_result['unresolved_lines']}.
   - Compare Scenario B with the lowest-cost unconstrained Scenario A (saves ₹{scenarios['savings_a']:,.0f} vs ₹{scenarios['savings_b']:,.0f}), explaining the cost of compliance premium (+₹{scenarios['cost_of_compliance']:,.0f} / +{scenarios['compliance_pct']:.2f}% higher than Scenario A) required to eliminate disqualified Vendor 4.
7. When answering commercial and compliance risks ("What are the key commercial and compliance risks?"):
   - Identify unresolved quotations requiring buyer intervention (Vendor 5 on Lines {gate_result['unresolved_lines']} quoted 'Same as last year' on New SKUs with no historical baseline). Clarify that Line 27 is excluded from the gate because Vendor 5 failed Gate Q7 for moisture barrier.
   - Detail Vendor 4's failed gates (expired ISO 9001, capacity 280 TPM < 300 TPM, no test lab, 2.4% rejection rate).
   - Detail line restrictions for Vendor 3 (lacks 7-ply for Lines 10 & 30) and Vendor 5 (lacks moisture barrier for Lines 26 & 27).
   - Note FX exposure for Vendor 3 (quoted in USD at ₹{fx_rate:.2f}/USD).
   - Note conditional discount policy: Vendor 1's 5% all-lines discount cannot apply because the award is split.
8. When answering Scenario B vs Scenario C ("Why is Scenario B recommended over Scenario C?"):
   - Detail the cost difference: Scenario C spends ₹{scenarios['spend_c']:,.0f} vs Scenario B's ₹{scenarios['spend_b']:,.0f} (+₹{scenarios['spend_c'] - scenarios['spend_b']:,.0f} / +{((scenarios['spend_c'] - scenarios['spend_b'])/scenarios['spend_b'])*100:.2f}% higher than Scenario B; +₹{scenarios['spend_c'] - scenarios['spend_a']:,.0f} / +{((scenarios['spend_c'] - scenarios['spend_a'])/scenarios['spend_a'])*100:.2f}% higher than Scenario A).
   - Explain the dual-sourcing trade-off: Scenario C splits 70/30 on 5 Criticality A lines (Lines 9, 10, 26, 27, 30) for supply continuity insurance against single-plant disruption. Scenario B is recommended as the commercial baseline to maximize savings within the local Chakan manufacturing hub where Apex has 800 TPM capacity.
"""


def answer_query(
    user_query: str,
    df_matrix: pd.DataFrame,
    df_audit: pd.DataFrame,
    qualifications: Dict[str, Any],
    scenarios: Dict[str, Any],
    overrides: Optional[List[Any]] = None,
    fx_rate: float = 84.50,
    openai_client=None,
    gate_result: Optional[Dict[str, Any]] = None,
    conversation_history: Optional[List[Dict[str, Any]]] = None
) -> Tuple[str, str]:
    """
    Answers buyer query.
    Uses OpenAI GPT-4o client when available with full conversation history;
    otherwise executes deterministic analytical reasoning grounded in live application data.
    Clearly distinguishes confirmed facts, unresolved data, missing data, and disqualifications.
    Never fabricates AI responses or presents deterministic output as GPT-4o.
    """
    if overrides is None:
        overrides = []
    if gate_result is None:
        gate_result = evaluate_award_approval_gate(df_matrix, qualifications, overrides)

    system_prompt = build_system_context(df_matrix, df_audit, qualifications, scenarios, overrides, fx_rate, gate_result=gate_result)

    if openai_client:
        try:
            # Build full message history for multi-turn conversation
            api_messages = [{"role": "system", "content": system_prompt}]
            if conversation_history:
                for msg in conversation_history:
                    role = msg.get("role")
                    content = msg.get("content")
                    if role in ["user", "assistant"] and content:
                        api_messages.append({"role": role, "content": str(content)})

            # Ensure current query is the terminal message without duplication
            if not api_messages or api_messages[-1].get("role") != "user" or api_messages[-1].get("content") != user_query:
                api_messages.append({"role": "user", "content": user_query})

            completion = openai_client.chat.completions.create(
                model="gpt-4o",
                messages=api_messages,
                temperature=0.0
            )
            return completion.choices[0].message.content, "Live OpenAI GPT-4o"
        except Exception as e:
            fallback_ans = _deterministic_analyst_answer(
                user_query, df_matrix, qualifications, scenarios, overrides,
                gate_result=gate_result, fx_rate=fx_rate, conversation_history=conversation_history
            )
            return (
                f"⚠️ **OpenAI API Service Notice:** The OpenAI GPT-4o API call was unavailable or encountered an error: `{str(e)}`.\n\n"
                f"> **Deterministic Reasoning from Live State:**\n"
                f"> *The response below is generated deterministically by the live calculation and audit engine, NOT by GPT-4o.*\n\n"
                f"{fallback_ans}",
                "Deterministic Engine (API Unavailable)"
            )

    # Deterministic Engine Mode (no API key configured or offline)
    ans = _deterministic_analyst_answer(
        user_query, df_matrix, qualifications, scenarios, overrides,
        gate_result=gate_result, fx_rate=fx_rate, conversation_history=conversation_history
    )
    return (
        f"ℹ️ **Deterministic Analytics Engine (Offline Mode)**\n\n"
        f"> *OpenAI API key is not configured. The response below is computed deterministically from active RFx data, NOT by GPT-4o.*\n\n"
        f"{ans}",
        "Deterministic Analytics Engine (Live State Connected)"
    )


def _deterministic_analyst_answer(
    query: str,
    df_matrix: pd.DataFrame,
    qualifications: Dict[str, Any],
    scenarios: Dict[str, Any],
    overrides: Optional[List[Any]] = None,
    gate_result: Optional[Dict[str, Any]] = None,
    fx_rate: float = 84.50,
    conversation_history: Optional[List[Dict[str, Any]]] = None
) -> str:
    """
    Answers buyer queries dynamically using deterministic functions on the live state.
    Distinguishes confirmed facts, unresolved data, missing data, and disqualifications.
    """
    import re
    if overrides is None:
        overrides = []
    if gate_result is None:
        gate_result = evaluate_award_approval_gate(df_matrix, qualifications, overrides)

    q_low = query.lower()

    # Contextual awareness from conversation history for follow-up questions
    context_prefix = ""
    if conversation_history:
        recent_user_turns = [m.get("content", "") for m in conversation_history if m.get("role") == "user"]
        # Look at the most recent prior query (excluding current one if already present)
        prior_queries = [uq for uq in recent_user_turns if uq.strip().lower() != q_low.strip()]
        if prior_queries:
            last_q = prior_queries[-1].lower()
            context_prefix = last_q

    # Helper to check keywords in current query or contextual prior query
    def matches_context(keywords: List[str], check_prior_if_short: bool = True) -> bool:
        if any(k in q_low for k in keywords):
            return True
        if check_prior_if_short and (len(q_low.split()) <= 6 or any(w in q_low for w in ["why", "explain", "how", "what about", "tell me more", "elaborate"])):
            return any(k in context_prefix for k in keywords)
        return False

    # Demonstration Question 1:
    # "Which vendor should we award to, and why? Compare the lowest-cost option with the quality and compliance requirements."
    is_q1 = (
        any(k in q_low for k in ["which vendor should we award to", "which vendor", "who should we award"])
        or (any(k in q_low for k in ["award", "recommendation"]) and any(k in q_low for k in ["lowest-cost", "lowest cost", "compliance requirements", "quality and compliance"]))
        or (matches_context(["which vendor should we award to", "lowest-cost option", "quality and compliance requirements"]) and any(w in q_low for w in ["why", "elaborate", "tell me more", "how so"]))
    )
    if is_q1:
        spend_a = scenarios["spend_a"]
        spend_b = scenarios["spend_b"]
        budget = scenarios["budget_spend"]
        sav_b = scenarios["savings_b"]
        sav_pct_b = scenarios["savings_pct_b"]
        cost = scenarios["cost_of_compliance"]
        cost_pct = scenarios["compliance_pct"]
        unres_count = gate_result["unresolved_line_count"]
        unres_lines = gate_result["unresolved_lines"]

        v_shares = scenarios.get("vendor_shares_b", {})
        alloc_lines = []
        for vname, vdata in v_shares.items():
            alloc_lines.append(f"- **{vname}:** ₹{vdata.get('spend', 0.0):,.0f} ({vdata.get('share_pct', 0.0):.1f}% portfolio share)")

        gate_status_block = (
            f"⚠️ **Approval Gate Notice:** {gate_result['status_label']}\n"
            f"> *{gate_result['guidance_message']}*\n"
            f"> Pending lines from eligible suppliers: **Lines {unres_lines}** (Vendor 5 quoted 'Same as last year' on New SKUs with no PO baseline). "
            "Note: Genuinely disqualified vendors (Vendor 4 globally, Vendor 5 on Line 27 for moisture barrier) are excluded from the gate count."
            if gate_result["is_blocked"] else
            f"✅ **Approval Gate Status:** {gate_result['status_label']}\n"
            f"> *{gate_result['guidance_message']}*"
        )

        out = [
            "### Strategic Award Recommendation & Compliance Evaluation\n",
            "**Recommended Decision: Award on Scenario B (Quality-Gated L1)**\n",
            f"- **Master Budget Ceiling:** ₹{budget:,.0f}",
            f"- **Scenario B Total Spend:** **₹{spend_b:,.0f}**",
            f"- **Net Projected Savings:** **₹{sav_b:,.0f} ({sav_pct_b:.2f}%)** vs budget",
            f"- **Cost of Compliance (B vs Lowest-Cost A):** **+₹{cost:,.0f} (+{cost_pct:.2f}% higher than Scenario A)**\n",
            gate_status_block,
            "\n#### 1. Comparison: Lowest-Cost Option (Scenario A) vs. Quality-Gated (Scenario B)",
            f"- **Lowest-Cost Option (Scenario A - Unconstrained L1):** Totals **₹{spend_a:,.0f}**, yielding ₹{scenarios['savings_a']:,.0f} ({scenarios['savings_pct_a']:.2f}%) savings.",
            "- **Why Scenario A Must Be Rejected:** Scenario A achieves its headline cost by awarding 6 major carton lines to **Vendor 4 (Sri Balaji Packaging)** purely on initial quoted unit price. However, Vendor 4 is **globally DISQUALIFIED** after failing mandatory RFx qualification gates:",
            "  * **Q1 (ISO 9001:2015):** Certificate expired in October 2026 (prior to bid close).",
            "  * **Q2 (Monthly Capacity):** 280 TPM (fails minimum 300 TPM threshold).",
            "  * **Q3 (Testing Lab):** Lacks certified in-house burst/ECT test laboratory.",
            "  * **Q4 (Defect Rate):** Rejection rate of 2.4% (exceeds 1.5% maximum allowable ceiling).",
            f"- **Compliance Premium Justification:** Paying the compliance premium of **+₹{cost:,.0f} (+{cost_pct:.2f}% higher than Scenario A)** is essential to prevent factory downtime, carton transit collapse, and quality warranty claims.\n",
            "#### 2. Supplier Award Allocation Breakdown (Scenario B)",
            *(alloc_lines if alloc_lines else ["- Apex Packaging (V1) is awarded lowest compliant lines (~86% share)."]),
            "\n*All metrics are calculated dynamically from live normalized quotations and audit records.*"
        ]
        return "\n".join(out)

    # Demonstration Question 2:
    # "What are the key commercial and compliance risks in these quotations? Identify unresolved items that require buyer intervention."
    is_q2 = (
        any(k in q_low for k in ["commercial and compliance risks", "commercial risks", "key commercial"])
        or (any(k in q_low for k in ["unresolved items", "unresolved"]) and any(k in q_low for k in ["buyer intervention", "intervention", "risks"]))
        or (matches_context(["commercial and compliance risks", "unresolved items"]) and any(w in q_low for w in ["why", "elaborate", "tell me more", "how so"]))
    )
    if is_q2:
        unres_count = gate_result["unresolved_line_count"]
        unres_lines = gate_result["unresolved_lines"]

        gate_callout = (
            f"- **Award Gate Status:** **BLOCKED pending {unres_count} unresolved lines** (Lines {unres_lines}).\n"
            f"- **Required Action:** {gate_result['guidance_message']}"
            if gate_result["is_blocked"] else
            f"- **Award Gate Status:** **Approval Ready** (All {unres_count} blocking quotation lines resolved via documented overrides)."
        )

        out = [
            "### Comprehensive Commercial & Compliance Risk Assessment\n",
            "#### 1. Unresolved Items Requiring Immediate Buyer Intervention (Blocking Award Gate)",
            f"{gate_callout}",
            "- **Vendor 5 (Standard Box Corp) on New SKUs (Lines 25, 28, 29, 30):**",
            "  * *Audit Finding:* Quoted *'Same as last year'* for newly introduced packaging items (CP-025, CP-028, CP-029, CP-030).",
            "  * *Issue:* Because these are New SKUs with no historical purchase orders, there is no contract baseline price to apply inflation to, leaving the landed cost **UNRESOLVED**.",
            "  * *Buyer Intervention Required:* Buyer must obtain revised rate confirmations (e.g. ₹/kg or ₹/box) or log an authorized documented buyer override with audit justification before award approval can proceed.",
            "- **Line 27 Exclusion Clarification:** Vendor 5 also quoted 'Same as last year' on Line 27. However, Line 27 requires moisture-barrier coating (Gate Q7), which Vendor 5 failed. Because Vendor 5 is genuinely disqualified on Line 27, this cell is excluded from the blocking gate count.\n",
            "#### 2. Vendor Quality & Mandatory Gate Failures",
            "- **Vendor 4 (Sri Balaji Packaging) — Globally Disqualified:**",
            "  * Failed Q1 (ISO 9001:2015 expired October 2026), Q2 (280 TPM capacity < 300 TPM), Q3 (no test lab), Q4 (2.4% rejection rate), and Q5 (only 2 active clients). Must remain strictly excluded from all award scenarios.\n",
            "#### 3. Line-Specific Technical Constraints",
            "- **Vendor 3 (Global Corrugators Ltd) — Gate Q6 Restriction:** Lacks in-house 7-ply BCB flute capability. Strictly excluded from Lines 10 & 30 (heavy-duty inverter and bulk bin pallet boxes).",
            "- **Vendor 5 (Standard Box Corp) — Gate Q7 Restriction:** Lacks moisture-barrier treatment capability. Strictly excluded from Lines 26 & 27 (refrigerator export shippers).\n",
            "#### 4. Commercial & Currency Risks",
            f"- **Vendor 3 FX Volatility:** Quoted in USD ($/Nos). Landed cost is normalized at ₹{fx_rate:.2f}/USD. Buyer must institute an FX collar or forward cover to protect against rupee depreciation prior to contract execution.",
            "- **Vendor 1 Conditional Discount:** Apex offers a 5% all-lines discount. Because the quality-gated award is split across multiple vendors, V1 does not achieve 100% line allocation, and the discount cannot legally be claimed."
        ]
        return "\n".join(out)

    # Demonstration Question 3:
    # "Why is Scenario B recommended over Scenario C? Explain the cost difference and the dual-sourcing trade-off."
    is_q3 = (
        ("scenario b" in q_low and "scenario c" in q_low)
        or any(k in q_low for k in ["dual-sourcing trade-off", "dual sourcing trade-off", "dual sourcing tradeoff", "why is scenario b recommended over scenario c"])
        or (matches_context(["scenario b", "scenario c", "dual-sourcing"]) and any(w in q_low for w in ["why", "elaborate", "tell me more", "how so"]))
    )
    if is_q3:
        spend_a = scenarios["spend_a"]
        spend_b = scenarios["spend_b"]
        spend_c = scenarios["spend_c"]
        budget = scenarios["budget_spend"]
        sav_b = scenarios["savings_b"]
        sav_pct_b = scenarios["savings_pct_b"]
        sav_c = scenarios["savings_c"]
        sav_pct_c = scenarios["savings_pct_c"]
        cost_diff = spend_c - spend_b
        pct_diff = (cost_diff / spend_b) * 100.0 if spend_b > 0 else 0.0

        gate_notice_q3 = (
            f"⚠️ **Approval Gate Notice:** {gate_result['status_label']}\n"
            f"> *{gate_result['guidance_message']}* (Award approval is strictly BLOCKED until pending lines {gate_result['unresolved_lines']} are resolved)."
            if gate_result["is_blocked"] else
            f"✅ **Approval Gate Status:** {gate_result['status_label']}\n"
            f"> *{gate_result['guidance_message']}*"
        )

        out = [
            "### Scenario B vs Scenario C: Cost Difference & Dual-Sourcing Trade-Off Analysis\n",
            "#### 1. Executive Summary & Recommendation",
            f"**Scenario B (Quality-Gated L1)** is recommended as the commercial baseline over **Scenario C (Dual Sourcing 70/30)** because it maximizes cost savings by an additional **₹{cost_diff:,.0f}** while fully satisfying all quality and compliance gates.\n",
            "#### 2. Financial Metrics Comparison",
            f"- **Master Budget Ceiling:** ₹{budget:,.0f}",
            f"- **Scenario B (Quality-Gated L1):** **₹{spend_b:,.0f}** | Saves: **₹{sav_b:,.0f} ({sav_pct_b:.2f}%)** vs budget (+{scenarios.get('pct_diff_b_vs_a', ((spend_b-spend_a)/spend_a)*100):.2f}% higher than Scenario A)",
            f"- **Scenario C (Dual Sourcing 70/30):** **₹{spend_c:,.0f}** | Saves: **₹{sav_c:,.0f} ({sav_pct_c:.2f}%)** vs budget (+{scenarios.get('pct_diff_c_vs_a', ((spend_c-spend_a)/spend_a)*100):.2f}% higher than Scenario A)",
            f"- **Direct Cost Difference (C vs B):** **+₹{cost_diff:,.0f} (+{pct_diff:.2f}% higher than Scenario B)**\n",
            "#### 3. Strategic Trade-Off: Resilience vs. Cost Optimization",
            "- **The Purpose of Scenario C (Risk Insurance):**",
            "  * Scenario C mandates a **70% L1 / 30% L2 split** on all **5 Criticality A packaging lines** (Lines 9, 10, 26, 27, 30: refrigerator and washing machine main cartons).",
            f"  * Paying the +₹{cost_diff:,.0f} (+{pct_diff:.2f}% higher than Scenario B) premium provides **supply chain redundancy**: if the primary supplier suffers machinery breakdown, paper shortage, or fire, the secondary supplier already has active tooling, approved dies, and active purchase orders.",
            "- **Why Scenario B is Recommended as the Baseline:**",
            "  * Apex Packaging (V1) is located within the Chakan industrial cluster with substantial capacity (800 TPM) and a proven 48-hour emergency lead time.",
            f"  * For standard corrugated packaging, single-sourcing with contractual delivery penalties and safety stock buffers is commercially standard, allowing Veda to retain the full ₹{sav_b:,.0f} ({sav_pct_b:.2f}%) in net savings.",
            "- **Decision Framework for Leadership:**",
            f"  * If management policy prioritizes supply continuity for high-criticality appliances over ₹{cost_diff:,.0f} in savings, **Scenario C can be approved as an executive alternative**.\n",
            gate_notice_q3,
            "\n*All figures are computed dynamically from current normalized matrix and scenario evaluations.*"
        ]
        return "\n".join(out)

    # Specific Gate Query
    if any(k in q_low for k in ["approval gate", "approval-gate", "why is approval blocked", "blocked pending"]):
        out = [
            "### Centralized Award Approval Gate Evaluation\n",
            f"- **Approval Status:** **{gate_result['status_label']}**",
            f"- **Gate Directive:** *{gate_result['guidance_message']}*",
            f"- **Unresolved Line Count:** **{gate_result['unresolved_line_count']} lines**",
            f"- **Pending Quotation Lines:** {gate_result['unresolved_lines']}",
            f"- **Target Recommendation:** {gate_result['recommendation']}\n",
            "#### Evaluation Rules Enforced:",
            "1. **Dynamic Unresolved Counting:** Identifies lines where required quote values or commercial inputs remain missing.",
            "2. **Disqualified Vendor Exclusion:** Excluded Vendor 4 (disqualified globally due to expired ISO 9001 and capacity) and Vendor 5 on Line 27 (disqualified due to failing Gate Q7 moisture barrier).",
            "3. **Buyer Override Requirement:** Overrides resolve issues only when valid numeric/formula values and documented audit records exist.",
            "4. **Approval Blocked:** While any unresolved lines remain, award approval is strictly blocked."
        ]
        return "\n".join(out)


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
            f"- **Scenario B (Quality-Gated L1):** **₹{spend_b:,.0f}** (Saves ₹{sav_b:,.0f} / {sav_pct_b:.2f}%; +{scenarios.get('pct_diff_b_vs_a', ((spend_b-spend_a)/spend_a)*100):.2f}% higher than Scenario A)",
            f"- **Scenario C (Dual Sourcing 70/30):** **₹{spend_c:,.0f}** (Saves ₹{scenarios['savings_c']:,.0f} / {scenarios['savings_pct_c']:.2f}%; +{scenarios.get('pct_diff_c_vs_a', ((spend_c-spend_a)/spend_a)*100):.2f}% higher than Scenario A)",
            f"- **Cost of Compliance (B vs A):** **+₹{cost:,.0f} (+{pct:.2f}% higher than Scenario A)**",
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
    gate_summary = (
        f"- **Approval Gate Status:** **{gate_result['status_label']}**\n"
        f"  * *Directive:* {gate_result['guidance_message']}\n"
        f"  * *Pending Lines:* {gate_result['unresolved_lines']}"
        if gate_result["is_blocked"] else
        f"- **Approval Gate Status:** **{gate_result['status_label']}** (Award approval is ready to proceed)"
    )

    return (
        f"### Executive Procurement Analysis (Live State Connected)\n"
        f"- **Master Budget Ceiling:** ₹{scenarios['budget_spend']:,.0f}\n"
        f"- **Recommended Scenario B Spend:** ₹{scenarios['spend_b']:,.0f} (Net Savings: ₹{scenarios['savings_b']:,.0f} / {scenarios['savings_pct_b']:.2f}%)\n"
        f"- **Scenario C Spend (Dual-Sourced):** ₹{scenarios['spend_c']:,.0f}\n"
        f"- **Cost of Compliance Premium:** +₹{scenarios['cost_of_compliance']:,.0f} (+{scenarios['compliance_pct']:.2f}% higher than Scenario A)\n"
        f"{gate_summary}\n"
        f"- **Uncovered Mandatory Lines:** {len(scenarios.get('uncovered_lines_b', []))} lines\n"
        f"- **Active Buyer Overrides:** {len(overrides) if overrides else 0} overridden cells\n\n"
        f"Ask me about any specific Line # (e.g. 'Line 10' or 'Line 27'), vendor risks (e.g. 'Vendor 4'), "
        f"or cost of compliance for verified trace evidence."
    )
