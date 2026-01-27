"""
Configuration constants for NBA Decision System
RBI-compliant definitions and SARFAESI rules for Indian Home Loan Recovery
"""

# =============================================================================
# RBI DELINQUENCY STAGE DEFINITIONS
# =============================================================================
# As per RBI Master Circular on Prudential Norms on Income Recognition, 
# Asset Classification and Provisioning pertaining to Advances

DELINQUENCY_STAGES = {
    "SMA-0": {
        "dpd_range": (1, 30),
        "description": "Special Mention Account - Early stress",
        "risk_level": "Low",
        "classification": "Standard Asset"
    },
    "SMA-1": {
        "dpd_range": (31, 60),
        "description": "Special Mention Account - Moderate stress",
        "risk_level": "Medium",
        "classification": "Standard Asset"
    },
    "SMA-2": {
        "dpd_range": (61, 90),
        "description": "Special Mention Account - High stress",
        "risk_level": "High",
        "classification": "Standard Asset"
    },
    "NPA": {
        "dpd_range": (91, float('inf')),
        "description": "Non-Performing Asset",
        "risk_level": "Critical",
        "classification": "Non-Performing Asset"
    }
}

# =============================================================================
# SARFAESI ACT 2002 - TIMELINE RULES
# =============================================================================
# Securitisation and Reconstruction of Financial Assets and Enforcement of 
# Security Interest Act, 2002

SARFAESI_TIMELINES = {
    "section_13_2": {
        "name": "Demand Notice under Section 13(2)",
        "prerequisite": "Account classified as NPA",
        "waiting_period_days": 60,
        "description": "Notice to borrower demanding payment of outstanding dues"
    },
    "section_13_4": {
        "name": "Possession Notice under Section 13(4)",
        "prerequisite": "60 days elapsed after 13(2) with no satisfactory response",
        "objection_period_days": 45,
        "description": "Notice of intention to take possession of secured asset"
    },
    "symbolic_possession": {
        "name": "Symbolic Possession",
        "prerequisite": "13(4) objection period elapsed",
        "publication_required": True,
        "description": "Taking symbolic possession of secured asset"
    },
    "physical_possession": {
        "name": "Physical Possession",
        "prerequisite": "Symbolic possession completed",
        "court_order_if_occupied": True,
        "description": "Taking physical possession of the property"
    },
    "auction": {
        "name": "Sale/Auction of Secured Asset",
        "prerequisite": "Physical possession obtained",
        "public_notice_days": 30,
        "description": "Sale of secured asset through public auction"
    }
}

# =============================================================================
# VALID RECOVERY ACTIONS BY STAGE
# =============================================================================

RECOVERY_ACTIONS = {
    "early_stage": [
        "Reminder Call",
        "SMS Reminder",
        "Email Reminder",
        "Soft Skill Call",
        "Payment Plan Discussion",
        "EMI Restructure Discussion"
    ],
    "mid_stage": [
        "Field Visit",
        "Formal Demand Letter",
        "Manager Escalation Call",
        "Restructure Proposal",
        "Moratorium Offer"
    ],
    "pre_legal": [
        "Legal Notice Warning",
        "Section 13(2) Notice Issuance",
        "One-Time Settlement (OTS) Proposal",
        "Restructure Final Offer"
    ],
    "legal": [
        "Section 13(4) Notice Issuance",
        "Symbolic Possession",
        "Physical Possession Proceedings",
        "DRT Filing"
    ],
    "resolution": [
        "Auction Initiation",
        "OTS Finalization",
        "Write-off Recommendation",
        "Account Closure"
    ]
}

# =============================================================================
# CONTACT TIME RESTRICTIONS (RBI Fair Practice Code)
# =============================================================================

CONTACT_RESTRICTIONS = {
    "permitted_hours_start": "08:00",
    "permitted_hours_end": "19:00",
    "prohibited_on_holidays": True,
    "max_calls_per_day": 3,
    "third_party_disclosure_prohibited": True
}

# =============================================================================
# RISK SCORING THRESHOLDS
# =============================================================================

RISK_THRESHOLDS = {
    "credit_score": {
        "Excellent": (750, 900),
        "Good": (700, 749),
        "Fair": (650, 699),
        "Poor": (300, 649)
    },
    "contactability": {
        "high": (70, 100),
        "medium": (40, 69),
        "low": (0, 39)
    },
    "broken_promises": {
        "acceptable": (0, 2),
        "concerning": (3, 5),
        "high_risk": (6, float('inf'))
    }
}

# =============================================================================
# ECONOMIC THRESHOLDS
# =============================================================================

ECONOMIC_THRESHOLDS = {
    "min_ots_discount_percent": 10,
    "max_ots_discount_percent": 50,
    "legal_cost_estimate_percent": 5,  # of outstanding amount
    "recovery_time_value_discount_annual": 12,  # discount rate for NPV
    "min_viable_recovery_amount": 50000  # INR
}

# =============================================================================
# OUTPUT CONFIDENCE LEVELS
# =============================================================================

CONFIDENCE_LEVELS = {
    "HIGH": "Strong alignment of all factors; clear recommendation",
    "MEDIUM": "Some conflicting signals; recommendation with caveats",
    "LOW": "Significant uncertainty; recommend conservative approach"
}
