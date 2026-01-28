"""
NBA Decision System - Chainlit Application
Fast, Actionable Recommendations for Indian Home Loan Recovery
"""

import chainlit as cl
import pandas as pd
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from agents import NBAAgent
from validators import validate_csv_input, dataframe_to_records


# Initialize agent
agent = None


def get_agent() -> NBAAgent:
    """Get or create NBA agent"""
    global agent
    if agent is None:
        agent = NBAAgent()
    return agent


@cl.on_chat_start
async def start():
    """Initialize chat session"""
    welcome_message = """#### 🏦 NBA Decision System

**Next Best Action Recommender** for Home Loan Recovery

Upload a CSV file (1-5 accounts) to get:
- 🎯 Single best action recommendation
- 📊 Key factors influencing decision
- ⚖️ RBI/SARFAESI compliance check

---
📎 **Upload your CSV to begin.**
"""
    await cl.Message(content=welcome_message).send()


@cl.on_message
async def main(message: cl.Message):
    """Handle file uploads"""
    
    if message.content.lower().strip() == "help":
        await send_help()
        return
    
    if not message.elements:
        await cl.Message(content="📎 Please upload a CSV file with loan data.").send()
        return
    
    csv_files = [el for el in message.elements if el.name.endswith('.csv')]
    
    if not csv_files:
        await cl.Message(content="❌ No CSV file found. Please upload a .csv file.").send()
        return
    
    csv_file = csv_files[0]
    
    try:
        # Processing message
        processing_msg = cl.Message(content=f"📂 Reading **{csv_file.name}**...")
        await processing_msg.send()
        
        # Read CSV
        if hasattr(csv_file, 'path') and csv_file.path:
            df = pd.read_csv(csv_file.path)
        elif hasattr(csv_file, 'content') and csv_file.content:
            import io
            if isinstance(csv_file.content, bytes):
                df = pd.read_csv(io.BytesIO(csv_file.content))
            else:
                df = pd.read_csv(io.StringIO(csv_file.content))
        else:
            processing_msg.content = "❌ Could not read file."
            await processing_msg.update()
            return
        
        # Validate
        validation = validate_csv_input(df, max_rows=5)
        
        if not validation.is_valid:
            processing_msg.content = f"❌ **Validation Failed**\n\n{validation.get_summary()}"
            await processing_msg.update()
            return
        
        records = dataframe_to_records(validation.validated_data)
        
        # Update with summary table
        summary = create_summary_table(validation.validated_data)
        processing_msg.content = summary
        await processing_msg.update()
        
        # Get agent
        nba_agent = get_agent()
        
        # Process each account
        for i, record in enumerate(records, 1):
            account_id = record.get('account_id', f'Account {i}')
            
            # Create analyzing message
            analyze_msg = cl.Message(content=f"⏳ Analyzing **{account_id}**...")
            await analyze_msg.send()
            
            # Get recommendation
            result = await nba_agent.get_recommendation(record)
            formatted_output = nba_agent.format_output(result)
            
            # Add account header
            account_header = f"""#### 📄 {account_id} | {record.get('customer_id', 'Unknown')}
**Stage:** NPA · **DPD:** {record.get('dpd', 0)} · **Outstanding:** ₹{record.get('outstanding_amount', 0):,.0f}

---
"""
            output = account_header + formatted_output
            
            # Update with result
            analyze_msg.content = output
            await analyze_msg.update()
        
        # Final message
        await cl.Message(content=f"✅ Done — {len(records)} account(s) processed").send()
        
    except Exception as e:
        await cl.Message(content=f"❌ Error: {str(e)}").send()


def create_summary_table(df: pd.DataFrame) -> str:
    """Create data summary as table"""
    lines = [
        "#### 📊 Accounts to Analyze",
        "",
        "| Account | Customer | Stage | DPD | Outstanding |",
        "|:--------|:---------|:------|----:|------------:|"
    ]
    
    for _, row in df.iterrows():
        outstanding = row.get('outstanding_amount', 0)
        lines.append(f"| {row.get('account_id', 'N/A')} | {row.get('customer_id', 'N/A')} | {row.get('delinquency_stage', 'N/A')} | {row.get('dpd', 0)} | ₹{outstanding:,.0f} |")
    
    lines.append("")
    lines.append("---")
    return "\n".join(lines)


async def send_help():
    """Send help message"""
    await cl.Message(content="""#### 📋 CSV Format

**Required columns:** `account_id`, `customer_id`, `loan_type`, `dpd`, `delinquency_stage`, `outstanding_amount`

**Delinquency Stages:**
• SMA-0: 1-30 DPD (Soft reminders)
• SMA-1: 31-60 DPD (Field visits)
• SMA-2: 61-90 DPD (Formal notices)
• NPA: >90 DPD (Legal action)

📎 Upload your CSV to get started!
""").send()
