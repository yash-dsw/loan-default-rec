"""
Next Best Action Synthesizer Agent
Final decision-maker that produces audit-ready recommendations.
"""

import json
import httpx
import os
from typing import Optional, List, Dict
from dotenv import load_dotenv

from schemas import NBAOutput
from prompts import get_nba_synthesizer_prompt, SYSTEM_PROMPTS

load_dotenv()


class NBASynthesizerAgent:
    """
    Agent responsible for:
    - Consuming all prior agent outputs
    - Selecting exactly ONE primary action
    - Selecting ONE fallback action
    - Producing structured, audit-ready reasoning
    """
    
    # Allowed actions in order of escalation
    ACTION_HIERARCHY = [
        "Gentle nudging / Digital reminder",
        "Relationship Manager intervention",
        "Restructuring / EMI recast",
        "Pre-legal notice",
        "SARFAESI Section 13(2) notice",
        "Symbolic possession",
        "Physical possession",
        "Auction initiation",
        "One-Time Settlement (OTS)",
        "ARC sale",
        "Technical write-off (policy-based)",
        "Hold / No action (regulatory or policy constraint)"
    ]
    
    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.model = "deepseek/deepseek-chat"
        
    async def synthesize(self, loan_data: dict, eligibility_output: dict,
                         borrower_intent_output: dict, collateral_output: dict,
                         regulatory_output: dict) -> dict:
        """
        Synthesize all agent outputs and produce final NBA recommendation.
        
        Args:
            loan_data: Original loan input data
            eligibility_output: Output from eligibility agent
            borrower_intent_output: Output from borrower intent agent
            collateral_output: Output from collateral agent
            regulatory_output: Output from regulatory agent
            
        Returns:
            Dictionary with final NBA recommendation
        """
        prompt = get_nba_synthesizer_prompt(
            loan_data, eligibility_output, borrower_intent_output,
            collateral_output, regulatory_output
        )
        
        try:
            response = await self._call_llm(prompt)
            parsed = self._parse_response(response, loan_data, eligibility_output,
                                         borrower_intent_output, collateral_output,
                                         regulatory_output)
            return parsed
        except Exception as e:
            return self._get_fallback_response(
                loan_data, eligibility_output, borrower_intent_output,
                collateral_output, regulatory_output, str(e)
            )
    
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
                {"role": "system", "content": SYSTEM_PROMPTS["nba_synthesizer"]},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0,
            "max_tokens": 1500
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(self.api_url, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
    
    def _parse_response(self, response: str, loan_data: dict, eligibility: dict,
                        borrower: dict, collateral: dict, regulatory: dict) -> dict:
        """Parse LLM response and validate structure."""
        try:
            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0]
            
            parsed = json.loads(json_str.strip())
            
            required_fields = [
                "next_best_action", "reasoning", "confidence_level",
                "fallback_action", "regulatory_notes", "economic_rationale", "rbi_alignment"
            ]
            for field in required_fields:
                if field not in parsed:
                    raise ValueError(f"Missing required field: {field}")
            
            # Validate action is in allowed list
            nba = parsed["next_best_action"]
            if nba not in self.ACTION_HIERARCHY:
                # Try to find closest match
                for action in self.ACTION_HIERARCHY:
                    if nba.lower() in action.lower() or action.lower() in nba.lower():
                        parsed["next_best_action"] = action
                        break
            
            # Validate action is not blocked
            blocked = regulatory.get("blocked_actions", [])
            if parsed["next_best_action"] in blocked:
                raise ValueError(f"Selected action '{parsed['next_best_action']}' is blocked by regulatory agent")
            
            return parsed
            
        except (json.JSONDecodeError, ValueError) as e:
            return self._get_fallback_response(
                loan_data, eligibility, borrower, collateral, regulatory,
                f"Parse error: {str(e)}"
            )
    
    def _get_available_actions(self, eligibility: dict, regulatory: dict) -> List[str]:
        """Get list of currently available actions."""
        legal_actions = eligibility.get("legal_actions_available", [])
        blocked_actions = regulatory.get("blocked_actions", [])
        
        available = []
        for action in self.ACTION_HIERARCHY:
            if action not in blocked_actions:
                # Check if action or similar is in legal_actions
                is_legal = False
                for legal in legal_actions:
                    if action.lower() in legal.lower() or legal.lower() in action.lower():
                        is_legal = True
                        break
                # Always include soft actions
                if action in self.ACTION_HIERARCHY[:3]:
                    is_legal = True
                # OTS is generally available for NPA
                if "OTS" in action and eligibility.get("is_npa", False):
                    is_legal = True
                # Hold is always available
                if "Hold" in action:
                    is_legal = True
                    
                if is_legal:
                    available.append(action)
        
        return available if available else [self.ACTION_HIERARCHY[0]]
    
    def _get_fallback_response(self, loan_data: dict, eligibility: dict,
                               borrower: dict, collateral: dict, 
                               regulatory: dict, error: str) -> dict:
        """Generate rule-based fallback response."""
        dpd = loan_data.get("dpd", 0)
        is_npa = eligibility.get("is_npa", False)
        sarfaesi_eligible = eligibility.get("sarfaesi_eligible", False)
        
        intent = borrower.get("intent_classification", "Non-responsive")
        willingness = borrower.get("willingness_to_pay", "Low")
        ability = borrower.get("ability_to_pay", "Low")
        
        npv_positive = collateral.get("npv_positive", False)
        recovery_viability = collateral.get("recovery_viability", "Marginal")
        
        blocked_actions = regulatory.get("blocked_actions", [])
        policy_constraints = regulatory.get("policy_constraints", [])
        
        available_actions = self._get_available_actions(eligibility, regulatory)
        
        # Decision logic
        nba = None
        fallback = None
        reasoning = []
        confidence = "Medium"
        
        # Check for regulatory holds first
        if any("court" in str(c).lower() or "stay" in str(c).lower() for c in policy_constraints):
            nba = "Hold / No action (regulatory or policy constraint)"
            fallback = "Gentle nudging / Digital reminder"
            reasoning = [
                f"Regulatory constraint in effect: {policy_constraints[0] if policy_constraints else 'Court order'}",
                "All enforcement actions blocked pending resolution",
                "Maintain contact with borrower while awaiting legal clarity"
            ]
            confidence = "High"
            
        # Early stage - soft collection
        elif dpd <= 30:
            if intent == "Cooperative":
                nba = "Gentle nudging / Digital reminder"
                fallback = "Relationship Manager intervention"
                reasoning = [
                    f"Early delinquency (DPD {dpd}) - appropriate for soft collection",
                    "Borrower classified as Cooperative - respond well to reminders",
                    "Preserve customer relationship at this stage"
                ]
            else:
                nba = "Relationship Manager intervention"
                fallback = "Gentle nudging / Digital reminder"
                reasoning = [
                    f"Early delinquency (DPD {dpd}) requires proactive engagement",
                    f"Borrower intent: {intent} - needs personal touch",
                    "RM can assess situation and offer solutions"
                ]
            confidence = "High"
            
        # SMA-1/SMA-2 stage
        elif dpd <= 90:
            if intent == "Cooperative" and ability == "Low":
                nba = "Restructuring / EMI recast"
                fallback = "Relationship Manager intervention"
                reasoning = [
                    f"SMA-{1 if dpd <= 60 else 2} classification (DPD {dpd})",
                    "Borrower willing but struggling - restructuring appropriate",
                    "Avoid NPA classification if possible through restructuring"
                ]
            elif intent in ["Strategic", "Non-responsive"]:
                nba = "Pre-legal notice"
                fallback = "Relationship Manager intervention"
                reasoning = [
                    f"Account approaching NPA threshold (DPD {dpd})",
                    f"Borrower {intent} - formal notice may prompt action",
                    "Establishes record of bank's due diligence"
                ]
            else:
                nba = "Relationship Manager intervention"
                fallback = "Restructuring / EMI recast"
                reasoning = [
                    f"SMA account (DPD {dpd}) - RM engagement appropriate",
                    "Assess restructuring feasibility",
                    "Prevent further deterioration"
                ]
            confidence = "High" if dpd > 60 else "Medium"
            
        # NPA stage
        else:
            if sarfaesi_eligible and intent in ["Strategic", "Non-responsive"]:
                if "SARFAESI Section 13(2) notice" not in blocked_actions:
                    nba = "SARFAESI Section 13(2) notice"
                    fallback = "One-Time Settlement (OTS)"
                    reasoning = [
                        f"NPA classification confirmed (DPD {dpd} > 90)",
                        "SARFAESI eligible - initiating statutory recovery process",
                        f"Borrower {intent} - legal action warranted",
                        "Notice triggers 60-day response window"
                    ]
                    confidence = "High"
                else:
                    nba = "Pre-legal notice"
                    fallback = "One-Time Settlement (OTS)"
                    reasoning = [
                        "SARFAESI 13(2) currently blocked",
                        "Pre-legal notice as interim measure",
                        "Resolve blocking issues before escalation"
                    ]
                    confidence = "Medium"
                    
            elif intent == "Cooperative" or willingness == "High":
                nba = "One-Time Settlement (OTS)"
                fallback = "Restructuring / EMI recast"
                reasoning = [
                    f"NPA account (DPD {dpd}) with cooperative borrower",
                    "OTS offers faster resolution at acceptable recovery",
                    "Borrower engagement suggests settlement willingness",
                    "NPV-favorable compared to prolonged enforcement"
                ]
                confidence = "High" if willingness == "High" else "Medium"
                
            elif recovery_viability == "Not viable" or not npv_positive:
                nba = "ARC sale"
                fallback = "Technical write-off (policy-based)"
                reasoning = [
                    f"NPA (DPD {dpd}) with poor recovery economics",
                    f"Recovery viability: {recovery_viability}, NPV positive: {npv_positive}",
                    "Enforcement cost exceeds expected recovery",
                    "ARC sale provides immediate portfolio cleanup"
                ]
                confidence = "Medium"
                
            else:
                nba = "One-Time Settlement (OTS)"
                fallback = "SARFAESI Section 13(2) notice" if sarfaesi_eligible else "ARC sale"
                reasoning = [
                    f"NPA account (DPD {dpd}) - recovery action required",
                    "OTS as first preference for quicker resolution",
                    "Enforcement as backup if OTS fails"
                ]
                confidence = "Medium"
        
        # Ensure selected actions are in available list
        if nba not in available_actions:
            nba = available_actions[0]
            reasoning.append(f"[Adjusted to available action due to restrictions]")
            confidence = "Low"
            
        if fallback == nba or fallback not in available_actions:
            # Find different fallback
            for action in available_actions:
                if action != nba:
                    fallback = action
                    break
            else:
                fallback = "Hold / No action (regulatory or policy constraint)"
        
        # Build regulatory notes
        reg_notes = []
        if regulatory.get("required_notices"):
            reg_notes.extend(regulatory["required_notices"])
        if regulatory.get("mandatory_waiting_periods"):
            reg_notes.extend(regulatory["mandatory_waiting_periods"])
        if not reg_notes:
            reg_notes = ["Standard RBI guidelines apply"]
        
        # Economic rationale
        cost_benefit = collateral.get("cost_benefit_ratio", 0)
        econ_rationale = f"Cost-benefit ratio: {cost_benefit:.2f}. "
        if npv_positive:
            econ_rationale += "Enforcement is NPV-positive. "
        else:
            econ_rationale += "Enforcement may not be economically optimal. "
        econ_rationale += f"Recovery viability: {recovery_viability}."
        
        # RBI alignment
        if is_npa:
            rbi_note = "Account classified as NPA per RBI IRAC norms (DPD > 90 days). "
            if sarfaesi_eligible:
                rbi_note += "SARFAESI actions permitted under Section 13. "
            else:
                rbi_note += f"SARFAESI not applicable: {eligibility.get('sarfaesi_ineligibility_reason', 'See eligibility')}. "
        else:
            rbi_note = f"Account is SMA-{0 if dpd <= 30 else (1 if dpd <= 60 else 2)} per RBI classification. "
            rbi_note += "Enforcement actions not yet permissible. "
        rbi_note += "Fair Practices Code compliance maintained."
        
        return {
            "next_best_action": nba,
            "reasoning": reasoning,
            "confidence_level": confidence,
            "fallback_action": fallback,
            "regulatory_notes": reg_notes,
            "economic_rationale": econ_rationale,
            "rbi_alignment": rbi_note
        }
