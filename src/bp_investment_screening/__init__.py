"""Lightweight BP-based investment screening package."""

from bp_investment_screening.pipeline import ScreeningPipeline
from bp_investment_screening.schemas import (
    BPClaims,
    DocumentParseResult,
    EvidenceGroup,
    EvidenceItem,
    InvestmentMemo,
    InvestmentRecommendation,
    Layer1ResearchItem,
    TopicInformationSummary,
)

__all__ = [
    "BPClaims",
    "DocumentParseResult",
    "EvidenceGroup",
    "EvidenceItem",
    "InvestmentMemo",
    "InvestmentRecommendation",
    "Layer1ResearchItem",
    "ScreeningPipeline",
    "TopicInformationSummary",
]
