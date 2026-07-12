"""Layer2 investment screening analysis."""

from __future__ import annotations

import json
import re
from pathlib import Path

from bp_investment_screening.llm import LLMClient
from bp_investment_screening.schemas import (
    BPClaims,
    Confidence,
    InvestmentRecommendation,
    Layer1ResearchItem,
    Recommendation,
)
from bp_investment_screening.tracing import NullTracer, Tracer


SYSTEM_PROMPT = """你是早期/成长期项目投资初筛分析师。你的任务是基于 Layer1 研究结果生成是否值得继续跟进的初步投资判断。"""


class InvestmentAnalyzer:
    """Convert layer1 research into a first-pass investment recommendation."""

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        tracer: Tracer | None = None,
        skill_path: str | Path = "skills/investment_screening.md",
    ) -> None:
        self.llm_client = llm_client or LLMClient()
        self.tracer = tracer or NullTracer()
        self.skill_path = Path(skill_path)

    def run(
        self,
        claims: BPClaims,
        layer1_items: list[Layer1ResearchItem],
    ) -> InvestmentRecommendation:
        with self.tracer.step("layer2 LLM investment screening"):
            result = self.llm_client.complete(
                SYSTEM_PROMPT,
                _build_prompt(claims, layer1_items, _read_skill(self.skill_path)),
            )
        if result:
            parsed = _parse_recommendation(result.text)
            if parsed:
                self.tracer.log("[layer2] recommendation parsed")
                return parsed
            self.tracer.log("[layer2] recommendation parse failed; fallback")
        return _fallback_recommendation(claims, layer1_items)


def _build_prompt(
    claims: BPClaims,
    layer1_items: list[Layer1ResearchItem],
    skill_text: str,
) -> str:
    return f"""
投资初筛 skill：
{skill_text}

项目基础信息：
- 公司/项目名称：{claims.company_name or "未知"}
- 行业：{claims.industry or "未知"}
- 产品概述：{claims.product_summary or "未知"}

Layer1 研究结果：
{_layer1_context(layer1_items)}

任务：
请通读以上所有 Layer1 内容，生成“初步建议”部分所需的正式投资初筛判断。

要求：
- 不要把 BP 主张直接当事实。
- 优势必须是相对可信、可解释的优势，不要写空泛套话。
- 疑问点/短板要服务下一步 DD。
- 初步判断要回答：是否值得继续投入时间跟进，以及为什么。
- 结论可以保守。
- 输出 JSON，不要输出 Markdown。

JSON 格式：
{{
  "recommendation": "建议跟进/谨慎跟进/暂不跟进",
  "confidence": "low/medium/high",
  "one_sentence_view": "一句话初步判断",
  "strengths": ["项目优势1", "项目优势2"],
  "weaknesses": ["核心短板或项目疑问点1", "核心短板或项目疑问点2"],
  "key_risks": ["关键风险1", "关键风险2"],
  "open_questions": ["下一步必须验证的问题1", "下一步必须验证的问题2"],
  "next_steps": ["下一步DD动作1", "下一步DD动作2"]
}}
""".strip()


def _layer1_context(layer1_items: list[Layer1ResearchItem]) -> str:
    chunks = []
    for item in layer1_items:
        chunks.append(
            "\n".join(
                part
                for part in [
                    f"【{item.topic}】",
                    f"证据优先级：{item.evidence_priority}",
                    f"置信度：{item.confidence}",
                    f"BP证据数/外部证据数：{len(item.bp_claims)}/{len(item.external_evidence)}",
                    _summary_text(item),
                    f"综合判断：{item.synthesis}",
                    "关键风险：" + "；".join(item.key_risks[:5]) if item.key_risks else "",
                    "待验证问题：" + "；".join(item.open_questions[:5]) if item.open_questions else "",
                ]
                if part
            )
        )
    return "\n\n".join(chunks)


def _summary_text(item: Layer1ResearchItem) -> str:
    if not item.information_summary:
        return ""
    return "\n".join(
        [
            f"BP主张摘要：{item.information_summary.bp_claims_summary}",
            f"外部证据摘要：{item.information_summary.external_evidence_summary}",
            f"信息整合：{item.information_summary.integrated_summary}",
        ]
    )


def _read_skill(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _parse_recommendation(text: str) -> InvestmentRecommendation | None:
    data = _parse_json(text)
    if not data:
        return None
    return InvestmentRecommendation(
        recommendation=_normalize_recommendation(data.get("recommendation")),
        confidence=_normalize_confidence(data.get("confidence")),
        one_sentence_view=str(data.get("one_sentence_view") or "").strip(),
        strengths=_string_list(data.get("strengths")),
        weaknesses=_string_list(data.get("weaknesses")),
        key_risks=_string_list(data.get("key_risks")),
        open_questions=_string_list(data.get("open_questions")),
        next_steps=_string_list(data.get("next_steps")),
    )


def _parse_json(text: str) -> dict | None:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _normalize_recommendation(value) -> Recommendation:
    text = str(value or "")
    if "暂不" in text:
        return "暂不跟进"
    if "建议跟进" in text and "谨慎" not in text:
        return "建议跟进"
    return "谨慎跟进"


def _normalize_confidence(value) -> Confidence:
    text = str(value or "").lower()
    if re.search(r"high|高", text):
        return "high"
    if re.search(r"medium|中", text):
        return "medium"
    return "low"


def _string_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _fallback_recommendation(
    claims: BPClaims,
    layer1_items: list[Layer1ResearchItem],
) -> InvestmentRecommendation:
    open_questions = [
        question
        for item in layer1_items
        for question in item.open_questions
    ]
    project = claims.company_name or "该项目"
    return InvestmentRecommendation(
        recommendation="谨慎跟进",
        confidence="low",
        one_sentence_view=(
            f"{project}已有 Layer1 资料归集和初步研究结果，但部分关键事实仍需核验，建议以谨慎跟进方式推进。"
        ),
        strengths=[
            "BP 已提供部分项目基础信息，可作为后续访谈和尽调起点。"
        ],
        weaknesses=[
            "当前外部证据和商业化验证信息不足，暂不能形成高置信投资判断。"
        ],
        key_risks=[
            "BP 中市场规模、客户、收入和技术优势等主张可能存在乐观表述。"
        ],
        open_questions=open_questions or [
            "需要补充外部搜索、客户验证、财务材料和竞品对比。"
        ],
        next_steps=[
            "补充客户、订单、收入、股权融资等底层材料。",
            "核验核心技术指标、知识产权权属和量产稳定性。",
            "对主要竞品和替代方案进行访谈或二次搜索验证。",
        ],
    )
