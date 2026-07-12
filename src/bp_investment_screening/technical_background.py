"""Generate project-specific headings for the technical background section."""

from __future__ import annotations

import json
import re

from bp_investment_screening.llm import LLMClient
from bp_investment_screening.schemas import EvidenceItem, InvestmentMemo, Layer1ResearchItem


TECHNICAL_TOPIC = "核心技术与技术壁垒"

SYSTEM_PROMPT = """你是投资机构的技术研究分析师，擅长把陌生技术拆成零基础读者可以逐步理解的学习路径。"""


def generate_technical_background_headings(
    memo: InvestmentMemo,
    llm_client: LLMClient | None = None,
) -> list[str]:
    client = llm_client or LLMClient()
    result = client.complete(SYSTEM_PROMPT, _build_user_prompt(memo))
    if result:
        headings = _parse_headings(result.text)
        if headings:
            return _normalize_numbering(headings)
    return _fallback_headings(memo)


def _build_user_prompt(memo: InvestmentMemo) -> str:
    technical_item = _find_technical_item(memo)
    technical_context = _technical_context(technical_item)
    return f"""
项目名称：{memo.project_name}
行业：{memo.industry or "未知"}

技术节点：
{technical_context}

任务：
请只基于上述“技术节点”生成“技术背景”部分的子标题。目标不是直接宣传项目技术，而是让一个对该技术门类零基础的投资人，能够按循序渐进的顺序理解：
1. 这个技术门类属于什么更大的技术/产业体系；
2. 该体系当前为什么重要，发展到什么阶段；
3. 现有技术路线或传统方案卡在哪里；
4. 项目所处技术路线为什么被提出；
5. 最后再自然引出本项目的技术切入点。

类比：如果项目是 ViT 模型，不要第一节就写 ViT，而应先写“深度学习与视觉任务基础”“视觉模型与语言模型的发展差异”“为什么语言模型已显现 scaling law 而视觉模型仍受限制”“ViT 如何把 Transformer 引入视觉任务”。

要求：
- 生成 4-6 个子标题。
- 标题要像学习路径，逐层递进，不要堆砌营销词。
- 不要编造具体技术指标、客户、收入或市场规模。
- 每个标题使用中文短句，格式为 `1、标题`。
- 输出 JSON，格式为 {{"headings": ["1、...", "2、..."]}}。
""".strip()


def _find_technical_item(memo: InvestmentMemo) -> Layer1ResearchItem | None:
    for item in memo.layer1_items:
        if item.topic == TECHNICAL_TOPIC:
            return item
    return None


def _technical_context(item: Layer1ResearchItem | None) -> str:
    if item is None:
        return "未找到核心技术与技术壁垒节点。"
    lines = [
        f"topic：{item.topic}",
        f"evidence_priority：{item.evidence_priority}",
        f"synthesis：{item.synthesis}",
        "BP 技术主张：",
    ]
    lines.extend(_evidence_lines(item.bp_claims))
    lines.append("外部技术证据：")
    lines.extend(_evidence_lines(item.external_evidence))
    if item.open_questions:
        lines.append("待验证问题：" + "；".join(item.open_questions))
    return "\n".join(lines)


def _evidence_lines(items: list[EvidenceItem], limit: int = 8) -> list[str]:
    if not items:
        return ["- 暂无"]
    lines: list[str] = []
    for evidence in items[:limit]:
        source = f"BP第{evidence.source_page}页" if evidence.source_page else evidence.source_type
        lines.append(f"- [{source}] {evidence.title}：{evidence.content}")
    return lines


def _parse_headings(text: str) -> list[str]:
    json_text = _extract_json_object(text)
    if json_text:
        try:
            data = json.loads(json_text)
        except json.JSONDecodeError:
            data = {}
        headings = data.get("headings")
        if isinstance(headings, list):
            return [str(item).strip() for item in headings if str(item).strip()]

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return [
        line
        for line in lines
        if re.match(r"^\d+[、.．]", line)
    ]


def _extract_json_object(text: str) -> str | None:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    return text[start : end + 1]


def _normalize_numbering(headings: list[str]) -> list[str]:
    normalized: list[str] = []
    for index, heading in enumerate(headings[:5], start=1):
        cleaned = re.sub(r"^\d+[、.．]\s*", "", heading).strip()
        if cleaned:
            normalized.append(f"{index}、{cleaned}")
    return normalized


def _fallback_headings(memo: InvestmentMemo) -> list[str]:
    industry = memo.industry or "所属行业"
    return [
        f"1、{industry}的产业链位置与核心应用场景",
        "2、项目核心产品涉及的关键技术原理",
        "3、现有技术路线的主要痛点与约束",
        "4、项目方案的技术切入点与验证重点",
    ]
