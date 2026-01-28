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
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(self.api_url, headers=self.headers, json=payload)
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
        """Fallback recommendation in structured format"""
        dpd = d.get("dpd", 0)
        response = d.get("response_to_calls", "None")
        field_outcome = d.get("field_visit_outcome", "Not Done")
        
        # Determine borrower intent
        if response == "Positive" or field_outcome == "Promise to Pay":
            borrower_intent = "Cooperative"
        elif response == "None" or field_outcome == "Not Done":
            borrower_intent = "Non-responsive"
        else:
            borrower_intent = "Hostile"
        
        # Determine action based on NPA stage
        action = "One-Time Settlement (OTS)"
        likelihood = "Medium"
        rationale = f"With DPD at {dpd} days in NPA stage, a negotiated settlement approach is recommended as the fallback strategy due to API unavailability."
        
        return f"""**ACTION_TITLE:** {action}

**SUCCESS_LIKELIHOOD:** {likelihood}

**RATIONALE:** {rationale}

**CONFIDENCE:** Low
**BORROWER_INTENT:** {borrower_intent}

**KEY_FACTORS:**
- DPD: {dpd} days — Account is in NPA stage
- Stage: {d.get('delinquency_stage', 'NPA')} — Legal action is eligible
- Response: {response} — Based on call response history
- Field Visit: {field_outcome} — Last field visit outcome
- Fallback recommendation — API error occurred

**IF_ACTION_FAILS:** Escalate to supervisor for manual review

**COMPLIANCE:**
- Follow RBI Fair Practice Code for all communications
- Document all recovery attempts as per regulatory requirements"""
    
    def format_output(self, r: Dict[str, Any]) -> str:
        """Format result for display with structured NPA output"""
        recommendation = r.get("recommendation", "")
        
        # Parse the structured response
        parsed = self._parse_recommendation(recommendation)
        
        # Build formatted output
        output_lines = []
        
        # Header with action title
        action_title = parsed.get("action_title", "Recovery Action")
        output_lines.append(f"### ⚙️ {action_title}")
        output_lines.append("")
        
        # Success Likelihood badge
        likelihood = parsed.get("success_likelihood", "Medium")
        likelihood_emoji = {"High": "🟢", "Medium": "🟡", "Low": "🔴"}.get(likelihood, "🟡")
        output_lines.append(f"**☑ Success Likelihood:** {likelihood_emoji} **{likelihood}**")
        output_lines.append("")
        
        # Rationale paragraph (italicized)
        rationale = parsed.get("rationale", "")
        if rationale:
            output_lines.append(f"*{rationale}*")
            output_lines.append("")
        
        # Attribute table (removed SMA/NPA row since all are NPA)
        confidence = parsed.get("confidence", "Medium")
        borrower_intent = parsed.get("borrower_intent", "Unknown")
        confidence_emoji = {"High": "🟢", "Medium": "🟡", "Low": "🔴"}.get(confidence, "🟡")
        
        output_lines.append("| Attribute | Value |")
        output_lines.append("|:----------|:------|")
        output_lines.append(f"| Confidence | {confidence_emoji} {confidence} |")
        output_lines.append(f"| Borrower Intent | {borrower_intent} |")
        output_lines.append("")
        
        # Key Factors section
        key_factors = parsed.get("key_factors", [])
        if key_factors:
            output_lines.append("#### 📋 Key Factors:")
            output_lines.append("")
            for factor in key_factors:
                output_lines.append(f"- {factor}")
            output_lines.append("")
        
        # Action Basis section (new)
        action_basis = parsed.get("action_basis", "")
        if action_basis:
            output_lines.append(f"#### 📜 Action Basis:")
            output_lines.append("")
            output_lines.append(f"{action_basis}")
            output_lines.append("")
        
        # Execution Guidance section (new)
        execution_guidance = parsed.get("execution_guidance", [])
        if execution_guidance:
            output_lines.append("#### 📝 Execution Guidance:")
            output_lines.append("")
            for point in execution_guidance:
                output_lines.append(f"- {point}")
            output_lines.append("")
        
        # If Action Fails section
        fallback = parsed.get("if_action_fails", "")
        if fallback:
            output_lines.append(f"**🔄 If Action Fails:** {fallback}")
            output_lines.append("")
        
        # Compliance section
        compliance = parsed.get("compliance", [])
        if compliance:
            output_lines.append("#### ⚖️ Compliance:")
            output_lines.append("")
            for item in compliance:
                output_lines.append(f"- {item}")
            output_lines.append("")
        
        # Add error note if any
        if r.get("error"):
            output_lines.append(f"⚠️ *{r['error']}*")
        
        return "\n".join(output_lines)
    
    def _parse_recommendation(self, text: str) -> Dict[str, Any]:
        """Parse structured recommendation text"""
        result = {
            "action_title": "Recovery Action",
            "success_likelihood": "Medium",
            "rationale": "",
            "confidence": "Medium",
            "borrower_intent": "Unknown",
            "key_factors": [],
            "action_basis": "",
            "execution_guidance": [],
            "if_action_fails": "",
            "compliance": []
        }
        
        if not text:
            return result
        
        lines = text.strip().split("\n")
        current_section = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Parse structured fields
            if line.startswith("**ACTION_TITLE:**"):
                result["action_title"] = line.replace("**ACTION_TITLE:**", "").strip()
            elif line.startswith("**SUCCESS_LIKELIHOOD:**"):
                result["success_likelihood"] = line.replace("**SUCCESS_LIKELIHOOD:**", "").strip()
            elif line.startswith("**RATIONALE:**"):
                result["rationale"] = line.replace("**RATIONALE:**", "").strip()
            elif line.startswith("**CONFIDENCE:**"):
                result["confidence"] = line.replace("**CONFIDENCE:**", "").strip()
            elif line.startswith("**BORROWER_INTENT:**"):
                result["borrower_intent"] = line.replace("**BORROWER_INTENT:**", "").strip()
            elif line.startswith("**KEY_FACTORS:**"):
                current_section = "key_factors"
            elif line.startswith("**ACTION_BASIS:**"):
                result["action_basis"] = line.replace("**ACTION_BASIS:**", "").strip()
                current_section = None
            elif line.startswith("**EXECUTION_GUIDANCE:**"):
                current_section = "execution_guidance"
            elif line.startswith("**IF_ACTION_FAILS:**"):
                result["if_action_fails"] = line.replace("**IF_ACTION_FAILS:**", "").strip()
                current_section = None
            elif line.startswith("**COMPLIANCE:**"):
                current_section = "compliance"
            elif line.startswith("- "):
                # Add to current list section
                item = line[2:].strip()
                if current_section == "key_factors":
                    result["key_factors"].append(item)
                elif current_section == "execution_guidance":
                    result["execution_guidance"].append(item)
                elif current_section == "compliance":
                    result["compliance"].append(item)
        
        return result
