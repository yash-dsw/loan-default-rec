"""
Agents package for Home Loan NBA Decision System.
Contains all 5 specialized agents for the decision pipeline.
"""

from agents.eligibility import EligibilityAgent
from agents.borrower_intent import BorrowerIntentAgent
from agents.collateral import CollateralAgent
from agents.regulatory import RegulatoryAgent
from agents.nba_synthesizer import NBASynthesizerAgent

__all__ = [
    'EligibilityAgent',
    'BorrowerIntentAgent', 
    'CollateralAgent',
    'RegulatoryAgent',
    'NBASynthesizerAgent'
]
