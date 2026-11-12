"""
Deterministic price normalization engine.
Handles:
- Currency conversion (INR & foreign currencies with explicit exchange rate & effective date)
- Per-piece and per-1,000 pieces
- Per-kg conversions only with valid weight basis (no invented default weight)
- Per-sqm conversions only with valid area basis
- Freight treatment (included vs extra) based on quote terms
- GST treatment (included vs excluded) without double-counting tax
- Conditional discounts applied only when conditions are satisfied
- Unresolved flagging with exact missing inputs for buyer review
- Preserves full audit traceability for every normalized quote
"""

import re
from typing import Tuple, Optional, Dict, Any, List
import numpy as np
import pandas as pd

from core.config import (
    TAKEUP_FACTORS,
    DEFAULT_FX_RATE,
    DEFAULT_FX_EFFECTIVE_DATE,
    DEFAULT_FREIGHT_RATES
)
from core.models import NormalizationResult, UnresolvedStatus, InferredStatus


def validate_technical_specification(
    ply: Any,
    flute: Any,
    liner_gsm: Any,
    fluting_gsm: Any,
    board_l_mm: Any = None,
    board_w_mm: Any = None,
    liner_bf: Any = None,
    uom: Any = None
) -> Tuple[bool, List[str]]:
    """
    Validates technical specifications required for composite weight calculation.
    Returns (is_valid, list_of_missing_or_invalid_inputs).
    Never silently substitutes defaults for missing inputs.
    """
    missing = []
    if ply is None or pd.isna(ply) or float(ply) <= 0:
        missing.append("Ply")
    flute_str = str(flute or "").strip().upper()
    if not flute_str or flute_str not in TAKEUP_FACTORS:
        missing.append(f"Flute ({flute or 'Missing'})")
    if liner_gsm is None or pd.isna(liner_gsm) or float(liner_gsm) <= 0:
        missing.append("Liner GSM")
    if fluting_gsm is None or pd.isna(fluting_gsm) or float(fluting_gsm) <= 0:
        missing.append("Fluting GSM")
    if board_l_mm is None or pd.isna(board_l_mm) or float(board_l_mm) <= 0:
        missing.append("Board Length (mm)")
    if board_w_mm is None or pd.isna(board_w_mm) or float(board_w_mm) <= 0:
        missing.append("Board Width (mm)")
    if liner_bf is not None and (pd.isna(liner_bf) or float(liner_bf) <= 0):
        missing.append("Liner BF")
    if uom is not None and parse_uom(str(uom)) in ["unknown", "unsupported"]:
        missing.append(f"UOM ({uom})")

    return len(missing) == 0, missing


def calculate_composite_weight(
    ply: float,
    flute: str,
    liner_gsm: float,
    fluting_gsm: float,
    board_l_mm: Optional[float] = None,
    board_w_mm: Optional[float] = None,
    takeup_factors: Optional[Dict[str, float]] = None,
    liner_bf: Optional[float] = None
) -> Tuple[Optional[float], Optional[float]]:
    """
    Calculates Composite GSM and Est. Weight per UoM (kg).
    Formula from RFx Master:
    Composite GSM = ((Ply + 1) / 2) * Liner_GSM + ((Ply - 1) / 2) * Fluting_GSM * Takeup
    Weight (kg) = (Board_L * Board_W / 1,000,000) * (Composite_GSM / 1,000)
    Note: Takeup factor for BCB is 1.45.
    
    If board dimensions or technical parameters are missing/non-positive,
    does NOT invent default dimensions (e.g. 1000 x 500 mm); returns None for weight.
    """
    factors = takeup_factors or TAKEUP_FACTORS
    flute_clean = str(flute or "").strip().upper()
    if flute_clean not in factors:
        return None, None

    if ply is None or liner_gsm is None or fluting_gsm is None or pd.isna(ply) or pd.isna(liner_gsm) or pd.isna(fluting_gsm):
        return None, None
    if float(ply) <= 0 or float(liner_gsm) <= 0 or float(fluting_gsm) <= 0:
        return None, None
    if liner_bf is not None and (pd.isna(liner_bf) or float(liner_bf) <= 0):
        return None, None

    takeup = factors[flute_clean]
    comp_gsm = ((float(ply) + 1.0) / 2.0) * float(liner_gsm) + ((float(ply) - 1.0) / 2.0) * float(fluting_gsm) * takeup

    # Check board dimensions strictly - do NOT use silent default dimensions
    if (
        board_l_mm is None or pd.isna(board_l_mm) or float(board_l_mm) <= 0 or
        board_w_mm is None or pd.isna(board_w_mm) or float(board_w_mm) <= 0
    ):
        return round(comp_gsm, 2), None

    bl = float(board_l_mm)
    bw = float(board_w_mm)
    area_sqm = (bl * bw) / 1e6
    weight_kg = area_sqm * (comp_gsm / 1e3)

    return round(comp_gsm, 2), round(weight_kg, 4)


def calculate_price_per_kg(
    landed_piece_price: Optional[float],
    item_weight_kg: Optional[float]
) -> Tuple[Optional[float], Optional[str]]:
    """
    Computes effective price per kg from landed piece price and item weight.
    Strictly excludes unresolved items where price or weight is missing, zero, or unconfirmed.
    Returns: (price_per_kg, status_or_reason)
    """
    if landed_piece_price is None or pd.isna(landed_piece_price) or float(landed_piece_price) <= 0:
        return None, "Unresolved: Landed piece price missing or invalid"
    if item_weight_kg is None or pd.isna(item_weight_kg) or float(item_weight_kg) <= 0:
        return None, "Unresolved: Item weight missing (cannot derive price per kg)"
    return round(float(landed_piece_price) / float(item_weight_kg), 2), "Valid"


def parse_uom(raw_unit: Optional[str]) -> str:
    """
    Classifies quotation unit of measure deterministically.
    Does NOT treat Nos, Set, Sqm, Running Metre, and Kg as interchangeable.
    Returns: 'piece', 'per_1000', 'kg', 'sqm', 'set', 'running_metre', or 'unsupported'
    """
    if not raw_unit or pd.isna(raw_unit):
        return "unknown"
    u = str(raw_unit).strip().lower()
    u_clean = u.replace(",", "")

    # Thousand rate
    if any(k in u_clean for k in ["per 1000", "per 1,000", "/1000", "/1,000", "1000 nos", "1000 pcs", "thousand", "k nos"]):
        return "per_1000"
    if u_clean in ["1000", "1,000"]:
        return "per_1000"

    # Weight
    if any(k in u for k in ["/kg", "per kg", "₹/kg", "rs/kg", "inr/kg", "kg"]):
        return "kg"

    # Area
    if any(k in u for k in ["/sqm", "per sqm", "sqm", "sq.m", "sq m", "m2", "/m2"]):
        return "sqm"

    # Set
    if "set" in u:
        return "set"

    # Running Metre
    if any(k in u for k in ["running metre", "running meter", "rm", "rmt", "/rm"]):
        return "running_metre"

    # Piece / Each
    if any(k in u for k in ["nos", "piece", "pc", "box", "ea", "each", "per piece", "per nos", "/piece", "/nos"]):
        return "piece"

    # Currency strings passed as unit (e.g. "USD", "$", "INR") represent direct unit prices
    if u in ["usd", "$", "inr", "rs", "₹", "eur", "gbp"]:
        return "piece"

    return "unsupported"


def normalize_price(
    raw_value: Any,
    raw_unit: Optional[str] = None,
    raw_currency: str = "INR",
    line_no: int = 1,
    delivery_location: Optional[str] = None,
    item_weight_kg: Optional[float] = None,
    item_area_sqm: Optional[float] = None,
    target_uom: str = "Nos",
    is_new_sku: bool = False,
    last_po_price: Optional[float] = None,
    fx_rate: Optional[float] = None,
    fx_effective_date: Optional[str] = None,
    freight_rates: Optional[Dict[str, float]] = None,
    freight_included: bool = False,
    freight_extra_rate: Optional[float] = None,
    gst_included: bool = False,
    gst_rate: float = 0.18,
    discount_pct: float = 0.0,
    discount_condition: Optional[str] = None,
    condition_met: bool = False,
    inflation_index: float = 0.036
) -> NormalizationResult:
    """
    Deterministic price normalizer strictly adhering to RFx assumptions:
    - Never uses silent default weight, freight, or exchange rate.
    - If conversion inputs are missing/ambiguous, sets normalized price to None and status to 'Unresolved'.
    - Returns NormalizationResult with full audit traceability (unpacks as 4-tuple for backward compatibility).
    """
    orig_val = raw_value
    orig_curr = str(raw_currency or "INR").strip().upper()
    orig_uom = str(raw_unit or "").strip()

    # 1. Missing or empty checks
    if raw_value is None or pd.isna(raw_value):
        raw_str = orig_uom.lower()
        if not raw_str or any(k in raw_str for k in ["missing", "none", "nan"]):
            return NormalizationResult(
                normalized_price=None,
                status="Missing",
                trust_flag="Missing / Not Quoted",
                formula_citation="Quote omitted by vendor",
                missing_inputs=["Quote price"],
                original_value=orig_val,
                original_currency=orig_curr,
                original_uom=orig_uom,
                unresolved_reason="Quote omitted by vendor"
            )
    else:
        raw_str = f"{raw_value} {orig_uom}".strip().lower()

    # Explicit Disqualified check
    if "disqualified" in raw_str:
        return NormalizationResult(
            normalized_price=None,
            status="Verified",
            trust_flag="Disqualified",
            formula_citation="Vendor disqualified for this line item specification",
            missing_inputs=[],
            original_value=orig_val,
            original_currency=orig_curr,
            original_uom=orig_uom,
            unresolved_reason="Vendor disqualified for this line item specification"
        )

    # Explicit Not Quoted check
    if any(k in raw_str for k in ["not quoted", "omitted"]):
        return NormalizationResult(
            normalized_price=None,
            status="Missing",
            trust_flag="Missing / Not Quoted",
            formula_citation=f"Line omitted by vendor: '{raw_value}'",
            missing_inputs=["Quote price"],
            original_value=orig_val,
            original_currency=orig_curr,
            original_uom=orig_uom,
            unresolved_reason=f"Quote omitted by vendor: '{raw_value}'"
        )

    # 2. Historical PO check ("Same as last year")
    if "same as last year" in raw_str or "historical" in raw_str:
        if is_new_sku or last_po_price is None or pd.isna(last_po_price) or float(last_po_price or 0) <= 0:
            citation = "Quoted 'Same as last year', but item is a New SKU with no PO history -> UNRESOLVED"
            return NormalizationResult(
                normalized_price=None,
                status=UnresolvedStatus("Unresolved"),
                trust_flag="UNRESOLVED",
                formula_citation=citation,
                missing_inputs=["FY25 Historical PO Price"],
                original_value=orig_val,
                original_currency=orig_curr,
                original_uom=orig_uom,
                unresolved_reason="Missing historical PO price for repeat SKU reference. Buyer review required."
            )
        else:
            base_po = float(last_po_price)
            landed = round(base_po * (1.0 + inflation_index), 2)
            citation = f"Resolved from FY25 PO (₹{base_po:.2f}) + {inflation_index*100:.1f}% index = ₹{landed:.2f}"
            return NormalizationResult(
                normalized_price=landed,
                status="Verified",
                trust_flag="Inferred (PO History)",
                formula_citation=citation,
                missing_inputs=[],
                original_value=orig_val,
                original_currency=orig_curr,
                original_uom=orig_uom,
                applied_formula=f"FY25_PO * (1 + {inflation_index})"
            )

    # 3. Extract numeric price
    match = re.search(r"[-+]?(?:\d*\.\d+|\d+)", str(raw_value).replace(",", ""))
    if not match:
        return NormalizationResult(
            normalized_price=None,
            status=UnresolvedStatus("Unresolved"),
            trust_flag="UNRESOLVED",
            formula_citation=f"Unparseable price string: '{raw_value}'",
            missing_inputs=["Numeric price value"],
            original_value=orig_val,
            original_currency=orig_curr,
            original_uom=orig_uom,
            unresolved_reason=f"Cannot extract numeric price from '{raw_value}'. Buyer review required."
        )

    quoted_numeric = float(match.group(0))

    # 4. Currency conversion check
    is_foreign_currency = (
        orig_curr != "INR" or
        "usd" in raw_str or "$" in raw_str or
        any(c in raw_str for c in ["eur", "gbp", "jpy", "cny"])
    )

    eff_fx_rate = 1.0
    eff_fx_date = None
    if is_foreign_currency:
        if fx_rate is None or pd.isna(fx_rate) or float(fx_rate) <= 0:
            return NormalizationResult(
                normalized_price=None,
                status=UnresolvedStatus("Unresolved"),
                trust_flag="UNRESOLVED",
                formula_citation=f"Foreign currency quote ({orig_curr}) with no configured FX rate -> UNRESOLVED",
                missing_inputs=["Configured exchange rate (FX Rate)"],
                original_value=orig_val,
                original_currency=orig_curr,
                original_uom=orig_uom,
                unresolved_reason=f"Missing exchange rate for {orig_curr}. Buyer review required."
            )
        eff_fx_rate = float(fx_rate)
        eff_fx_date = fx_effective_date or DEFAULT_FX_EFFECTIVE_DATE
        price_in_inr = quoted_numeric * eff_fx_rate
        fx_formula_part = f"{orig_curr} {quoted_numeric:.4f} × ₹{eff_fx_rate:.2f}/{orig_curr} (RFx bid-close assumption: {eff_fx_date})"
    else:
        price_in_inr = quoted_numeric
        fx_formula_part = f"₹{quoted_numeric:.2f}"

    # 5. Determine quoted and target UOM
    quoted_uom_type = parse_uom(raw_unit if raw_unit else raw_str)
    target_uom_type = parse_uom(target_uom)

    # 6. UOM conversions
    # Unsupported or unknown UOM
    if quoted_uom_type in ["unknown", "unsupported"]:
        return NormalizationResult(
            normalized_price=None,
            status=UnresolvedStatus("Unresolved"),
            trust_flag="UNRESOLVED",
            formula_citation=f"Unsupported or ambiguous UOM: '{raw_unit or raw_value}' -> UNRESOLVED",
            missing_inputs=["Valid standard unit of measure (UOM)"],
            original_value=orig_val,
            original_currency=orig_curr,
            original_uom=orig_uom,
            exchange_rate=eff_fx_rate if is_foreign_currency else None,
            exchange_rate_date=eff_fx_date if is_foreign_currency else None,
            unresolved_reason=f"Unsupported UOM '{raw_unit or raw_value}'. Cannot convert to {target_uom}. Buyer review required."
        )

    # Check for non-interchangeable UOM combinations:
    # Set vs Piece
    if quoted_uom_type == "set" and target_uom_type != "set":
        return NormalizationResult(
            normalized_price=None,
            status=UnresolvedStatus("Unresolved"),
            trust_flag="UNRESOLVED",
            formula_citation="Quoted per Set while target is Nos/Piece without piece-per-set ratio -> UNRESOLVED",
            missing_inputs=["Pieces per Set specification"],
            original_value=orig_val,
            original_currency=orig_curr,
            original_uom=orig_uom,
            unresolved_reason="Quoted per Set; pieces per Set conversion basis missing. Buyer review required."
        )
    if quoted_uom_type != "set" and target_uom_type == "set" and quoted_uom_type not in ["kg", "sqm"]:
        # Piece quoted for a Set line without piece-per-set ratio
        return NormalizationResult(
            normalized_price=None,
            status=UnresolvedStatus("Unresolved"),
            trust_flag="UNRESOLVED",
            formula_citation=f"Quoted {quoted_uom_type} while target UOM is Set without conversion ratio -> UNRESOLVED",
            missing_inputs=["Set composition / piece ratio"],
            original_value=orig_val,
            original_currency=orig_curr,
            original_uom=orig_uom,
            unresolved_reason="Quoted per piece while RFx line UOM is Set. Buyer review required."
        )

    # Running Metre
    if quoted_uom_type == "running_metre":
        return NormalizationResult(
            normalized_price=None,
            status=UnresolvedStatus("Unresolved"),
            trust_flag="UNRESOLVED",
            formula_citation="Quoted per Running Metre; conversion to piece requires cutting/board length -> UNRESOLVED",
            missing_inputs=["Board length per piece for running metre conversion"],
            original_value=orig_val,
            original_currency=orig_curr,
            original_uom=orig_uom,
            unresolved_reason="Quoted in Running Metre. Conversion basis missing. Buyer review required."
        )

    # 7. Convert base price according to UOM
    price_per_piece = 0.0
    uom_formula_part = ""
    applied_formula_name = ""
    missing_inputs_list: List[str] = []

    if quoted_uom_type == "per_1000":
        price_per_piece = price_in_inr / 1000.0
        uom_formula_part = f"{fx_formula_part} ÷ 1,000"
        applied_formula_name = "Price / 1000"

    elif quoted_uom_type == "kg":
        # Per-kg conversion REQUIRES known, valid weight basis
        if item_weight_kg is None or pd.isna(item_weight_kg) or float(item_weight_kg) <= 0:
            return NormalizationResult(
                normalized_price=None,
                status=UnresolvedStatus("Unresolved"),
                trust_flag="UNRESOLVED",
                formula_citation="Weight missing for kg-based conversion -> UNRESOLVED",
                missing_inputs=["Item weight basis (kg/UoM)"],
                original_value=orig_val,
                original_currency=orig_curr,
                original_uom=orig_uom,
                exchange_rate=eff_fx_rate if is_foreign_currency else None,
                exchange_rate_date=eff_fx_date if is_foreign_currency else None,
                unresolved_reason="Quoted in ₹/kg but item weight basis is missing or zero. Buyer review required."
            )
        wt = float(item_weight_kg)

        # Handle freight for kg quote
        # Freight included vs extra
        freight_per_kg = 0.0
        freight_treatment_desc = "Freight included in base quote"
        if not freight_included:
            if freight_extra_rate is not None and not pd.isna(freight_extra_rate) and float(freight_extra_rate) >= 0:
                freight_per_kg = float(freight_extra_rate)
                freight_treatment_desc = f"Freight extra: ₹{freight_per_kg:.2f}/kg applied"
            elif delivery_location:
                f_rates = freight_rates or DEFAULT_FREIGHT_RATES
                if delivery_location in f_rates:
                    freight_per_kg = f_rates[delivery_location]
                    freight_treatment_desc = f"Freight extra: ₹{freight_per_kg:.2f}/kg for {delivery_location}"
                else:
                    return NormalizationResult(
                        normalized_price=None,
                        status=UnresolvedStatus("Unresolved"),
                        trust_flag="UNRESOLVED",
                        formula_citation=f"Delivery location '{delivery_location}' missing freight rate -> UNRESOLVED",
                        missing_inputs=[f"Freight rate for delivery location '{delivery_location}'"],
                        original_value=orig_val,
                        original_currency=orig_curr,
                        original_uom=orig_uom,
                        unresolved_reason=f"Freight rate unknown for '{delivery_location}'. Buyer review required."
                    )
            else:
                return NormalizationResult(
                    normalized_price=None,
                    status=UnresolvedStatus("Unresolved"),
                    trust_flag="UNRESOLVED",
                    formula_citation="Freight extra quoted but delivery location/rate missing -> UNRESOLVED",
                    missing_inputs=["Delivery location or freight rate"],
                    original_value=orig_val,
                    original_currency=orig_curr,
                    original_uom=orig_uom,
                    unresolved_reason="'Freight extra' quoted without rate or location. Landed cost unresolved. Buyer review required."
                )

        total_rate_per_kg = price_in_inr + freight_per_kg
        price_per_piece = total_rate_per_kg * wt
        f_note = f" + ₹{freight_per_kg:.2f} freight" if (not freight_included and freight_per_kg > 0) else ""
        uom_formula_part = f"({fx_formula_part}/kg{f_note}) × {wt:.4f}kg"
        applied_formula_name = "(Rate/kg + Freight/kg) * Weight_kg"

    elif quoted_uom_type == "sqm":
        # Per-sqm conversion REQUIRES known, valid area basis
        if item_area_sqm is None or pd.isna(item_area_sqm) or float(item_area_sqm) <= 0:
            return NormalizationResult(
                normalized_price=None,
                status=UnresolvedStatus("Unresolved"),
                trust_flag="UNRESOLVED",
                formula_citation="Area basis missing for sqm-based conversion -> UNRESOLVED",
                missing_inputs=["Item area basis (sqm/UoM)"],
                original_value=orig_val,
                original_currency=orig_curr,
                original_uom=orig_uom,
                exchange_rate=eff_fx_rate if is_foreign_currency else None,
                exchange_rate_date=eff_fx_date if is_foreign_currency else None,
                unresolved_reason="Quoted in ₹/sqm but item board area is missing. Buyer review required."
            )
        area = float(item_area_sqm)
        price_per_piece = price_in_inr * area
        uom_formula_part = f"({fx_formula_part}/sqm) × {area:.4f}sqm"
        applied_formula_name = "Rate_sqm * Area_sqm"

    else:
        # Standard piece quote
        price_per_piece = price_in_inr
        uom_formula_part = fx_formula_part
        applied_formula_name = "Direct piece quote"

    # 8. Tax Treatment: GST included vs excluded (RFQ requires landed price excluding GST)
    tax_treatment_desc = "GST 18% extra (excluded from landed price)"
    if gst_included:
        # Quote includes GST -> back out GST to avoid double-counting tax
        tax_treatment_desc = f"GST {gst_rate*100:.0f}% included in quote; backed out (÷ {1.0+gst_rate:.2f})"
        price_per_piece = price_per_piece / (1.0 + gst_rate)
        uom_formula_part = f"({uom_formula_part}) ÷ {1.0+gst_rate:.2f} [GST Excluded]"

    # 9. Conditional Discounts: Applied ONLY if conditions are satisfied
    discount_applied_amount = 0.0
    if discount_pct > 0:
        if condition_met:
            discount_applied_amount = price_per_piece * discount_pct
            price_per_piece = price_per_piece * (1.0 - discount_pct)
            uom_formula_part = f"({uom_formula_part}) - {discount_pct*100:.1f}% discount [{discount_condition}]"
            discount_desc = f"{discount_pct*100:.1f}% applied (Condition satisfied: {discount_condition})"
        else:
            discount_desc = f"{discount_pct*100:.1f}% NOT applied (Condition unmet: {discount_condition})"
    else:
        discount_desc = None

    if is_foreign_currency:
        val = round(price_per_piece, 4)
        if round(val, 2) == val:
            landed_cost = round(val, 2)
        elif round(val, 3) == val:
            landed_cost = round(val, 3)
        else:
            landed_cost = val
    else:
        landed_cost = round(price_per_piece, 2)

    cost_str = f"₹{landed_cost:.3f}" if (is_foreign_currency and round(landed_cost, 2) != landed_cost) else f"₹{landed_cost:.2f}"
    final_citation = f"{uom_formula_part} = {cost_str}"

    # Determine trust flag and status per PRD classification:
    # Directly extracted -> Verified; System-derived currency conversion -> Inferred
    if is_foreign_currency:
        trust_flag = "Inferred (USD to INR)" if orig_curr == "USD" else f"Inferred ({orig_curr} to INR)"
        status_val = InferredStatus("Inferred")
    elif quoted_uom_type == "per_1000":
        trust_flag = "Inferred (/1000 to piece)"
        status_val = "Verified"
    elif quoted_uom_type == "kg":
        trust_flag = "Inferred (kg to piece)"
        status_val = "Verified"
    elif quoted_uom_type == "sqm":
        trust_flag = "Inferred (sqm to piece)"
        status_val = "Verified"
    else:
        trust_flag = "Verified"
        status_val = "Verified"

    return NormalizationResult(
        normalized_price=landed_cost,
        status=status_val,
        trust_flag=trust_flag,
        formula_citation=final_citation,
        missing_inputs=[],
        original_value=orig_val,
        original_currency=orig_curr,
        original_uom=orig_uom,
        applied_formula=applied_formula_name,
        exchange_rate=eff_fx_rate if is_foreign_currency else None,
        exchange_rate_date=eff_fx_date if is_foreign_currency else None,
        freight_treatment="Included" if freight_included else "Extra",
        tax_treatment=tax_treatment_desc,
        applied_discount=discount_pct if (discount_pct > 0 and condition_met) else 0.0,
        discount_condition=discount_condition,
        unresolved_reason=None
    )


def prepare_quote_editor_df(
    df_norm: pd.DataFrame,
    editor_cols: List[str],
    vendor_cols: List[str]
) -> pd.DataFrame:
    """
    Prepares a display and editing DataFrame for Streamlit's st.data_editor.
    Converts vendor price columns into object/string representations that:
    - Display formatted prices (e.g. '6.12') for verified quotes.
    - Display 'UNRESOLVED' for unresolved, missing, or unverified quotes requiring buyer review.
    - Use string data kinds so that st.column_config.TextColumn is 100% compatible with Streamlit.
    - Preserves all non-vendor columns with their native types.
    """
    display_df = df_norm[editor_cols].copy()
    for col in vendor_cols:
        if col not in display_df.columns:
            continue
        v_code = col.split()[0]
        status_col = f"{v_code} Status"
        trust_col = "V5 Trust Flag" if col.startswith("V5") else None

        formatted_vals = []
        for _, row in df_norm.iterrows():
            val = row.get(col)
            stat = row.get(status_col)
            trust = row.get(trust_col) if trust_col else None

            # If status is Unresolved, or trust flag is UNRESOLVED, or val is null/NaN
            if stat == "Unresolved" or trust == "UNRESOLVED" or pd.isna(val):
                formatted_vals.append("UNRESOLVED")
            else:
                formatted_vals.append(f"{float(val):.2f}")
        display_df[col] = formatted_vals
    return display_df


def parse_vendor_cell_edit(
    edited_val: Any,
    current_val: Any,
    line_no: int,
    delivery_location: Optional[str] = None,
    item_weight_kg: Optional[float] = None,
    is_new_sku: bool = False,
    fx_rate: Optional[float] = None,
    freight_rates: Optional[Dict[str, float]] = None
) -> Tuple[Optional[float], str, Optional[str], Optional[str], bool]:
    """
    Parses a user edit from the Streamlit Quote Comparison Matrix data editor.
    Safely converts edited string representations back into expected typed values.

    Returns:
    (converted_numeric_price, status, citation, unresolved_reason, has_changed)

    - If unchanged: has_changed=False, preserves existing values.
    - If cleared / null: has_changed=True (if was notna), returns (None, 'Unresolved', ...).
    - If 'UNRESOLVED': has_changed=True (if was notna), returns (None, 'Unresolved', ...).
    - If valid numeric or formula (e.g. '12.50', '₹42/kg', '$0.15'): runs through normalize_price,
      returning the numeric landed float, 'Verified' status, and audit citation.
    """
    # 1. Null / empty / cleared cell
    if edited_val is None or pd.isna(edited_val) or str(edited_val).strip() in ["", "none", "null", "nan"]:
        if pd.notna(current_val):
            return None, "Unresolved", "Buyer Overridden: Value cleared", "Buyer cleared quotation value", True
        return None, "Unresolved", None, "Unresolved quote", False

    edited_str = str(edited_val).strip()

    # 2. Check if unchanged numeric value
    if pd.notna(current_val):
        try:
            numeric_check = float(edited_str.replace("₹", "").replace("$", "").replace(",", "").strip())
            if abs(numeric_check - float(current_val)) < 1e-4:
                return float(current_val), "Verified", None, None, False
        except ValueError:
            pass

    # 3. Explicit UNRESOLVED status
    if edited_str.upper() == "UNRESOLVED":
        if pd.notna(current_val):
            return None, "Unresolved", "Buyer Overridden: Explicitly set to UNRESOLVED", "Buyer marked line as Unresolved", True
        return None, "Unresolved", None, "Unresolved quote requiring buyer review", False

    # 4. Infer unit and currency from user string input
    lower_str = edited_str.lower()
    if any(k in lower_str for k in ["/kg", "per kg", "₹/kg", "rs/kg", "inr/kg", "kg"]):
        raw_unit = "₹/kg"
        raw_curr = "INR"
    elif any(k in lower_str for k in ["1000", "per 1000", "/1000", "thousand"]):
        raw_unit = "per 1,000 Nos"
        raw_curr = "INR"
    elif any(k in lower_str for k in ["/sqm", "per sqm", "sqm", "m2"]):
        raw_unit = "sqm"
        raw_curr = "INR"
    elif "usd" in lower_str or "$" in lower_str:
        raw_unit = "Nos"
        raw_curr = "USD"
    else:
        raw_unit = "Nos"
        raw_curr = "INR"

    norm_res = normalize_price(
        raw_value=edited_str,
        raw_unit=raw_unit,
        raw_currency=raw_curr,
        line_no=line_no,
        delivery_location=delivery_location,
        item_weight_kg=item_weight_kg,
        is_new_sku=is_new_sku,
        fx_rate=fx_rate or DEFAULT_FX_RATE,
        freight_rates=freight_rates or DEFAULT_FREIGHT_RATES,
        freight_included=False
    )

    cite = f"Buyer Overridden: '{edited_str}' -> {norm_res.formula_citation}"

    if norm_res.status == "Verified" and norm_res.normalized_price is not None:
        new_val = float(norm_res.normalized_price)
        if pd.isna(current_val) or abs(new_val - float(current_val)) > 1e-4:
            return new_val, "Verified", cite, None, True
        return float(current_val), "Verified", None, None, False
    else:
        # Normalization failed or unresolved
        if pd.notna(current_val):
            return None, "Unresolved", cite, norm_res.unresolved_reason, True
        return None, "Unresolved", cite, norm_res.unresolved_reason, False
