"""Generate educational technical background sections."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from bp_investment_screening.llm import LLMClient
from bp_investment_screening.schemas import InvestmentMemo, Layer1ResearchItem


TECHNICAL_TOPIC = "核心技术与技术壁垒"

TECHNICAL_PATTERNS = (
    "YAG晶体",
    "YAG",
    "激光晶体",
    "固体激光器",
    "增益介质",
    "浓度渐变",
    "键合晶体",
    "板条",
    "高损伤阈值",
    "镀膜",
    "超精密光学元件",
    "光学元件",
    "InGaAs",
    "探测器",
    "激光测距",
    "激光雷达",
    "ToF",
    "FMCW",
    "调Q晶体",
    "热透镜",
)

STATUS_WORDS = (
    "客户",
    "订单",
    "融资",
    "营收",
    "收入",
    "团队",
    "估值",
    "量产",
    "列装",
    "自研",
    "供应",
    "批量",
    "唯一",
    "第一梯队",
    "定型",
)

SYSTEM_PROMPT = (
    "你是投资机构的技术科普研究员。你擅长根据一组技术关键词，"
    "把技术门类、基础原理、关键指标和演进逻辑讲给零基础投资人。"
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
    profile = _build_technology_profile(memo, technical_item)
    return f"""
技术画像：
{profile}

任务：
请根据“技术画像”写 Word 报告里的“技术背景”章节。这个章节是技术科普：把技术门类本身讲明白。

写作目标：
1. 先解释这组技术属于什么上位系统；
2. 解释核心材料/部件在系统中承担什么功能；
3. 解释关键物理原理、典型结构或工艺；
4. 解释评价这类技术好坏的关键指标；
5. 解释传统方案卡在哪里，以及新路线为什么出现。

写作要求：
- 每段必须有具体技术信息，不能写“需要理解上位体系”“关键元件很重要”这种空话。
- 可使用必要英文缩写和括号解释，例如 YAG、ToF、FMCW、InGaAs。
- 不需要评价任何主体的进展，直接讲技术本身即可。
- 不要写“列装、量产、客户、订单、自研、供应、第一梯队、唯一”等主体状态词。
- 不要输出投资判断、风险、DD 问题。

输出 JSON，不要输出 Markdown：
{{
  "technology_category": "YAG/激光晶体及其在固体激光器中的作用",
  "sections": [
    {{
      "heading": "1、固体激光器与激光晶体的关系",
      "body": "技术科普正文，150-260字。"
    }}
  ]
}}

要求：
- 生成 4-6 个 sections；
- heading 必须编号为 `1、...`；
- body 必须讲具体技术知识；
- 如果技术画像中出现 YAG、浓度渐变、键合晶体、镀膜等词，应优先围绕这些技术展开。
""".strip()


def _find_technical_item(memo: InvestmentMemo) -> Layer1ResearchItem | None:
    for item in memo.layer1_items:
        if item.topic == TECHNICAL_TOPIC:
            return item
    return None


def _build_technology_profile(
    memo: InvestmentMemo,
    item: Layer1ResearchItem | None,
) -> str:
    if item is None:
        return f"行业：{memo.industry or '未知'}\n核心技术关键词：暂无明确技术关键词。"

    evidence_text = "\n".join(
        evidence.content
        for evidence in [*item.bp_claims, *item.external_evidence]
    )
    terms = _extract_technical_terms(evidence_text)
    raw_clues = _extract_technical_clues(evidence_text)
    lines = [
        f"行业：{memo.industry or '未知'}",
        "核心技术关键词：" + ("、".join(terms) if terms else "暂无明确技术关键词"),
        "建议科普重点：" + _suggested_focus(terms, memo.industry),
    ]
    return "\n".join(lines)


def _extract_technical_terms(text: str) -> list[str]:
    terms = []
    normalized = text.replace(" ", "")
    for pattern in TECHNICAL_PATTERNS:
        if pattern.lower() in normalized.lower() and pattern not in terms:
            terms.append(pattern)
    return terms[:12]


def _extract_technical_clues(text: str) -> list[str]:
    sentences = [
        sentence.strip()
        for sentence in re.split(r"[。；;\n]", text)
        if sentence.strip()
    ]
    clues = []
    for sentence in sentences:
        if any(pattern.lower() in sentence.lower() for pattern in TECHNICAL_PATTERNS):
            cleaned = _remove_business_status(sentence)
            if cleaned and cleaned not in clues:
                clues.append(cleaned)
    return clues


def _remove_business_status(text: str) -> str:
    if any(word in text for word in STATUS_WORDS):
        return ""
    return text[:180]


def _suggested_focus(terms: list[str], industry: str | None) -> str:
    joined = "、".join(terms)
    if any(term in joined for term in ("YAG", "激光晶体", "固体激光器")):
        return (
            "固体激光器如何产生激光；YAG 晶体作为增益介质的作用；Nd:YAG 等掺杂晶体的能级跃迁；"
            "热透镜、热致双折射、损伤阈值等关键瓶颈；浓度渐变、键合晶体、板条结构和高损伤阈值镀膜的技术逻辑。"
        )
    if any(term in joined for term in ("InGaAs", "探测器", "激光测距")):
        return (
            "激光测距的 ToF/FMCW 原理；发射端激光器、接收端探测器和时序电路的分工；"
            "InGaAs 探测器的响应波段、噪声、带宽和弱信号检测能力。"
        )
    return f"{industry or '相关技术'}的上位技术体系、核心部件、基础原理、关键指标、传统瓶颈和技术演进。"


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
        body = _remove_company_framing(_remove_status_sentences(section.body))
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


def _remove_status_sentences(text: str) -> str:
    sentences = re.split(r"(?<=[。！？])", text)
    kept = [
        sentence
        for sentence in sentences
        if sentence.strip()
        and not any(word in sentence for word in STATUS_WORDS)
    ]
    return "".join(kept).strip() or text


def _fallback_sections(memo: InvestmentMemo) -> list[TechnicalBackgroundSection]:
    technical_item = _find_technical_item(memo)
    profile_text = _build_technology_profile(memo, technical_item)
    if "YAG" in profile_text or "激光晶体" in profile_text or "固体激光器" in profile_text:
        return _yag_laser_crystal_sections()
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


def _yag_laser_crystal_sections() -> list[TechnicalBackgroundSection]:
    return [
        TechnicalBackgroundSection(
            heading="1、固体激光器与增益介质",
            body=(
                "固体激光器可以理解为把电能或泵浦光转化为高方向性激光的装置。其核心不是普通玻璃，"
                "而是能够储存并释放光能的“增益介质”。YAG 晶体即钇铝石榴石晶体，常作为激光基质，"
                "通过掺入钕、镱、铒等稀土离子获得不同波长的激光输出。"
            ),
        ),
        TechnicalBackgroundSection(
            heading="2、YAG晶体为什么适合做激光材料",
            body=(
                "YAG 晶体的优势在于机械强度、热导率和光学稳定性较好，能承受较高泵浦功率，适合用于"
                "测距、照射、加工、医疗和科研等场景。评价这类晶体时，通常要看掺杂浓度均匀性、吸收效率、"
                "散热能力、光束质量、损伤阈值以及长期工作稳定性。"
            ),
        ),
        TechnicalBackgroundSection(
            heading="3、热效应是高功率激光晶体的核心瓶颈",
            body=(
                "当泵浦能量进入晶体后，并非全部转化为激光，剩余能量会形成热。热量分布不均会导致热透镜、"
                "热致双折射、端面形变甚至开裂，进而降低光束质量和输出稳定性。因此，高功率固体激光器的"
                "材料设计，本质上是在光能转换效率和热管理之间寻找平衡。"
            ),
        ),
        TechnicalBackgroundSection(
            heading="4、浓度渐变与键合晶体的技术逻辑",
            body=(
                "传统均匀掺杂晶体在不同位置吸收泵浦光的强度不同，容易造成局部过热。浓度渐变晶体通过让"
                "掺杂浓度沿轴向或径向变化，使增益分布更接近泵浦光衰减规律。键合晶体则把不同功能段拼接，"
                "例如用未掺杂端帽帮助散热、降低端面损伤，从结构上改善热管理。"
            ),
        ),
        TechnicalBackgroundSection(
            heading="5、高损伤阈值镀膜与超精密加工",
            body=(
                "激光晶体还需要端面抛光和光学镀膜。高损伤阈值镀膜要求膜层在高能量密度下不击穿、不脱落，"
                "并保持反射率、透过率和面形精度稳定。对于大口径或高功率应用，抛光粗糙度、膜层均匀性、"
                "杂质控制和洁净工艺都会直接影响器件寿命。"
            ),
        ),
    ]
