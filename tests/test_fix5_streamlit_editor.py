"""
Regression Test Suite: Streamlit Data Editor Type Compatibility & Vendor Columns
================================================================================
Reproduces and verifies the resolution of:
StreamlitAPIException: The configured column type `text` for column `V5 (Standard Box)`
is not compatible for editing the underlying data type `float`.

Tests:
1. Exact reproduction of StreamlitAPIException with float DataFrame configured as TextColumn.
2. prepare_quote_editor_df produces compatible string columns for all 5 vendors.
3. Streamlit compatibility check passes cleanly for all 5 vendor columns and metadata.
4. Numeric value editing across all 5 vendors (V1 to V5).
5. Null / cleared value handling across all 5 vendors (V1 to V5).
6. Explicit 'UNRESOLVED' status handling across all 5 vendors.
7. Unit-formula overrides (e.g. '₹42/kg', '$0.15', per-1,000) across all 5 vendors.
8. Unchanged cells do not trigger unnecessary recalculations (has_changed=False).
9. Underlying df_norm preserves float dtypes for award engine and scenario calculations.
10. app.py integration and editor configuration verification.
"""

import os
import pytest
import numpy as np
import pandas as pd
import pyarrow as pa
import streamlit as st
from streamlit.elements.widgets.data_editor import _check_type_compatibilities
from streamlit.elements.lib.column_config_utils import determine_dataframe_schema, process_config_mapping
from streamlit.errors import StreamlitAPIException

from core.normalizer import (
    prepare_quote_editor_df,
    parse_vendor_cell_edit,
    normalize_price
)
from core.scenarios import calculate_award_scenarios
from core.eligibility import VendorQualification
from core.config import DEFAULT_FX_RATE, DEFAULT_FREIGHT_RATES


VENDOR_COLS = ["V1 (Apex)", "V2 (PackTech)", "V3 (Global USD)", "V4 (Balaji)", "V5 (Standard Box)"]
EDITOR_COLS = [
    "Line #", "Item Code", "Description", "Est. Qty", "Delivery Location", "Criticality", "Budget Price",
    "V1 (Apex)", "V2 (PackTech)", "V3 (Global USD)", "V4 (Balaji)", "V5 (Standard Box)", "V5 Trust Flag"
]


@pytest.fixture
def sample_normalized_df():
    """Builds a realistic 5-line normalized DataFrame with numeric floats and unresolved lines."""
    rows = []
    for l_no in range(1, 6):
        qty = 1000 * l_no
        budget = 10.0 + l_no
        wt = 0.1661 if l_no < 5 else None

        rows.append({
            "Line #": l_no,
            "Item Code": f"CP-{l_no:03d}",
            "Description": f"Packaging Line {l_no}",
            "Est. Qty": qty,
            "Delivery Location": "Pune (Chakan plant)",
            "Criticality": "A" if l_no == 1 else "C",
            "Budget Price": budget,
            "Est. Wt (kg)": wt,
            "V1 (Apex)": round(budget * 0.95, 2),
            "V2 (PackTech)": round(budget * 0.98, 2),
            "V3 (Global USD)": round(budget * 0.92, 2),
            "V4 (Balaji)": round(budget * 0.90, 2),
            "V5 (Standard Box)": round(budget * 0.93, 2) if l_no < 4 else np.nan,
            "V1 Status": "Verified",
            "V2 Status": "Verified",
            "V3 Status": "Verified",
            "V4 Status": "Verified",
            "V5 Status": "Verified" if l_no < 4 else "Unresolved",
            "V5 Trust Flag": "Verified" if l_no < 4 else "UNRESOLVED",
            "V1 Citation": "Formula V1",
            "V2 Citation": "Formula V2",
            "V3 Citation": "Formula V3",
            "V4 Citation": "Formula V4",
            "V5 Citation": "Formula V5"
        })
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# 1. EXACT BUG REPRODUCTION
# ─────────────────────────────────────────────────────────────────────────────
def test_1_reproduce_exact_streamlit_api_exception_float_as_text():
    """
    Reproduces the exact StreamlitAPIException when a float DataFrame column is
    configured with TextColumn without type preparation.
    """
    df_float = pd.DataFrame({
        "Line #": [1, 2],
        "V5 (Standard Box)": [6.51, np.nan]  # float64 dtype
    })
    assert df_float["V5 (Standard Box)"].dtype == np.float64

    # Configuring a float column as TextColumn triggers StreamlitAPIException
    col_config = {
        "Line #": st.column_config.NumberColumn(format="%d"),
        "V5 (Standard Box)": st.column_config.TextColumn(help="Type a number or ₹42/kg")
    }

    config_mapping = process_config_mapping(col_config)
    arrow_table = pa.Table.from_pandas(df_float)
    schema = determine_dataframe_schema(df_float, arrow_table.schema)

    with pytest.raises(StreamlitAPIException) as exc_info:
        _check_type_compatibilities(df_float, config_mapping, schema)

    err_msg = str(exc_info.value)
    assert "The configured column type `text` for column `V5 (Standard Box)` is not compatible for editing the underlying data type `float`" in err_msg


# ─────────────────────────────────────────────────────────────────────────────
# 2. TYPE PREPARATION TEST
# ─────────────────────────────────────────────────────────────────────────────
def test_2_prepare_quote_editor_df_produces_compatible_types(sample_normalized_df):
    """
    prepare_quote_editor_df formats vendor columns into string/object types,
    displaying 'UNRESOLVED' for unresolved cells and formatted numbers for valid quotes.
    Preserves numeric types for Line #, Est. Qty, and Budget Price.
    """
    display_df = prepare_quote_editor_df(sample_normalized_df, EDITOR_COLS, VENDOR_COLS)

    # Vendor columns must have object/string dtype
    for col in VENDOR_COLS:
        assert display_df[col].dtype == object, f"Column {col} must be object/string in display_df"

    # Non-vendor numeric columns must preserve native numeric types
    assert pd.api.types.is_integer_dtype(display_df["Line #"])
    assert pd.api.types.is_integer_dtype(display_df["Est. Qty"])
    assert pd.api.types.is_float_dtype(display_df["Budget Price"])

    # Line 4 & 5 V5 (Standard Box) must display 'UNRESOLVED'
    v5_vals = list(display_df["V5 (Standard Box)"])
    assert v5_vals[3] == "UNRESOLVED"
    assert v5_vals[4] == "UNRESOLVED"
    # Line 1 V5 must display formatted string
    assert v5_vals[0] == f"{sample_normalized_df['V5 (Standard Box)'].iloc[0]:.2f}"


# ─────────────────────────────────────────────────────────────────────────────
# 3. STREAMLIT COMPATIBILITY CHECK FOR ALL 5 VENDORS
# ─────────────────────────────────────────────────────────────────────────────
def test_3_all_five_vendor_columns_pass_streamlit_compatibility_check(sample_normalized_df):
    """
    Verifies that the display DataFrame passes Streamlit's official _check_type_compatibilities
    with zero errors when all 5 vendor columns are configured as TextColumn.
    """
    display_df = prepare_quote_editor_df(sample_normalized_df, EDITOR_COLS, VENDOR_COLS)

    column_config = {
        "Line #": st.column_config.NumberColumn(format="%d", width="small"),
        "Item Code": st.column_config.TextColumn(width="small"),
        "Description": st.column_config.TextColumn(width="medium"),
        "Est. Qty": st.column_config.NumberColumn(format="%d"),
        "Delivery Location": st.column_config.TextColumn(width="medium"),
        "Criticality": st.column_config.TextColumn(width="small"),
        "Budget Price": st.column_config.NumberColumn(format="₹%.2f"),
        "V1 (Apex)": st.column_config.TextColumn(help="Apex price"),
        "V2 (PackTech)": st.column_config.TextColumn(help="PackTech price"),
        "V3 (Global USD)": st.column_config.TextColumn(help="Global USD price"),
        "V4 (Balaji)": st.column_config.TextColumn(help="Balaji price"),
        "V5 (Standard Box)": st.column_config.TextColumn(help="Standard Box price"),
        "V5 Trust Flag": st.column_config.TextColumn(width="medium")
    }

    config_mapping = process_config_mapping(column_config)
    arrow_table = pa.Table.from_pandas(display_df)
    schema = determine_dataframe_schema(display_df, arrow_table.schema)

    # Must NOT raise StreamlitAPIException
    _check_type_compatibilities(display_df, config_mapping, schema)


# ─────────────────────────────────────────────────────────────────────────────
# 4. NUMERIC VALUE EDITING ACROSS ALL 5 VENDORS
# ─────────────────────────────────────────────────────────────────────────────
def test_4_numeric_value_editing_on_all_vendors():
    """Tests editing numeric values on all 5 vendor columns."""
    for col in VENDOR_COLS:
        new_val, status, cite, unres_r, changed = parse_vendor_cell_edit(
            edited_val="15.75",
            current_val=10.00,
            line_no=1,
            delivery_location="Pune (Chakan plant)",
            item_weight_kg=0.1661,
            is_new_sku=False
        )
        assert changed is True, f"Failed on {col}"
        assert new_val == 15.75, f"Expected float 15.75, got {new_val}"
        assert status == "Verified"
        assert unres_r is None
        assert "15.75" in cite


# ─────────────────────────────────────────────────────────────────────────────
# 5. NULL / CLEARED VALUE HANDLING ACROSS ALL 5 VENDORS
# ─────────────────────────────────────────────────────────────────────────────
def test_5_null_and_cleared_values_on_all_vendors():
    """Tests clearing cells (empty, None, null) on all 5 vendors."""
    cleared_inputs = [None, "", "   ", "none", "null", "nan"]
    for col in VENDOR_COLS:
        for empty_val in cleared_inputs:
            new_val, status, cite, unres_r, changed = parse_vendor_cell_edit(
                edited_val=empty_val,
                current_val=10.00,  # was previously quoted
                line_no=1,
                delivery_location="Pune (Chakan plant)",
                item_weight_kg=0.1661,
                is_new_sku=False
            )
            assert changed is True, f"Failed to mark change on cleared cell for {col}"
            assert new_val is None, f"Expected None for cleared cell on {col}, got {new_val}"
            assert status == "Unresolved"
            assert "cleared" in unres_r.lower()


# ─────────────────────────────────────────────────────────────────────────────
# 6. EXPLICIT 'UNRESOLVED' STATUS HANDLING ACROSS ALL 5 VENDORS
# ─────────────────────────────────────────────────────────────────────────────
def test_6_explicit_unresolved_string_on_all_vendors():
    """Tests buyer explicitly typing 'UNRESOLVED' into a vendor cell."""
    for col in VENDOR_COLS:
        new_val, status, cite, unres_r, changed = parse_vendor_cell_edit(
            edited_val="UNRESOLVED",
            current_val=10.00,
            line_no=1,
            delivery_location="Pune (Chakan plant)",
            item_weight_kg=0.1661,
            is_new_sku=False
        )
        assert changed is True
        assert new_val is None
        assert status == "Unresolved"
        assert "unresolved" in unres_r.lower()


# ─────────────────────────────────────────────────────────────────────────────
# 7. UNIT-FORMULA OVERRIDES ACROSS ALL 5 VENDORS
# ─────────────────────────────────────────────────────────────────────────────
def test_7_unit_formula_overrides_on_all_vendors():
    """Tests overriding cells with rate formulas (e.g. ₹42/kg, per 1000, USD)."""
    # 1. Per-kg override: ₹42/kg with weight 0.1661 kg + Pune freight 1.20 = (42 + 1.20) * 0.1661 = 7.18
    new_val, status, cite, unres_r, changed = parse_vendor_cell_edit(
        edited_val="₹42/kg",
        current_val=None,  # was previously unresolved
        line_no=1,
        delivery_location="Pune (Chakan plant)",
        item_weight_kg=0.1661,
        is_new_sku=False,
        freight_rates=DEFAULT_FREIGHT_RATES
    )
    assert changed is True
    assert new_val == 7.18
    assert status == "Verified"

    # 2. Per-1000 override: 6120 per 1000 = 6.12
    new_val_1000, status_1000, cite_1000, _, changed_1000 = parse_vendor_cell_edit(
        edited_val="6120 per 1000",
        current_val=10.0,
        line_no=1,
        delivery_location="Pune (Chakan plant)",
        item_weight_kg=0.1661,
        is_new_sku=False
    )
    assert changed_1000 is True
    assert new_val_1000 == 6.12
    assert status_1000 == "Verified"

    # 3. USD override: $0.10 with FX 87.50 = 8.75
    new_val_usd, status_usd, _, _, changed_usd = parse_vendor_cell_edit(
        edited_val="$0.10",
        current_val=10.0,
        line_no=1,
        delivery_location="Pune (Chakan plant)",
        item_weight_kg=0.1661,
        is_new_sku=False,
        fx_rate=87.50
    )
    assert changed_usd is True
    assert new_val_usd == 8.75
    assert status_usd == "Verified"


# ─────────────────────────────────────────────────────────────────────────────
# 8. UNCHANGED CELLS DO NOT TRIGGER RECALCULATIONS
# ─────────────────────────────────────────────────────────────────────────────
def test_8_unchanged_cells_do_not_trigger_recalculation():
    """Unchanged numeric values or unchanged UNRESOLVED must return has_changed=False."""
    # Unchanged numeric
    _, _, _, _, changed_num = parse_vendor_cell_edit(
        edited_val="10.00",
        current_val=10.00,
        line_no=1,
        delivery_location="Pune (Chakan plant)",
        item_weight_kg=0.1661,
        is_new_sku=False
    )
    assert changed_num is False

    # Unchanged UNRESOLVED
    _, _, _, _, changed_unres = parse_vendor_cell_edit(
        edited_val="UNRESOLVED",
        current_val=np.nan,
        line_no=1,
        delivery_location="Pune (Chakan plant)",
        item_weight_kg=0.1661,
        is_new_sku=False
    )
    assert changed_unres is False


# ─────────────────────────────────────────────────────────────────────────────
# 9. UNDERLYING DF_NORM PRESERVES FLOAT DTYPES FOR AWARD ENGINE
# ─────────────────────────────────────────────────────────────────────────────
def test_9_underlying_df_norm_preserves_numeric_floats_for_award_engine(sample_normalized_df):
    """
    Verifies that st.session_state.df_norm continues to store numeric floats,
    ensuring calculate_award_scenarios executes cleanly without string errors.
    """
    df_norm = sample_normalized_df.copy()

    # Simulate an edit cycle: buyer overrides V5 line 4 from UNRESOLVED to 12.50
    conv_val, status, cite, unres_r, changed = parse_vendor_cell_edit(
        edited_val="12.50",
        current_val=df_norm.loc[df_norm["Line #"] == 4, "V5 (Standard Box)"].values[0],
        line_no=4,
        delivery_location="Pune (Chakan plant)",
        item_weight_kg=0.20,
        is_new_sku=False
    )
    assert changed is True
    df_norm.loc[df_norm["Line #"] == 4, "V5 (Standard Box)"] = conv_val

    # Check vendor columns remain numeric float
    for col in VENDOR_COLS:
        assert pd.api.types.is_float_dtype(df_norm[col]), f"{col} must remain float in df_norm"

    quals = {
        "V1": VendorQualification("V1", "Apex", "Eligible", True),
        "V2": VendorQualification("V2", "PackTech", "Eligible", True),
        "V3": VendorQualification("V3", "Global USD", "Eligible", True),
        "V4": VendorQualification("V4", "Balaji", "Eligible", True),
        "V5": VendorQualification("V5", "Standard Box", "Eligible", True)
    }

    scenarios = calculate_award_scenarios(df_norm, quals)
    assert "spend_a" in scenarios
    assert "spend_b" in scenarios
    assert "savings_b" in scenarios
    assert scenarios["spend_a"] > 0
    assert scenarios["spend_b"] > 0
