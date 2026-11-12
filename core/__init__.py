"""
Core procurement co-pilot module.
"""

from core.scenarios import calculate_award_scenarios, evaluate_award_approval_gate
from core.eligibility import evaluate_vendor_qualifications, is_vendor_eligible_for_line
from core.normalizer import normalize_price, prepare_quote_editor_df, parse_vendor_cell_edit
from core.analyst import answer_query, build_system_context
from core.models import VendorQualification, BuyerOverrideRecord, NormalizationResult

