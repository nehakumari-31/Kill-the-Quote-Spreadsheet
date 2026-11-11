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

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional
from core.eligibility import VendorQualification, is_vendor_eligible_for_line, _extract_vendor_id


def _get_vendor_columns(df_matrix: pd.DataFrame, qualifications: Dict[str, VendorQualification]) -> List[str]:
    """Dynamically identifies vendor quote columns from the matrix without hardcoding vendor names."""
    excluded = {
        "Line #", "Item Code", "Description", "Est. Qty", "Delivery Location",
        "Criticality", "Budget Price", "Est. Wt (kg)", "V5 Trust Flag",
        "L1_A", "L1_Price_A", "L1_Vendor_A"
    }
    candidates = [
        c for c in df_matrix.columns
        if c not in excluded and not str(c).endswith("Citation") and not str(c).endswith("Trust Flag")
    ]
    # Filter or prioritize columns matching known vendors from qualifications
    matched = [c for c in candidates if _extract_vendor_id(c) in qualifications]
    return matched if matched else candidates


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
    df["Est. Qty"] = pd.to_numeric(df["Est. Qty"], errors="coerce").fillna(0)
    df["Budget Price"] = pd.to_numeric(df["Budget Price"], errors="coerce").fillna(0)

    # Master Budget
    budget_spend = float((df["Budget Price"] * df["Est. Qty"]).sum())

    # 1. SCENARIO A: Unconstrained L1
    df["L1_Price_A"] = df[vendor_cols].min(axis=1, skipna=True)
    df["L1_Vendor_A"] = df[vendor_cols].idxmin(axis=1, skipna=True)
    spend_a = float((df["L1_Price_A"] * df["Est. Qty"]).sum())

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

    spend_b = float(sum(item["Line Spend (₹)"] for item in b_line_allocations))
    spend_c = float(sum(item["Line Spend (₹)"] for item in c_line_allocations))

    # EVALUATE CONDITIONAL DISCOUNTS (APPLIED ONLY WHEN CONDITIONS SATISFIED)
    discounts_evaluated = {}
    if conditional_discounts:
        total_covered_lines_b = len([a for a in b_line_allocations if a["Awarded Vendor"] != "UNCOVERED"])
        for v_key, disc_info in conditional_discounts.items():
            # Match vendor column
            matched_v = next((c for c in vendor_cols if v_key in c or _extract_vendor_id(c) == v_key), None)
            if not matched_v:
                continue

            pct = float(disc_info.get("discount_pct", 0.0))
            cond_type = str(disc_info.get("condition_type", "all_lines")).lower()
            desc = disc_info.get("description", "Conditional discount")
            thresh = float(disc_info.get("threshold", 0.0))

            v_lines_won = len([a for a in b_line_allocations if a["Awarded Vendor"] == matched_v])
            v_curr_spend = b_vendor_spends.get(matched_v, 0.0)

            # Evaluate condition
            condition_met = False
            unmet_reason = ""
            if cond_type == "all_lines":
                if v_lines_won == total_covered_lines_b and total_covered_lines_b > 0:
                    condition_met = True
                else:
                    unmet_reason = f"Won {v_lines_won} of {total_covered_lines_b} lines (Split award)"
            elif cond_type == "spend_threshold":
                if v_curr_spend >= thresh:
                    condition_met = True
                else:
                    unmet_reason = f"Spend ₹{v_curr_spend:,.0f} below ₹{thresh:,.0f} threshold"
            elif cond_type == "share_threshold":
                share = (v_curr_spend / spend_b) if spend_b > 0 else 0.0
                if share >= thresh:
                    condition_met = True
                else:
                    unmet_reason = f"Share {share*100:.1f}% below {thresh*100:.1f}% threshold"

            if condition_met and pct > 0:
                disc_amount = v_curr_spend * pct
                b_vendor_spends[matched_v] -= disc_amount
                spend_b -= disc_amount
                discounts_evaluated[matched_v] = {
                    "applied": True,
                    "discount_pct": pct,
                    "discount_amount": disc_amount,
                    "description": desc,
                    "status": f"Applied {pct*100:.1f}% discount ({desc})"
                }
            else:
                discounts_evaluated[matched_v] = {
                    "applied": False,
                    "discount_pct": pct,
                    "discount_amount": 0.0,
                    "description": desc,
                    "status": f"NOT applied: {unmet_reason}"
                }

    savings_a = budget_spend - spend_a
    savings_b = budget_spend - spend_b
    savings_c = budget_spend - spend_c

    savings_pct_a = (savings_a / budget_spend) * 100.0 if budget_spend > 0 else 0.0
    savings_pct_b = (savings_b / budget_spend) * 100.0 if budget_spend > 0 else 0.0
    savings_pct_c = (savings_c / budget_spend) * 100.0 if budget_spend > 0 else 0.0

    cost_of_compliance = spend_b - spend_a
    compliance_pct = (cost_of_compliance / spend_a) * 100.0 if spend_a > 0 else 0.0

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
        "b_line_allocations": b_line_allocations,
        "c_line_allocations": c_line_allocations,
        "vendor_shares_b": vendor_shares_b,
        "vendor_shares_c": vendor_shares_c,
        "risks_b": risks_b,
        "risks_c": risks_c,
        "discounts_evaluated": discounts_evaluated,
        "max_supplier_share_enforced": max_single_vendor_share
    }
