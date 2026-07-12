"""Generate project-specific headings for the technical background section."""

from __future__ import annotations

import json
import re

from bp_investment_screening.llm import LLMClient
from bp_investment_screening.schemas import InvestmentMemo


SYSTEM_PROMPT = """你是投资机构的技术研究分析师。请生成渐进式、项目个性化的技术背景子标题。"""


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
    layer1_summary = "\n".join(
        f"- {item.topic}：{item.synthesis}"
        for item in memo.layer1_items
    )
    return f"""
项目名称：{memo.project_name}
行业：{memo.industry or "未知"}
一句话理解：{memo.recommendation.one_sentence_view}

Layer1 摘要：
{layer1_summary}

请输出 JSON，格式为 {{"headings": ["1、...", "2、..."]}}。
""".strip()


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
