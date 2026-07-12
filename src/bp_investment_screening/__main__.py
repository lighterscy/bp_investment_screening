"""Command-line entrypoint for BP investment screening."""

from __future__ import annotations

import argparse
from pathlib import Path

from bp_investment_screening.pipeline import ScreeningPipeline


def main() -> None:
    parser = argparse.ArgumentParser(prog="bp_investment_screening")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run screening for one BP file.")
    run_parser.add_argument("bp_path", help="Path to a PDF, PPTX, TXT, or Markdown BP.")
    run_parser.add_argument(
        "--output",
        "-o",
        default=None,
        help=(
            "Directory for generated JSON/Markdown/docx artifacts. "
            "Defaults to the sibling outputs/ directory when bp_path is under inputs/."
        ),
    )
    run_parser.add_argument(
        "--template",
        default=None,
        help="Optional docxtpl Word template path.",
    )

    args = parser.parse_args()
    if args.command == "run":
        _run(args.bp_path, args.output, args.template)


def _run(bp_path: str, output_dir: str, template_path: str | None) -> None:
    from bp_investment_screening.report_writer import ReportWriter

    writer = ReportWriter(template_path=template_path) if template_path else None
    resolved_output_dir = _default_output_dir(Path(bp_path), output_dir)
    memo = ScreeningPipeline(report_writer=writer).run(bp_path, resolved_output_dir)
    print(f"项目：{memo.project_name}")
    print(f"行业：{memo.industry or '未知'}")
    print(f"建议：{memo.recommendation.recommendation}")
    print(f"置信度：{memo.recommendation.confidence}")
    print(f"输出目录：{Path(resolved_output_dir).resolve()}")


def _default_output_dir(bp_path: Path, output_dir: str | None) -> Path:
    if output_dir:
        return Path(output_dir)
    if bp_path.parent.name == "inputs":
        return bp_path.parent.parent / "outputs"
    return Path("data/outputs/demo")


if __name__ == "__main__":
    main()
