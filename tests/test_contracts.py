from __future__ import annotations

from pathlib import Path

from bp_investment_screening.bp_parser import PlainTextParser, choose_parser
from bp_investment_screening.claim_extractor import BPClaimExtractor
from bp_investment_screening.config import Settings
from bp_investment_screening.layer1 import DEFAULT_LAYER1_TOPICS
from bp_investment_screening.layer1_synthesizer import Layer1Synthesizer
from bp_investment_screening.llm import LLMClient
from bp_investment_screening.pipeline import ScreeningPipeline
from bp_investment_screening.report_writer import ReportWriter
from bp_investment_screening.schemas import BPClaims, Claim
from bp_investment_screening.search import NullSearchClient
from bp_investment_screening.technical_background import (
    _build_user_prompt,
    generate_technical_background_sections,
    generate_technical_background_headings,
)


def _test_pipeline() -> ScreeningPipeline:
    settings = Settings(
        llm_base_url=None,
        llm_api_key=None,
        llm_model=None,
        tavily_api_key=None,
        tavily_base_url=None,
        output_root=Path("data"),
    )
    llm_client = LLMClient(settings=settings)
    return ScreeningPipeline(
        search_client=NullSearchClient(),
        layer1_synthesizer=Layer1Synthesizer(llm_client),
        report_writer=ReportWriter(llm_client=llm_client),
    )


def test_skeleton_pipeline_writes_memo(tmp_path: Path) -> None:
    bp_path = tmp_path / "demo_bp.md"
    bp_path.write_text("# Demo BP\n\n项目介绍", encoding="utf-8")
    claims = BPClaims(
        company_name="Demo Company",
        industry="AI Infra",
        product_summary="AI 推理基础设施",
        business_model_claims=[
            Claim(text="按 API 调用量收费", category="商业模式", source_page=1)
        ],
    )

    memo = _test_pipeline().run(bp_path, tmp_path / "outputs", claims=claims)

    assert memo.project_name == "Demo Company"
    assert memo.recommendation.recommendation == "谨慎跟进"
    assert (tmp_path / "outputs" / "investment_memo.json").exists()
    assert (tmp_path / "outputs" / "investment_memo.md").exists()
    assert (tmp_path / "outputs" / "project_research_memo.docx").exists()


def test_plain_text_parser_and_claim_extractor(tmp_path: Path) -> None:
    bp_path = tmp_path / "demo_bp.md"
    bp_path.write_text(
        "\n".join(
            [
                "公司名称：新源汇博科技有限公司",
                "行业：光学材料",
                "产品：面向光刻机和强激光领域的光学元件解决方案",
                "客户：已与多家下游客户开展试点合作",
                "融资：计划融资 5000 万元用于产线建设",
            ]
        ),
        encoding="utf-8",
    )

    parser = choose_parser(bp_path)
    assert isinstance(parser, PlainTextParser)

    claims = BPClaimExtractor().extract(parser.parse(bp_path))

    assert claims.company_name == "新源汇博科技有限公司"
    assert claims.industry == "光学材料"
    assert claims.product_summary is not None
    assert claims.customer_claims
    assert claims.fundraising_claims


def test_pipeline_extracts_claims_without_fixture_claims(tmp_path: Path) -> None:
    bp_path = tmp_path / "auto_bp.md"
    bp_path.write_text(
        "公司名称：Demo Robotics 公司\n行业：机器人\n产品：工业机器人控制平台",
        encoding="utf-8",
    )

    memo = _test_pipeline().run(bp_path, tmp_path / "outputs")

    assert memo.project_name == "Demo Robotics 公司"
    assert memo.industry == "机器人"


def test_technical_background_headings_have_numbering(tmp_path: Path) -> None:
    bp_path = tmp_path / "auto_bp.md"
    bp_path.write_text(
        "公司名称：Demo Photonics 有限公司\n行业：光学材料\n产品：激光晶体材料",
        encoding="utf-8",
    )

    memo = _test_pipeline().run(bp_path, tmp_path / "outputs")
    headings = generate_technical_background_headings(
        memo,
        llm_client=LLMClient(
            settings=Settings(
                llm_base_url=None,
                llm_api_key=None,
                llm_model=None,
                tavily_api_key=None,
                tavily_base_url=None,
                output_root=Path("data"),
            )
        ),
    )

    assert 3 <= len(headings) <= 5
    assert headings[0].startswith("1、")


def test_layer1_topics_are_deoverlapped() -> None:
    topic_names = [topic.name for topic in DEFAULT_LAYER1_TOPICS]

    assert "核心技术与技术壁垒" in topic_names
    assert "商业模式与商业化进展" in topic_names
    assert "政策环境与监管约束" in topic_names
    assert "技术趋势与政策环境" not in topic_names
    assert "商业模式与增长证据" not in topic_names


def test_technical_background_prompt_only_uses_technical_topic(tmp_path: Path) -> None:
    bp_path = tmp_path / "auto_bp.md"
    bp_path.write_text(
        "\n".join(
            [
                "公司名称：Demo Photonics 有限公司",
                "行业：光学材料",
                "产品：激光晶体材料",
                "技术：采用浓度渐变晶体提升热管理能力",
                "团队：创始人具备多年产业经验",
                "客户：已与下游客户开展试点",
            ]
        ),
        encoding="utf-8",
    )

    memo = _test_pipeline().run(bp_path, tmp_path / "outputs")
    prompt = _build_user_prompt(memo)

    assert "技术线索" in prompt
    assert "浓度渐变晶体" in prompt
    assert "技术背景”部分的子标题" not in prompt
    assert "这一章只做技术科普" in prompt
    assert "绝对不要写" in prompt
    assert "团队与资源匹配度" not in prompt
    assert "商业模式与商业化进展" not in prompt


def test_technical_background_sections_are_educational_not_company_status(tmp_path: Path) -> None:
    bp_path = tmp_path / "auto_bp.md"
    bp_path.write_text(
        "\n".join(
            [
                "公司名称：Demo Photonics 有限公司",
                "行业：光学材料",
                "技术：采用浓度渐变 YAG 晶体提升热管理能力",
                "客户：已与下游客户开展试点",
                "订单：已经进入批量供应阶段",
            ]
        ),
        encoding="utf-8",
    )

    memo = _test_pipeline().run(bp_path, tmp_path / "outputs")
    sections = generate_technical_background_sections(
        memo,
        llm_client=LLMClient(
            settings=Settings(
                llm_base_url=None,
                llm_api_key=None,
                llm_model=None,
                tavily_api_key=None,
                tavily_base_url=None,
                output_root=Path("data"),
            )
        ),
    )

    joined = "\n".join(f"{section.heading}\n{section.body}" for section in sections)
    assert "客户" not in joined
    assert "订单" not in joined
    assert "量产" not in joined
    assert "融资" not in joined


def test_layer1_contains_information_summary_and_evidence_groups(tmp_path: Path) -> None:
    bp_path = tmp_path / "auto_bp.md"
    bp_path.write_text(
        "公司名称：Demo Photonics 有限公司\n行业：光学材料\n技术：采用浓度渐变晶体提升热管理能力",
        encoding="utf-8",
    )

    memo = _test_pipeline().run(bp_path, tmp_path / "outputs")
    technical_item = next(
        item for item in memo.layer1_items if item.topic == "核心技术与技术壁垒"
    )

    assert technical_item.information_summary is not None
    assert technical_item.information_summary.integrated_summary
    assert technical_item.evidence_groups
    assert isinstance(technical_item.key_risks, list)
