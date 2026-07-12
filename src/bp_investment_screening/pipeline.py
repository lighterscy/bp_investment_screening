"""Standalone BP investment screening pipeline."""

from __future__ import annotations

from pathlib import Path

from bp_investment_screening.bp_parser import choose_parser
from bp_investment_screening.claim_extractor import BPClaimExtractor
from bp_investment_screening.layer1 import Layer1Researcher
from bp_investment_screening.layer1_synthesizer import Layer1Synthesizer
from bp_investment_screening.llm import LLMClient
from bp_investment_screening.layer2 import InvestmentAnalyzer
from bp_investment_screening.report_writer import ReportWriter
from bp_investment_screening.schemas import BPClaims, InvestmentMemo
from bp_investment_screening.search import NullSearchClient, SearchClient, TavilySearchClient
from bp_investment_screening.tracing import NullTracer, Tracer


class ScreeningPipeline:
    """Run BP parsing, lightweight layer1, layer2 screening, and report output."""

    def __init__(
        self,
        search_client: SearchClient | None = None,
        report_writer: ReportWriter | None = None,
        claim_extractor: BPClaimExtractor | None = None,
        layer1_synthesizer: Layer1Synthesizer | None = None,
        investment_analyzer: InvestmentAnalyzer | None = None,
        tracer: Tracer | None = None,
    ) -> None:
        self.tracer = tracer or NullTracer()
        self.search_client = search_client or _default_search_client(self.tracer)
        self.claim_extractor = claim_extractor or BPClaimExtractor()
        llm_client = LLMClient(tracer=self.tracer)
        synthesizer = layer1_synthesizer or Layer1Synthesizer(
            llm_client,
            tracer=self.tracer,
        )
        self.layer1 = Layer1Researcher(
            self.search_client,
            synthesizer=synthesizer,
            tracer=self.tracer,
        )
        self.layer2 = investment_analyzer or InvestmentAnalyzer(
            llm_client=llm_client,
            tracer=self.tracer,
        )
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
        with self.tracer.step("parse BP document"):
            parser = choose_parser(bp_path)
            parse_result = parser.parse(bp_path)
        with self.tracer.step("extract BP claims"):
            extracted_claims = claims or self.claim_extractor.extract(parse_result)
        layer1_items = self.layer1.run(extracted_claims)
        with self.tracer.step("layer2 investment screening"):
            recommendation = self.layer2.run(extracted_claims, layer1_items)
        memo = InvestmentMemo(
            project_name=extracted_claims.company_name or parse_result.source_path.stem,
            industry=extracted_claims.industry,
            recommendation=recommendation,
            layer1_items=layer1_items,
            source_bp_path=parse_result.source_path,
        )
        with self.tracer.step("write reports"):
            self.report_writer.write(memo, output_dir)
        return memo


def _default_search_client(tracer: Tracer | None = None) -> SearchClient:
    tavily = TavilySearchClient(tracer=tracer)
    if tavily.is_configured:
        return tavily
    return NullSearchClient()
