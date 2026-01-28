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
    cl.user_session.set("csv_data", None)
    cl.user_session.set("validated_loans", None)
    cl.user_session.set("results", None)
    
    welcome_message = """
# 🏦 Home Loan Next Best Action (NBA) System

Welcome to the **AI-powered NBA Decision System** for Indian Home Loan Recovery.

## Quick Start:
1. 📎 **Upload** a CSV file with loan data
2. 🔍 **Review** the validation results
3. 🚀 **Run** NBA analysis
4. 📥 **Download** results

**📎 Upload your CSV file to begin.**
"""
    await cl.Message(content=welcome_message).send()


@cl.on_message
async def main(message: cl.Message):
    """Handle incoming messages and file uploads."""
    
    # Check if this is a command to run analysis
    if message.content.strip().lower() in ["run", "analyze", "run analysis", "start", "run nba analysis"]:
        validated_loans = cl.user_session.get("validated_loans")
        if validated_loans:
            await run_nba_analysis(validated_loans)
        else:
            await cl.Message(content="❌ No validated loan data. Please upload a CSV file first.").send()
        return
    
    # Check for file attachments
    if not message.elements:
        await cl.Message(content="Please upload a CSV file or type **'run'** to start the analysis.").send()
        return
    
    # Filter for CSV files
    csv_files = [el for el in message.elements if el.name.endswith('.csv')]
    
    if not csv_files:
        await cl.Message(content="❌ Please upload a `.csv` file.").send()
        return
    
    csv_file = csv_files[0]
    
    # Read file content
    file_content = None
    try:
        if hasattr(csv_file, 'content') and csv_file.content:
            file_content = csv_file.content
        elif hasattr(csv_file, 'path') and csv_file.path:
            with open(csv_file.path, 'rb') as f:
                file_content = f.read()
        
        if not file_content:
            await cl.Message(content="❌ Could not read file. Please try again.").send()
            return
    except Exception as e:
        await cl.Message(content=f"❌ Error: {str(e)}").send()
        return
    
    # Get preview
    preview_df, preview_error = get_preview_dataframe(file_content, num_rows=5)
    
    if preview_error:
        await cl.Message(content=f"❌ Error: {preview_error}").send()
        return
    
    # Validate CSV
    validation_result = load_and_validate_csv(file_content, csv_file.name)
    
    if not validation_result.is_valid:
        validation_msg = format_validation_errors(validation_result)
        await cl.Message(content=validation_msg).send()
        return
    
    # Store validated loans
    cl.user_session.set("csv_data", file_content)
    cl.user_session.set("validated_loans", validation_result.valid_loans)
    
    # Show success and action button
    actions = [
        cl.Action(
            name="run_analysis",
            payload={"action": "run"},
            label="🚀 Run NBA Analysis"
        )
    ]
    
    await cl.Message(
        content=f"✅ **{validation_result.valid_count} loans** validated successfully.\n\nClick below or type **'run'** to start analysis.",
        actions=actions
    ).send()


@cl.action_callback("run_analysis")
async def on_run_analysis(action: cl.Action):
    """Handle the run analysis button click."""
    validated_loans = cl.user_session.get("validated_loans")
    if validated_loans:
        await run_nba_analysis(validated_loans)
    else:
        await cl.Message(content="❌ No validated loans. Please upload a CSV file first.").send()


async def run_nba_analysis(validated_loans: List[LoanInput]):
    """Run the NBA analysis pipeline and stream results."""
    
    total_loans = len(validated_loans)
    results = []
    
    # Create a single streaming message for all results
    msg = cl.Message(content="")
    await msg.send()
    
    content = f"# 📊 NBA Analysis Results\n\n**Processing {total_loans} loan(s)...**\n\n"
    await msg.stream_token(content)
    
    # Process each loan
    for idx, loan in enumerate(validated_loans, 1):
        loan_data = loan.to_agent_context()
        loan_id = loan.loan_id
        
        # Stream status
        await msg.stream_token(f"---\n\n## 📋 Loan: **{loan_id}**\n")
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
            success_likelihood = nba_output.get("success_likelihood", confidence)
            success_explanation = nba_output.get("success_explanation", "")
            fallback = nba_output.get("fallback_action", "N/A")
            if_fails = nba_output.get("if_action_fails", "")
            reasoning = nba_output.get("reasoning", [])
            reg_notes = nba_output.get("regulatory_notes", [])
            economic = nba_output.get("economic_rationale", "")
            rbi_align = nba_output.get("rbi_alignment", "")
            sma = eligibility_output.get("sma_classification", "N/A")
            intent = borrower_output.get("intent_classification", "N/A")
            
            # Emojis for likelihood
            likelihood_emoji = {"High": "🟢", "Medium": "🟡", "Low": "🔴"}.get(success_likelihood, "⚪")
            conf_emoji = {"High": "🟢", "Medium": "🟡", "Low": "🔴"}.get(confidence, "⚪")
            
            # Stream the result with improved format
            result_text = f"""
### 🎯 **{action}**

**📈 Success Likelihood:** {likelihood_emoji} {success_likelihood}
> {success_explanation if success_explanation else 'Based on borrower profile and collateral assessment'}

| Attribute | Value |
|-----------|-------|
| Confidence | {conf_emoji} {confidence} |
| SMA/NPA | {sma} |
| Borrower Intent | {intent} |

"""
            await msg.stream_token(result_text)
            
            # Add Key Factors (reasoning)
            if reasoning:
                reasoning_text = "\n".join([f"- {r}" for r in reasoning[:5]])  # Top 5 key factors
                await msg.stream_token(f"**📊 Key Factors:**\n{reasoning_text}\n\n")
            
            # Add fallback action
            await msg.stream_token(f"**🔄 If Action Fails:** {if_fails if if_fails else fallback}\n\n")
            
            # Add regulatory notes if any
            if reg_notes and len(reg_notes) > 0:
                first_note = reg_notes[0] if isinstance(reg_notes[0], str) else str(reg_notes[0])
                if first_note not in ["None", "No restrictions at current stage", "Standard procedures apply", ""]:
                    notes_text = "\n".join([f"- {n}" for n in reg_notes[:2]])
                    await msg.stream_token(f"**⚖️ Compliance:**\n{notes_text}\n\n")
            
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
        borrower = result.get("borrower_intent", {})
        
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
            "borrower_intent": borrower.get("intent_classification", "N/A"),
            "next_best_action": nba.get("next_best_action", "N/A"),
            "success_likelihood": nba.get("success_likelihood", nba.get("confidence_level", "N/A")),
            "success_explanation": nba.get("success_explanation", ""),
            "confidence_level": nba.get("confidence_level", "N/A"),
            "fallback_action": nba.get("fallback_action", "N/A"),
            "if_action_fails": nba.get("if_action_fails", ""),
            "key_factors": " | ".join(nba.get("reasoning", [])[:5]),
            "regulatory_notes": " | ".join(nba.get("regulatory_notes", [])[:2]),
            "economic_rationale": nba.get("economic_rationale", ""),
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
