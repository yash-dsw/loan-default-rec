"""
NBA Decision System - Single Agent for Fast Recommendations
Uses OpenRouter API for LLM inference
"""

import os
from typing import Dict, Any
import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from prompts import NBA_RECOMMENDATION_PROMPT


class NBAAgent:
    """Single agent for fast NBA recommendations"""
    
    def __init__(self, model_name: str = None):
        """Initialize agent with OpenRouter model"""
        self.api_key = os.environ.get("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable required")
        
        self.model_name = model_name or os.environ.get("MODEL_NAME", "meta-llama/llama-3.3-70b-instruct")
        self.temperature = float(os.environ.get("MODEL_TEMPERATURE", "0.5"))
        self.max_tokens = int(os.environ.get("MODEL_MAX_TOKENS", "800"))
        
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://nba-decision-system.local",
            "X-Title": "NBA Decision System"
        }
    
    def format_borrower_data(self, d: Dict[str, Any]) -> str:
        """Format account data compactly"""
        return f"""**Account:** {d.get('account_id')} | **Customer:** {d.get('customer_id')}
**Loan:** {d.get('loan_type')} ({d.get('secured_flag')}) — ₹{d.get('outstanding_amount', 0):,.0f} of ₹{d.get('loan_amount', 0):,.0f} | EMI: ₹{d.get('emi_amount', 0):,.0f}
**Status:** {d.get('delinquency_stage')} | DPD: {d.get('dpd')} | Max DPD: {d.get('max_dpd_ever')} | Times Delinquent: {d.get('times_delinquent')}
**Customer:** {d.get('customer_type')} | {d.get('geography')} | Income: {d.get('income_band')} | Credit: {d.get('credit_score_band')}
**Contact:** Score {d.get('contactability_score')}/100 | Response: {d.get('response_to_calls')} | Visit: {d.get('field_visit_outcome')} | Broken Promises: {d.get('broken_promises_count')}
**Last Action:** {d.get('last_action_taken')} ({d.get('days_since_last_action')} days ago)
**Legal:** Notice: {d.get('legal_notice_sent')} | SARFAESI: {d.get('sarfaesi_stage')} | Restructure: {d.get('restructure_offered')} | OTS: {d.get('ots_offered')}
**Recovery:** 30d: ₹{d.get('recovery_amount_30d', 0):,.0f} | 90d: ₹{d.get('recovery_amount_90d', 0):,.0f}"""
    
    async def get_recommendation(self, account_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get NBA recommendation for a single account"""
        try:
            borrower_data = self.format_borrower_data(account_data)
            prompt = NBA_RECOMMENDATION_PROMPT.format(borrower_data=borrower_data)
            
            payload = {
                "model": self.model_name,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": self.temperature,
                "max_tokens": self.max_tokens
            }
            
            with httpx.Client(timeout=30.0) as client:
                response = client.post(self.api_url, headers=self.headers, json=payload)
                response.raise_for_status()
                result = response.json()
                
                if "choices" in result and len(result["choices"]) > 0:
                    recommendation = result["choices"][0]["message"]["content"]
                else:
                    raise ValueError("Invalid API response")
            
            return {
                "account_id": account_data.get("account_id", "Unknown"),
                "customer_id": account_data.get("customer_id", "Unknown"),
                "stage": account_data.get("delinquency_stage", "Unknown"),
                "dpd": account_data.get("dpd", 0),
                "outstanding": account_data.get("outstanding_amount", 0),
                "recommendation": recommendation,
                "success": True,
                "error": None
            }
            
        except Exception as e:
            return {
                "account_id": account_data.get("account_id", "Unknown"),
                "customer_id": account_data.get("customer_id", "Unknown"),
                "stage": account_data.get("delinquency_stage", "Unknown"),
                "dpd": account_data.get("dpd", 0),
                "outstanding": account_data.get("outstanding_amount", 0),
                "recommendation": self._fallback(account_data),
                "success": False,
                "error": str(e)
            }
    
    def _fallback(self, d: Dict[str, Any]) -> str:
        """Fallback recommendation"""
        dpd = d.get("dpd", 0)
        if dpd <= 30: action = "Reminder Call"
        elif dpd <= 60: action = "Field Visit"
        elif dpd <= 90: action = "Formal Demand Letter"
        else: action = "Legal Notice Review"
        
        return f"""**🎯 Recommended Action:** {action}

**📊 Key Factors:**
- DPD: {dpd} days
- Stage: {d.get('delinquency_stage', 'Unknown')}
- Fallback due to API error

**📈 Success Likelihood:** Low — Unable to assess, using conservative approach

**🔄 If Action Fails:** Escalate to supervisor

**⚖️ Compliance:** Follow RBI Fair Practice Code"""
    
    def format_output(self, r: Dict[str, Any]) -> str:
        """Format result for display"""
        header = f"""#### {r['account_id']} | {r['customer_id']}
**Stage:** {r['stage']} · **DPD:** {r['dpd']} · **Outstanding:** ₹{r['outstanding']:,.0f}

---
"""
        output = header + r["recommendation"]
        if r.get("error"):
            output += f"\n\n⚠️ *{r['error']}*"
        return output
