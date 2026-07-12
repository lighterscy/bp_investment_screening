"""Standalone BP investment screening pipeline."""

from __future__ import annotations

from pathlib import Path

from bp_investment_screening.bp_parser import choose_parser
from bp_investment_screening.claim_extractor import BPClaimExtractor
from bp_investment_screening.layer1 import Layer1Researcher
from bp_investment_screening.layer2 import InvestmentAnalyzer
from bp_investment_screening.report_writer import ReportWriter
from bp_investment_screening.schemas import BPClaims, InvestmentMemo
from bp_investment_screening.search import NullSearchClient, SearchClient


class ScreeningPipeline:
    """Run BP parsing, lightweight layer1, layer2 screening, and report output."""

    def __init__(
        self,
        search_client: SearchClient | None = None,
        report_writer: ReportWriter | None = None,
        claim_extractor: BPClaimExtractor | None = None,
    ) -> None:
        self.search_client = search_client or NullSearchClient()
        self.claim_extractor = claim_extractor or BPClaimExtractor()
        self.layer1 = Layer1Researcher(self.search_client)
        self.layer2 = InvestmentAnalyzer()
        self.report_writer = report_writer or ReportWriter()

    def run(
        self,
        bp_path: str | Path,
        output_dir: str | Path,
        claims: BPClaims | None = None,
    ) -> InvestmentMemo:
        """Run the current skeleton pipeline.

        `claims` is optional for now so the framework can be tested before the
        LLM-based BP claim extractor is implemented.
        """
        parser = choose_parser(bp_path)
        parse_result = parser.parse(bp_path)
        extracted_claims = claims or self.claim_extractor.extract(parse_result)
        layer1_items = self.layer1.run(extracted_claims)
        recommendation = self.layer2.run(extracted_claims, layer1_items)
        memo = InvestmentMemo(
            project_name=extracted_claims.company_name or parse_result.source_path.stem,
            industry=extracted_claims.industry,
            recommendation=recommendation,
            layer1_items=layer1_items,
            source_bp_path=parse_result.source_path,
        )
        self.report_writer.write(memo, output_dir)
        return memo
