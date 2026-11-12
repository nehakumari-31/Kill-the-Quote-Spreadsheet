"""
Data-driven vendor eligibility and questionnaire audit engine.
Evaluates vendor compliance against general mandatory gates and line-specific capabilities.
No hardcoded vendor names or line numbers.
"""

import re
from typing import Dict, List, Any, Optional, Set, Tuple
import pandas as pd
from core.models import VendorQualification


def _extract_vendor_id(col_name: str) -> str:
    """Extracts normalized vendor identifier from column header (e.g., 'V1: Apex' -> 'V1')."""
    s = str(col_name).strip()
    m = re.match(r"^(V\d+)", s, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    parts = s.split(":")
    if len(parts) > 1 and re.match(r"^V\d+$", parts[0].strip(), re.IGNORECASE):
        return parts[0].strip().upper()
    return s.split()[0].strip().upper() if s else "UNKNOWN"


def _lookup_answer(audit_dict: Dict[str, Any], v_col: str, keywords: List[str]) -> str:
    """Finds vendor response text matching given question keywords."""
    for criterion, row in audit_dict.items():
        c_low = str(criterion).lower()
        if any(k in c_low for k in keywords):
            val = row.get(v_col, "")
            return "" if pd.isna(val) else str(val).strip()
    return ""


def _extract_number(val_str: str) -> Optional[float]:
    """Extracts float number from text string."""
    m = re.search(r"[-+]?(?:\d*\.\d+|\d+)", str(val_str).replace(",", ""))
    return float(m.group(0)) if m else None


def _evaluate_q1_iso(text: str) -> Tuple[str, str]:
    """
    Evaluates Q1: ISO 9001:2015 Certification.
    Mandatory gate; uncertified or expired vendor disqualified.
    Missing evidence -> Pending Review.
    Returns: (verdict, explanation) where verdict in ('passed', 'failed', 'pending')
    """
    s = str(text or "").strip().lower()
    if not s or any(k in s for k in ["pending", "under review", "awaited", "missing", "tbd", "unverified"]):
        return "pending", "ISO 9001:2015 certificate verification pending review"

    if any(k in s for k in ["fail", "expired", "invalid", "rejected"]):
        return "failed", f"ISO 9001:2015 certificate expired or invalid: '{text}'"

    m = re.search(r"exp(?:ired|ires|iry|:)?\s*[:\s]?\s*(?:[a-z]{3}\s*)?(\d{4})", s)
    if m:
        exp_year = int(m.group(1))
        if exp_year < 2026:
            return "failed", f"ISO 9001:2015 certificate expired in {exp_year} (prior to RFx closing Nov 2026)"

    if any(k in s for k in ["pass", "valid", "certified", "yes"]):
        return "passed", f"Valid ISO 9001:2015 certificate verified ({text})"

    return "pending", f"Ambiguous ISO 9001:2015 certificate status: '{text}'"


def _evaluate_q2_capacity(text: str) -> Tuple[str, str]:
    """
    Evaluates Q2: Monthly Capacity (>= 300 TPM).
    Returns: (verdict, explanation)
    """
    s = str(text or "").strip().lower()
    if not s or any(k in s for k in ["pending", "under review", "awaited", "missing"]):
        return "pending", "Monthly capacity verification pending review"

    cap_val = _extract_number(s)
    if cap_val is not None:
        if cap_val < 300:
            return "failed", f"Monthly capacity ({cap_val:.0f} TPM) is below 300 TPM threshold"
        return "passed", f"Monthly capacity ({cap_val:.0f} TPM) meets requirement (>=300 TPM)"

    if "fail" in s:
        return "failed", "Monthly capacity below 300 TPM threshold"
    if "pass" in s:
        return "passed", "Monthly capacity meets requirement"

    return "pending", f"Monthly capacity unverified: '{text}'"


def _evaluate_q3_lab(text: str) -> Tuple[str, str]:
    """
    Evaluates Q3: In-House Testing Lab.
    Returns: (verdict, explanation)
    """
    s = str(text or "").strip().lower()
    if not s or any(k in s for k in ["pending", "under review", "awaited", "missing"]):
        return "pending", "Testing lab verification pending review"

    if any(k in s for k in ["no", "fail", "external", "lacks", "absent"]):
        return "failed", f"Lacks certified in-house board testing lab ({text})"
    if any(k in s for k in ["yes", "pass", "available", "present"]):
        return "passed", "In-house board testing lab verified"

    return "pending", f"Testing lab status unverified: '{text}'"


def _evaluate_q4_rejection(text: str) -> Tuple[str, str]:
    """
    Evaluates Q4: Customer Rejection Rate (<= 1.5%).
    Returns: (verdict, explanation)
    """
    s = str(text or "").strip().lower()
    if not s or any(k in s for k in ["pending", "under review", "awaited", "missing"]):
        return "pending", "Customer rejection rate verification pending review"

    rej_val = _extract_number(s)
    if rej_val is not None:
        if rej_val > 1.5:
            return "failed", f"Customer rejection rate ({rej_val:.1f}%) exceeds 1.5% maximum"
        return "passed", f"Customer rejection rate ({rej_val:.1f}%) within tolerance (<=1.5%)"

    if "fail" in s:
        return "failed", "Customer rejection rate exceeds 1.5% maximum"
    if "pass" in s:
        return "passed", "Customer rejection rate within tolerance"

    return "pending", f"Rejection rate unverified: '{text}'"


def _evaluate_q5_customers(text: str) -> Tuple[str, str]:
    """
    Evaluates Q5: Active Customers (>= 3).
    Returns: (verdict, explanation)
    """
    s = str(text or "").strip().lower()
    if not s or any(k in s for k in ["pending", "under review", "awaited", "missing"]):
        return "pending", "Active customer references verification pending review"

    cust_val = _extract_number(s)
    if cust_val is not None:
        if cust_val < 3:
            return "failed", f"Active client references ({cust_val:.0f}) below minimum 3"
        return "passed", f"Active client references ({cust_val:.0f}) meets requirement (>=3)"

    if "fail" in s:
        return "failed", "Insufficient active customer references (<3)"
    if "pass" in s:
        return "passed", "Active customer references meet requirement"

    return "pending", f"Customer references unverified: '{text}'"


def _evaluate_q6_7ply(text: str) -> Tuple[str, str]:
    """
    Evaluates Q6: 7-Ply BCB Capability (Applies strictly to 7-ply lines).
    Returns: (verdict, explanation)
    """
    s = str(text or "").strip().lower()
    if not s or any(k in s for k in ["pending", "under review", "awaited", "missing"]):
        return "pending", "7-ply BCB capability verification pending review"

    if any(k in s for k in ["no", "fail", "cannot", "disqualified", "absent"]):
        return "failed", "Lacks 7-ply (BCB triple-wall) in-house manufacturing capability"
    if any(k in s for k in ["yes", "pass", "available"]):
        return "passed", "7-ply (BCB triple-wall) in-house manufacturing capability confirmed"

    return "pending", f"7-ply capability unverified: '{text}'"


def _evaluate_q7_moisture(text: str) -> Tuple[str, str]:
    """
    Evaluates Q7: Moisture Barrier Capability (Applies strictly to moisture-barrier lines).
    Returns: (verdict, explanation)
    """
    s = str(text or "").strip().lower()
    if not s or any(k in s for k in ["pending", "under review", "awaited", "missing"]):
        return "pending", "Moisture barrier capability verification pending review"

    if any(k in s for k in ["no", "fail", "cannot", "disqualified", "absent"]):
        return "failed", "Lacks moisture-barrier treatment capability"
    if any(k in s for k in ["yes", "pass", "available"]):
        return "passed", "Moisture-barrier treatment capability confirmed"

    return "pending", f"Moisture barrier capability unverified: '{text}'"


def evaluate_vendor_qualifications(
    df_audit: pd.DataFrame,
    df_items: pd.DataFrame,
    rfx_closing_year: int = 2026,
    rfx_closing_month: int = 11
) -> Dict[str, VendorQualification]:
    """
    Evaluates vendor qualification derived entirely from actual questionnaire responses
    and mandatory RFx requirements.
    - No hardcoded vendor-name exclusions.
    - Separates supplier-wide requirements (Q1-Q5) from line-specific requirements (Q6, Q7).
    - Missing mandatory evidence is treated as 'Pending Review', not compliant.
    - Stores the reason and source evidence for every qualification decision.
    """
    results: Dict[str, VendorQualification] = {}

    # Identify vendor columns in audit sheet
    non_vendor_cols = {
        "question / gate criteria", "evaluation rule & impact", "q#",
        "criteria", "rule", "impact", "notes", "evaluation notes"
    }
    vendor_cols = [c for c in df_audit.columns if str(c).strip().lower() not in non_vendor_cols]

    # Convert audit criteria to dictionary for lookup
    audit_dict = df_audit.set_index("Question / Gate Criteria").to_dict(orient="index")

    # Dynamically derive lines requiring specific technical capabilities from item specs
    lines_requiring_7ply: Set[int] = set()
    lines_requiring_moisture: Set[int] = set()

    for _, row in df_items.iterrows():
        try:
            l_no = int(row["Line #"])
        except (ValueError, TypeError):
            continue

        ply = float(row.get("Ply", 3)) if pd.notna(row.get("Ply")) else 3.0
        flute = str(row.get("Flute", "")).strip().upper()
        desc = str(row.get("Item Description", "")).lower()
        finish = str(row.get("Print / Finish", "")).lower()

        if ply >= 7.0 or flute == "BCB" or "7-ply" in desc or "triple" in desc:
            lines_requiring_7ply.add(l_no)

        if "moisture" in desc or "barrier" in desc or "moisture" in finish or "barrier" in finish:
            lines_requiring_moisture.add(l_no)

    for v_col in vendor_cols:
        v_id = _extract_vendor_id(v_col)
        v_name = v_col.strip()

        failed_general: List[str] = []
        pending_general: List[str] = []
        banned_lines: Set[int] = set()
        evidence: Dict[str, str] = {}
        line_restrictions: Dict[int, str] = {}

        # 1. Supplier-Wide Gate Q1: ISO 9001:2015 Cert
        q1_text = _lookup_answer(audit_dict, v_col, ["q1", "iso 9001"])
        evidence["Q1_ISO"] = q1_text
        v1_res, v1_exp = _evaluate_q1_iso(q1_text)
        if v1_res == "failed":
            failed_general.append(f"Q1 (ISO 9001): {v1_exp}")
        elif v1_res == "pending":
            pending_general.append(f"Q1 (ISO 9001): {v1_exp}")

        # 2. Supplier-Wide Gate Q2: Monthly Capacity (>= 300 TPM)
        q2_text = _lookup_answer(audit_dict, v_col, ["q2", "capacity"])
        evidence["Q2_Capacity"] = q2_text
        v2_res, v2_exp = _evaluate_q2_capacity(q2_text)
        if v2_res == "failed":
            failed_general.append(f"Q2 (Capacity): {v2_exp}")
        elif v2_res == "pending":
            pending_general.append(f"Q2 (Capacity): {v2_exp}")

        # 3. Supplier-Wide Gate Q3: In-House Testing Lab
        q3_text = _lookup_answer(audit_dict, v_col, ["q3", "lab", "testing"])
        evidence["Q3_Lab"] = q3_text
        v3_res, v3_exp = _evaluate_q3_lab(q3_text)
        if v3_res == "failed":
            failed_general.append(f"Q3 (Testing Lab): {v3_exp}")
        elif v3_res == "pending":
            pending_general.append(f"Q3 (Testing Lab): {v3_exp}")

        # 4. Supplier-Wide Gate Q4: Customer Rejection Rate (<= 1.5%)
        q4_text = _lookup_answer(audit_dict, v_col, ["q4", "rejection"])
        evidence["Q4_Rejection"] = q4_text
        v4_res, v4_exp = _evaluate_q4_rejection(q4_text)
        if v4_res == "failed":
            failed_general.append(f"Q4 (Rejection Rate): {v4_exp}")
        elif v4_res == "pending":
            pending_general.append(f"Q4 (Rejection Rate): {v4_exp}")

        # 5. Supplier-Wide Gate Q5: Active Customers (>= 3)
        q5_text = _lookup_answer(audit_dict, v_col, ["q5", "customers", "active"])
        evidence["Q5_Customers"] = q5_text
        v5_res, v5_exp = _evaluate_q5_customers(q5_text)
        if v5_res == "failed":
            failed_general.append(f"Q5 (Active Customers): {v5_exp}")
        elif v5_res == "pending":
            pending_general.append(f"Q5 (Active Customers): {v5_exp}")

        # 6. Line-Specific Gate Q6: 7-Ply BCB Capability
        q6_text = _lookup_answer(audit_dict, v_col, ["q6", "7-ply", "triple"])
        evidence["Q6_7Ply"] = q6_text
        v6_res, v6_exp = _evaluate_q6_7ply(q6_text)
        if v6_res in ["failed", "pending"]:
            for l in lines_requiring_7ply:
                banned_lines.add(l)
                line_restrictions[l] = f"Q6 (7-Ply BCB): {v6_exp}"

        # 7. Line-Specific Gate Q7: Moisture Barrier Capability
        q7_text = _lookup_answer(audit_dict, v_col, ["q7", "moisture", "barrier"])
        evidence["Q7_Moisture"] = q7_text
        v7_res, v7_exp = _evaluate_q7_moisture(q7_text)
        if v7_res in ["failed", "pending"]:
            for l in lines_requiring_moisture:
                banned_lines.add(l)
                line_restrictions[l] = f"Q7 (Moisture Barrier): {v7_exp}"

        # Determine overall qualification status
        if failed_general:
            status = "Disqualified"
            reason = f"Disqualified across all lines: {'; '.join(failed_general)}"
            # If supplier fails general mandatory requirements, banned across all lines
            banned_lines = set(range(1, len(df_items) + 1))
            passed_mandatory = False
        elif pending_general:
            status = "Pending Review"
            reason = f"Pending mandatory verification: {'; '.join(pending_general)}"
            passed_mandatory = False
        elif banned_lines:
            status = "Conditionally Eligible"
            reason = f"Passed general gates; restricted on {len(banned_lines)} specialized lines ({sorted(list(banned_lines))})"
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
            reason=reason,
            pending_gates=pending_general,
            line_restrictions=line_restrictions
        )

    return results


def is_vendor_eligible_for_line(
    vendor_id: str,
    line_no: int,
    qualifications: Dict[str, VendorQualification]
) -> bool:
    """
    Returns True if the vendor is qualified and eligible to be awarded the given line.
    A supplier must NEVER be recommended for a line if it fails a mandatory requirement for that line.
    Pending Review suppliers are treated as not eligible until reviewed.
    """
    qual = qualifications.get(vendor_id)
    if not qual:
        return False
    if qual.status in ["Disqualified", "Pending Review"]:
        return False
    if line_no in qual.banned_lines:
        return False
    return True


def evaluate_award_approval_gate(*args, **kwargs):
    """Convenience alias to centralized evaluate_award_approval_gate in core.scenarios."""
    from core.scenarios import evaluate_award_approval_gate as _impl
    return _impl(*args, **kwargs)

