"""
Deterministic price normalization engine.
Handles:
- Per-piece, Per-1,000, Per-kg, Per-sqm
- FX conversions with configurable rate and effective date
- Freight rate additions (freight included vs freight extra)
- Historical PO resolution for repeat SKUs (+3.6% index)
- Unresolved flagging for New SKUs with missing PO history
- Take-up factors (with BCB = 1.45)
- Preserves exact source citations and trust flags
"""

import re
import numpy as np
import pandas as pd
from typing import Tuple, Optional, Dict, Any

from core.config import TAKEUP_FACTORS, DEFAULT_FX_RATE, DEFAULT_FREIGHT_RATES


def calculate_composite_weight(
    ply: float,
    flute: str,
    liner_gsm: float,
    fluting_gsm: float,
    board_l_mm: float,
    board_w_mm: float,
    takeup_factors: Optional[Dict[str, float]] = None
) -> Tuple[float, float]:
    """
    Calculates Composite GSM and Est. Weight per UoM (kg).
    Formula from RFx Master:
    Composite GSM = ((Ply + 1) / 2) * Liner_GSM + ((Ply - 1) / 2) * Fluting_GSM * Takeup
    Weight (kg) = (Board_L * Board_W / 1,000,000) * (Composite_GSM / 1,000)
    Note: Takeup factor for BCB is 1.45.
    """
    factors = takeup_factors or TAKEUP_FACTORS
    flute_clean = str(flute or "B").strip().upper()
    takeup = factors.get(flute_clean, 1.32)

    comp_gsm = ((ply + 1.0) / 2.0) * liner_gsm + ((ply - 1.0) / 2.0) * fluting_gsm * takeup
    
    # Board dimensions in meters
    bl = float(board_l_mm) if pd.notna(board_l_mm) and board_l_mm > 0 else 1000.0
    bw = float(board_w_mm) if pd.notna(board_w_mm) and board_w_mm > 0 else 500.0
    area_sqm = (bl * bw) / 1e6
    weight_kg = area_sqm * (comp_gsm / 1e3)

    return round(comp_gsm, 2), round(weight_kg, 4)


def normalize_price(
    raw_value: Any,
    raw_unit: Optional[str] = None,
    raw_currency: str = "INR",
    line_no: int = 1,
    delivery_location: str = "Pune (Chakan plant)",
    item_weight_kg: Optional[float] = None,
    is_new_sku: bool = False,
    last_po_price: Optional[float] = None,
    fx_rate: float = DEFAULT_FX_RATE,
    freight_rates: Optional[Dict[str, float]] = None,
    freight_included: bool = False,
    inflation_index: float = 0.036
) -> Tuple[Optional[float], str, str, str]:
    """
    Deterministic price normalizer returning:
    (landed_cost, trust_flag, formula_citation, extraction_status)
    """
    f_rates = freight_rates or DEFAULT_FREIGHT_RATES
    freight_rate = f_rates.get(delivery_location, 1.20)

    # Missing or empty checks
    if raw_value is None or pd.isna(raw_value):
        raw_str = str(raw_unit or "").strip().lower()
        if not raw_str or any(k in raw_str for k in ["missing", "none", "nan"]):
            return None, "Missing / Not Quoted", "Quote omitted by vendor", "Missing"
    else:
        raw_str = f"{raw_value} {raw_unit or ''}".strip().lower()

    if any(k in raw_str for k in ["unresolved", "not quoted", "disqualified", "omitted"]):
        if "disqualified" in raw_str:
            return None, "Disqualified", "Vendor disqualified for this line item specification", "Verified"
        return None, "UNRESOLVED", f"Unresolved quotation entry: '{raw_value}'", "Needs Review"

    # Historical PO check ("Same as last year")
    if "same as last year" in raw_str or "historical" in raw_str:
        if is_new_sku or pd.isna(last_po_price) or float(last_po_price or 0) <= 0:
            citation = "Quoted 'Same as last year', but item is a New SKU with no PO history -> UNRESOLVED"
            return None, "UNRESOLVED", citation, "Needs Review"
        else:
            landed = round(float(last_po_price) * (1.0 + inflation_index), 2)
            citation = f"Resolved from FY25 PO (₹{float(last_po_price):.2f}) + {inflation_index*100:.1f}% index = ₹{landed:.2f}"
            return landed, "Inferred (PO History)", citation, "Verified"

    # Extract numeric amount
    match = re.search(r"[-+]?(?:\d*\.\d+|\d+)", str(raw_value).replace(",", ""))
    if not match:
        return None, "UNRESOLVED", f"Unparseable price string: '{raw_value}'", "Needs Review"

    numeric_val = float(match.group(0))

    # Currency conversion: USD
    if "usd" in raw_str or "$" in raw_str or str(raw_currency).upper() == "USD":
        inr_val = round(numeric_val * fx_rate, 2)
        citation = f"USD ${numeric_val:.4f} × ₹{fx_rate:.2f}/USD = ₹{inr_val:.2f}"
        return inr_val, "Inferred (USD to INR)", citation, "Verified"

    # Weight-based pricing: ₹/kg
    if "kg" in raw_str or "per kg" in raw_str:
        if item_weight_kg is None or pd.isna(item_weight_kg) or item_weight_kg <= 0:
            return None, "UNRESOLVED", "Weight missing for kg-based conversion -> UNRESOLVED", "Needs Review"
        
        wt = float(item_weight_kg)
        eff_freight = 0.0 if freight_included else freight_rate
        landed = round((numeric_val + eff_freight) * wt, 2)
        f_note = "" if freight_included else f" + ₹{eff_freight:.2f} freight"
        citation = f"(₹{numeric_val:.2f}/kg{f_note}) × {wt:.4f}kg = ₹{landed:.2f}"
        return landed, "Inferred (kg to piece)", citation, "Verified"

    # Thousand rate: Per 1,000 Nos
    if "1000" in raw_str or "/1,000" in raw_str:
        landed = round(numeric_val / 1000.0, 2)
        citation = f"₹{numeric_val:,.2f} per 1,000 Nos ÷ 1000 = ₹{landed:.2f}"
        return landed, "Inferred (/1000 to piece)", citation, "Verified"

    # Standard direct rate
    return round(numeric_val, 2), "Verified", f"₹{numeric_val:.2f} direct piece quote", "Verified"
