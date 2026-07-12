"""Conservative BP claim extraction.

This module is intentionally deterministic. It gives the pipeline a useful
local baseline before a real LLM extractor is wired in.
"""

from __future__ import annotations

import re

from bp_investment_screening.schemas import BPClaims, Claim, DocumentParseResult


SECTION_KEYWORDS = {
    "business_model_claims": ("商业模式", "盈利模式", "收费", "收入模式", "渠道", "采购", "销售"),
    "market_claims": ("市场", "行业", "规模", "空间", "增速", "赛道", "国内", "海外", "全球", "国产替代"),
    "traction_claims": ("客户", "订单", "收入", "营收", "增长", "落地", "试点", "合作", "批量", "供应", "认证"),
    "team_claims": ("团队", "创始", "核心成员", "履历", "博士", "教授"),
    "financial_claims": ("财务", "收入", "营收", "毛利", "利润", "现金流", "业绩", "规划", "预测", "目标"),
    "fundraising_claims": ("融资", "估值", "募资", "出让", "资金用途", "股权", "股东", "持股", "增资", "投资人"),
    "customer_claims": ("客户", "合作", "案例", "订单", "供应商", "渠道"),
    "technology_claims": ("技术", "产品", "专利", "知识产权", "软著", "研发", "算法", "材料", "工艺", "晶体", "镀膜"),
    "risk_disclosures": ("风险", "挑战", "不确定", "依赖", "瓶颈"),
}

INDUSTRY_PATTERNS = (
    re.compile(r"(?:所属)?行业[：:\s]+([^\n，,。；;]{2,30})"),
    re.compile(r"(?:赛道|领域)[：:\s]+([^\n，,。；;]{2,30})"),
)

COMPANY_PATTERNS = (
    re.compile(r"(?:公司名称|企业名称|项目名称)[：:\s]+([^\n，,。；;]{2,50})"),
    re.compile(
        r"([\u4e00-\u9fa5A-Za-z0-9（）()·\-]{2,50}"
        r"(?:有限责任公司|股份有限公司|有限公司|集团|Corporation|Inc\.))"
    ),
)


class BPClaimExtractor:
    """Extract project-party claims from parsed BP text."""

    def extract(self, parse_result: DocumentParseResult) -> BPClaims:
        company_name = _first_match(parse_result, COMPANY_PATTERNS)
        industry = _first_match(parse_result, INDUSTRY_PATTERNS)
        product_summary = _extract_product_summary(parse_result)
        claims_by_field: dict[str, list[Claim]] = {
            field: [] for field in SECTION_KEYWORDS
        }

        for page in parse_result.pages:
            for line in _candidate_lines(page.text):
                for field, keywords in SECTION_KEYWORDS.items():
                    if any(keyword in line for keyword in keywords):
                        claims_by_field[field].append(
                            Claim(
                                text=line,
                                category=_category_name(field),
                                source_page=page.page_number,
                                needs_verification=field
                                not in {"team_claims", "technology_claims"},
                            )
                        )

        missing_information = _missing_information(company_name, industry, product_summary)
        return BPClaims(
            company_name=company_name,
            industry=industry,
            product_summary=product_summary,
            business_model_claims=_dedupe_claims(claims_by_field["business_model_claims"]),
            market_claims=_dedupe_claims(claims_by_field["market_claims"]),
            traction_claims=_dedupe_claims(claims_by_field["traction_claims"]),
            team_claims=_dedupe_claims(claims_by_field["team_claims"]),
            financial_claims=_dedupe_claims(claims_by_field["financial_claims"]),
            fundraising_claims=_dedupe_claims(claims_by_field["fundraising_claims"]),
            customer_claims=_dedupe_claims(claims_by_field["customer_claims"]),
            technology_claims=_dedupe_claims(claims_by_field["technology_claims"]),
            risk_disclosures=_dedupe_claims(claims_by_field["risk_disclosures"]),
            missing_information=missing_information,
        )


def _candidate_lines(text: str) -> list[str]:
    lines: list[str] = []
    for raw_line in re.split(r"[\n\r]+", text):
        line = re.sub(r"\s+", " ", raw_line).strip(" -\t")
        if 6 <= len(line) <= 180:
            lines.append(line)
    return lines


def _first_match(parse_result: DocumentParseResult, patterns: tuple[re.Pattern[str], ...]) -> str | None:
    for page in parse_result.pages:
        for pattern in patterns:
            match = pattern.search(page.text)
            if match:
                return match.group(1).strip()
    return None


def _extract_product_summary(parse_result: DocumentParseResult) -> str | None:
    for page in parse_result.pages[:3]:
        for line in _candidate_lines(page.text):
            if any(keyword in line for keyword in ("产品", "解决方案", "平台", "服务")):
                return line
    first_text_page = next((page for page in parse_result.pages if page.text.strip()), None)
    if not first_text_page:
        return None
    lines = _candidate_lines(first_text_page.text)
    return lines[0] if lines else None


def _category_name(field: str) -> str:
    return {
        "business_model_claims": "商业模式",
        "market_claims": "市场与行业",
        "traction_claims": "商业化进展",
        "team_claims": "团队",
        "financial_claims": "财务",
        "fundraising_claims": "融资",
        "customer_claims": "客户与合作",
        "technology_claims": "技术与产品",
        "risk_disclosures": "风险披露",
    }[field]


def _dedupe_claims(claims: list[Claim], limit: int = 12) -> list[Claim]:
    seen: set[str] = set()
    deduped: list[Claim] = []
    for claim in claims:
        key = claim.text
        if key in seen:
            continue
        seen.add(key)
        deduped.append(claim)
        if len(deduped) >= limit:
            break
    return deduped


def _missing_information(
    company_name: str | None,
    industry: str | None,
    product_summary: str | None,
) -> list[str]:
    missing: list[str] = []
    if not company_name:
        missing.append("未稳定识别公司/项目名称，需要人工或 LLM 抽取确认。")
    if not industry:
        missing.append("未稳定识别所属行业/赛道，需要后续补充。")
    if not product_summary:
        missing.append("未稳定识别产品与服务描述，需要后续补充。")
    return missing
