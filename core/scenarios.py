"""
Dynamic award scenarios optimization engine.
Calculates:
- Master Budget
- Scenario A: Unconstrained L1 (lowest quoted landed cost)
- Scenario B: Quality-Gated L1 (lowest cost among eligible vendors; flags uncovered lines)
- Scenario C: Quality-Gated + Dual Sourcing 70/30 on Criticality A lines
- Cost of Compliance and savings metrics
- Max supplier share constraints
"""

import re
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from core.eligibility import VendorQualification, is_vendor_eligible_for_line, _extract_vendor_id
from core.config import ELIGIBLE_BIDDER_COLUMNS, VENDORS

# Explicit patterns that must NEVER enter candidate bidder columns
EXCLUDED_COLUMN_PATTERNS = [
    "raw value", "raw uom", "raw", "uom", "status", "unresolved reason",
    "reason", "citation", "trust flag", "trust", "audit", "flag",
    "line #", "item code", "description", "est. qty", "delivery location",
    "criticality", "budget price", "est. wt (kg)", "l1_a", "l1_price_a", "l1_vendor_a"
]


def _is_excluded_column(col_name: str) -> bool:
    """Checks if a column name matches any raw extraction, metadata, citation, reason, or audit pattern."""
    s = str(col_name).strip().lower()
    for pattern in EXCLUDED_COLUMN_PATTERNS:
        if pattern in s:
            return True
    return False


def _get_vendor_columns(df_matrix: pd.DataFrame, qualifications: Optional[Dict[str, VendorQualification]] = None) -> List[str]:
    """
    Identifies the exact normalized vendor quote columns from the matrix.
    Explicitly excludes all raw extraction, citation, status, trust, UOM, reason, and audit columns.
    Only normalized vendor price columns may participate in award calculations:
    - V1 (Apex)
    - V2 (PackTech)
    - V3 (Global USD)
    - V4 (Balaji)
    - V5 (Standard Box)
    """
    # 1. Primary rule: check for exact configured eligible bidder columns present in the matrix
    configured_present = [c for c in ELIGIBLE_BIDDER_COLUMNS if c in df_matrix.columns]
    if configured_present:
        return configured_present

    # 2. Strict filtering for custom/dynamic test matrices
    candidates = []
    for c in df_matrix.columns:
        c_str = str(c).strip()
        if _is_excluded_column(c_str):
            continue
        v_id = _extract_vendor_id(c_str)
        if qualifications and v_id in qualifications:
            candidates.append(c_str)
        elif v_id in VENDORS:
            candidates.append(c_str)
        elif re.match(r"^V\d+", c_str, re.IGNORECASE):
            candidates.append(c_str)
    return candidates


def _evaluate_and_apply_scenario_discounts(
    scenario_name: str,
    line_allocations: List[Dict[str, Any]],
    vendor_spends: Dict[str, float],
    vendor_cols: List[str],
    conditional_discounts: Optional[Dict[str, Dict[str, Any]]],
    total_rfx_lines: int,
    is_dual_source: bool = False
) -> Tuple[List[Dict[str, Any]], Dict[str, float], float, Dict[str, Dict[str, Any]]]:
    """
    Evaluates conditional discounts independently for a given award scenario.
    Enforces strict rules:
    - An all-lines discount is applied ONLY when the vendor receives 100% of all required RFx lines.
    - If the award is split across multiple vendors, or any required line is uncovered,
      the all-lines discount is NEVER applied to any portion of that vendor's award.
    - Recalculates vendor totals, line-level prices, line spends, and scenario spend after discount eligibility is determined.
    - Never applies the same discount twice.
    - Returns: (updated_allocations, updated_vendor_spends, total_scenario_spend, discounts_evaluated)
    """
    allocs = [dict(a) for a in line_allocations]
    v_spends = dict(vendor_spends)
    discounts_evaluated: Dict[str, Dict[str, Any]] = {}

    if not conditional_discounts:
        total_spend = round(float(sum(a.get("Line Spend (₹)", 0.0) for a in allocs)), 2)
        return allocs, v_spends, total_spend, {}

    total_scenario_spend = float(sum(a.get("Line Spend (₹)", 0.0) for a in allocs))

    for v_key, disc_info in conditional_discounts.items():
        matched_v = next((c for c in vendor_cols if v_key in c or _extract_vendor_id(c) == v_key), None)
        if not matched_v:
            continue

        pct = float(disc_info.get("discount_pct", 0.0))
        cond_type = str(disc_info.get("condition_type", "all_lines")).strip().lower()
        desc = disc_info.get("description", "Conditional discount")
        thresh = float(disc_info.get("threshold", 0.0))

        # Check line allocations for matched_v
        v_full_lines = 0
        v_partial_lines = 0
        other_awarded_vendors = set()
        uncovered_lines = 0

        for a in allocs:
            awarded = a.get("Awarded Vendor")
            if awarded == matched_v:
                v_full_lines += 1
            elif awarded == "UNCOVERED":
                uncovered_lines += 1
            elif awarded:
                other_awarded_vendors.add(awarded)
            else:
                # Scenario C (Dual sourcing)
                l1_v = a.get("L1 Vendor")
                l2_v = a.get("L2 Vendor")
                if l1_v == "UNCOVERED" or l2_v == "UNCOVERED":
                    uncovered_lines += 1
                elif l1_v == matched_v and l2_v in ["-", "None (Single Eligible)", None]:
                    v_full_lines += 1
                elif l1_v == matched_v or l2_v == matched_v:
                    v_partial_lines += 1
                    if l1_v and l1_v != matched_v and l1_v != "UNCOVERED":
                        other_awarded_vendors.add(l1_v)
                    if l2_v and l2_v != matched_v and l2_v not in ["-", "None (Single Eligible)", "UNCOVERED", None]:
                        other_awarded_vendors.add(l2_v)
                else:
                    if l1_v and l1_v != "UNCOVERED":
                        other_awarded_vendors.add(l1_v)
                    if l2_v and l2_v not in ["-", "None (Single Eligible)", "UNCOVERED", None]:
                        other_awarded_vendors.add(l2_v)

        orig_spend = v_spends.get(matched_v, 0.0)

        # Evaluate condition
        condition_met = False
        unmet_reason = ""

        if cond_type == "all_lines":
            if v_full_lines == total_rfx_lines and uncovered_lines == 0 and len(other_awarded_vendors) == 0 and v_partial_lines == 0:
                condition_met = True
            else:
                other_names = ", ".join(sorted([_extract_vendor_id(v) for v in other_awarded_vendors])) or "other vendors"
                if uncovered_lines > 0:
                    unmet_reason = f"Won {v_full_lines} of {total_rfx_lines} lines ({uncovered_lines} line(s) uncovered; award not 100%). All-lines discount cannot be applied."
                else:
                    unmet_reason = f"Won {v_full_lines} of {total_rfx_lines} lines (Split award: remaining lines awarded to {other_names}). All-lines discount cannot be applied."

        elif cond_type == "spend_threshold":
            if orig_spend >= thresh:
                condition_met = True
            else:
                unmet_reason = f"Spend ₹{orig_spend:,.2f} is below required threshold of ₹{thresh:,.2f}"

        elif cond_type == "share_threshold":
            share = (orig_spend / total_scenario_spend) if total_scenario_spend > 0 else 0.0
            if share >= thresh:
                condition_met = True
            else:
                unmet_reason = f"Spend share {share*100:.1f}% is below required threshold of {thresh*100:.1f}%"

        elif cond_type == "line_count_threshold":
            target_lines = int(thresh) if thresh > 0 else total_rfx_lines
            if v_full_lines >= target_lines:
                condition_met = True
            else:
                unmet_reason = f"Won {v_full_lines} lines below required threshold of {target_lines} lines"

        elif cond_type == "unconditional":
            condition_met = True

        else:
            unmet_reason = f"Unknown condition type '{cond_type}'"

        if condition_met and pct > 0:
            disc_amount = round(orig_spend * pct, 2)
            for a in allocs:
                if a.get("Awarded Vendor") == matched_v:
                    base_p = a.get("Original Quoted Price", a.get("Landed Price (₹)", 0.0))
                    a["Original Quoted Price"] = base_p
                    a["Eligible Discount %"] = pct
                    new_p = round(base_p * (1.0 - pct), 2)
                    a["Landed Price (₹)"] = new_p
                    a["Line Spend (₹)"] = round(new_p * a["Qty"], 2)
                    a["Discount Status"] = f"Applied {pct*100:.1f}% discount ({desc})"
                elif a.get("L1 Vendor") == matched_v:
                    base_p = a.get("L1 Original Price", a.get("L1 Price", 0.0))
                    a["L1 Original Price"] = base_p
                    new_p = round(base_p * (1.0 - pct), 2)
                    a["L1 Price"] = new_p
                    p2 = a.get("L2 Price", 0.0)
                    q1 = a.get("L1 Qty", 0.0)
                    q2 = a.get("L2 Qty", 0.0)
                    a["Line Spend (₹)"] = round(new_p * q1 + p2 * q2, 2)
                elif a.get("L2 Vendor") == matched_v:
                    base_p = a.get("L2 Original Price", a.get("L2 Price", 0.0))
                    a["L2 Original Price"] = base_p
                    new_p = round(base_p * (1.0 - pct), 2)
                    a["L2 Price"] = new_p
                    p1 = a.get("L1 Price", 0.0)
                    q1 = a.get("L1 Qty", 0.0)
                    q2 = a.get("L2 Qty", 0.0)
                    a["Line Spend (₹)"] = round(p1 * q1 + new_p * q2, 2)

            v_recalc = 0.0
            for a in allocs:
                if a.get("Awarded Vendor") == matched_v:
                    v_recalc += a["Line Spend (₹)"]
                elif a.get("L1 Vendor") == matched_v:
                    v_recalc += a["L1 Price"] * a.get("L1 Qty", 0.0)
                elif a.get("L2 Vendor") == matched_v:
                    v_recalc += a["L2 Price"] * a.get("L2 Qty", 0.0)

            v_spends[matched_v] = round(v_recalc, 2)
            final_award = v_spends[matched_v]

            discounts_evaluated[matched_v] = {
                "vendor": matched_v,
                "vendor_id": _extract_vendor_id(matched_v),
                "condition_type": cond_type,
                "description": desc,
                "original_amount": orig_spend,
                "eligible_discount": f"{pct*100:.1f}%",
                "discount_pct": pct,
                "discount_amount": disc_amount,
                "discount_applied": disc_amount,
                "discount_not_applied_reason": None,
                "final_award_amount": final_award,
                "applied": True,
                "status": f"Applied {pct*100:.1f}% discount ({desc})"
            }
        else:
            discounts_evaluated[matched_v] = {
                "vendor": matched_v,
                "vendor_id": _extract_vendor_id(matched_v),
                "condition_type": cond_type,
                "description": desc,
                "original_amount": orig_spend,
                "eligible_discount": f"{pct*100:.1f}%",
                "discount_pct": pct,
                "discount_amount": 0.0,
                "discount_applied": 0.0,
                "discount_not_applied_reason": unmet_reason,
                "final_award_amount": orig_spend,
                "applied": False,
                "status": f"NOT applied: {unmet_reason}"
            }

    recalc_scenario_spend = round(float(sum(a.get("Line Spend (₹)", 0.0) for a in allocs)), 2)
    return allocs, v_spends, recalc_scenario_spend, discounts_evaluated


def calculate_award_scenarios(
    df_matrix: pd.DataFrame,
    qualifications: Dict[str, VendorQualification],
    max_single_vendor_share: Optional[float] = None,
    conditional_discounts: Optional[Dict[str, Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Computes all award scenarios dynamically based on current matrix values and qualifications.
    Enforces:
    - Quality gating (disqualified and pending review vendors are NEVER awarded lines).
    - Mandatory line coverage (uncovered lines explicitly flagged).
    - Maximum supplier-share restrictions when specified.
    - Conditional discounts applied only when their conditions are satisfied.
    - Dynamic recalculation on buyer overrides.
    """
    df = df_matrix.copy()
    if "Line #" in df.columns:
        df = df[df["Line #"].notna()].copy()
    vendor_cols = _get_vendor_columns(df, qualifications)

    for col in vendor_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
        # Ensure non-positive, zero, or missing values cannot participate in L1 selection
        df.loc[df[col] <= 0, col] = np.nan
    df["Est. Qty"] = pd.to_numeric(df["Est. Qty"], errors="coerce").fillna(0)
    df["Budget Price"] = pd.to_numeric(df["Budget Price"], errors="coerce").fillna(0)

    # Master Budget
    budget_spend = float((df["Budget Price"] * df["Est. Qty"]).sum())

    # 1. SCENARIO A: Unconstrained L1
    has_valid_quotes = df[vendor_cols].notna().any(axis=1)
    df["L1_Price_A"] = df[vendor_cols].min(axis=1, skipna=True)
    df["L1_Vendor_A"] = pd.Series(index=df.index, dtype=object)
    if has_valid_quotes.any():
        df.loc[has_valid_quotes, "L1_Vendor_A"] = df.loc[has_valid_quotes, vendor_cols].idxmin(axis=1, skipna=True)

    a_line_allocations = []
    a_vendor_spends = {v: 0.0 for v in vendor_cols}
    for _, row in df.iterrows():
        l_no = int(row["Line #"])
        item_code = str(row["Item Code"])
        desc = str(row.get("Description", ""))
        qty = float(row["Est. Qty"])
        best_v = row["L1_Vendor_A"]
        best_p = row["L1_Price_A"]
        if pd.notna(best_v) and pd.notna(best_p):
            line_spend = float(best_p * qty)
            a_vendor_spends[best_v] += line_spend
            a_line_allocations.append({
                "Line #": l_no,
                "Item Code": item_code,
                "Description": desc,
                "Awarded Vendor": best_v,
                "Landed Price (₹)": float(best_p),
                "Qty": qty,
                "Line Spend (₹)": line_spend,
                "Status": "Awarded"
            })
        else:
            budget_p = float(row["Budget Price"])
            a_line_allocations.append({
                "Line #": l_no,
                "Item Code": item_code,
                "Description": desc,
                "Awarded Vendor": "UNCOVERED",
                "Landed Price (₹)": budget_p,
                "Qty": qty,
                "Line Spend (₹)": float(budget_p * qty),
                "Status": "UNCOVERED"
            })

    # 2. SCENARIO B: Quality-Gated L1
    # 3. SCENARIO C: Quality-Gated + Dual Sourcing (70/30 on Criticality A)
    b_line_allocations = []
    c_line_allocations = []
    uncovered_lines_b = []
    uncovered_lines_c = []
    risks_b = []
    risks_c = []

    b_vendor_spends = {v: 0.0 for v in vendor_cols}
    c_vendor_spends = {v: 0.0 for v in vendor_cols}
    b_eligible_quotes_per_line = {}

    for _, row in df.iterrows():
        l_no = int(row["Line #"])
        item_code = str(row["Item Code"])
        desc = str(row.get("Description", ""))
        qty = float(row["Est. Qty"])
        budget_p = float(row["Budget Price"])
        crit = str(row.get("Criticality", "C")).strip().upper()

        # Find eligible vendors who quoted a valid price
        # Disqualified or Pending Review vendors are strictly excluded
        eligible_quotes = []
        for v_col in vendor_cols:
            v_id = _extract_vendor_id(v_col)
            if is_vendor_eligible_for_line(v_id, l_no, qualifications):
                val = row[v_col]
                if pd.notna(val) and val > 0:
                    eligible_quotes.append((v_col, float(val)))

        # Sort by price ascending
        eligible_quotes.sort(key=lambda x: x[1])
        b_eligible_quotes_per_line[l_no] = eligible_quotes

        # Evaluate Scenario B
        if eligible_quotes:
            best_v, best_p = eligible_quotes[0]
            line_spend_b = best_p * qty
            b_vendor_spends[best_v] += line_spend_b
            b_line_allocations.append({
                "Line #": l_no,
                "Item Code": item_code,
                "Description": desc,
                "Criticality": crit,
                "Awarded Vendor": best_v,
                "Landed Price (₹)": best_p,
                "Qty": qty,
                "Line Spend (₹)": line_spend_b,
                "Status": "Awarded"
            })
        else:
            # Mandatory Line is Uncovered! Never allocate to disqualified vendor
            uncovered_lines_b.append(l_no)
            line_spend_b = budget_p * qty  # fallback to budget placeholder with clear flag
            b_line_allocations.append({
                "Line #": l_no,
                "Item Code": item_code,
                "Description": desc,
                "Criticality": crit,
                "Awarded Vendor": "UNCOVERED",
                "Landed Price (₹)": budget_p,
                "Qty": qty,
                "Line Spend (₹)": line_spend_b,
                "Status": "UNCOVERED (No eligible vendor quoted)"
            })
            risks_b.append(f"Line {l_no} ({item_code}): No eligible vendor available. Mandatory line is UNCOVERED.")

        # Evaluate Scenario C (Dual Sourcing 70/30 on Criticality A lines)
        if not eligible_quotes:
            uncovered_lines_c.append(l_no)
            c_line_allocations.append({
                "Line #": l_no,
                "Item Code": item_code,
                "Description": desc,
                "Criticality": crit,
                "L1 Vendor": "UNCOVERED",
                "L1 Qty": 0,
                "L1 Price": 0.0,
                "L2 Vendor": "UNCOVERED",
                "L2 Qty": 0,
                "L2 Price": 0.0,
                "Line Spend (₹)": budget_p * qty,
                "Status": "UNCOVERED"
            })
            risks_c.append(f"Line {l_no} ({item_code}): No eligible vendor available. Mandatory line is UNCOVERED.")
        elif crit == "A":
            if len(eligible_quotes) >= 2:
                v1, p1 = eligible_quotes[0]
                v2, p2 = eligible_quotes[1]
                q1 = 0.70 * qty
                q2 = 0.30 * qty
                s1 = q1 * p1
                s2 = q2 * p2
                c_vendor_spends[v1] += s1
                c_vendor_spends[v2] += s2
                c_line_allocations.append({
                    "Line #": l_no,
                    "Item Code": item_code,
                    "Description": desc,
                    "Criticality": crit,
                    "L1 Vendor": v1,
                    "L1 Qty": q1,
                    "L1 Price": p1,
                    "L2 Vendor": v2,
                    "L2 Qty": q2,
                    "L2 Price": p2,
                    "Line Spend (₹)": s1 + s2,
                    "Status": "Dual Sourced (70/30)"
                })
            else:
                # Single eligible supplier on a critical line
                v1, p1 = eligible_quotes[0]
                s1 = qty * p1
                c_vendor_spends[v1] += s1
                c_line_allocations.append({
                    "Line #": l_no,
                    "Item Code": item_code,
                    "Description": desc,
                    "Criticality": crit,
                    "L1 Vendor": v1,
                    "L1 Qty": qty,
                    "L1 Price": p1,
                    "L2 Vendor": "None (Single Eligible)",
                    "L2 Qty": 0,
                    "L2 Price": 0.0,
                    "Line Spend (₹)": s1,
                    "Status": "Single Source (Criticality A Risk)"
                })
                risks_c.append(f"Critical Line {l_no} ({item_code}): Only 1 eligible supplier ({v1}). Cannot dual-source.")
        else:
            # Non-critical lines: 100% to best eligible vendor
            best_v, best_p = eligible_quotes[0]
            line_spend_c = best_p * qty
            c_vendor_spends[best_v] += line_spend_c
            c_line_allocations.append({
                "Line #": l_no,
                "Item Code": item_code,
                "Description": desc,
                "Criticality": crit,
                "L1 Vendor": best_v,
                "L1 Qty": qty,
                "L1 Price": best_p,
                "L2 Vendor": "-",
                "L2 Qty": 0,
                "L2 Price": 0.0,
                "Line Spend (₹)": line_spend_c,
                "Status": "100% L1 Award"
            })

    # ENFORCE MAXIMUM SUPPLIER SHARE RESTRICTIONS (IF CONFIGURED)
    if max_single_vendor_share is not None and 0.0 < max_single_vendor_share < 1.0:
        spend_b_init = float(sum(item["Line Spend (₹)"] for item in b_line_allocations))
        if spend_b_init > 0:
            cap_limit = max_single_vendor_share * spend_b_init
            max_iterations = 50
            iteration = 0
            while iteration < max_iterations:
                iteration += 1
                # Find vendor exceeding cap
                over_vendors = [v for v, s in b_vendor_spends.items() if s > cap_limit + 1.0]
                if not over_vendors:
                    break

                target_v = max(over_vendors, key=lambda v: b_vendor_spends[v])
                # Find best line to reallocate from target_v with minimal cost increase
                best_swap = None
                min_cost_delta = float("inf")

                for alloc_idx, alloc in enumerate(b_line_allocations):
                    if alloc["Awarded Vendor"] == target_v:
                        l_num = alloc["Line #"]
                        l_qty = alloc["Qty"]
                        quotes = b_eligible_quotes_per_line.get(l_num, [])
                        # Look for alternate eligible vendor not exceeding cap
                        for alt_v, alt_p in quotes:
                            if alt_v != target_v:
                                delta = (alt_p - alloc["Landed Price (₹)"]) * l_qty
                                if delta < min_cost_delta:
                                    min_cost_delta = delta
                                    best_swap = (alloc_idx, alt_v, alt_p, delta)

                if best_swap:
                    a_idx, new_v, new_p, delta = best_swap
                    old_v = b_line_allocations[a_idx]["Awarded Vendor"]
                    old_spend = b_line_allocations[a_idx]["Line Spend (₹)"]
                    new_spend = new_p * b_line_allocations[a_idx]["Qty"]

                    b_vendor_spends[old_v] -= old_spend
                    b_vendor_spends[new_v] += new_spend

                    b_line_allocations[a_idx]["Awarded Vendor"] = new_v
                    b_line_allocations[a_idx]["Landed Price (₹)"] = new_p
                    b_line_allocations[a_idx]["Line Spend (₹)"] = new_spend
                    b_line_allocations[a_idx]["Status"] = f"Awarded (Capped: Reallocated to satisfy {max_single_vendor_share*100:.0f}% share restriction)"
                else:
                    risks_b.append(f"Supplier share cap ({max_single_vendor_share*100:.0f}%) reached constraint limit for {target_v}: no further alternate eligible quotes available.")
                    break

    total_rfx_lines = len(df)

    # EVALUATE CONDITIONAL DISCOUNTS INDEPENDENTLY FOR SCENARIO A, SCENARIO B, AND SCENARIO C
    a_line_allocations, a_vendor_spends, spend_a, discounts_evaluated_a = _evaluate_and_apply_scenario_discounts(
        scenario_name="Scenario A",
        line_allocations=a_line_allocations,
        vendor_spends=a_vendor_spends,
        vendor_cols=vendor_cols,
        conditional_discounts=conditional_discounts,
        total_rfx_lines=total_rfx_lines,
        is_dual_source=False
    )

    b_line_allocations, b_vendor_spends, spend_b, discounts_evaluated_b = _evaluate_and_apply_scenario_discounts(
        scenario_name="Scenario B",
        line_allocations=b_line_allocations,
        vendor_spends=b_vendor_spends,
        vendor_cols=vendor_cols,
        conditional_discounts=conditional_discounts,
        total_rfx_lines=total_rfx_lines,
        is_dual_source=False
    )

    c_line_allocations, c_vendor_spends, spend_c, discounts_evaluated_c = _evaluate_and_apply_scenario_discounts(
        scenario_name="Scenario C",
        line_allocations=c_line_allocations,
        vendor_spends=c_vendor_spends,
        vendor_cols=vendor_cols,
        conditional_discounts=conditional_discounts,
        total_rfx_lines=total_rfx_lines,
        is_dual_source=True
    )

    savings_a = budget_spend - spend_a
    savings_b = budget_spend - spend_b
    savings_c = budget_spend - spend_c

    savings_pct_a = (savings_a / budget_spend) * 100.0 if budget_spend > 0 else 0.0
    savings_pct_b = (savings_b / budget_spend) * 100.0 if budget_spend > 0 else 0.0
    savings_pct_c = (savings_c / budget_spend) * 100.0 if budget_spend > 0 else 0.0

    cost_of_compliance = spend_b - spend_a
    compliance_pct = (cost_of_compliance / spend_a) * 100.0 if spend_a > 0 else 0.0

    # Vendor spend shares for Scenario A
    vendor_shares_a = {}
    for v, s in a_vendor_spends.items():
        if spend_a > 0 and s > 0:
            vendor_shares_a[v] = {
                "spend": s,
                "share_pct": (s / spend_a) * 100.0
            }

    # Vendor spend shares for Scenario B
    vendor_shares_b = {}
    for v, s in b_vendor_spends.items():
        if spend_b > 0 and s > 0:
            vendor_shares_b[v] = {
                "spend": s,
                "share_pct": (s / spend_b) * 100.0
            }

    # Vendor spend shares for Scenario C
    vendor_shares_c = {}
    for v, s in c_vendor_spends.items():
        if spend_c > 0 and s > 0:
            vendor_shares_c[v] = {
                "spend": s,
                "share_pct": (s / spend_c) * 100.0
            }

    return {
        "budget_spend": budget_spend,
        "spend_a": spend_a,
        "spend_b": spend_b,
        "spend_c": spend_c,
        "savings_a": savings_a,
        "savings_b": savings_b,
        "savings_c": savings_c,
        "savings_pct_a": savings_pct_a,
        "savings_pct_b": savings_pct_b,
        "savings_pct_c": savings_pct_c,
        "cost_of_compliance": cost_of_compliance,
        "compliance_pct": compliance_pct,
        "uncovered_lines_b": uncovered_lines_b,
        "uncovered_lines_c": uncovered_lines_c,
        "a_line_allocations": a_line_allocations,
        "b_line_allocations": b_line_allocations,
        "c_line_allocations": c_line_allocations,
        "vendor_shares_a": vendor_shares_a,
        "vendor_shares_b": vendor_shares_b,
        "vendor_shares_c": vendor_shares_c,
        "risks_b": risks_b,
        "risks_c": risks_c,
        "discounts_evaluated": discounts_evaluated_b,
        "discounts_evaluated_a": discounts_evaluated_a,
        "discounts_evaluated_b": discounts_evaluated_b,
        "discounts_evaluated_c": discounts_evaluated_c,
        "max_supplier_share_enforced": max_single_vendor_share
    }


def evaluate_award_approval_gate(
    df_matrix: pd.DataFrame,
    qualifications: Dict[str, VendorQualification],
    overrides: Optional[List[Any]] = None
) -> Dict[str, Any]:
    """
    Centralized award approval gate function.
    Reused across Overview, Award screen, and Executive Summary.

    Rules:
    1. Count unresolved quotation lines dynamically.
    2. Unresolved means a required quote value or required commercial input remains unresolved.
    3. Exclude genuinely ineligible or disqualified vendors from the unresolved count.
    4. A buyer override must resolve the relevant issue only when a valid override and audit record exist.
    5. If unresolved items remain, approval must be blocked.
       Display: "Award on Scenario B — BLOCKED pending X unresolved lines."
       Also display: "Buyer clarification or documented override required before award approval."
    6. When no blocking unresolved items remain, display the approval-ready state.
    7. Do not change the actual award recommendation merely to bypass the gate.
    """
    vendor_cols = _get_vendor_columns(df_matrix, qualifications)

    # Build map of valid buyer overrides that resolve quotes
    valid_overrides = {}
    if overrides:
        for o in overrides:
            l_num = getattr(o, "line_no", None) if hasattr(o, "line_no") else (o.get("line_no") if isinstance(o, dict) else None)
            v_col = getattr(o, "vendor_col", None) if hasattr(o, "vendor_col") else (o.get("vendor_col") if isinstance(o, dict) else None)
            corr_val = getattr(o, "corrected_value", None) if hasattr(o, "corrected_value") else (o.get("corrected_value") if isinstance(o, dict) else None)
            reason = getattr(o, "reason", None) if hasattr(o, "reason") else (o.get("reason") if isinstance(o, dict) else None)

            is_resolving = (
                corr_val is not None
                and not pd.isna(corr_val)
                and str(corr_val).strip().upper() != "UNRESOLVED"
                and str(corr_val).strip() != ""
            )
            has_audit = bool(reason and str(reason).strip())

            if is_resolving and has_audit and l_num is not None and v_col:
                v_id = _extract_vendor_id(str(v_col))
                valid_overrides[(int(l_num), v_id)] = o

    unresolved_lines = set()
    unresolved_details = []

    for _, row in df_matrix.iterrows():
        raw_l = row.get("Line #")
        if pd.isna(raw_l):
            continue
        try:
            l_no = int(raw_l)
        except (ValueError, TypeError):
            continue

        for col in vendor_cols:
            v_id = _extract_vendor_id(col)

            # Rule 3: Exclude genuinely ineligible or disqualified vendors from the unresolved count
            if not is_vendor_eligible_for_line(v_id, l_no, qualifications):
                continue

            # Rule 4: A buyer override must resolve the relevant issue only when a valid override and audit record exist
            if (l_no, v_id) in valid_overrides:
                continue

            # Rule 2: Unresolved means a required quote value or required commercial input remains unresolved
            val = row.get(col)
            status_val = str(row.get(f"{v_id} Status", "")).strip().lower()
            cite_val = str(row.get(f"{v_id} Citation", "")).strip().lower()
            reason_val = str(row.get(f"{v_id} Unresolved Reason", "")).strip().lower()
            trust_val = str(row.get(f"{v_id} Trust Flag", "")).strip().lower()

            is_unres = False
            unres_msg = ""
            if status_val in ["unresolved", "needs review"]:
                is_unres = True
                unres_msg = str(row.get(f"{v_id} Unresolved Reason") or row.get(f"{v_id} Citation") or "Unresolved quote status")
            elif "unresolved" in cite_val:
                is_unres = True
                unres_msg = str(row.get(f"{v_id} Citation"))
            elif "unresolved" in reason_val:
                is_unres = True
                unres_msg = str(row.get(f"{v_id} Unresolved Reason"))
            elif "unresolved" in trust_val:
                is_unres = True
                unres_msg = f"{col} flagged as UNRESOLVED"
            elif pd.isna(val) or val is None:
                if "unresolved" in cite_val or "unresolved" in reason_val or status_val in ["unresolved", "needs review"]:
                    is_unres = True
                    unres_msg = str(row.get(f"{v_id} Unresolved Reason") or row.get(f"{v_id} Citation") or "Missing required quote value")

            if is_unres:
                unresolved_lines.add(l_no)
                unresolved_details.append({
                    "line_no": l_no,
                    "item_code": row.get("Item Code", f"CP-{l_no:03d}"),
                    "description": row.get("Description", ""),
                    "vendor_id": v_id,
                    "vendor_col": col,
                    "reason": unres_msg
                })

    unres_count = len(unresolved_lines)
    is_blocked = unres_count > 0

    if is_blocked:
        status_label = f"Award on Scenario B — BLOCKED pending {unres_count} unresolved lines."
        guidance_message = "Buyer clarification or documented override required before award approval."
    else:
        status_label = "Award on Scenario B — Approval Ready"
        guidance_message = "All required quotation lines resolved and verified. Ready for commercial award approval."

    return {
        "is_blocked": is_blocked,
        "unresolved_line_count": unres_count,
        "unresolved_lines": sorted(list(unresolved_lines)),
        "unresolved_details": unresolved_details,
        "status_label": status_label,
        "guidance_message": guidance_message,
        "recommendation": "Award on Scenario B (Quality-Gated L1)",
        "target_scenario": "Scenario B"
    }
