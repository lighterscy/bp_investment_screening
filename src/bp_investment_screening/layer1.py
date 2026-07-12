"""Layer1 foundation research planning and synthesis."""

from __future__ import annotations

from dataclasses import dataclass

from bp_investment_screening.schemas import (
    BPClaims,
    EvidenceItem,
    EvidencePriority,
    Layer1ResearchItem,
)
from bp_investment_screening.search import SearchClient, SearchQuery


@dataclass(frozen=True, slots=True)
class Layer1Topic:
    domain: str
    name: str
    evidence_priority: EvidencePriority
    search_query_template: str | None = None


DEFAULT_LAYER1_TOPICS = [
    Layer1Topic("company", "公司基本信息", "bp_first", None),
    Layer1Topic("company", "产品与服务", "bp_first", None),
    Layer1Topic("company", "商业模式与增长证据", "external_first", "{company} 商业模式 客户 收入 增长"),
    Layer1Topic("company", "团队与资源匹配度", "bp_first", "{company} 创始人 团队 履历"),
    Layer1Topic("industry", "行业阶段与市场空间", "external_first", "{industry} 行业 阶段 市场规模 增长"),
    Layer1Topic("industry", "竞争格局与替代方案", "external_first", "{industry} 竞争格局 竞品 替代方案"),
    Layer1Topic("industry", "技术趋势与政策环境", "external_first", "{industry} 技术趋势 政策 监管"),
]


class Layer1Researcher:
    """Lightweight layer1 researcher combining BP claims and external evidence."""

    def __init__(
        self,
        search_client: SearchClient,
        topics: list[Layer1Topic] | None = None,
    ) -> None:
        self.search_client = search_client
        self.topics = topics or DEFAULT_LAYER1_TOPICS

    def run(self, claims: BPClaims) -> list[Layer1ResearchItem]:
        items: list[Layer1ResearchItem] = []
        company = claims.company_name or "未知公司"
        industry = claims.industry or "未知行业"
        for topic in self.topics:
            external_evidence: list[EvidenceItem] = []
            if topic.search_query_template:
                query = topic.search_query_template.format(company=company, industry=industry)
                external_evidence = self.search_client.search(
                    SearchQuery(query=query, purpose=topic.name)
                )
            bp_evidence = _bp_evidence_for_topic(topic.name, claims)
            items.append(
                Layer1ResearchItem(
                    domain=topic.domain,  # type: ignore[arg-type]
                    topic=topic.name,
                    evidence_priority=topic.evidence_priority,
                    bp_claims=bp_evidence,
                    external_evidence=external_evidence,
                    synthesis=_placeholder_synthesis(topic, bp_evidence, external_evidence),
                    confidence="low" if not external_evidence else "medium",
                    open_questions=_open_questions(topic, external_evidence),
                )
            )
        return items


def _bp_evidence_for_topic(topic: str, claims: BPClaims) -> list[EvidenceItem]:
    evidence: list[EvidenceItem] = []
    if topic == "公司基本信息":
        for title, value in [
            ("公司名称", claims.company_name),
            ("行业", claims.industry),
            ("产品概述", claims.product_summary),
        ]:
            if value:
                evidence.append(EvidenceItem(source_type="bp", title=title, content=value))
    claim_groups = []
    if topic == "产品与服务":
        claim_groups = [claims.technology_claims, claims.customer_claims]
    elif topic == "商业模式与增长证据":
        claim_groups = [claims.business_model_claims, claims.traction_claims, claims.financial_claims]
    elif topic == "团队与资源匹配度":
        claim_groups = [claims.team_claims, claims.fundraising_claims]
    elif topic.startswith("行业"):
        claim_groups = [claims.market_claims]
    for group in claim_groups:
        for claim in group:
            evidence.append(
                EvidenceItem(
                    source_type="bp",
                    title=claim.category,
                    content=claim.text,
                    source_page=claim.source_page,
                    confidence="low" if claim.needs_verification else "medium",
                )
            )
    return evidence


def _placeholder_synthesis(
    topic: Layer1Topic,
    bp_evidence: list[EvidenceItem],
    external_evidence: list[EvidenceItem],
) -> str:
    return (
        f"{topic.name}已收集 BP 证据 {len(bp_evidence)} 条、外部证据 {len(external_evidence)} 条。"
        "当前为框架占位综合，后续应由 LLM 按证据优先级生成正式研究结论。"
    )


def _open_questions(topic: Layer1Topic, external_evidence: list[EvidenceItem]) -> list[str]:
    if topic.evidence_priority == "external_first" and not external_evidence:
        return [f"{topic.name}缺少外部证据，需要联网搜索或人工补充。"]
    return []

