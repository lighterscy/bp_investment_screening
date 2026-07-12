"""Core schemas for BP investment screening.

The schemas are intentionally plain dataclasses so the project can be moved out
without bringing heavy framework dependencies.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal


SourceType = Literal["bp", "external", "synthesis"]
EvidencePriority = Literal["bp_first", "external_first", "balanced"]
Confidence = Literal["low", "medium", "high"]
Recommendation = Literal["建议跟进", "谨慎跟进", "暂不跟进"]


@dataclass(frozen=True, slots=True)
class DocumentPage:
    page_number: int
    text: str
    source_path: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class DocumentParseResult:
    source_path: Path
    pages: list[DocumentPage]
    parser_name: str

    def to_dict(self) -> dict:
        return {
            "source_path": str(self.source_path),
            "pages": [page.to_dict() for page in self.pages],
            "parser_name": self.parser_name,
        }


@dataclass(frozen=True, slots=True)
class Claim:
    text: str
    category: str
    source_page: int | None = None
    needs_verification: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class BPClaims:
    company_name: str | None = None
    industry: str | None = None
    product_summary: str | None = None
    business_model_claims: list[Claim] = field(default_factory=list)
    market_claims: list[Claim] = field(default_factory=list)
    traction_claims: list[Claim] = field(default_factory=list)
    team_claims: list[Claim] = field(default_factory=list)
    financial_claims: list[Claim] = field(default_factory=list)
    fundraising_claims: list[Claim] = field(default_factory=list)
    customer_claims: list[Claim] = field(default_factory=list)
    technology_claims: list[Claim] = field(default_factory=list)
    risk_disclosures: list[Claim] = field(default_factory=list)
    missing_information: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    source_type: SourceType
    title: str
    content: str
    url: str | None = None
    source_page: int | None = None
    confidence: Confidence = "medium"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class TopicInformationSummary:
    bp_claims_summary: str
    external_evidence_summary: str
    integrated_summary: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class EvidenceGroup:
    aspect: str
    bp_claims: list[EvidenceItem] = field(default_factory=list)
    external_evidence: list[EvidenceItem] = field(default_factory=list)
    summary: str = ""
    conflicts: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class Layer1ResearchItem:
    domain: Literal["company", "industry"]
    topic: str
    evidence_priority: EvidencePriority
    bp_claims: list[EvidenceItem]
    external_evidence: list[EvidenceItem]
    synthesis: str
    confidence: Confidence
    evidence_groups: list[EvidenceGroup] = field(default_factory=list)
    information_summary: TopicInformationSummary | None = None
    key_risks: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class InvestmentRecommendation:
    recommendation: Recommendation
    confidence: Confidence
    one_sentence_view: str
    strengths: list[str]
    weaknesses: list[str]
    key_risks: list[str]
    open_questions: list[str]
    next_steps: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class InvestmentMemo:
    project_name: str
    industry: str | None
    recommendation: InvestmentRecommendation
    layer1_items: list[Layer1ResearchItem]
    source_bp_path: Path

    def to_dict(self) -> dict:
        return {
            "project_name": self.project_name,
            "industry": self.industry,
            "recommendation": self.recommendation.to_dict(),
            "layer1_items": [item.to_dict() for item in self.layer1_items],
            "source_bp_path": str(self.source_bp_path),
        }
