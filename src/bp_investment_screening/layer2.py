"""Layer2 lightweight investment screening analysis."""

from __future__ import annotations

from bp_investment_screening.schemas import (
    BPClaims,
    InvestmentRecommendation,
    Layer1ResearchItem,
)


class InvestmentAnalyzer:
    """Convert layer1 research into a first-pass investment recommendation."""

    def run(
        self,
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
                f"{project}已完成初步资料归集，但当前框架尚未接入正式 LLM 分析与外部证据校验。"
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
                "完成 BP claims 抽取。",
                "对 external_first topic 执行少量高价值搜索。",
                "用投资初筛 skill 生成正式优势、劣势、风险和跟进建议。",
            ],
        )

