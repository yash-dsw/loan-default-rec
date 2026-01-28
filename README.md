# Home Loan NBA Agent System

## Overview
This is an Agentic AI "Next Best Action" decision system for Indian Home Loan recovery, built with Chainlit. It provides bank-grade, explainable recommendations compliant with RBI guidelines and SARFAESI Act.

## Features
- CSV file upload and validation
- 5 sequential AI agents for comprehensive analysis
- RBI/SARFAESI compliant recommendations
- Audit-ready decision explanations
- Export results to CSV

## Tech Stack
- Python 3.9+
- Chainlit (UI and orchestration)
- Pydantic (data validation)
- OpenRouter API (LLM backend)
- Pandas (data processing)

## Quick Start

### 1. Install Dependencies
```bash
pip install chainlit pydantic pandas python-dotenv httpx tabulate
```

### 2. Configure API Key
Create a `.env` file with your OpenRouter API key:
```
OPENROUTER_API_KEY=your_api_key_here
```

### 3. Run the Application
```bash
chainlit run app.py
```

### 4. Upload Sample Data
Use the provided `sample_loans.csv` to test the system.

## File Structure
```
infosys_recommender/
├── app.py              # Chainlit entry point
├── prompts.py          # Agent prompts (RBI-compliant)
├── schemas.py          # Pydantic data models
├── csv_loader.py       # CSV validation
├── agents/
│   ├── __init__.py
│   ├── eligibility.py      # SMA/NPA classification
│   ├── borrower_intent.py  # Intent assessment
│   ├── collateral.py       # Recovery economics
│   ├── regulatory.py       # Compliance checks
│   └── nba_synthesizer.py  # Final decision
├── sample_loans.csv    # Test data
└── .env               # API configuration
```

## Agent Pipeline

1. **Eligibility Agent**: Classifies account as SMA-0/1/2 or NPA, determines SARFAESI eligibility
2. **Borrower Intent Agent**: Assesses willingness/ability to pay, classifies intent
3. **Collateral Agent**: Analyzes recovery economics, NPV calculations
4. **Regulatory Agent**: Ensures RBI/SARFAESI compliance, blocks illegal actions
5. **NBA Synthesizer**: Produces final recommendation with confidence and fallback

## Allowed Actions
- Gentle nudging / Digital reminder
- Relationship Manager intervention
- Restructuring / EMI recast
- Pre-legal notice
- SARFAESI Section 13(2) notice
- Symbolic possession
- Physical possession
- Auction initiation
- One-Time Settlement (OTS)
- ARC sale
- Technical write-off
- Hold / No action

## CSV Input Format
See `sample_loans.csv` for the required column format.

## Output
- Per-loan NBA recommendation
- Confidence level (High/Medium/Low)
- Fallback action
- Regulatory notes
- Exportable CSV with all results

## Compliance
- RBI asset classification norms (SMA-0/1/2/NPA)
- SARFAESI Act Section 13 sequencing
- Fair Practices Code
- State-specific considerations

## License
Internal use only - Bank proprietary system
