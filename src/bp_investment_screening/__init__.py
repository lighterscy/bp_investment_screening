"""Lightweight BP-based investment screening package."""

from bp_investment_screening.pipeline import ScreeningPipeline
from bp_investment_screening.schemas import (
    BPClaims,
    DocumentParseResult,
    EvidenceItem,
    InvestmentMemo,
    InvestmentRecommendation,
    Layer1ResearchItem,
)

__all__ = [
    "BPClaims",
    "DocumentParseResult",
    "EvidenceItem",
    "InvestmentMemo",
    "InvestmentRecommendation",
    "Layer1ResearchItem",
    "ScreeningPipeline",
]

