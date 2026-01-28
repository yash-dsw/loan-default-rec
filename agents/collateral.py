"""
Collateral & Recovery Economics Agent
Evaluates collateral value, recovery costs, and NPV analysis.
"""

import json
import httpx
import os
from typing import Optional
from dotenv import load_dotenv

from schemas import CollateralOutput
from prompts import get_collateral_prompt, SYSTEM_PROMPTS

load_dotenv()


class CollateralAgent:
    """
    Agent responsible for:
    - Evaluating collateral liquidity and value
    - Performing cost-benefit analysis
    - Applying NPV/time value of money calculations
    - Recommending recovery path based on economics
    """
    
    # Location-based discount factors for auction realization
    LOCATION_DISCOUNTS = {
        "Metro": 0.15,      # 15% discount from expected recovery
        "Tier-1": 0.20,
        "Tier-2": 0.30,
        "Tier-3": 0.40,
        "Rural": 0.50
    }
    
    # Annual discount rate for NPV calculation (bank's cost of capital)
    DISCOUNT_RATE = 0.12
    
    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.model = "deepseek/deepseek-chat"
        
    async def analyze(self, loan_data: dict) -> dict:
        """
        Analyze collateral economics and return viability assessment.
        
        Args:
            loan_data: Dictionary containing loan input data
            
        Returns:
            Dictionary with collateral economics assessment
        """
        prompt = get_collateral_prompt(loan_data)
        
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
                {"role": "system", "content": SYSTEM_PROMPTS["collateral"]},
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
                "collateral_liquidity", "estimated_sale_value", "recovery_viability",
                "npv_positive", "cost_benefit_ratio", "recommended_recovery_path", "reasoning"
            ]
            for field in required_fields:
                if field not in parsed:
                    raise ValueError(f"Missing required field: {field}")
            
            return parsed
            
        except (json.JSONDecodeError, ValueError) as e:
            return self._get_fallback_response(loan_data, f"Parse error: {str(e)}")
    
    def _calculate_npv(self, expected_recovery: float, time_months: int, 
                       cost_of_recovery: float) -> float:
        """Calculate Net Present Value of recovery."""
        # Convert annual rate to monthly
        monthly_rate = self.DISCOUNT_RATE / 12
        
        # NPV of expected recovery
        npv_recovery = expected_recovery / ((1 + monthly_rate) ** time_months)
        
        # NPV = Discounted recovery - immediate cost
        npv = npv_recovery - cost_of_recovery
        
        return npv
    
    def _get_fallback_response(self, loan_data: dict, error: str) -> dict:
        """Generate rule-based fallback response."""
        collateral_quality = loan_data.get("collateral_quality", "Medium")
        geographic_location = loan_data.get("geographic_location", "Tier-2")
        expected_recovery = loan_data.get("expected_recovery", 0)
        cost_of_recovery = loan_data.get("cost_of_recovery", 0)
        time_months = loan_data.get("time_value_recovery_months", 12)
        documentation = loan_data.get("documentation_type", "Incomplete")
        
        # Determine collateral liquidity
        liquidity_map = {
            ("High", "Metro"): "High",
            ("High", "Tier-1"): "High",
            ("High", "Tier-2"): "Medium",
            ("Medium", "Metro"): "High",
            ("Medium", "Tier-1"): "Medium",
            ("Medium", "Tier-2"): "Medium",
            ("Medium", "Tier-3"): "Low",
            ("Low", "Metro"): "Medium",
            ("Low", "Tier-1"): "Low",
            ("Low", "Rural"): "Low"
        }
        liquidity = liquidity_map.get((collateral_quality, geographic_location), "Medium")
        
        # Adjust for documentation
        if documentation != "Complete":
            if liquidity == "High":
                liquidity = "Medium"
            elif liquidity == "Medium":
                liquidity = "Low"
        
        # Calculate estimated sale value
        location_discount = self.LOCATION_DISCOUNTS.get(geographic_location, 0.30)
        quality_adjustment = {"High": 0, "Medium": 0.10, "Low": 0.20}.get(collateral_quality, 0.15)
        total_discount = min(location_discount + quality_adjustment, 0.60)
        
        estimated_sale_value = expected_recovery * (1 - total_discount)
        
        # Calculate cost-benefit ratio
        if cost_of_recovery > 0:
            cost_benefit_ratio = estimated_sale_value / cost_of_recovery
        else:
            cost_benefit_ratio = float('inf') if estimated_sale_value > 0 else 0
        
        # Calculate NPV
        npv = self._calculate_npv(estimated_sale_value, time_months, cost_of_recovery)
        npv_positive = npv > 0
        
        # Determine recovery viability
        if cost_benefit_ratio > 2.0 and npv_positive:
            recovery_viability = "Viable"
        elif cost_benefit_ratio > 1.2 and npv_positive:
            recovery_viability = "Marginal"
        else:
            recovery_viability = "Not viable"
        
        # Recommend recovery path
        if recovery_viability == "Viable":
            if liquidity == "High":
                recommended_path = "Proceed with SARFAESI enforcement if eligible"
            else:
                recommended_path = "Consider OTS negotiation alongside enforcement"
        elif recovery_viability == "Marginal":
            recommended_path = "Prioritize OTS negotiation; enforcement as backup"
        else:
            recommended_path = "Consider ARC sale or technical write-off"
        
        return {
            "collateral_liquidity": liquidity,
            "estimated_sale_value": round(estimated_sale_value, 2),
            "recovery_viability": recovery_viability,
            "npv_positive": npv_positive,
            "cost_benefit_ratio": round(cost_benefit_ratio, 2) if cost_benefit_ratio != float('inf') else 999.99,
            "recommended_recovery_path": recommended_path,
            "reasoning": f"[Rule-based fallback due to: {error}] Location={geographic_location}, Quality={collateral_quality}, Expected=₹{expected_recovery:,.0f}, Estimated Sale=₹{estimated_sale_value:,.0f}, NPV=₹{npv:,.0f}"
        }
