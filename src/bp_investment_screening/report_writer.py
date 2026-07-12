"""Report rendering interfaces."""

from __future__ import annotations

import json
from pathlib import Path

from bp_investment_screening.llm import LLMClient
from bp_investment_screening.schemas import InvestmentMemo


class ReportWriter:
    """Write structured memo artifacts.

    JSON and Markdown are always written. Word rendering is attempted only when
    a docxtpl template exists, so the pipeline remains usable before a final
    memo template is designed.
    """

    def __init__(
        self,
        template_path: str | Path | None = None,
        llm_client: LLMClient | None = None,
    ) -> None:
        self.template_path = Path(template_path) if template_path else Path(
            "templates/investment_memo.docx"
        )
        self.llm_client = llm_client

    def write(self, memo: InvestmentMemo, output_dir: str | Path) -> dict[str, Path]:
        root = Path(output_dir)
        root.mkdir(parents=True, exist_ok=True)
        json_path = root / "investment_memo.json"
        md_path = root / "investment_memo.md"
        json_path.write_text(
            json.dumps(memo.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        md_path.write_text(_render_markdown(memo), encoding="utf-8")
        paths = {"json": json_path, "markdown": md_path}
        formal_docx_path = _try_render_formal_docx(memo, root, self.llm_client)
        if formal_docx_path:
            paths["formal_docx"] = formal_docx_path
        docx_path = _try_render_docx(memo, root, self.template_path)
        if docx_path:
            paths["template_docx"] = docx_path
        return paths


def _render_markdown(memo: InvestmentMemo) -> str:
    rec = memo.recommendation
    lines = [
        "# 项目初筛投资研判",
        "",
        f"- 项目：{memo.project_name}",
        f"- 行业：{memo.industry or '未知'}",
        f"- 初筛建议：{rec.recommendation}",
        f"- 置信度：{rec.confidence}",
        "",
        "## 一句话结论",
        "",
        rec.one_sentence_view,
        "",
        "## 投资亮点",
        "",
    ]
    lines.extend(f"- {item}" for item in rec.strengths)
    lines.extend(["", "## 核心短板", ""])
    lines.extend(f"- {item}" for item in rec.weaknesses)
    lines.extend(["", "## 关键风险", ""])
    lines.extend(f"- {item}" for item in rec.key_risks)
    lines.extend(["", "## 待验证问题", ""])
    lines.extend(f"- {item}" for item in rec.open_questions)
    lines.extend(["", "## 建议下一步", ""])
    lines.extend(f"- {item}" for item in rec.next_steps)
    lines.extend(["", "## Layer1 基础研究", ""])
    for item in memo.layer1_items:
        lines.extend(
            [
                f"### {item.topic}",
                "",
                f"- 证据优先级：{item.evidence_priority}",
                f"- 置信度：{item.confidence}",
                f"- 信息整合：{item.information_summary.integrated_summary if item.information_summary else '暂无'}",
                f"- 综合判断：{item.synthesis}",
                f"- BP 主张：{len(item.bp_claims)} 条",
                f"- 外部证据：{len(item.external_evidence)} 条",
            ]
        )
        if item.key_risks:
            lines.append("- 关键风险：" + "；".join(item.key_risks))
        if item.open_questions:
            lines.append("- 开放问题：" + "；".join(item.open_questions))
        lines.append("")
    lines.append("")
    return "\n".join(lines)


def _try_render_docx(
    memo: InvestmentMemo,
    output_dir: Path,
    template_path: Path,
) -> Path | None:
    if not template_path.exists():
        return None
    try:
        from docxtpl import DocxTemplate
    except ImportError as exc:
        raise RuntimeError(
            "Word rendering requires the optional dependency `docxtpl`. "
            "Install with `pip install '.[docs]'`."
        ) from exc

    doc = DocxTemplate(template_path)
    context = memo.to_dict()
    context["recommendation"] = memo.recommendation.to_dict()
    context["layer1_items"] = [item.to_dict() for item in memo.layer1_items]
    doc.render(context)
    docx_path = output_dir / "investment_memo.docx"
    doc.save(docx_path)
    return docx_path


def _try_render_formal_docx(
    memo: InvestmentMemo,
    output_dir: Path,
    llm_client: LLMClient | None,
) -> Path | None:
    try:
        from bp_investment_screening.formal_docx import FormalDocxWriter
    except ImportError:
        return None
    return FormalDocxWriter(llm_client=llm_client).write(memo, output_dir)
