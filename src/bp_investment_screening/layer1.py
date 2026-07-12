"""Layer1 foundation research planning and synthesis."""

from __future__ import annotations

from dataclasses import dataclass

from bp_investment_screening.evidence_normalizer import EvidenceNormalizer
from bp_investment_screening.layer1_synthesizer import Layer1Synthesizer
from bp_investment_screening.schemas import (
    BPClaims,
    EvidenceItem,
    EvidencePriority,
    Layer1ResearchItem,
)
from bp_investment_screening.search import SearchClient, SearchQuery
from bp_investment_screening.tracing import NullTracer, Tracer


@dataclass(frozen=True, slots=True)
class Layer1Topic:
    domain: str
    name: str
    evidence_priority: EvidencePriority
    search_query_templates: tuple[str, ...] = ()


DEFAULT_LAYER1_TOPICS = [
    Layer1Topic("company", "公司基本信息", "bp_first"),
    Layer1Topic("company", "产品与服务", "bp_first"),
    Layer1Topic(
        "company",
        "核心技术与技术壁垒",
        "balanced",
        (
            "{company} {industry} 核心技术 专利 技术壁垒",
            "{industry} 技术路线 关键指标 成熟度",
        ),
    ),
    Layer1Topic(
        "company",
        "商业模式与商业化进展",
        "balanced",
        (
            "{company} 商业模式 客户 收入 订单",
            "{industry} 商业模式 客户认证 供应链",
        ),
    ),
    Layer1Topic(
        "company",
        "股权结构与融资计划",
        "bp_first",
        (
            "{company} 融资 估值 股东 股权",
        ),
    ),
    Layer1Topic(
        "company",
        "知识产权与资质认证",
        "balanced",
        (
            "{company} 专利 知识产权 资质 认证",
            "{company} 高新技术企业 专精特新",
        ),
    ),
    Layer1Topic(
        "company",
        "业绩表现与发展规划",
        "balanced",
        (
            "{company} 营收 收入 业绩 发展规划",
            "{industry} 企业 营收 增长 规划",
        ),
    ),
    Layer1Topic("company", "团队与资源匹配度", "bp_first", ("{company} 创始人 团队 履历",)),
    Layer1Topic(
        "industry",
        "行业阶段与市场空间",
        "external_first",
        (
            "{industry} 行业 阶段 市场规模 增长",
            "{industry} 产业链 上游 下游 应用场景",
        ),
    ),
    Layer1Topic(
        "industry",
        "国内外发展现状",
        "external_first",
        (
            "{industry} 海外 发展现状 主要企业",
            "{industry} 国内 发展现状 国产替代",
        ),
    ),
    Layer1Topic(
        "industry",
        "市场规模与增长测算",
        "external_first",
        (
            "{industry} 国内 市场规模 增速",
            "{industry} 全球 市场规模 CAGR",
        ),
    ),
    Layer1Topic(
        "industry",
        "竞争格局与替代方案",
        "external_first",
        (
            "{industry} 竞争格局 主要厂商",
            "{industry} 替代方案 技术路线 对比",
        ),
    ),
    Layer1Topic(
        "industry",
        "政策环境与监管约束",
        "external_first",
        (
            "{industry} 政策 监管 产业政策",
            "{industry} 认证 准入 合规 风险",
        ),
    ),
]


class Layer1Researcher:
    """Lightweight layer1 researcher combining BP claims and external evidence."""

    def __init__(
        self,
        search_client: SearchClient,
        topics: list[Layer1Topic] | None = None,
        evidence_normalizer: EvidenceNormalizer | None = None,
        synthesizer: Layer1Synthesizer | None = None,
        tracer: Tracer | None = None,
    ) -> None:
        self.search_client = search_client
        self.topics = topics or DEFAULT_LAYER1_TOPICS
        self.evidence_normalizer = evidence_normalizer or EvidenceNormalizer()
        self.synthesizer = synthesizer or Layer1Synthesizer()
        self.tracer = tracer or NullTracer()

    def run(self, claims: BPClaims) -> list[Layer1ResearchItem]:
        items: list[Layer1ResearchItem] = []
        company = claims.company_name or "未知公司"
        industry = claims.industry or "未知行业"
        for topic in self.topics:
            with self.tracer.step(f"layer1 topic: {topic.name}"):
                external_evidence = self._search_topic(topic, company, industry)
                self.tracer.log(
                    f"[layer1] evidence topic={topic.name} bp={len(_bp_evidence_for_topic(topic.name, claims))} "
                    f"external={len(external_evidence)}"
                )
            bp_evidence = _bp_evidence_for_topic(topic.name, claims)
            evidence_groups = self.evidence_normalizer.normalize(
                topic.name,
                bp_evidence,
                external_evidence,
            )
            synthesis_result = self.synthesizer.synthesize(topic, evidence_groups)
            items.append(
                Layer1ResearchItem(
                    domain=topic.domain,  # type: ignore[arg-type]
                    topic=topic.name,
                    evidence_priority=topic.evidence_priority,
                    bp_claims=bp_evidence,
                    external_evidence=external_evidence,
                    synthesis=synthesis_result.synthesis,
                    confidence=synthesis_result.confidence,
                    evidence_groups=_merge_group_details(
                        evidence_groups,
                        synthesis_result.evidence_groups,
                    ),
                    information_summary=synthesis_result.information_summary,
                    key_risks=synthesis_result.key_risks,
                    open_questions=synthesis_result.open_questions,
                )
            )
        return items

    def _search_topic(
        self,
        topic: Layer1Topic,
        company: str,
        industry: str,
    ) -> list[EvidenceItem]:
        evidence: list[EvidenceItem] = []
        seen: set[tuple[str | None, str]] = set()
        for template in topic.search_query_templates:
            query_text = template.format(company=company, industry=industry)
            for item in self.search_client.search(
                SearchQuery(query=query_text, purpose=topic.name)
            ):
                key = (item.url, item.title)
                if key in seen:
                    continue
                seen.add(key)
                evidence.append(item)
        return evidence


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
        if claims.product_summary:
            evidence.append(
                EvidenceItem(
                    source_type="bp",
                    title="产品概述",
                    content=claims.product_summary,
                )
            )
        claim_groups = []
    elif topic == "核心技术与技术壁垒":
        claim_groups = [claims.technology_claims]
    elif topic == "商业模式与商业化进展":
        claim_groups = [claims.business_model_claims, claims.traction_claims, claims.financial_claims]
    elif topic == "股权结构与融资计划":
        claim_groups = [claims.fundraising_claims]
    elif topic == "知识产权与资质认证":
        claim_groups = [claims.technology_claims]
    elif topic == "业绩表现与发展规划":
        claim_groups = [claims.financial_claims, claims.traction_claims]
    elif topic == "团队与资源匹配度":
        claim_groups = [claims.team_claims]
    elif topic == "行业阶段与市场空间":
        claim_groups = [claims.market_claims]
    elif topic == "国内外发展现状":
        claim_groups = [claims.market_claims]
    elif topic == "市场规模与增长测算":
        claim_groups = [claims.market_claims, claims.financial_claims]
    elif topic == "竞争格局与替代方案":
        claim_groups = []
    elif topic == "政策环境与监管约束":
        claim_groups = [claims.risk_disclosures]
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


def _merge_group_details(
    evidence_groups,
    synthesized_groups,
):
    synthesized_by_aspect = {group.aspect: group for group in synthesized_groups}
    merged = []
    for group in evidence_groups:
        synthesized = synthesized_by_aspect.get(group.aspect)
        if synthesized:
            merged.append(
                type(group)(
                    aspect=group.aspect,
                    bp_claims=group.bp_claims,
                    external_evidence=group.external_evidence,
                    summary=synthesized.summary,
                    conflicts=synthesized.conflicts,
                    open_questions=synthesized.open_questions,
                )
            )
        else:
            merged.append(group)
    return merged
