"""Search abstractions for external evidence collection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from bp_investment_screening.schemas import EvidenceItem


@dataclass(frozen=True, slots=True)
class SearchQuery:
    query: str
    purpose: str
    max_results: int = 3


class SearchClient(Protocol):
    def search(self, query: SearchQuery) -> list[EvidenceItem]:
        """Return external evidence items for a query."""


class NullSearchClient:
    """No-op search client for local contract tests."""

    def search(self, query: SearchQuery) -> list[EvidenceItem]:
        return []

