"""
Configuration and constants for the AI Procurement Co-pilot.
"""

# Flute take-up factors (fluting paper length per metre of board)
# Note: BCB factor corrected to 1.45 per original RFx specification.
TAKEUP_FACTORS = {
    'B': 1.32,
    'C': 1.43,
    'E': 1.25,
    'BC': 1.38,
    'BCB': 1.45
}

# Currency exchange rates
DEFAULT_FX_RATE = 84.50  # USD to INR
DEFAULT_FX_EFFECTIVE_DATE = "19-Nov-2026"

# Freight rates in ₹/kg by delivery location
DEFAULT_FREIGHT_RATES = {
    "Pune (Chakan plant)": 1.20,
    "Bhiwandi DC": 2.20,
    "Bengaluru (Peenya plant)": 4.50
}

# RFx Metadata
RFX_REFERENCE = "RFx-CORR-2026-017"
RFX_CLOSING_DATE = "19-Nov-2026"
BUYER_PERSONA = "Veda Home Appliances Pvt Ltd"
CATEGORY = "Corrugated Packaging"

# Master vendor list
VENDORS = {
    "V1": {"name": "V1 (Apex)", "full_name": "Apex Packaging", "currency": "INR", "location": "Pune"},
    "V2": {"name": "V2 (PackTech)", "full_name": "PackTech Solutions", "currency": "INR", "location": "Bengaluru"},
    "V3": {"name": "V3 (Global USD)", "full_name": "Global Corrugators Ltd", "currency": "USD", "location": "Nhava Sheva"},
    "V4": {"name": "V4 (Balaji)", "full_name": "Sri Balaji Packaging", "currency": "INR", "location": "Chakan, Pune"},
    "V5": {"name": "V5 (Standard Box)", "full_name": "Standard Box Corp", "currency": "INR", "location": "Bhiwandi"}
}

# Questionnaire evaluation rules
MANDATORY_CRITERIA = {
    "Q1": {"desc": "Valid ISO 9001:2015 Cert", "scope": "All", "rule": "Valid on closing date"},
    "Q2": {"desc": "Monthly Capacity >= 300 TPM", "scope": "All", "rule": "Min 300 TPM"},
    "Q3": {"desc": "In-House Testing Lab", "scope": "All", "rule": "Must be Yes"},
    "Q4": {"desc": "Customer Rejection <= 1.5%", "scope": "All", "rule": "Max 1.5%"},
    "Q5": {"desc": "Active Customers >= 3", "scope": "All", "rule": "Min 3 references"},
    "Q6": {"desc": "7-Ply BCB Capability", "scope": "Line-specific", "applies_to": "7-ply / BCB"},
    "Q7": {"desc": "Moisture-Barrier Treatment", "scope": "Line-specific", "applies_to": "Moisture barrier"}
}
