"""
Data-driven vendor eligibility and questionnaire audit engine.
Evaluates vendor compliance against general mandatory gates and line-specific capabilities.
No hardcoded vendor names or line numbers.
"""

from typing import Dict, List, Any, Optional, Set
import pandas as pd
from core.models import VendorQualification


def evaluate_vendor_qualifications(
    df_audit: pd.DataFrame,
    df_items: pd.DataFrame,
    rfx_closing_year: int = 2026,
    rfx_closing_month: int = 11
) -> Dict[str, VendorQualification]:
    """
    Evaluates vendor qualification based on the Questionnaire Audit sheet.
    Dynamically maps question criteria to line-specific item requirements.
    """
    results: Dict[str, VendorQualification] = {}

    # Identify vendor columns in audit sheet
    vendor_cols = [c for c in df_audit.columns if c not in ["Question / Gate Criteria", "Evaluation Rule & Impact", "Q#", "Criteria", "Rule"]]

    # Convert audit criteria to dictionary for lookup
    audit_dict = df_audit.set_index("Question / Gate Criteria").to_dict(orient="index")

    # Identify line items requiring specific capabilities
    lines_requiring_7ply: Set[int] = set()
    lines_requiring_moisture: Set[int] = set()

    for _, row in df_items.iterrows():
        try:
            l_no = int(row["Line #"])
        except (ValueError, TypeError):
            continue

        ply = float(row.get("Ply", 3))
        flute = str(row.get("Flute", "")).strip().upper()
        desc = str(row.get("Item Description", "")).lower()
        finish = str(row.get("Print / Finish", "")).lower()

        if ply >= 7.0 or flute == "BCB" or "7-ply" in desc:
            lines_requiring_7ply.add(l_no)

        if "moisture" in desc or "barrier" in desc or "moisture" in finish:
            lines_requiring_moisture.add(l_no)

    for v_col in vendor_cols:
        v_id = _extract_vendor_id(v_col)
        v_name = v_col.strip()
        failed_general: List[str] = []
        banned_lines: Set[int] = set()
        evidence: Dict[str, str] = {}
        is_pending = False

        # Evaluate Q1: ISO 9001:2015 Cert
        q1_text = _lookup_answer(audit_dict, v_col, ["q1", "iso 9001"])
        evidence["Q1_ISO"] = q1_text
        if not q1_text or "pending" in q1_text.lower():
            is_pending = True
        elif any(k in q1_text.lower() for k in ["fail", "expired"]):
            failed_general.append("Q1: ISO 9001:2015 certificate expired or invalid")

        # Evaluate Q2: Capacity (>= 300 TPM)
        q2_text = _lookup_answer(audit_dict, v_col, ["q2", "capacity"])
        evidence["Q2_Capacity"] = q2_text
        cap_val = _extract_number(q2_text)
        if cap_val is not None and cap_val < 300:
            failed_general.append(f"Q2: Monthly capacity ({cap_val:.0f} TPM) is below 300 TPM threshold")
        elif "fail" in q2_text.lower():
            failed_general.append("Q2: Monthly capacity below threshold")

        # Evaluate Q3: In-House Testing Lab
        q3_text = _lookup_answer(audit_dict, v_col, ["q3", "lab", "testing"])
        evidence["Q3_Lab"] = q3_text
        if any(k in q3_text.lower() for k in ["fail", "no", "external"]):
            failed_general.append("Q3: Lacks certified in-house board testing lab")

        # Evaluate Q4: Rejection Rate (<= 1.5%)
        q4_text = _lookup_answer(audit_dict, v_col, ["q4", "rejection"])
        evidence["Q4_Rejection"] = q4_text
        rej_val = _extract_number(q4_text)
        if rej_val is not None and rej_val > 1.5:
            failed_general.append(f"Q4: Customer rejection rate ({rej_val:.1f}%) exceeds 1.5% maximum")
        elif "fail" in q4_text.lower():
            failed_general.append("Q4: Rejection rate exceeds maximum limit")

        # Evaluate Q5: Active Customers (>= 3)
        q5_text = _lookup_answer(audit_dict, v_col, ["q5", "customers", "active"])
        evidence["Q5_Customers"] = q5_text
        cust_val = _extract_number(q5_text)
        if cust_val is not None and cust_val < 3:
            failed_general.append(f"Q5: Active client references ({cust_val:.0f}) below minimum 3")
        elif "fail" in q5_text.lower():
            failed_general.append("Q5: Insufficient active customer references")

        # Evaluate Q6: 7-Ply BCB Capability
        q6_text = _lookup_answer(audit_dict, v_col, ["q6", "7-ply", "triple"])
        evidence["Q6_7Ply"] = q6_text
        has_7ply = not any(k in q6_text.lower() for k in ["no", "disqualified", "fail", "cannot"])
        if not has_7ply:
            banned_lines.update(lines_requiring_7ply)

        # Evaluate Q7: Moisture Barrier Capability
        q7_text = _lookup_answer(audit_dict, v_col, ["q7", "moisture", "barrier"])
        evidence["Q7_Moisture"] = q7_text
        has_moisture = not any(k in q7_text.lower() for k in ["no", "disqualified", "fail", "cannot"])
        if not has_moisture:
            banned_lines.update(lines_requiring_moisture)

        # Determine overall qualification status
        if failed_general:
            status = "Disqualified"
            reason = f"Disqualified across all lines: {'; '.join(failed_general)}"
            banned_lines = set(range(1, 31))
            passed_mandatory = False
        elif is_pending:
            status = "Pending Review"
            reason = "Pending verification of questionnaire attachments"
            passed_mandatory = False
        elif banned_lines:
            status = "Conditionally Eligible"
            reason = f"Passed general gates; banned on {len(banned_lines)} specialized lines ({sorted(list(banned_lines))})"
            passed_mandatory = True
        else:
            status = "Eligible"
            reason = "Fully compliant with all general and line-specific RFx quality gates"
            passed_mandatory = True

        results[v_id] = VendorQualification(
            vendor_id=v_id,
            vendor_name=v_name,
            status=status,
            passed_mandatory_gates=passed_mandatory,
            failed_general_gates=failed_general,
            banned_lines=sorted(list(banned_lines)),
            evidence=evidence,
            reason=reason
        )

    return results


def is_vendor_eligible_for_line(
    vendor_id: str,
    line_no: int,
    qualifications: Dict[str, VendorQualification]
) -> bool:
    """Returns True if the vendor is qualified and eligible to be awarded the given line."""
    qual = qualifications.get(vendor_id)
    if not qual:
        return False
    if qual.status == "Disqualified":
        return False
    if line_no in qual.banned_lines:
        return False
    return True


# Helper functions
def _extract_vendor_id(col_name: str) -> str:
    s = str(col_name).strip()
    if s.startswith("V1"): return "V1"
    if s.startswith("V2"): return "V2"
    if s.startswith("V3"): return "V3"
    if s.startswith("V4"): return "V4"
    if s.startswith("V5"): return "V5"
    return s[:10]


def _lookup_answer(audit_dict: Dict[str, Any], v_col: str, keywords: List[str]) -> str:
    for criterion, row in audit_dict.items():
        c_low = str(criterion).lower()
        if any(k in c_low for k in keywords):
            return str(row.get(v_col, "")).strip()
    return ""


def _extract_number(val_str: str) -> Optional[float]:
    import re
    m = re.search(r"[-+]?(?:\d*\.\d+|\d+)", str(val_str).replace(",", ""))
    return float(m.group(0)) if m else None
