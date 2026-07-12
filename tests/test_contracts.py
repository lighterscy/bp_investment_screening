from __future__ import annotations

from pathlib import Path

from bp_investment_screening.bp_parser import PlainTextParser, choose_parser
from bp_investment_screening.claim_extractor import BPClaimExtractor
from bp_investment_screening.pipeline import ScreeningPipeline
from bp_investment_screening.schemas import BPClaims, Claim
from bp_investment_screening.technical_background import generate_technical_background_headings


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

    memo = ScreeningPipeline().run(bp_path, tmp_path / "outputs", claims=claims)

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

    memo = ScreeningPipeline().run(bp_path, tmp_path / "outputs")

    assert memo.project_name == "Demo Robotics 公司"
    assert memo.industry == "机器人"


def test_technical_background_headings_have_numbering(tmp_path: Path) -> None:
    bp_path = tmp_path / "auto_bp.md"
    bp_path.write_text(
        "公司名称：Demo Photonics 有限公司\n行业：光学材料\n产品：激光晶体材料",
        encoding="utf-8",
    )

    memo = ScreeningPipeline().run(bp_path, tmp_path / "outputs")
    headings = generate_technical_background_headings(memo)

    assert 3 <= len(headings) <= 5
    assert headings[0].startswith("1、")
