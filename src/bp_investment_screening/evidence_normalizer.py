"""Normalize BP claims and external evidence into topic-level evidence groups."""

from __future__ import annotations

from bp_investment_screening.schemas import EvidenceGroup, EvidenceItem


TOPIC_ASPECTS = {
    "公司基本信息": ("公司身份", "产品概述", "待核验信息"),
    "产品与服务": ("产品形态", "应用场景", "交付边界"),
    "核心技术与技术壁垒": ("技术门类", "核心技术路线", "关键指标与成熟度", "知识产权与壁垒"),
    "商业模式与商业化进展": ("商业模式", "客户与订单", "收入与增长"),
    "团队与资源匹配度": ("核心团队", "产业资源", "能力缺口"),
    "行业阶段与市场空间": ("行业定义", "发展阶段", "市场空间"),
    "竞争格局与替代方案": ("主要竞争者", "替代方案", "差异化"),
    "政策环境与监管约束": ("政策支持", "监管约束", "合规风险"),
}

ASPECT_KEYWORDS = {
    "公司身份": ("公司", "企业", "成立", "地址", "高新"),
    "产品概述": ("产品", "服务", "解决方案", "平台"),
    "待核验信息": ("融资", "股权", "收入", "订单", "客户"),
    "产品形态": ("产品", "材料", "元件", "设备", "平台"),
    "应用场景": ("应用", "场景", "客户", "市场", "领域"),
    "交付边界": ("交付", "量产", "供应", "服务"),
    "技术门类": ("技术", "材料", "晶体", "算法", "模型", "工艺"),
    "核心技术路线": ("路线", "工艺", "方案", "结构", "键合", "渐变"),
    "关键指标与成熟度": ("指标", "性能", "良率", "损伤", "稳定", "量产"),
    "知识产权与壁垒": ("专利", "壁垒", "know-how", "独家", "唯一"),
    "商业模式": ("商业模式", "盈利", "收费", "销售", "采购"),
    "客户与订单": ("客户", "订单", "合作", "试点", "供应"),
    "收入与增长": ("收入", "营收", "增长", "利润", "毛利"),
    "核心团队": ("团队", "创始", "博士", "教授", "履历"),
    "产业资源": ("资源", "院所", "政府", "渠道", "合作"),
    "能力缺口": ("缺口", "不足", "短板", "风险"),
    "行业定义": ("行业", "定义", "产业链", "上游", "下游"),
    "发展阶段": ("阶段", "现状", "成熟", "导入", "爆发"),
    "市场空间": ("市场", "规模", "空间", "增速", "CAGR"),
    "主要竞争者": ("竞争", "对手", "玩家", "企业", "厂商"),
    "替代方案": ("替代", "方案", "路线", "传统"),
    "差异化": ("差异", "优势", "壁垒", "比较"),
    "政策支持": ("政策", "支持", "鼓励", "规划"),
    "监管约束": ("监管", "准入", "资质", "认证"),
    "合规风险": ("风险", "合规", "限制", "制裁"),
}


class EvidenceNormalizer:
    """Group evidence by the research aspects of a topic."""

    def normalize(
        self,
        topic: str,
        bp_claims: list[EvidenceItem],
        external_evidence: list[EvidenceItem],
    ) -> list[EvidenceGroup]:
        aspects = TOPIC_ASPECTS.get(topic, ("基本信息", "支持证据", "待验证问题"))
        groups = [
            EvidenceGroup(
                aspect=aspect,
                bp_claims=_match_evidence(aspect, bp_claims),
                external_evidence=_match_evidence(aspect, external_evidence),
            )
            for aspect in aspects
        ]
        return _attach_unmatched(groups, bp_claims, external_evidence)


def _match_evidence(aspect: str, evidence: list[EvidenceItem]) -> list[EvidenceItem]:
    keywords = ASPECT_KEYWORDS.get(aspect, ())
    if not keywords:
        return []
    return [
        item
        for item in evidence
        if any(keyword.lower() in f"{item.title} {item.content}".lower() for keyword in keywords)
    ]


def _attach_unmatched(
    groups: list[EvidenceGroup],
    bp_claims: list[EvidenceItem],
    external_evidence: list[EvidenceItem],
) -> list[EvidenceGroup]:
    matched_bp_ids = {id(item) for group in groups for item in group.bp_claims}
    matched_external_ids = {id(item) for group in groups for item in group.external_evidence}
    unmatched_bp = [item for item in bp_claims if id(item) not in matched_bp_ids]
    unmatched_external = [
        item for item in external_evidence if id(item) not in matched_external_ids
    ]
    if unmatched_bp or unmatched_external:
        groups.append(
            EvidenceGroup(
                aspect="其他相关信息",
                bp_claims=unmatched_bp,
                external_evidence=unmatched_external,
            )
        )
    return groups
