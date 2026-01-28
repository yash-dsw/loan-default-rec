"""
Eligibility & Classification Agent
Classifies loan accounts based on RBI SMA/NPA norms and determines legal eligibility.
"""

import json
import httpx
import os
from typing import Optional
from dotenv import load_dotenv

from schemas import EligibilityOutput
from prompts import get_eligibility_prompt, SYSTEM_PROMPTS

load_dotenv()


class EligibilityAgent:
    """
    Agent responsible for:
    - Classifying accounts as SMA-0/SMA-1/SMA-2/NPA
    - Determining SARFAESI eligibility
    - Identifying legally permissible actions
    """
    
    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.model = "deepseek/deepseek-chat"  # Cost-effective and capable
        
    async def analyze(self, loan_data: dict) -> dict:
        """
        Analyze loan data and return eligibility classification.
        
        Args:
            loan_data: Dictionary containing loan input data
            
        Returns:
            Dictionary with eligibility assessment
        """
        prompt = get_eligibility_prompt(loan_data)
        
        try:
            response = await self._call_llm(prompt)
            parsed = self._parse_response(response, loan_data)
            return parsed
        except Exception as e:
            # Return conservative fallback
            return self._get_fallback_response(loan_data, str(e))
    
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
                {"role": "system", "content": SYSTEM_PROMPTS["eligibility"]},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0,  # Deterministic output
            "max_tokens": 1000
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(self.api_url, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
    
    def _parse_response(self, response: str, loan_data: dict) -> dict:
        """Parse LLM response and validate structure."""
        try:
            # Extract JSON from response
            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0]
            
            parsed = json.loads(json_str.strip())
            
            # Validate required fields
            required_fields = [
                "sma_classification", "is_npa", "sarfaesi_eligible",
                "loan_stage", "legal_actions_available", "reasoning"
            ]
            for field in required_fields:
                if field not in parsed:
                    raise ValueError(f"Missing required field: {field}")
            
            return parsed
            
        except (json.JSONDecodeError, ValueError) as e:
            # Return rule-based fallback
            return self._get_fallback_response(loan_data, f"Parse error: {str(e)}")
    
    def _get_fallback_response(self, loan_data: dict, error: str) -> dict:
        """Generate rule-based fallback response."""
        dpd = loan_data.get("dpd", 0)
        outstanding = loan_data.get("outstanding_amount", 0)
        secured = loan_data.get("secured_unsecured", "Unsecured")
        loan_vintage = loan_data.get("loan_vintage_months", 0)
        documentation = loan_data.get("documentation_type", "Incomplete")
        
        # Determine SMA classification
        if dpd == 0:
            sma_class = "Standard"
        elif dpd <= 30:
            sma_class = "SMA-0"
        elif dpd <= 60:
            sma_class = "SMA-1"
        elif dpd <= 90:
            sma_class = "SMA-2"
        else:
            sma_class = "NPA"
        
        is_npa = sma_class == "NPA"
        
        # Determine SARFAESI eligibility
        sarfaesi_eligible = (
            is_npa and 
            secured == "Secured" and 
            outstanding > 100000 and
            documentation == "Complete"
        )
        
        sarfaesi_reason = None
        if not sarfaesi_eligible:
            if not is_npa:
                sarfaesi_reason = "Account not classified as NPA (DPD <= 90)"
            elif secured != "Secured":
                sarfaesi_reason = "Loan is unsecured"
            elif outstanding <= 100000:
                sarfaesi_reason = "Outstanding amount <= ₹1,00,000"
            elif documentation != "Complete":
                sarfaesi_reason = "Documentation incomplete"
        
        # Determine loan stage
        loan_stage = "New default" if loan_vintage < 12 else "Late-stage default"
        
        # Determine available legal actions
        legal_actions = ["Gentle nudging / Digital reminder"]
        if dpd > 30:
            legal_actions.append("Relationship Manager intervention")
        if dpd > 60:
            legal_actions.append("Pre-legal notice")
            legal_actions.append("Restructuring / EMI recast")
        if is_npa:
            legal_actions.append("One-Time Settlement (OTS)")
            if sarfaesi_eligible:
                legal_actions.append("SARFAESI Section 13(2) notice")
        
        return {
            "sma_classification": sma_class,
            "is_npa": is_npa,
            "sarfaesi_eligible": sarfaesi_eligible,
            "sarfaesi_ineligibility_reason": sarfaesi_reason,
            "loan_stage": loan_stage,
            "legal_actions_available": legal_actions,
            "reasoning": f"[Rule-based fallback due to: {error}] Classification based on DPD={dpd}, Secured={secured}, Outstanding=₹{outstanding:,.0f}"
        }
