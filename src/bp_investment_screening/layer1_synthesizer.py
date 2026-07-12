"""LLM-backed Layer1 topic synthesis."""

from __future__ import annotations

import json
import re
from typing import Protocol

from bp_investment_screening.llm import LLMClient
from bp_investment_screening.schemas import (
    Confidence,
    EvidenceGroup,
    TopicInformationSummary,
)
from bp_investment_screening.tracing import NullTracer, Tracer


SYSTEM_PROMPT = """你是投资机构的 Layer1 基础研究分析师。你必须区分 BP 主张、外部证据和综合判断。"""


class TopicLike(Protocol):
    name: str
    evidence_priority: str


class Layer1SynthesisResult:
    def __init__(
        self,
        information_summary: TopicInformationSummary,
        synthesis: str,
        confidence: Confidence,
        key_risks: list[str],
        open_questions: list[str],
        evidence_groups: list[EvidenceGroup],
    ) -> None:
        self.information_summary = information_summary
        self.synthesis = synthesis
        self.confidence = confidence
        self.key_risks = key_risks
        self.open_questions = open_questions
        self.evidence_groups = evidence_groups


class Layer1Synthesizer:
    def __init__(self, llm_client: LLMClient | None = None, tracer: Tracer | None = None) -> None:
        self.llm_client = llm_client or LLMClient()
        self.tracer = tracer or NullTracer()

    def synthesize(
        self,
        topic: TopicLike,
        evidence_groups: list[EvidenceGroup],
    ) -> Layer1SynthesisResult:
        with self.tracer.step(f"layer1 synthesis: {topic.name}"):
            result = self.llm_client.complete(
                SYSTEM_PROMPT,
                _build_prompt(topic, evidence_groups),
            )
        if result:
            parsed = _parse_result(result.text)
            if parsed:
                self.tracer.log(f"[layer1] synthesis parsed topic={topic.name}")
                return parsed
            self.tracer.log(f"[layer1] synthesis parse failed topic={topic.name}")
        self.tracer.log(f"[layer1] synthesis fallback topic={topic.name}")
        return _fallback_result(topic, evidence_groups)


def _build_prompt(topic: TopicLike, evidence_groups: list[EvidenceGroup]) -> str:
    groups_text = "\n\n".join(_group_text(group) for group in evidence_groups)
    return f"""
当前 topic：{topic.name}
证据优先级：{topic.evidence_priority}

证据分组：
{groups_text}

请输出 JSON，不要输出 Markdown。要求：
1. information_summary 是信息整合压缩，不是投资判断。
2. bp_claims_summary 只总结 BP 主张，并标注其仍待验证。
3. external_evidence_summary 只总结外部证据；没有外部证据时明确说明缺失。
4. integrated_summary 对 BP 与外部证据做归并，说明能合并出的信息图景、冲突和缺口。
5. synthesis 才输出研究判断，不能把 BP 乐观表述直接当事实。
6. confidence 只能是 low、medium、high。

JSON 格式：
{{
  "information_summary": {{
    "bp_claims_summary": "...",
    "external_evidence_summary": "...",
    "integrated_summary": "..."
  }},
  "evidence_group_summaries": [
    {{
      "aspect": "...",
      "summary": "...",
      "conflicts": ["..."],
      "open_questions": ["..."]
    }}
  ],
  "synthesis": "...",
  "confidence": "low",
  "key_risks": ["..."],
  "open_questions": ["..."]
}}
""".strip()


def _group_text(group: EvidenceGroup) -> str:
    bp_lines = _evidence_lines(group.bp_claims)
    external_lines = _evidence_lines(group.external_evidence)
    return f"""
【{group.aspect}】
BP 主张：
{bp_lines}
外部证据：
{external_lines}
""".strip()


def _evidence_lines(items, limit: int = 8) -> str:
    if not items:
        return "- 暂无"
    lines = []
    for item in items[:limit]:
        source = f"BP第{item.source_page}页" if item.source_page else item.source_type
        url = f" {item.url}" if item.url else ""
        lines.append(f"- [{source}] {item.title}：{item.content}{url}")
    return "\n".join(lines)


def _parse_result(text: str) -> Layer1SynthesisResult | None:
    data = _parse_json(text)
    if not data:
        return None
    summary = data.get("information_summary") or {}
    information_summary = TopicInformationSummary(
        bp_claims_summary=str(summary.get("bp_claims_summary") or "").strip(),
        external_evidence_summary=str(summary.get("external_evidence_summary") or "").strip(),
        integrated_summary=str(summary.get("integrated_summary") or "").strip(),
    )
    confidence = _normalize_confidence(data.get("confidence"))
    evidence_groups = _parse_group_summaries(data.get("evidence_group_summaries"))
    return Layer1SynthesisResult(
        information_summary=information_summary,
        synthesis=str(data.get("synthesis") or "").strip(),
        confidence=confidence,
        key_risks=_string_list(data.get("key_risks")),
        open_questions=_string_list(data.get("open_questions")),
        evidence_groups=evidence_groups,
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


def _parse_group_summaries(value) -> list[EvidenceGroup]:
    if not isinstance(value, list):
        return []
    groups: list[EvidenceGroup] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        aspect = str(item.get("aspect") or "").strip()
        if not aspect:
            continue
        groups.append(
            EvidenceGroup(
                aspect=aspect,
                summary=str(item.get("summary") or "").strip(),
                conflicts=_string_list(item.get("conflicts")),
                open_questions=_string_list(item.get("open_questions")),
            )
        )
    return groups


def _string_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _normalize_confidence(value) -> Confidence:
    text = str(value or "low").lower()
    if re.search(r"high|高", text):
        return "high"
    if re.search(r"medium|中", text):
        return "medium"
    return "low"


def _fallback_result(
    topic: TopicLike,
    evidence_groups: list[EvidenceGroup],
) -> Layer1SynthesisResult:
    bp_count = sum(len(group.bp_claims) for group in evidence_groups)
    external_count = sum(len(group.external_evidence) for group in evidence_groups)
    information_summary = TopicInformationSummary(
        bp_claims_summary=f"BP 在“{topic.name}”下归集到 {bp_count} 条项目方主张，均需后续核验。",
        external_evidence_summary=f"当前归集到 {external_count} 条外部证据。",
        integrated_summary=(
            f"当前信息显示“{topic.name}”已有初步资料，但证据压缩仍以结构化归集为主，"
            "需要 LLM 或人工研究进一步形成稳定判断。"
        ),
    )
    open_questions = []
    if topic.evidence_priority == "external_first" and external_count == 0:
        open_questions.append(f"{topic.name}缺少外部证据，需要联网搜索或人工补充。")
    return Layer1SynthesisResult(
        information_summary=information_summary,
        synthesis=(
            f"{topic.name}已完成证据归类：BP 证据 {bp_count} 条、外部证据 {external_count} 条。"
            "当前为 fallback 结论，正式判断需 LLM synthesis 或人工复核。"
        ),
        confidence="low" if external_count == 0 else "medium",
        key_risks=["BP 主张尚未充分外部核验。"] if bp_count else [],
        open_questions=open_questions,
        evidence_groups=evidence_groups,
    )
