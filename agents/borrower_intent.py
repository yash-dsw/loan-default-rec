"""
Borrower Intent & Behaviour Agent
Assesses borrower's willingness and ability to repay, classifies intent type.
"""

import json
import httpx
import os
from typing import Optional
from dotenv import load_dotenv

from schemas import BorrowerIntentOutput
from prompts import get_borrower_intent_prompt, SYSTEM_PROMPTS

load_dotenv()


class BorrowerIntentAgent:
    """
    Agent responsible for:
    - Assessing willingness vs ability to repay
    - Classifying borrower intent (cooperative/stressed/strategic/non-responsive)
    - Recommending engagement approach
    """
    
    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.model = "deepseek/deepseek-chat"
        
    async def analyze(self, loan_data: dict) -> dict:
        """
        Analyze borrower behavior and return intent classification.
        
        Args:
            loan_data: Dictionary containing loan input data
            
        Returns:
            Dictionary with borrower intent assessment
        """
        prompt = get_borrower_intent_prompt(loan_data)
        
        try:
            response = await self._call_llm(prompt)
            parsed = self._parse_response(response, loan_data)
            return parsed
        except Exception as e:
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
                {"role": "system", "content": SYSTEM_PROMPTS["borrower_intent"]},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0,
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
            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0]
            
            parsed = json.loads(json_str.strip())
            
            required_fields = [
                "intent_classification", "willingness_to_pay", "ability_to_pay",
                "risk_profile", "recommended_approach", "reasoning"
            ]
            for field in required_fields:
                if field not in parsed:
                    raise ValueError(f"Missing required field: {field}")
            
            return parsed
            
        except (json.JSONDecodeError, ValueError) as e:
            return self._get_fallback_response(loan_data, f"Parse error: {str(e)}")
    
    def _get_fallback_response(self, loan_data: dict, error: str) -> dict:
        """Generate rule-based fallback response."""
        responsiveness = loan_data.get("customer_responsiveness", "Non-responsive")
        repayment_history = loan_data.get("repayment_history", "Poor")
        employment_stability = loan_data.get("employment_stability", "Unstable")
        cibil_score = loan_data.get("cibil_score", 500)
        
        # Determine intent classification
        if responsiveness == "Cooperative":
            if repayment_history in ["Excellent", "Good"]:
                intent = "Cooperative"
            else:
                intent = "Stressed"
        elif responsiveness == "Strategic":
            intent = "Strategic"
        elif responsiveness == "Partially-responsive":
            if employment_stability == "Stable" and cibil_score > 650:
                intent = "Strategic"
            else:
                intent = "Stressed"
        else:
            intent = "Non-responsive"
        
        # Determine willingness
        willingness_map = {
            "Cooperative": "High",
            "Stressed": "Medium",
            "Strategic": "Low",
            "Non-responsive": "Low"
        }
        willingness = willingness_map.get(intent, "Medium")
        
        # Determine ability
        if employment_stability == "Stable" and cibil_score > 700:
            ability = "High"
        elif employment_stability in ["Stable", "Moderate"] and cibil_score > 600:
            ability = "Medium"
        else:
            ability = "Low"
        
        # Determine risk profile
        risk_matrix = {
            ("High", "High"): "Low Risk",
            ("High", "Medium"): "Moderate Risk",
            ("High", "Low"): "Moderate Risk",
            ("Medium", "High"): "Moderate Risk",
            ("Medium", "Medium"): "Moderate Risk",
            ("Medium", "Low"): "High Risk",
            ("Low", "High"): "High Risk",
            ("Low", "Medium"): "High Risk",
            ("Low", "Low"): "Critical Risk"
        }
        risk_profile = risk_matrix.get((willingness, ability), "High Risk")
        
        # Determine recommended approach
        approach_map = {
            "Cooperative": "Supportive engagement with restructuring options",
            "Stressed": "Empathetic approach with payment plan assistance",
            "Strategic": "Firm stance with legal escalation path",
            "Non-responsive": "Field visits and traced communication"
        }
        recommended_approach = approach_map.get(intent, "Standard collection process")
        
        return {
            "intent_classification": intent,
            "willingness_to_pay": willingness,
            "ability_to_pay": ability,
            "risk_profile": risk_profile,
            "recommended_approach": recommended_approach,
            "reasoning": f"[Rule-based fallback due to: {error}] Based on responsiveness={responsiveness}, repayment_history={repayment_history}, employment={employment_stability}, CIBIL={cibil_score}"
        }
