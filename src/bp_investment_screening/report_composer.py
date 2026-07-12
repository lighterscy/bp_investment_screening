"""Compose Word report sections from Layer1 research items."""

from __future__ import annotations

import json

from bp_investment_screening.llm import LLMClient
from bp_investment_screening.schemas import InvestmentMemo, Layer1ResearchItem


SECTION_TOPIC_MAP = {
    "公司基础概况": ("公司基本信息",),
    "股权结构与融资计划": ("股权结构与融资计划",),
    "核心团队情况": ("团队与资源匹配度",),
    "技术情况": ("核心技术与技术壁垒",),
    "产品情况": ("产品与服务",),
    "知产情况": ("知识产权与资质认证", "核心技术与技术壁垒"),
    "业务与市场布局": ("商业模式与商业化进展",),
    "业绩及发展规划": ("业绩表现与发展规划",),
    "行业核心定义": ("行业阶段与市场空间",),
    "海外发展现状": ("国内外发展现状",),
    "国内发展现状": ("国内外发展现状",),
    "技术突破与核心痛点": ("核心技术与技术壁垒", "行业阶段与市场空间"),
    "国内市场规模": ("市场规模与增长测算", "行业阶段与市场空间"),
    "全球市场规模": ("市场规模与增长测算", "行业阶段与市场空间"),
    "行业主要竞争对手": ("竞争格局与替代方案",),
}

SYSTEM_PROMPT = """你是投资机构的研判报告撰写助手。请基于 Layer1 结果生成正式报告段落。"""


class ReportSectionComposer:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client or LLMClient()

    def compose(
        self,
        memo: InvestmentMemo,
        section_name: str,
        fallback: str,
        use_llm: bool = True,
    ) -> str:
        items = _items_for_section(memo, section_name)
        if not items:
            return fallback
        if use_llm and self.llm_client.is_configured:
            result = self.llm_client.complete(
                SYSTEM_PROMPT,
                _build_prompt(memo, section_name, items),
            )
            parsed = _parse_body(result.text if result else "")
            if parsed:
                return parsed
        return _compose_without_llm(items, fallback)


def _items_for_section(
    memo: InvestmentMemo,
    section_name: str,
) -> list[Layer1ResearchItem]:
    topics = SECTION_TOPIC_MAP.get(section_name, ())
    return [item for item in memo.layer1_items if item.topic in topics]


def _build_prompt(
    memo: InvestmentMemo,
    section_name: str,
    items: list[Layer1ResearchItem],
) -> str:
    context = "\n\n".join(_item_context(item) for item in items)
    return f"""
项目：{memo.project_name}
章节：{section_name}

Layer1 信息：
{context}

任务：
请为 Word 初步研判报告的“{section_name}”章节写一段正式正文。

要求：
- 只使用给定 Layer1 信息，不要编造。
- 区分 BP 主张和外部证据。
- 如果证据不足，要明确写“需进一步核验”，但不要简单写“待补充”。
- 文字风格应适合正式研判报告，克制、准确、可追溯。
- 120-260 字。

输出 JSON：
{{"body": "..."}}
""".strip()


def _item_context(item: Layer1ResearchItem) -> str:
    parts = [
        f"topic：{item.topic}",
        f"confidence：{item.confidence}",
    ]
    if item.information_summary:
        parts.extend(
            [
                f"BP主张摘要：{item.information_summary.bp_claims_summary}",
                f"外部证据摘要：{item.information_summary.external_evidence_summary}",
                f"信息整合：{item.information_summary.integrated_summary}",
            ]
        )
    parts.append(f"综合判断：{item.synthesis}")
    if item.key_risks:
        parts.append("关键风险：" + "；".join(item.key_risks[:5]))
    if item.open_questions:
        parts.append("待验证问题：" + "；".join(item.open_questions[:5]))
    return "\n".join(parts)


def _parse_body(text: str) -> str | None:
    if not text:
        return None
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return text.strip()[:1000]
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    body = data.get("body")
    return str(body).strip() if body else None


def _compose_without_llm(items: list[Layer1ResearchItem], fallback: str) -> str:
    sentences: list[str] = []
    for item in items:
        if item.information_summary and item.information_summary.integrated_summary:
            sentences.append(item.information_summary.integrated_summary)
        elif item.synthesis:
            sentences.append(item.synthesis)
    if sentences:
        return "".join(sentences[:2])
    return fallback
