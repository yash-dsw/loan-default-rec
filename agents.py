"""
NBA Decision System - Single Agent for Fast Recommendations
Uses OpenRouter API for LLM inference
"""

import os
from typing import Dict, Any
import httpx
import json
import asyncio
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
        return f"""**Account:** {d.get('account_id')} | **Customer:** {d.get('customer_id')} ({d.get('customer_full_name', 'N/A')})
**Loan:** {d.get('loan_type')} ({d.get('secured_flag')}) — ₹{d.get('outstanding_amount', 0):,.0f} of ₹{d.get('loan_amount', 0):,.0f} | EMI: ₹{d.get('emi_amount', 0):,.0f} | Rate: {d.get('interest_rate')}%
**Status:** DPD: {d.get('dpd')} | CIBIL: {d.get('cibil_score')} | Tenure: {d.get('tenure_months')} months | Vintage: {d.get('loan_vintage_months')} months
**Customer:** {d.get('customer_type')} | {d.get('geography')} | Income: {d.get('annual_income_total')}
**Contact:** Score {d.get('contactability_score')}/100 | Response: {d.get('response_to_calls')} | Visit: {d.get('field_visit_outcome')} | Broken Promises: {d.get('broken_promises_count')}
**Last Action:** {d.get('last_action_taken')} ({d.get('days_since_last_action')} days ago)
**Collateral:** {d.get('collateral_type')} ({d.get('collateral_quality')}) | Liquidity: {d.get('collateral_liquidity')} | Cost: ₹{d.get('cost_of_recovery', 0):,.0f} | Expected: ₹{d.get('expected_recovery', 0):,.0f}
**Legal:** Notice: {d.get('legal_notice_sent')} | Possession: {d.get('possession')} | Auction: {d.get('auction')} | Restructure: {d.get('restructure_offered')}/{d.get('restructure_accepted')} | OTS: {d.get('ots_offered')}/{d.get('ots_accepted')}
**SARFAESI Ready:** {d.get('sarfaesi_ready_flag')} | Charge Registration: {d.get('charge_registered_flag')} | DSC: {d.get('dsc_available_flag')}
**Documents:** Sanction Letter: {d.get('sanction_letter_flag')} | Hypothecation Deed: {d.get('hypothecation_deed_flag')} | Charge Particulars: {d.get('charge_instrument_flag')}
**Identity/Corporate:** DIN: {d.get('director_din_available') if 'corporate' in str(d.get('loan_type')).lower() else 'N/A (Individual)'} | PAN/Signatory: {d.get('authorized_signatory_pan')} | CS Membership: {d.get('cs_membership_no_flag')} | Cert of Reg: {d.get('certificate_of_registration_flag')}
**Enforcement Docs:** Magistrate Application Docs: {d.get('magistrate_application_docs', 'No')}"""
    
    async def get_recommendation_stream(self, account_data: Dict[str, Any]):
        """Get NBA recommendation as a stream of tokens"""
        try:
            borrower_data = self.format_borrower_data(account_data)
            prompt = NBA_RECOMMENDATION_PROMPT.format(borrower_data=borrower_data)
            
            payload = {
                "model": self.model_name,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "stream": True
            }
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream("POST", self.api_url, headers=self.headers, json=payload) as response:
                    response.raise_for_status()
                    
                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        
                        try:
                            data = json.loads(data_str)
                            if "choices" in data and len(data["choices"]) > 0:
                                delta = data["choices"][0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                        except json.JSONDecodeError:
                            continue

        except (GeneratorExit, asyncio.CancelledError):
            # Silence expected exit signals to allow clean up (crucial for Python 3.13)
            return
        except Exception as e:
            # Yield error information and fallback for actual runtime exceptions
            yield f"\n⚠️ Error during streaming: {str(e)}\n"
            yield self._fallback(account_data)

    async def get_recommendation(self, account_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get NBA recommendation (blocking/accumulated)"""
        full_text = ""
        async for chunk in self.get_recommendation_stream(account_data):
            # Check if this is a fallback already
            if "**ACTION_TITLE:**" in chunk and not full_text:
                full_text = chunk
                break
            full_text += chunk
        
        return {
            "account_id": account_data.get("account_id", "Unknown"),
            "customer_id": account_data.get("customer_id", "Unknown"),
            "stage": account_data.get("delinquency_stage", "Unknown"),
            "dpd": account_data.get("dpd", 0),
            "outstanding": account_data.get("outstanding_amount", 0),
            "recommendation": full_text,
            "success": "⚠️ Error" not in full_text,
            "error": None if "⚠️ Error" not in full_text else "Streaming error occurred"
        }
    
    def _fallback(self, d: Dict[str, Any]) -> str:
        """Fallback recommendation in structured format based on new data schema"""
        dpd = d.get("dpd", 0)
        response = str(d.get("response_to_calls", "None")).lower()
        field_outcome = str(d.get("field_visit_outcome", "Not Done")).lower()
        contactability = d.get("contactability_score", 50)
        broken_promises = d.get("broken_promises_count", 0)
        cibil = d.get("cibil_score", 600)
        collateral_liquidity = str(d.get("collateral_liquidity", "Medium")).lower()
        sarfaesi_ready = str(d.get("sarfaesi_ready_flag", "No")).lower()
        legal_notice = str(d.get("legal_notice_sent", "No")).lower()
        possession = str(d.get("possession", "No")).lower()
        loan_type = str(d.get("loan_type", "Home Loan")).lower()
        
        # Determine symbolic & physical possession readiness based on documents
        charge_reg = str(d.get("charge_registered_flag", "No")).lower()
        dsc = str(d.get("dsc_available_flag", "No")).lower()
        din = str(d.get("director_din_available", "No")).lower()
        magistrate_docs = str(d.get("magistrate_application_docs", "No")).lower() # Default to No as requested
        
        symbolic_ready = (charge_reg == "yes" and dsc == "yes")
        if "corporate" in loan_type:
            symbolic_ready = symbolic_ready and (din == "yes")
            
        physical_ready = symbolic_ready and (magistrate_docs == "yes")
            
        # Overall possession status for fallback display (using physical for final trigger)
        possession_status = "Yes" if physical_ready and possession == "yes" else "No"
        
        # Determine borrower intent based...
        if response in ["responsive", "positive"] or "promise" in field_outcome:
            borrower_intent = "Cooperative"
        elif response in ["no response", "none"] or "refused" in field_outcome:
            borrower_intent = "Non-responsive"
        elif response in ["avoiding", "irregular"]:
            borrower_intent = "Evasive"
        else:
            borrower_intent = "Unknown"
        
        # Determine action and likelihood based on multiple factors
        if dpd >= 270 and sarfaesi_ready == "yes" and possession == "yes":
            action = "Initiate Auction Proceedings"
            likelihood = "High" if collateral_liquidity == "high" else "Medium"
        elif dpd >= 180 and sarfaesi_ready == "yes" and legal_notice == "yes":
            action = "Proceed with SARFAESI 13(4) Possession"
            likelihood = "Medium" if contactability < 30 else "High"
        elif dpd >= 120 and sarfaesi_ready == "yes":
            action = "Issue Section 13(2) Notice"
            likelihood = "High" if broken_promises < 3 else "Medium"
        elif contactability >= 40 and borrower_intent == "Cooperative":
            action = "Negotiate One-Time Settlement (OTS)"
            likelihood = "High" if cibil >= 600 else "Medium"
        else:
            action = "Intensify Collection Efforts with Field Visit"
            likelihood = "Low" if broken_promises >= 4 else "Medium"
        
        rationale = f"With DPD at {dpd} days, contactability score of {contactability}/100, and CIBIL {cibil}, this action is recommended based on borrower profile and recovery probability."
        
        return f"""#### 📜 Action: {action}
#### Action Reasoning:
Legal basis Section 13(2) of SARFAESI Act 2002. Given the DPD of {dpd} and current document readiness, this is the most effective legal step to initiate recovery.

**Recovery Likelihood:** {likelihood}
**Reasoning:** High recovery potential due to secured collateral and legal eligibility.

**Confidence:** Low
**Reasoning:** Fallback logic used; detailed behavioral analysis unavailable.

**Borrower Behaviour:** {borrower_intent}
**Reasoning:** Based on response pattern '{response}' and field visit outcome '{field_outcome}'.

#### 📋 Key Factors:
- DPD: {dpd} days — Determines legal action eligibility
- Contactability: {contactability}/100 — {d.get('response_to_calls')} response pattern
- CIBIL Score: {cibil} — Indicates repayment capacity
- Collateral: {d.get('collateral_quality')} ({collateral_liquidity} liquidity) — Recovery potential
- Broken Promises: {broken_promises} — Borrower reliability indicator

#### 📜 Documentation Status:
- Section 13(2) Ready: {sarfaesi_ready.title()} — {'Missing Sanction Letter, Hypothecation Deed, or Charge Particulars' if sarfaesi_ready == 'no' else 'Documentation complete'}
- Symbolic Possession Ready: {('Yes' if symbolic_ready else 'No')} — {'Missing Charge Registration, DSC' + (', or DIN' if 'corporate' in loan_type else '') if not symbolic_ready else 'Documentation complete'}
- Physical Possession Ready: {('Yes' if physical_ready else 'No')} — {'Missing Magistrate Application Docs' if not physical_ready else 'Documentation complete'}
- Auction Ready: {'No' if auction == 'no' else 'Yes'}

#### 📝 Execution Guidance:
- Point 1: Verify all physical documents against the digital flags
- Point 2: Ensure the latest valuation report is on file
- Point 3: Initiate legal notice through empaneled counsel

**🔄 If Action Fails:** Escalate to supervisor for manual review

#### ⚖️ Compliance:
- Follows RBI Fair Practice Code for all communications
- Document all recovery attempts as per regulatory requirements"""
    
    def format_output(self, r: Dict[str, Any]) -> tuple:
        """Format result for display with structured NBA output
        
        Returns:
            tuple: (formatted_string, parsed_data) where parsed_data contains factor_weightages
        """
        recommendation = r.get("recommendation", "")
        
        # Parse the structured response
        parsed = self._parse_recommendation(recommendation)
        
        # If the recommendation already has the "#### Action:" header,
        # it means it's already in the "pretty" format from the prompt.
        if "#### Action:" in recommendation:
            # Add error note if any
            output = recommendation
            if r.get("error"):
                output += f"\n\n⚠️ *{r['error']}*"
            return output, parsed
            
        # Fallback for old raw format if needed
        output_lines = []
        # ... (rest of old formatting logic if needed, but we'll prioritize the pretty one)
        return recommendation, parsed
    
    def _parse_recommendation(self, text: str) -> Dict[str, Any]:
        """Parse structured recommendation text"""
        result = {
            "action_title": "Recovery Action",
            "success_likelihood": "Medium",
            "recovery_likelihood_reasoning": "",
            "rationale": "",
            "confidence": "Medium",
            "confidence_reasoning": "",
            "borrower_intent": "Unknown",
            "borrower_reasoning": "",
            "key_factors": [],
            "factor_weightages": {},
            "action_basis": "",
            "execution_guidance": [],
            "if_action_fails": "",
            "compliance": []
        }
        
        if not text:
            return result
        
        lines = text.strip().split("\n")
        current_section = None
        last_metric = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Parse structured fields
            if line.startswith("#### Action:") or line.startswith("**ACTION_TITLE:**") or line.startswith("#### 📜 Action:"):
                result["action_title"] = line.replace("#### Action:", "").replace("**ACTION_TITLE:**", "").replace("#### 📜 Action:", "").strip()
            elif line.startswith("#### 📜 Action Reasoning:") or line.startswith("#### Action Reasoning:") or line.startswith("#### 📜 Action Basis:") or line.startswith("**ACTION_BASIS:**"):
                current_section = "action_basis"
            elif line.startswith("**Recovery Likelihood:**") or line.startswith("**SUCCESS_LIKELIHOOD:**"):
                val = line.replace("**Recovery Likelihood:**", "").replace("**SUCCESS_LIKELIHOOD:**", "").strip()
                # Strip emojis if present
                for em in ["🟢", "🟡", "🔴"]: val = val.replace(em, "").strip()
                result["success_likelihood"] = val
                last_metric = "likelihood"
            elif line.startswith("**Recovery Likelihood Reasoning:**"):
                result["recovery_likelihood_reasoning"] = line.replace("**Recovery Likelihood Reasoning:**", "").strip()
            elif line.startswith("**Reasoning:**"):
                val = line.replace("**Reasoning:**", "").strip()
                if last_metric == "likelihood":
                    result["recovery_likelihood_reasoning"] = val
                elif last_metric == "confidence":
                    result["confidence_reasoning"] = val
                elif last_metric == "borrower":
                    result["borrower_reasoning"] = val
            elif line.startswith("**RATIONALE:**"):
                val = line.replace("**RATIONALE:**", "").strip()
                result["rationale"] = val.strip("*")
            elif line.startswith("**Confidence:**") or line.startswith("**CONFIDENCE:**"):
                val = line.replace("**Confidence:**", "").replace("**CONFIDENCE:**", "").strip()
                for em in ["🟢", "🟡", "🔴"]: val = val.replace(em, "").strip()
                result["confidence"] = val
                last_metric = "confidence"
            elif line.startswith("**Confidence Reasoning:**"):
                result["confidence_reasoning"] = line.replace("**Confidence Reasoning:**", "").strip()
            elif line.startswith("**Borrower:**") or line.startswith("**BORROWER_INTENT:**") or line.startswith("**Borrower Behaviour:**"):
                val = line.replace("**Borrower:**", "").replace("**BORROWER_INTENT:**", "").replace("**Borrower Behaviour:**", "").strip()
                for em in ["🤝", "⚔️", "🏃", "❓"]: val = val.replace(em, "").strip()
                result["borrower_intent"] = val
                last_metric = "borrower"
            elif line.startswith("**Borrower Reasoning:**"):
                result["borrower_reasoning"] = line.replace("**Borrower Reasoning:**", "").strip()
            elif line.startswith("#### 📋 Key Factors:") or line.startswith("**KEY_FACTORS:**"):
                current_section = "key_factors"
                last_metric = None
            elif line.startswith("#### 📝 Execution Guidance:") or line.startswith("**EXECUTION_GUIDANCE:**"):
                current_section = "execution_guidance"
            elif line.startswith("**🔄 If Action Fails:**") or line.startswith("**IF_ACTION_FAILS:**"):
                result["if_action_fails"] = line.replace("**🔄 If Action Fails:**", "").replace("**IF_ACTION_FAILS:**", "").strip()
                current_section = None
            elif line.startswith("**FACTOR_WEIGHTAGES:**"):
                current_section = "factor_weightages"
            elif line.startswith("#### ⚖️ Compliance:") or line.startswith("**COMPLIANCE:**"):
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
                elif current_section == "factor_weightages":
                    # Parse "Factor Name: XX%" format
                    if ":" in item and "%" in item:
                        parts = item.split(":")
                        if len(parts) >= 2:
                            factor_name = parts[0].strip()
                            # Skip SARFAESI Doc Status from pie chart
                            if "sarfaesi" in factor_name.lower() or "doc status" in factor_name.lower():
                                continue
                            percentage_str = parts[1].strip().replace("%", "").strip()
                            try:
                                percentage = float(percentage_str)
                                result["factor_weightages"][factor_name] = percentage
                            except ValueError:
                                pass
                elif current_section == "action_basis":
                    result["action_basis"] += " " + item if result["action_basis"] else item
            elif current_section == "action_basis" and not line.startswith("####"):
                result["action_basis"] += " " + line if result["action_basis"] else line
        
        # If no factor_weightages provided but we have key_factors, calculate dynamic weightages
        if not result["factor_weightages"] and result["key_factors"]:
            result["factor_weightages"] = self._calculate_dynamic_weightages(result["key_factors"])
        
        return result
    
    def _calculate_dynamic_weightages(self, key_factors: list) -> dict:
        """Calculate dynamic weightages based on key factors identified by the LLM.
        
        Assigns weights based on factor importance for recovery decisions.
        High-priority factors get more weight, remaining is distributed evenly.
        """
        weightages = {}
        
        # Extract factor names from key_factors list (format: "Factor: Value — Explanation")
        factor_names = []
        for factor in key_factors:
            if ":" in factor:
                name = factor.split(":")[0].strip()
                # Normalize common variations
                name = name.replace(" Score", "").replace(" Count", "").strip()
                factor_names.append(name)
        
        if not factor_names:
            return weightages
        
        # Priority weights for common factors in loan recovery
        priority_weights = {
            "DPD": 25,
            "CIBIL": 20,
            "Contactability": 20,
            "Collateral Liquidity": 15,
            "Collateral": 15,
            "Broken Promises": 15,
            "Response": 10,
            "SARFAESI": 10,
            "Outstanding": 10,
            "EMI": 10,
            "Income": 10,
        }
        
        # Assign weights to factors
        total_weight = 0
        assigned_factors = []
        
        for name in factor_names:
            # Skip SARFAESI Doc Status from pie chart weightages
            if "sarfaesi" in name.lower() or "doc status" in name.lower():
                continue
            # Find matching priority
            weight = 10  # Default weight
            for key, w in priority_weights.items():
                if key.lower() in name.lower():
                    weight = w
                    break
            weightages[name] = weight
            total_weight += weight
            assigned_factors.append(name)
        
        # Normalize to 100%
        if total_weight > 0:
            for name in assigned_factors:
                weightages[name] = round((weightages[name] / total_weight) * 100, 1)
        
        return weightages
