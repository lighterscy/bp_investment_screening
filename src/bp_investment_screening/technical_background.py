"""Generate educational technical background sections.

The technical background chapter is not a company progress review. It extracts
the relevant technology category from the project and explains that technology
itself for a reader with little prior knowledge.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from bp_investment_screening.llm import LLMClient
from bp_investment_screening.schemas import EvidenceItem, InvestmentMemo, Layer1ResearchItem


TECHNICAL_TOPIC = "核心技术与技术壁垒"

FORBIDDEN_COMPANY_WORDS = (
    "公司",
    "项目",
    "客户",
    "订单",
    "融资",
    "营收",
    "收入",
    "量产",
    "供应",
    "团队",
    "专精特新",
)

SYSTEM_PROMPT = (
    "你是投资机构的技术科普研究员，擅长把陌生技术门类讲给零基础投资人。"
    "你的任务是解释技术背景本身，而不是评价某家公司。"
)


@dataclass(frozen=True, slots=True)
class TechnicalBackgroundSection:
    heading: str
    body: str


def generate_technical_background_sections(
    memo: InvestmentMemo,
    llm_client: LLMClient | None = None,
) -> list[TechnicalBackgroundSection]:
    client = llm_client or LLMClient()
    result = client.complete(SYSTEM_PROMPT, _build_user_prompt(memo))
    if result:
        sections = _parse_sections(result.text)
        if sections:
            return _normalize_sections(sections)
    return _fallback_sections(memo)


def generate_technical_background_headings(
    memo: InvestmentMemo,
    llm_client: LLMClient | None = None,
) -> list[str]:
    return [
        section.heading
        for section in generate_technical_background_sections(memo, llm_client)
    ]


def _build_user_prompt(memo: InvestmentMemo) -> str:
    technical_item = _find_technical_item(memo)
    technical_terms = _technical_terms_context(technical_item)
    return f"""
行业初步归类：{memo.industry or "未知"}

技术线索：
{technical_terms}

任务：
请写“技术背景”章节。注意，这一章只做技术科普，用来解释项目涉及的技术门类本身，理论上应当与具体公司无关。

你需要先从“技术线索”中识别最核心的技术门类。例如线索里出现 YAG 晶体、浓度渐变晶体、键合晶体、固体激光器，就应围绕“YAG/激光晶体及其在固体激光器中的作用”展开，而不是写公司是否量产、客户是谁、技术壁垒强不强。

写作目标：
1. 让一个对该技术 0 基础的投资人理解这门技术是什么；
2. 先讲上位技术体系，再讲核心部件/材料，再讲关键原理；
3. 再讲传统方案为什么会遇到瓶颈；
4. 最后讲该技术门类为什么会演进出新的技术路线。

绝对不要写：
- 具体公司名称、项目名称；
- 公司进展、客户、订单、营收、融资、团队、量产、供应情况；
- “本项目”“该公司”“项目方”等表述；
- 投资判断、可信度、风险、DD 问题。

输出 JSON，不要输出 Markdown：
{{
  "technology_category": "识别出的技术门类",
  "sections": [
    {{
      "heading": "1、上位技术体系与基本概念",
      "body": "面向零基础读者的技术科普正文，120-220字。"
    }}
  ]
}}

要求：
- 生成 4-6 个 sections；
- heading 必须编号为 `1、...`；
- body 只讲技术背景知识，不讲公司；
- 如果证据不足，写通用但准确的技术科普，不要编造公司事实。
""".strip()


def _find_technical_item(memo: InvestmentMemo) -> Layer1ResearchItem | None:
    for item in memo.layer1_items:
        if item.topic == TECHNICAL_TOPIC:
            return item
    return None


def _technical_terms_context(item: Layer1ResearchItem | None) -> str:
    if item is None:
        return "未找到核心技术节点。"

    evidence = item.bp_claims + item.external_evidence
    lines = []
    for evidence_item in evidence[:16]:
        if _looks_like_company_status(evidence_item.content):
            content = _strip_status_language(evidence_item.content)
        else:
            content = evidence_item.content
        lines.append(f"- {evidence_item.title}：{content}")
    return "\n".join(lines) if lines else "暂无明确技术线索。"


def _looks_like_company_status(text: str) -> bool:
    return any(word in text for word in FORBIDDEN_COMPANY_WORDS)


def _strip_status_language(text: str) -> str:
    sentences = re.split(r"[。；;\n]", text)
    technical_sentences = [
        sentence.strip()
        for sentence in sentences
        if sentence.strip()
        and not any(word in sentence for word in ("客户", "订单", "融资", "营收", "收入", "团队"))
    ]
    return "；".join(technical_sentences[:3]) or text[:120]


def _parse_sections(text: str) -> list[TechnicalBackgroundSection]:
    json_text = _extract_json_object(text)
    if not json_text:
        return []
    try:
        data = json.loads(json_text)
    except json.JSONDecodeError:
        return []
    sections = data.get("sections")
    if not isinstance(sections, list):
        return []
    parsed: list[TechnicalBackgroundSection] = []
    for item in sections:
        if not isinstance(item, dict):
            continue
        heading = str(item.get("heading") or "").strip()
        body = str(item.get("body") or "").strip()
        if heading and body:
            parsed.append(TechnicalBackgroundSection(heading=heading, body=body))
    return parsed


def _extract_json_object(text: str) -> str | None:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    return text[start : end + 1]


def _normalize_sections(
    sections: list[TechnicalBackgroundSection],
) -> list[TechnicalBackgroundSection]:
    normalized: list[TechnicalBackgroundSection] = []
    for index, section in enumerate(sections[:6], start=1):
        heading_text = re.sub(r"^\d+[、.．]\s*", "", section.heading).strip()
        body = _remove_company_framing(section.body)
        if heading_text and body:
            normalized.append(
                TechnicalBackgroundSection(
                    heading=f"{index}、{heading_text}",
                    body=body,
                )
            )
    return normalized


def _remove_company_framing(text: str) -> str:
    replacements = {
        "本项目": "该技术路线",
        "该项目": "该技术路线",
        "项目方": "相关技术主体",
        "该公司": "相关技术主体",
    }
    cleaned = text
    for source, target in replacements.items():
        cleaned = cleaned.replace(source, target)
    return cleaned


def _fallback_sections(memo: InvestmentMemo) -> list[TechnicalBackgroundSection]:
    industry = memo.industry or "相关技术"
    return [
        TechnicalBackgroundSection(
            heading=f"1、{industry}所属的上位技术体系",
            body=(
                f"{industry}需要放在其上位技术体系中理解。对于硬科技项目，技术背景首先要回答其服务的"
                "应用场景、所在产业链环节以及关键性能指标，而不是直接讨论某一主体的商业化进展。"
            ),
        ),
        TechnicalBackgroundSection(
            heading="2、核心材料或部件的基本作用",
            body=(
                "许多高端装备的性能并不只由整机设计决定，核心材料、关键元件和加工工艺往往共同决定"
                "系统效率、稳定性、寿命和一致性。理解这类项目时，需要先弄清核心部件在系统中的功能位置。"
            ),
        ),
        TechnicalBackgroundSection(
            heading="3、传统技术路线的主要约束",
            body=(
                "传统方案通常会在效率、散热、可靠性、加工精度或规模化一致性上遇到约束。技术演进的"
                "主要动力，往往来自下游应用对更高功率、更高精度、更长寿命或更低成本的持续要求。"
            ),
        ),
        TechnicalBackgroundSection(
            heading="4、新技术路线的演进逻辑",
            body=(
                "新的技术路线通常不是凭空出现，而是在传统方案接近性能边界后，对材料结构、器件设计、"
                "制造工艺或系统集成方式进行重新组合，以解决原有路线中的关键瓶颈。"
            ),
        ),
    ]
