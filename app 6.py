"""
Home Loan NBA (Next Best Action) Decision System
Chainlit-based interface for Agentic AI loan recovery recommendations.
"""

import chainlit as cl
import pandas as pd
import io
from typing import List, Dict, Optional
from dotenv import load_dotenv

from schemas import LoanInput, CSVValidationResult
from csv_loader import (
    load_and_validate_csv, 
    format_validation_errors, 
    get_preview_dataframe
)
from agents import (
    EligibilityAgent,
    BorrowerIntentAgent,
    CollateralAgent,
    RegulatoryAgent,
    NBASynthesizerAgent
)

from db import get_loan_by_id

load_dotenv()

# Initialize agents
eligibility_agent = EligibilityAgent()
borrower_intent_agent = BorrowerIntentAgent()
collateral_agent = CollateralAgent()
regulatory_agent = RegulatoryAgent()
nba_synthesizer = NBASynthesizerAgent()


@cl.on_chat_start
async def start():
    """Initialize the chat session."""
    cl.user_session.set("loan_data", None)
    cl.user_session.set("results", None)
    
    welcome_message = """
#### 🏦 Home Loan Next Best Action (NBA) System

Welcome to the **AI-powered NBA Decision System** for Indian Home Loan Recovery.

#### Quick Start:
1. 🔍 **Search** for a loan by entering the **Account ID**.
2. 🚀 **Run** NBA analysis.
3. 📥 **Download** results.

**🔍 Please enter the Account ID to search for a loan record.**
"""
    await cl.Message(content=welcome_message).send()


@cl.on_message
async def main(message: cl.Message):
    """Handle incoming messages and search for account_id."""
    
    # Check if this is a command to run analysis
    if message.content.strip().lower() in ["run", "analyze", "run analysis", "start", "run nba analysis"]:
        loan_data = cl.user_session.get("loan_data")
        if loan_data:
            await run_nba_analysis([loan_data])
        else:
            await cl.Message(content="❌ No loan data found. Please enter a valid Account ID first.").send()
        return
    
    # Otherwise, treat input as account_id
    account_id = message.content.strip()
    
    # Show search status
    msg = cl.Message(content=f"🔍 Searching for Account ID: **{account_id}**...")
    await msg.send()
    
    try:
        loan_input = get_loan_by_id(account_id)
        
        if not loan_input:
            msg.content = f"❌ No record found for Account ID: **{account_id}**. Please try another one."
            await msg.update()
            return
        
        # Store loan data
        cl.user_session.set("loan_data", loan_input)
        
        # Show success and preview
        msg.content = f"✅ Record found for **{account_id}**."
        await msg.update()
        
        preview_text = f"""
| Attribute | Value |
|-----------|-------|
| Account ID | {loan_input.loan_id} |
| DPD | {loan_input.dpd} |
| Outstanding | ₹{loan_input.outstanding_amount:,.2f} |
| Secured | {loan_input.secured_unsecured} |
| Collateral | {loan_input.collateral_quality} |
"""
        await cl.Message(content=f"#### 📋 Loan Summary\n{preview_text}").send()
        
        # Show action button
        actions = [
            cl.Action(
                name="run_analysis",
                payload={"action": "run"},
                label="🚀 Run NBA Analysis"
            )
        ]
        
        await cl.Message(
            content="Click below or type **'run'** to start analysis.",
            actions=actions
        ).send()
        
    except Exception as e:
        msg.content = "Please Try Again!"
        await msg.update()
        print(e)


@cl.action_callback("run_analysis")
async def on_run_analysis(action: cl.Action):
    """Handle the run analysis button click."""
    loan_data = cl.user_session.get("loan_data")
    if loan_data:
        await run_nba_analysis([loan_data])
    else:
        await cl.Message(content="❌ No loan data found. Please enter a valid Account ID first.").send()


async def run_nba_analysis(validated_loans: List[LoanInput]):
    """Run the NBA analysis pipeline and stream results."""
    
    total_loans = len(validated_loans)
    results = []
    
    # Create a single streaming message for all results
    msg = cl.Message(content="")
    await msg.send()
    
    content = f"#### 📊 NBA Analysis Results\n\n**Processing {total_loans} loan(s)...**\n\n"
    await msg.stream_token(content)
    
    # Process each loan
    for idx, loan in enumerate(validated_loans, 1):
        loan_data = loan.to_agent_context()
        loan_id = loan.loan_id
        
        # Stream status
        await msg.stream_token(f"---\n\n#### 📋 Loan: **{loan_id}**\n")
        await msg.stream_token(f"DPD: {loan.dpd} | Outstanding: ₹{loan.outstanding_amount:,.0f} | Type: {loan.borrower_type}\n\n")
        
        try:
            # Run all agents
            await msg.stream_token("🔄 Analyzing...\n\n")
            
            eligibility_output = await eligibility_agent.analyze(loan_data)
            borrower_output = await borrower_intent_agent.analyze(loan_data)
            collateral_output = await collateral_agent.analyze(loan_data)
            regulatory_output = await regulatory_agent.analyze(
                loan_data, eligibility_output, borrower_output, collateral_output
            )
            nba_output = await nba_synthesizer.synthesize(
                loan_data, eligibility_output, borrower_output, 
                collateral_output, regulatory_output
            )
            
            # Get values
            action = nba_output.get("next_best_action", "Hold / No action")
            confidence = nba_output.get("confidence_level", "Medium")
            fallback = nba_output.get("fallback_action", "N/A")
            reasoning = nba_output.get("reasoning", [])
            reg_notes = nba_output.get("regulatory_notes", [])
            economic = nba_output.get("economic_rationale", "")
            rbi_align = nba_output.get("rbi_alignment", "")
            sma = eligibility_output.get("sma_classification", "N/A")
            intent = borrower_output.get("intent_classification", "N/A")
            
            # Confidence emoji
            conf_emoji = {"High": "🟢", "Medium": "🟡", "Low": "🔴"}.get(confidence, "⚪")
            
            # Stream the result
            result_text = f"""
#### ✅ **{action}**

| Attribute | Value |
|-----------|-------|
| Confidence | {conf_emoji} {confidence} |
| Fallback | {fallback} |
| SMA/NPA | {sma} |
| Borrower Intent | {intent} |

"""
            await msg.stream_token(result_text)
            
            # Add reasoning
            if reasoning:
                reasoning_text = "\n".join([f"- {r}" for r in reasoning[:3]])  # Top 3
                await msg.stream_token(f"**Reasoning:**\n{reasoning_text}\n\n")
            
            # Add regulatory notes if any
            if reg_notes and reg_notes[0] not in ["None", "Standard procedures apply"]:
                notes_text = "\n".join([f"- {n}" for n in reg_notes[:2]])  # Top 2
                await msg.stream_token(f"**⚠️ Regulatory Notes:**\n{notes_text}\n\n")
            
            # Store result
            result = {
                "loan_id": loan_id,
                "eligibility": eligibility_output,
                "borrower_intent": borrower_output,
                "collateral": collateral_output,
                "regulatory": regulatory_output,
                "nba": nba_output,
                "status": "Success"
            }
            results.append(result)
            
        except Exception as e:
            await msg.stream_token(f"### ❌ Error\n\n`{str(e)}`\n\n")
            error_result = {
                "loan_id": loan_id,
                "eligibility": {},
                "borrower_intent": {},
                "collateral": {},
                "regulatory": {},
                "nba": {
                    "next_best_action": "Hold / No action (regulatory or policy constraint)",
                    "reasoning": [f"Error: {str(e)}"],
                    "confidence_level": "Low",
                    "fallback_action": "Hold / No action",
                    "regulatory_notes": ["Manual review required"],
                    "economic_rationale": "Unable to determine",
                    "rbi_alignment": "Unable to determine"
                },
                "status": f"Error: {str(e)}"
            }
            results.append(error_result)
    
    # Store results
    cl.user_session.set("results", results)
    
    # Add summary
    success_count = sum(1 for r in results if r["status"] == "Success")
    await msg.stream_token(f"\n---\n\n## 📈 Summary\n\n✅ **{success_count}/{total_loans}** loans analyzed successfully.\n\n")
    
    # Create export CSV
    await create_export_csv(results, validated_loans, msg)


async def create_export_csv(results: List[Dict], validated_loans: List[LoanInput], msg: cl.Message):
    """Create downloadable CSV with results."""
    
    # Build export data
    export_rows = []
    
    for i, result in enumerate(results):
        loan = validated_loans[i]
        nba = result.get("nba", {})
        eligibility = result.get("eligibility", {})
        
        row = {
            "loan_id": loan.loan_id,
            "dpd": loan.dpd,
            "outstanding_amount": loan.outstanding_amount,
            "borrower_type": loan.borrower_type,
            "secured_unsecured": loan.secured_unsecured,
            "collateral_quality": loan.collateral_quality,
            "cibil_score": loan.cibil_score,
            "sma_classification": eligibility.get("sma_classification", "N/A"),
            "is_npa": eligibility.get("is_npa", False),
            "sarfaesi_eligible": eligibility.get("sarfaesi_eligible", False),
            "next_best_action": nba.get("next_best_action", "N/A"),
            "confidence_level": nba.get("confidence_level", "N/A"),
            "fallback_action": nba.get("fallback_action", "N/A"),
            "reasoning": " | ".join(nba.get("reasoning", [])[:3]),
            "regulatory_notes": " | ".join(nba.get("regulatory_notes", [])[:2]),
            "status": result.get("status", "N/A")
        }
        export_rows.append(row)
    
    # Create DataFrame and CSV
    export_df = pd.DataFrame(export_rows)
    csv_buffer = io.StringIO()
    export_df.to_csv(csv_buffer, index=False)
    csv_content = csv_buffer.getvalue()
    
    # Create file element
    elements = [
        cl.File(
            name="nba_results.csv",
            content=csv_content.encode(),
            display="inline"
        )
    ]
    
    await msg.stream_token("📥 **Download results:** Click the file below.\n\n")
    
    # Send a separate message with the file
    await cl.Message(
        content="📥 **Export Ready:**",
        elements=elements
    ).send()
