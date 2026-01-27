"""
Data models for NBA Decision System
Pydantic models for type safety and validation
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Literal
from enum import Enum


class DelinquencyStage(str, Enum):
    """RBI-defined delinquency stages"""
    SMA_0 = "SMA-0"
    SMA_1 = "SMA-1"
    SMA_2 = "SMA-2"
    NPA = "NPA"


class SARFAESIStage(str, Enum):
    """SARFAESI Act enforcement stages"""
    NONE = "None"
    SECTION_13_2 = "13(2)"
    SECTION_13_4 = "13(4)"
    POSSESSION = "Possession"
    AUCTION = "Auction"


class CustomerType(str, Enum):
    """Customer employment/business type"""
    SALARIED = "Salaried"
    SELF_EMPLOYED = "Self-employed"
    CORPORATE = "Corporate"


class ResponseToCall(str, Enum):
    """Borrower response patterns"""
    POSITIVE = "Positive"
    DELAYED = "Delayed"
    NONE = "None"


class FieldVisitOutcome(str, Enum):
    """Field visit results"""
    PROMISE_TO_PAY = "Promise to Pay"
    REFUSED = "Refused"
    NOT_DONE = "Not Done"


class LoanAccount(BaseModel):
    """
    Complete loan account model based on input CSV schema.
    All fields map to the indian_loan_delinquency_synthetic(in).csv columns.
    """
    
    # Account Identification
    account_id: str = Field(..., description="Unique account identifier")
    customer_id: str = Field(..., description="Customer identifier")
    
    # Loan Details
    loan_type: str = Field(..., description="Type of loan (Home, Vehicle, Personal, etc.)")
    secured_flag: str = Field(..., description="Secured or Unsecured")
    loan_amount: float = Field(..., gt=0, description="Original loan amount in INR")
    outstanding_amount: float = Field(..., ge=0, description="Current outstanding amount in INR")
    emi_amount: float = Field(..., gt=0, description="EMI amount in INR")
    tenure_months: int = Field(..., gt=0, description="Total loan tenure in months")
    loan_vintage_months: int = Field(..., ge=0, description="Months since loan disbursement")
    
    # Customer Profile
    customer_type: str = Field(..., description="Salaried/Self-employed/Corporate")
    geography: str = Field(..., description="Urban/Semi-urban/Rural")
    co_borrower_present: str = Field(..., description="Yes/No")
    income_band: str = Field(..., description="Low/Medium/High")
    credit_score_band: str = Field(..., description="Poor/Fair/Good/Excellent")
    
    # Delinquency Information
    dpd: int = Field(..., ge=0, description="Days Past Due")
    delinquency_stage: str = Field(..., description="SMA-0/SMA-1/SMA-2/NPA")
    times_delinquent: int = Field(..., ge=0, description="Number of times delinquent historically")
    max_dpd_ever: int = Field(..., ge=0, description="Maximum DPD ever reached")
    last_payment_days_ago: int = Field(..., ge=0, description="Days since last payment")
    
    # Contact History
    contactability_score: int = Field(..., ge=0, le=100, description="Contactability score 0-100")
    response_to_calls: str = Field(..., description="Positive/Delayed/None")
    field_visit_outcome: str = Field(..., description="Promise to Pay/Refused/Not Done")
    broken_promises_count: int = Field(..., ge=0, description="Number of broken payment promises")
    
    # Flags and Status
    fraud_flag: str = Field(..., description="Yes/No")
    last_action_taken: str = Field(..., description="Last recovery action taken")
    days_since_last_action: int = Field(..., ge=0, description="Days since last action")
    
    # Legal Status
    legal_notice_sent: str = Field(..., description="Yes/No")
    sarfaesi_stage: str = Field(..., description="None/13(2)/13(4)/Possession/Auction")
    restructure_offered: str = Field(..., description="Yes/No")
    ots_offered: str = Field(..., description="Yes/No - One Time Settlement offered")
    action_accepted: str = Field(..., description="Yes/No")
    
    # Recovery History
    recovery_amount_30d: float = Field(..., ge=0, description="Recovery in last 30 days")
    recovery_amount_90d: float = Field(..., ge=0, description="Recovery in last 90 days")
    account_resolved: str = Field(..., description="Yes/No")
    resolution_type: Optional[str] = Field(None, description="Regularized/Settled/Written-off")
    
    # Step Tracking (workflow steps completed)
    step_call_done: str = Field(..., description="Yes/No")
    step_field_visit_done: str = Field(..., description="Yes/No")
    step_restructure_initiated: str = Field(..., description="Yes/No")
    step_legal_notice_sent: str = Field(..., description="Yes/No")
    step_sarfaesi_invoked: str = Field(..., description="Yes/No")
    step_possession: str = Field(..., description="Yes/No")
    step_auction: str = Field(..., description="Yes/No")
    step_ots_offered: str = Field(..., description="Yes/No")
    step_ots_accepted: str = Field(..., description="Yes/No")
    
    class Config:
        use_enum_values = True
    
    @classmethod
    def from_csv_row(cls, row: dict) -> "LoanAccount":
        """Create LoanAccount from a CSV row dictionary"""
        return cls(**row)
    
    def get_recovery_rate_30d(self) -> float:
        """Calculate 30-day recovery rate as percentage of EMI"""
        if self.emi_amount > 0:
            return (self.recovery_amount_30d / self.emi_amount) * 100
        return 0.0
    
    def is_secured(self) -> bool:
        """Check if loan is secured"""
        return self.secured_flag.lower() == "secured"
    
    def is_home_loan(self) -> bool:
        """Check if this is a home loan"""
        return self.loan_type.lower() == "home"
    
    def days_in_npa(self) -> int:
        """Calculate days in NPA status"""
        if self.delinquency_stage == "NPA":
            return max(0, self.dpd - 90)
        return 0


class AgentOutput(BaseModel):
    """Standardized output from each agent"""
    agent_name: str
    analysis: str
    risk_factors: List[str]
    recommended_actions: List[str]
    constraints: List[str]
    confidence: Literal["High", "Medium", "Low"]


class NBAResult(BaseModel):
    """Final Next Best Action output"""
    account_id: str
    customer_id: str
    next_best_action: str
    reasoning: List[str]
    confidence_level: Literal["High", "Medium", "Low"]
    fallback_action: str
    regulatory_notes: List[str]
    
    def to_formatted_string(self) -> str:
        """Format NBA result as bank-grade output"""
        reasoning_bullets = "\n".join([f"- {r}" for r in self.reasoning])
        regulatory_bullets = "\n".join([f"- {r}" for r in self.regulatory_notes])
        
        return f"""
## Account: {self.account_id} | Customer: {self.customer_id}

### Next Best Action
**{self.next_best_action}**

### Reasoning
{reasoning_bullets}

### Confidence Level: {self.confidence_level}

### Fallback Action
{self.fallback_action}

### Regulatory Notes
{regulatory_bullets}

---
"""
