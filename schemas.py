"""
Pydantic schemas for Home Loan NBA Agent System.
Defines all input/output models for loan data and agent responses.
Uses flexible string fields with normalization for better CSV compatibility.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal, List
from enum import Enum


# ============================================================================
# ENUMS FOR OUTPUT CONTROLLED VALUES
# ============================================================================

class SMAClassification(str, Enum):
    STANDARD = "Standard"
    SMA_0 = "SMA-0"
    SMA_1 = "SMA-1"
    SMA_2 = "SMA-2"
    NPA = "NPA"


class BorrowerIntent(str, Enum):
    COOPERATIVE = "Cooperative"
    STRESSED = "Stressed"
    STRATEGIC = "Strategic"
    NON_RESPONSIVE = "Non-responsive"


class ConfidenceLevel(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class NextBestAction(str, Enum):
    GENTLE_NUDGING = "Gentle nudging / Digital reminder"
    RM_INTERVENTION = "Relationship Manager intervention"
    RESTRUCTURING = "Restructuring / EMI recast"
    PRE_LEGAL_NOTICE = "Pre-legal notice"
    SARFAESI_13_2 = "SARFAESI Section 13(2) notice"
    SYMBOLIC_POSSESSION = "Symbolic possession"
    PHYSICAL_POSSESSION = "Physical possession"
    AUCTION_INITIATION = "Auction initiation"
    OTS = "One-Time Settlement (OTS)"
    ARC_SALE = "ARC sale"
    TECHNICAL_WRITEOFF = "Technical write-off (policy-based)"
    HOLD_NO_ACTION = "Hold / No action (regulatory or policy constraint)"


# ============================================================================
# INPUT SCHEMA - LOAN DATA FROM CSV (FLEXIBLE)
# ============================================================================

class LoanInput(BaseModel):
    """
    Complete input schema for a single Home Loan NPA account.
    Fully aligned with loan_delinquency_cases database table.
    """

    # Primary Identifiers
    loan_id: str = Field(..., alias="account_id")
    customer_id: str
    customer_full_name: str

    # Loan & Collateral Details
    loan_type: str
    secured_unsecured: str = Field(..., alias="secured_flag")
    collateral_type: Optional[str]
    collateral_quality: Optional[str]
    collateral_liquidity: Optional[str]

    loan_amount: float
    outstanding_amount: float
    emi_amount: float
    tenure_months: int
    loan_vintage_months: int

    # Customer Profile
    borrower_type: str = Field(..., alias="customer_type")
    geographic_location: str = Field(..., alias="geography")
    annual_income_total: Optional[str]
    interest_rate: int

    # Recovery Economics
    cost_of_recovery: float
    expected_recovery: float
    cibil_score: int

    # Delinquency & Behaviour
    dpd: int
    contactability_score: int
    customer_responsiveness: str = Field(..., alias="response_to_calls")
    field_visit_outcome: Optional[str]
    broken_promises_count: int

    # Collection Actions
    last_action_taken: Optional[str]
    days_since_last_action: int

    call_done: str
    field_visit_done: str
    restructure_offered: str
    restructure_accepted: str

    legal_notice_sent: str
    possession: str
    auction: str
    ots_offered: str
    ots_accepted: str

    # Documentation & Legal Readiness
    chg_form_type: Optional[str]
    hypothecation_deed_flag: str
    sanction_letter_flag: str
    charge_instrument_flag: str
    borrower_response_logged: str

    charge_registered_flag: str
    dsc_available_flag: str
    director_din_available: str
    certificate_of_registration_flag: str
    authorized_signatory_pan: str
    cs_membership_no_flag: str

    # SARFAESI
    sarfaesi_ready_flag: str

    created_at: Optional[str]

    # -------- Optional / Derived Fields for Agent Logic --------
    employment_stability: str = "Moderate"
    repayment_history: str = "Irregular"
    pincode: str = "000000"
    time_value_recovery_months: int = 12
    regulatory_constraints: str = "None"
    bank_portfolio_strategy: str = "Standard Recovery"
    jurisdiction: str = "India"
    documentation_type: str = "Complete"
    loan_officer_remarks: str = ""

    # ---------------- Validators ----------------

    @field_validator("pincode")
    @classmethod
    def validate_pincode(cls, v):
        v = str(v).strip()
        if "." in v:
            v = v.split(".")[0]
        v = v.zfill(6)
        if not v.isdigit() or len(v) != 6:
            raise ValueError("Pincode must be a 6-digit number")
        return v

    @field_validator("secured_unsecured")
    @classmethod
    def normalize_secured(cls, v):
        v = str(v).strip().lower()
        if "secured" in v and "unsecured" not in v:
            return "Secured"
        if "unsecured" in v:
            return "Unsecured"
        return v.title()

    @field_validator("borrower_type")
    @classmethod
    def normalize_borrower_type(cls, v):
        v = str(v).strip().lower()
        if "corporate" in v or "company" in v:
            return "Corporate"
        if "self" in v:
            return "Self-employed"
        if "salar" in v:
            return "Salaried"
        return "Individual"

    @field_validator("collateral_quality")
    @classmethod
    def normalize_collateral_quality(cls, v):
        if not v:
            return v
        v = v.lower()
        if v in ["high", "excellent", "prime"]:
            return "High"
        if v in ["medium", "moderate", "average"]:
            return "Medium"
        if v in ["low", "poor"]:
            return "Low"
        return v.title()

    @field_validator("geographic_location")
    @classmethod
    def normalize_geography(cls, v):
        v = str(v).strip().lower()
        if v in ["metro", "urban"]:
            return "Metro"
        if "semi" in v or "tier-1" in v:
            return "Tier-1"
        if "tier-2" in v:
            return "Tier-2"
        if "tier-3" in v:
            return "Tier-3"
        if "rural" in v:
            return "Rural"
        return v.title()

    @field_validator("customer_responsiveness")
    @classmethod
    def normalize_responsiveness(cls, v):
        v = str(v).strip().lower()
        if v in ["responsive", "cooperative", "good"]:
            return "Cooperative"
        if v in ["partial", "moderate"]:
            return "Partially-responsive"
        if v in ["no response", "non-responsive", "unresponsive"]:
            return "Non-responsive"
        if v in ["wilful", "strategic"]:
            return "Strategic"
        return v.title()

    # ---------------- Agent Context ----------------

    def to_agent_context(self) -> dict:
        """
        Converts model into dict for GenAI / Agent prompt usage.
        Keeps DB aliases intact.
        """
        return self.model_dump(by_alias=True)
 


# ============================================================================
# AGENT OUTPUT SCHEMAS
# ============================================================================

class EligibilityOutput(BaseModel):
    """Output from Eligibility & Classification Agent."""
    sma_classification: str = Field(..., description="SMA/NPA classification")
    is_npa: bool = Field(..., description="Whether account is NPA")
    sarfaesi_eligible: bool = Field(..., description="Eligible for SARFAESI action")
    sarfaesi_ineligibility_reason: Optional[str] = Field(None, description="Reason if not eligible")
    loan_stage: str = Field(..., description="New default / Late-stage default")
    legal_actions_available: List[str] = Field(..., description="List of legally available actions")
    reasoning: str = Field(..., description="Reasoning for classification")


class BorrowerIntentOutput(BaseModel):
    """Output from Borrower Intent & Behaviour Agent."""
    intent_classification: str = Field(..., description="Borrower intent category")
    willingness_to_pay: str = Field(..., description="High/Medium/Low willingness")
    ability_to_pay: str = Field(..., description="High/Medium/Low ability")
    risk_profile: str = Field(..., description="Risk assessment")
    recommended_approach: str = Field(..., description="Suggested engagement approach")
    reasoning: str = Field(..., description="Reasoning for classification")


class CollateralOutput(BaseModel):
    """Output from Collateral & Recovery Economics Agent."""
    collateral_liquidity: str = Field(..., description="High/Medium/Low liquidity")
    estimated_sale_value: float = Field(..., description="Estimated sale value in INR")
    recovery_viability: str = Field(..., description="Viable/Marginal/Not viable")
    npv_positive: bool = Field(..., description="Whether enforcement is NPV-positive")
    cost_benefit_ratio: float = Field(..., description="Expected recovery / Cost ratio")
    recommended_recovery_path: str = Field(..., description="Suggested recovery approach")
    reasoning: str = Field(..., description="Reasoning for economics analysis")


class RegulatoryOutput(BaseModel):
    """Output from Regulatory & Policy Guardrail Agent."""
    compliance_status: str = Field(..., description="Compliant/Non-compliant/Restricted")
    blocked_actions: List[str] = Field(..., description="Actions that cannot be taken now")
    required_notices: List[str] = Field(..., description="Notices required before escalation")
    mandatory_waiting_periods: List[str] = Field(..., description="Required waiting periods")
    policy_constraints: List[str] = Field(..., description="Internal policy constraints")
    regulatory_notes: str = Field(..., description="Important regulatory notes")
    reasoning: str = Field(..., description="Reasoning for compliance assessment")


class NBAOutput(BaseModel):
    """Final output from NBA Synthesizer Agent."""
    next_best_action: str = Field(..., description="Recommended primary action")
    reasoning: List[str] = Field(..., description="Bullet-point reasoning")
    confidence_level: str = Field(..., description="Confidence in recommendation")
    fallback_action: str = Field(..., description="Fallback if primary fails")
    regulatory_notes: List[str] = Field(..., description="Regulatory notes and requirements")
    economic_rationale: str = Field(..., description="NPV/economic justification")
    rbi_alignment: str = Field(..., description="RBI compliance notes")


# ============================================================================
# COMPLETE OUTPUT FOR A SINGLE LOAN
# ============================================================================

class LoanDecision(BaseModel):
    """Complete decision output for a single loan."""
    loan_id: str
    eligibility: EligibilityOutput
    borrower_intent: BorrowerIntentOutput
    collateral: CollateralOutput
    regulatory: RegulatoryOutput
    nba: NBAOutput
    processing_status: str = Field(default="Success")
    error_message: Optional[str] = None


# ============================================================================
# VALIDATION ERROR SCHEMA
# ============================================================================

class ValidationError(BaseModel):
    """Validation error for CSV row."""
    row_number: int
    loan_id: Optional[str]
    column_name: str
    error_message: str
    provided_value: str


class CSVValidationResult(BaseModel):
    """Result of CSV validation."""
    is_valid: bool
    valid_loans: List[LoanInput]
    errors: List[ValidationError]
    total_rows: int
    valid_count: int
    error_count: int
