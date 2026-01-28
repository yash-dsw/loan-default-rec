"""
Regulatory & Policy Guardrail Agent
Ensures compliance with RBI, SARFAESI, and internal policies.
"""

import json
import httpx
import os
from typing import Optional, List
from dotenv import load_dotenv

from schemas import RegulatoryOutput
from prompts import get_regulatory_prompt, SYSTEM_PROMPTS

load_dotenv()


class RegulatoryAgent:
    """
    Agent responsible for:
    - Ensuring RBI compliance
    - Enforcing SARFAESI action sequencing
    - Blocking illegal or premature actions
    - Identifying required notices and waiting periods
    """
    
    # SARFAESI action sequence - each action requires all previous steps completed
    SARFAESI_SEQUENCE = [
        "SARFAESI Section 13(2) notice",
        "Symbolic possession",
        "Physical possession",
        "Auction initiation"
    ]
    
    # Actions that require NPA status
    NPA_REQUIRED_ACTIONS = [
        "SARFAESI Section 13(2) notice",
        "Symbolic possession",
        "Physical possession",
        "Auction initiation",
        "ARC sale"
    ]
    
    # Mandatory waiting periods
    WAITING_PERIODS = {
        "SARFAESI Section 13(2) notice": "60 days must elapse before possession",
        "Symbolic possession": "30-day objection window required",
        "Auction initiation": "30-day public notice mandatory"
    }
    
    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.model = "deepseek/deepseek-chat"
        
    async def analyze(self, loan_data: dict, eligibility_output: dict,
                      borrower_intent_output: dict, collateral_output: dict) -> dict:
        """
        Analyze regulatory constraints and return compliance assessment.
        
        Args:
            loan_data: Dictionary containing loan input data
            eligibility_output: Output from eligibility agent
            borrower_intent_output: Output from borrower intent agent
            collateral_output: Output from collateral agent
            
        Returns:
            Dictionary with regulatory compliance assessment
        """
        prompt = get_regulatory_prompt(loan_data, eligibility_output, 
                                       borrower_intent_output, collateral_output)
        
        try:
            response = await self._call_llm(prompt)
            parsed = self._parse_response(response, loan_data, eligibility_output)
            return parsed
        except Exception as e:
            return self._get_fallback_response(loan_data, eligibility_output, str(e))
    
    async def _call_llm(self, prompt: str) -> str:
        """Make API call to LLM."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "Home Loan NBA Agent"
        }
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPTS["regulatory"]},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0,
            "max_tokens": 1200
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(self.api_url, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
    
    def _parse_response(self, response: str, loan_data: dict, eligibility_output: dict) -> dict:
        """Parse LLM response and validate structure."""
        try:
            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0]
            
            parsed = json.loads(json_str.strip())
            
            required_fields = [
                "compliance_status", "blocked_actions", "required_notices",
                "mandatory_waiting_periods", "policy_constraints", 
                "regulatory_notes", "reasoning"
            ]
            for field in required_fields:
                if field not in parsed:
                    raise ValueError(f"Missing required field: {field}")
            
            return parsed
            
        except (json.JSONDecodeError, ValueError) as e:
            return self._get_fallback_response(loan_data, eligibility_output, f"Parse error: {str(e)}")
    
    def _get_fallback_response(self, loan_data: dict, eligibility_output: dict, error: str) -> dict:
        """Generate rule-based fallback response."""
        dpd = loan_data.get("dpd", 0)
        regulatory_constraints = loan_data.get("regulatory_constraints", "None")
        documentation = loan_data.get("documentation_type", "Incomplete")
        secured = loan_data.get("secured_unsecured", "Unsecured")
        outstanding = loan_data.get("outstanding_amount", 0)
        bank_strategy = loan_data.get("bank_portfolio_strategy", "Recovery")
        jurisdiction = loan_data.get("jurisdiction", "")
        
        is_npa = eligibility_output.get("is_npa", False)
        sarfaesi_eligible = eligibility_output.get("sarfaesi_eligible", False)
        
        blocked_actions: List[str] = []
        required_notices: List[str] = []
        waiting_periods: List[str] = []
        policy_constraints: List[str] = []
        
        # Block SARFAESI actions for non-NPA accounts
        if not is_npa:
            blocked_actions.extend([
                "SARFAESI Section 13(2) notice",
                "Symbolic possession",
                "Physical possession",
                "Auction initiation",
                "ARC sale"
            ])
            
        # Block SARFAESI if not eligible
        if not sarfaesi_eligible:
            for action in self.SARFAESI_SEQUENCE:
                if action not in blocked_actions:
                    blocked_actions.append(action)
        
        # For NPA without SARFAESI, still block possession/auction
        if is_npa and not any("13(2)" in str(loan_data.get("loan_officer_remarks", ""))):
            # Assume no 13(2) notice sent yet
            blocked_actions.extend([
                "Symbolic possession",
                "Physical possession",
                "Auction initiation"
            ])
        
        # Check for regulatory constraints (court stays, etc.)
        if regulatory_constraints and regulatory_constraints.lower() != "none":
            constraint_lower = regulatory_constraints.lower()
            if "court stay" in constraint_lower or "stay order" in constraint_lower:
                blocked_actions.append("All enforcement actions pending court order")
                policy_constraints.append(f"Court stay in effect: {regulatory_constraints}")
            if "ibc" in constraint_lower:
                blocked_actions.append("All recovery actions - IBC proceedings in progress")
                policy_constraints.append("IBC admission blocks individual recovery")
            if "drt" in constraint_lower:
                policy_constraints.append("DRT proceedings - coordinate with legal team")
        
        # Documentation constraints
        if documentation != "Complete":
            if "SARFAESI Section 13(2) notice" not in blocked_actions:
                blocked_actions.append("SARFAESI Section 13(2) notice")
            policy_constraints.append("Incomplete documentation - complete before enforcement")
        
        # Bank strategy constraints
        if bank_strategy.lower() == "growth":
            policy_constraints.append("Growth strategy - prioritize restructuring over enforcement")
        
        # Determine required notices based on current stage
        if dpd > 60 and dpd <= 90:
            required_notices.append("Pre-legal notice before any escalation")
        elif is_npa and sarfaesi_eligible:
            required_notices.append("SARFAESI Section 13(2) notice required before possession")
            waiting_periods.append("60 days mandatory waiting after 13(2) notice")
        
        # State-specific considerations
        if jurisdiction.lower() in ["maharashtra", "kerala", "west bengal"]:
            policy_constraints.append(f"State-specific provisions may apply in {jurisdiction}")
        
        # Determine compliance status
        if blocked_actions and regulatory_constraints.lower() != "none":
            compliance_status = "Restricted"
        elif documentation != "Complete":
            compliance_status = "Non-compliant"
        else:
            compliance_status = "Compliant"
        
        # Remove duplicates
        blocked_actions = list(set(blocked_actions))
        
        regulatory_notes = []
        if is_npa:
            regulatory_notes.append("Account is NPA - recovery actions permissible per RBI guidelines")
        else:
            regulatory_notes.append(f"Account is SMA (DPD {dpd}) - focus on soft collection and restructuring")
        
        if sarfaesi_eligible:
            regulatory_notes.append("SARFAESI eligible - follow prescribed sequence strictly")
        else:
            reason = eligibility_output.get("sarfaesi_ineligibility_reason", "Not eligible")
            regulatory_notes.append(f"SARFAESI not applicable: {reason}")
        
        return {
            "compliance_status": compliance_status,
            "blocked_actions": blocked_actions,
            "required_notices": required_notices,
            "mandatory_waiting_periods": waiting_periods,
            "policy_constraints": policy_constraints,
            "regulatory_notes": "; ".join(regulatory_notes),
            "reasoning": f"[Rule-based fallback due to: {error}] Based on DPD={dpd}, NPA={is_npa}, SARFAESI_eligible={sarfaesi_eligible}, Constraints={regulatory_constraints}"
        }
