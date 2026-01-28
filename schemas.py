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
    Complete input schema for a single home loan account.
    Maps directly to CSV columns with flexible value handling.
    """
    loan_id: str = Field(..., description="Unique loan identifier")
    secured_unsecured: str = Field(..., description="Secured or Unsecured loan")
    dpd: int = Field(..., ge=0, description="Days Past Due (delinquency)")
    outstanding_amount: float = Field(..., gt=0, description="Outstanding loan amount in INR")
    borrower_type: str = Field(..., description="Type of borrower")
    employment_stability: str = Field(..., description="Employment/business stability")
    repayment_history: str = Field(..., description="Historical repayment behavior")
    loan_vintage_months: int = Field(..., ge=0, description="Loan age in months")
    collateral_quality: str = Field(..., description="Collateral liquidity and quality")
    geographic_location: str = Field(..., description="Location classification")
    pincode: str = Field(..., description="Property pincode")
    customer_responsiveness: str = Field(..., description="Customer communication pattern")
    cost_of_recovery: float = Field(..., ge=0, description="Estimated recovery cost in INR")
    expected_recovery: float = Field(..., ge=0, description="Expected recovery amount in INR")
    time_value_recovery_months: int = Field(..., ge=0, description="Expected time to recover in months")
    regulatory_constraints: str = Field(default="None", description="Any regulatory constraints")
    bank_portfolio_strategy: str = Field(..., description="Bank's portfolio strategy")
    jurisdiction: str = Field(..., description="Legal jurisdiction (state)")
    cibil_score: int = Field(..., ge=300, le=900, description="CIBIL credit score")
    loan_officer_remarks: str = Field(default="", description="Officer notes")
    documentation_type: str = Field(..., description="Documentation completeness")

    @field_validator('pincode')
    @classmethod
    def validate_pincode(cls, v):
        v = str(v).strip()
        # Remove any decimal point (Excel sometimes adds .0)
        if '.' in v:
            v = v.split('.')[0]
        v = v.zfill(6) if len(v) < 6 else v
        if not v.isdigit() or len(v) != 6:
            raise ValueError(f'Pincode must be a 6-digit number, got: {v}')
        return v

    @field_validator('secured_unsecured')
    @classmethod
    def normalize_secured(cls, v):
        v = str(v).strip().lower()
        if 'secured' in v and 'unsecured' not in v:
            return "Secured"
        elif 'unsecured' in v:
            return "Unsecured"
        return v.title()

    @field_validator('borrower_type')
    @classmethod  
    def normalize_borrower_type(cls, v):
        v = str(v).strip().lower()
        if 'corporate' in v or 'company' in v:
            return "Corporate"
        elif 'self' in v and 'employ' in v:
            return "Self-employed"
        elif 'salar' in v:
            return "Salaried"
        elif 'individual' in v:
            return "Individual"
        return str(v).title()

    @field_validator('employment_stability')
    @classmethod
    def normalize_stability(cls, v):
        v = str(v).strip().lower()
        if v in ['stable', 'strong', 'high']:
            return "Stable"
        elif v in ['moderate', 'medium', 'average']:
            return "Moderate"
        elif v in ['unstable', 'weak', 'low', 'poor']:
            return "Unstable"
        return str(v).title()

    @field_validator('repayment_history')
    @classmethod
    def normalize_repayment(cls, v):
        v = str(v).strip().lower()
        if v in ['excellent', 'outstanding']:
            return "Excellent"
        elif v in ['good', 'regular']:
            return "Good"
        elif v in ['irregular', 'delayed', 'partial']:
            return "Irregular"
        elif v in ['poor', 'bad', 'defaulted', 'default']:
            return "Poor"
        return str(v).title()

    @field_validator('collateral_quality')
    @classmethod
    def normalize_quality(cls, v):
        v = str(v).strip().lower()
        if v in ['high', 'excellent', 'prime']:
            return "High"
        elif v in ['medium', 'moderate', 'average']:
            return "Medium"
        elif v in ['low', 'poor', 'weak']:
            return "Low"
        return str(v).title()

    @field_validator('geographic_location')
    @classmethod
    def normalize_location(cls, v):
        v = str(v).strip().lower()
        if v in ['metro', 'metropolitan', 'urban']:
            return "Metro"
        elif 'semi' in v or v == 'tier-1' or v == 'tier1':
            return "Tier-1"
        elif v in ['tier-2', 'tier2', 'city']:
            return "Tier-2"
        elif v in ['tier-3', 'tier3', 'town']:
            return "Tier-3"
        elif v in ['rural', 'village']:
            return "Rural"
        return str(v).title()

    @field_validator('customer_responsiveness')
    @classmethod
    def normalize_responsiveness(cls, v):
        v = str(v).strip().lower()
        if v in ['cooperative', 'high', 'good', 'responsive']:
            return "Cooperative"
        elif v in ['partially-responsive', 'partial', 'medium', 'moderate']:
            return "Partially-responsive"
        elif v in ['non-responsive', 'none', 'no', 'low', 'unresponsive']:
            return "Non-responsive"
        elif v in ['strategic', 'wilful', 'willful']:
            return "Strategic"
        return str(v).title()

    @field_validator('documentation_type')
    @classmethod
    def normalize_documentation(cls, v):
        v = str(v).strip().lower()
        if v in ['complete', 'full', 'yes']:
            return "Complete"
        elif v in ['incomplete', 'partial']:
            return "Incomplete"
        elif v in ['missing', 'none', 'no']:
            return "Missing"
        return str(v).title()

    def to_agent_context(self) -> dict:
        """Convert to dictionary for agent prompts."""
        return {
            "loan_id": self.loan_id,
            "secured_unsecured": self.secured_unsecured,
            "dpd": self.dpd,
            "outstanding_amount": self.outstanding_amount,
            "borrower_type": self.borrower_type,
            "employment_stability": self.employment_stability,
            "repayment_history": self.repayment_history,
            "loan_vintage_months": self.loan_vintage_months,
            "collateral_quality": self.collateral_quality,
            "geographic_location": self.geographic_location,
            "pincode": self.pincode,
            "customer_responsiveness": self.customer_responsiveness,
            "cost_of_recovery": self.cost_of_recovery,
            "expected_recovery": self.expected_recovery,
            "time_value_recovery_months": self.time_value_recovery_months,
            "regulatory_constraints": self.regulatory_constraints,
            "bank_portfolio_strategy": self.bank_portfolio_strategy,
            "jurisdiction": self.jurisdiction,
            "cibil_score": self.cibil_score,
            "loan_officer_remarks": self.loan_officer_remarks,
            "documentation_type": self.documentation_type,
        }


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
