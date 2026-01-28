"""
NBA Decision System - Chainlit Application
Fast, Actionable Recommendations for Indian Home Loan Recovery
"""

import chainlit as cl
import pandas as pd
import io
import os
import base64
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from agents import NBAAgent
from db import get_loan_by_id
from schemas import LoanInput


# Initialize agent
agent = None


def get_agent() -> NBAAgent:
    """Get or create NBA agent"""
    global agent
    if agent is None:
        agent = NBAAgent()
    return agent


def format_indian_currency(n) -> str:
    """Format number with Indian numbering system (e.g. 10,00,000)"""
    try:
        n = float(n)
        s = f"{n:.0f}"
        if len(s) <= 3:
            return s
        
        last_three = s[-3:]
        remaining = s[:-3]
        
        formatted_remaining = ""
        while len(remaining) > 2:
            formatted_remaining = "," + remaining[-2:] + formatted_remaining
            remaining = remaining[:-2]
        
        formatted_remaining = remaining + formatted_remaining
        
        return formatted_remaining + "," + last_three
    except:
        return str(n)


@cl.on_chat_start
async def start():
    """Initialize chat session"""
    cl.user_session.set("loan_data", None)
    
    welcome_message = """#### 🏦 NBA Decision System

**Next Best Action Recommender** for Home Loan Recovery

#### Quick Start:
1. 🔍 **Search** for a loan by **Account ID**, **Customer ID**, or **Customer Name**
2. 📊 **Review** the loan summary
3. 🚀 **Run** NBA analysis

---
**🔍 Enter Account ID, Customer ID, or Customer Name to search.**
"""
    await cl.Message(content=welcome_message).send()


@cl.on_message
async def main(message: cl.Message):
    """Handle incoming messages"""
    
    # Check for help command
    if message.content.lower().strip() == "help":
        await send_help()
        return
    
    # Check if this is a command to run analysis
    if message.content.strip().lower() in ["run", "analyze", "run analysis", "start", "run nba analysis"]:
        loan_data = cl.user_session.get("loan_data")
        if loan_data:
            await run_nba_analysis(loan_data)
        else:
            await cl.Message(content="❌ No loan data found. Please enter a valid Account ID first.").send()
        return
    
    # Otherwise, treat input as search term (account_id, customer_id, or name)
    search_term = message.content.strip()
    
    if not search_term:
        await cl.Message(content="📎 Please enter an Account ID, Customer ID, or Name to search.").send()
        return
    
    # Show search status
    msg = cl.Message(content=f"🔍 Searching for: **{search_term}**...")
    await msg.send()
    
    try:
        loan_input = get_loan_by_id(search_term)
        
        if not loan_input:
            msg.content = f"❌ No record found for: **{search_term}**. Try Account ID, Customer ID, or Name."
            await msg.update()
            return
        
        # Store loan data
        cl.user_session.set("loan_data", loan_input)
        
        # Show success
        msg.content = f"✅ Record found: **{loan_input.customer_full_name}** ({loan_input.loan_id})"
        await msg.update()
        
        # Show loan summary
        summary = create_loan_summary(loan_input)
        await cl.Message(content=summary).send()
        
        # Show action button
        actions = [
            cl.Action(
                name="run_analysis",
                payload={"action": "run"},
                label="🚀 Run Analysis"
            )
        ]
        
        await cl.Message(
            content="Click below or type **'run'** to start analysis.",
            actions=actions
        ).send()
        
    except Exception as e:
        msg.content = f"❌ Error: {str(e)}"
        await msg.update()


@cl.action_callback("run_analysis")
async def on_run_analysis(action: cl.Action):
    """Handle the run analysis button click"""
    loan_data = cl.user_session.get("loan_data")
    if loan_data:
        await run_nba_analysis(loan_data)
    else:
        await cl.Message(content="❌ No loan data found. Please enter a valid Account ID first.").send()


async def run_nba_analysis(loan_input: LoanInput):
    """Run analysis for a single loan"""
    
    # Get agent context (dict format for the agent)
    account_data = loan_input.to_agent_context()
    account_id = loan_input.loan_id
    
    # Create analyzing message
    analyze_msg = cl.Message(content=f"⏳ Analyzing **{account_id}**...")
    await analyze_msg.send()
    
    # Get agent
    nba_agent = get_agent()
    
    # Get recommendation
    result = await nba_agent.get_recommendation(account_data)
    formatted_output, parsed_data = nba_agent.format_output(result)
    
    # Add account header
    account_header = f"""#### 📄 **Account ID:** {account_id} | **Customer ID:** {loan_input.customer_id} 
**Customer Name:** {loan_input.customer_full_name}
**DPD:** {loan_input.dpd} · **Outstanding:** ₹{format_indian_currency(loan_input.outstanding_amount)}

---
"""
    output = account_header + formatted_output
    
    # Update with result
    analyze_msg.content = output
    await analyze_msg.update()
    
    # Generate and send pie chart for factor weightages
    await create_pie_chart(parsed_data.get("factor_weightages", {}), account_id)
    
    # Create and send export CSV
    await create_export_csv(loan_input, result)


async def create_pie_chart(factor_weightages: dict, account_id: str):
    """Create and send a pie chart showing factor contribution distribution"""
    
    if not factor_weightages:
        # No weightages available, skip pie chart
        return
    
    # Prepare data for pie chart
    labels = list(factor_weightages.keys())
    sizes = list(factor_weightages.values())
    
    # Define a modern, vibrant color palette
    colors = [
        '#6366F1',  # Indigo
        '#8B5CF6',  # Violet
        '#EC4899',  # Pink
        '#F97316',  # Orange
        '#14B8A6',  # Teal
        '#22C55E',  # Green
        '#EAB308',  # Yellow
        '#3B82F6',  # Blue
    ]
    
    # Use only needed colors
    pie_colors = colors[:len(labels)]
    
    # Create figure with dark background for modern look
    fig, ax = plt.subplots(figsize=(8, 6), facecolor='#1a1a2e')
    ax.set_facecolor('#1a1a2e')
    
    # Create pie chart with explosion effect for emphasis
    explode = [0.02] * len(labels)  # Slight separation for all slices
    
    wedges, texts, autotexts = ax.pie(
        sizes,
        labels=labels,
        colors=pie_colors,
        autopct='%1.1f%%',
        startangle=90,
        explode=explode,
        shadow=False,
        wedgeprops=dict(width=0.7, edgecolor='#1a1a2e', linewidth=2),
        textprops={'fontsize': 10, 'color': 'white', 'fontweight': 'bold'},
        pctdistance=0.75
    )
    
    # Style autopct labels
    for autotext in autotexts:
        autotext.set_color('#ffffff')
        autotext.set_fontsize(9)
        autotext.set_fontweight('bold')
    
    # Style labels
    for text in texts:
        text.set_fontsize(9)
        text.set_color('#e2e8f0')
    
    # Add title
    ax.set_title(
        'Factor Contribution Distribution',
        fontsize=14,
        fontweight='bold',
        color='white',
        pad=20
    )
    
    # Add a center circle for donut chart effect
    centre_circle = plt.Circle((0, 0), 0.4, fc='#1a1a2e')
    ax.add_patch(centre_circle)
    
    # Add center text
    ax.text(0, 0, 'Factors', ha='center', va='center', fontsize=12, 
            color='white', fontweight='bold')
    
    # Equal aspect ratio ensures pie is circular
    ax.axis('equal')
    
    # Tight layout
    plt.tight_layout()
    
    # Save to bytes buffer
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, facecolor='#1a1a2e', 
                edgecolor='none', bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)
    
    # Convert to base64 for inline display
    img_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    
    # Create image element
    elements = [
        cl.Image(
            name="factor_distribution",
            content=buf.getvalue(),
            display="inline",
            size="large"
        )
    ]
    
    # Send message with pie chart
    await cl.Message(
        content="#### 📊 Factor Contribution Analysis",
        elements=elements
    ).send()


async def create_export_csv(loan: LoanInput, result: dict):
    """Create downloadable CSV with results."""
    
    # Parse recommendation to extract key fields
    recommendation = result.get("recommendation", "")
    parsed = _parse_recommendation_for_export(recommendation)
    
    # Build export row
    export_row = {
        "account_id": loan.loan_id,
        "customer_id": loan.customer_id,
        "dpd": loan.dpd,
        "outstanding_amount": loan.outstanding_amount,
        "loan_amount": loan.loan_amount,
        "borrower_type": loan.borrower_type,
        "secured_unsecured": loan.secured_unsecured,
        "collateral_quality": loan.collateral_quality,
        "cibil_score": loan.cibil_score,
        "next_best_action": parsed.get("action_title", "N/A"),
        "success_likelihood": parsed.get("success_likelihood", "N/A"),
        "confidence": parsed.get("confidence", "N/A"),
        "borrower_intent": parsed.get("borrower_intent", "N/A"),
        "key_factors": " | ".join(parsed.get("key_factors", [])[:3]),
        "fallback_action": parsed.get("if_action_fails", "N/A"),
        "status": "Success" if result.get("success") else "Error"
    }
    
    # Create DataFrame and CSV
    export_df = pd.DataFrame([export_row])
    csv_buffer = io.StringIO()
    export_df.to_csv(csv_buffer, index=False)
    csv_content = csv_buffer.getvalue()
    
    # Create file element
    elements = [
        cl.File(
            name=f"nba_result_{loan.loan_id}.csv",
            content=csv_content.encode(),
            display="inline"
        )
    ]
    
    # Send message with the file
    await cl.Message(
        content="📥 **Download Results:**",
        elements=elements
    ).send()


def _parse_recommendation_for_export(text: str) -> dict:
    """Parse structured recommendation text for CSV export."""
    result = {
        "action_title": "N/A",
        "success_likelihood": "N/A",
        "confidence": "N/A",
        "borrower_intent": "N/A",
        "key_factors": [],
        "if_action_fails": "N/A"
    }
    
    if not text:
        return result
    
    lines = text.strip().split("\n")
    current_section = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        if line.startswith("**ACTION_TITLE:**"):
            result["action_title"] = line.replace("**ACTION_TITLE:**", "").strip()
        elif line.startswith("**SUCCESS_LIKELIHOOD:**"):
            result["success_likelihood"] = line.replace("**SUCCESS_LIKELIHOOD:**", "").strip()
        elif line.startswith("**CONFIDENCE:**"):
            result["confidence"] = line.replace("**CONFIDENCE:**", "").strip()
        elif line.startswith("**BORROWER_INTENT:**"):
            result["borrower_intent"] = line.replace("**BORROWER_INTENT:**", "").strip()
        elif line.startswith("**KEY_FACTORS:**"):
            current_section = "key_factors"
        elif line.startswith("**IF_ACTION_FAILS:**"):
            result["if_action_fails"] = line.replace("**IF_ACTION_FAILS:**", "").strip()
            current_section = None
        elif line.startswith("- ") and current_section == "key_factors":
            result["key_factors"].append(line[2:].strip())
    
    return result


def create_loan_summary(loan: LoanInput) -> str:
    """Create loan summary table"""
    return f"""#### 📋 Loan Summary

| **Attribute** | **Value** |
|-----------|-------|
| Account ID | {loan.loan_id} |
| Customer ID | {loan.customer_id} |
| Customer Name | {loan.customer_full_name} |
| DPD | {loan.dpd} days |
| Outstanding | ₹{format_indian_currency(loan.outstanding_amount)} |
| Loan Amount | ₹{format_indian_currency(loan.loan_amount)} |
| EMI | ₹{format_indian_currency(loan.emi_amount)} |
| Interest Rate | {loan.interest_rate}% |
| Secured | {loan.secured_unsecured} |
| Collateral | {loan.collateral_type} ({loan.collateral_quality}) |
| Collateral Liquidity | {loan.collateral_liquidity} |
| Customer Type | {loan.borrower_type} |
| Location | {loan.geographic_location} |
| Annual Income | {loan.annual_income_total} |
| CIBIL Score | {loan.cibil_score} |
| SARFAESI Ready | {loan.sarfaesi_ready_flag} |

---"""


async def send_help():
    """Send help message"""
    await cl.Message(content="""#### 📋 How to Use

1. **Enter Account ID** — Type the loan account ID to search
2. **Review Summary** — Check the loan details displayed
3. **Run Analysis** — Click the button or type 'run' to get NBA recommendation

**Example Account IDs:** Check your database for existing records.
""").send()

