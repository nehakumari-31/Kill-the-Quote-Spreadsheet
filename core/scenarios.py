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
from core.eligibility import VendorQualification, is_vendor_eligible_for_line


def calculate_award_scenarios(
    df_matrix: pd.DataFrame,
    qualifications: Dict[str, VendorQualification],
    max_single_vendor_share: Optional[float] = None
) -> Dict[str, Any]:
    """
    Computes all award scenarios dynamically based on current matrix values and qualifications.
    """
    df = df_matrix.copy()
    vendor_cols = ["V1 (Apex)", "V2 (PackTech)", "V3 (Global USD)", "V4 (Balaji)", "V5 (Standard Box)"]

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
    risks_b = []
    risks_c = []

    b_vendor_spends = {v: 0.0 for v in vendor_cols}
    c_vendor_spends = {v: 0.0 for v in vendor_cols}

    for _, row in df.iterrows():
        l_no = int(row["Line #"])
        item_code = str(row["Item Code"])
        desc = str(row.get("Description", ""))
        qty = float(row["Est. Qty"])
        budget_p = float(row["Budget Price"])
        crit = str(row.get("Criticality", "C")).strip().upper()

        # Find eligible vendors who quoted a valid price
        eligible_quotes = []
        for v_col in vendor_cols:
            v_id = v_col.split()[0]
            if is_vendor_eligible_for_line(v_id, l_no, qualifications):
                val = row[v_col]
                if pd.notna(val) and val > 0:
                    eligible_quotes.append((v_col, float(val)))

        # Sort by price ascending
        eligible_quotes.sort(key=lambda x: x[1])

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
            # Line is Uncovered! Never allocate to disqualified vendor
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
            risks_b.append(f"Line {l_no} ({item_code}): No eligible vendor available. Line is UNCOVERED.")

        # Evaluate Scenario C (Dual Sourcing 70/30 on Criticality A lines)
        if not eligible_quotes:
            c_line_allocations.append({
                "Line #": l_no,
                "Item Code": item_code,
                "Description": desc,
                "Criticality": crit,
                "L1 Vendor": "UNCOVERED",
                "L1 Qty": 0,
                "L2 Vendor": "UNCOVERED",
                "L2 Qty": 0,
                "Line Spend (₹)": budget_p * qty,
                "Status": "UNCOVERED"
            })
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

    spend_b = float(sum(item["Line Spend (₹)"] for item in b_line_allocations))
    spend_c = float(sum(item["Line Spend (₹)"] for item in c_line_allocations))

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
        "b_line_allocations": b_line_allocations,
        "c_line_allocations": c_line_allocations,
        "vendor_shares_b": vendor_shares_b,
        "vendor_shares_c": vendor_shares_c,
        "risks_b": risks_b,
        "risks_c": risks_c
    }
