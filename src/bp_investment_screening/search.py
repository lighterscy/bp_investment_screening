"""Search abstractions for external evidence collection."""

from __future__ import annotations

import json
from dataclasses import dataclass
import urllib.error
import urllib.request
from typing import Protocol

from bp_investment_screening.config import Settings
from bp_investment_screening.http import default_ssl_context
from bp_investment_screening.schemas import EvidenceItem
from bp_investment_screening.tracing import NullTracer, Tracer


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


class TavilySearchClient:
    """Tavily search client for external evidence collection."""

    def __init__(
        self,
        settings: Settings | None = None,
        timeout_seconds: int = 60,
        tracer: Tracer | None = None,
    ) -> None:
        self.settings = settings or Settings.from_env()
        self.timeout_seconds = timeout_seconds
        self.tracer = tracer or NullTracer()

    @property
    def is_configured(self) -> bool:
        return bool(self.settings.tavily_api_key)

    def search(self, query: SearchQuery) -> list[EvidenceItem]:
        if not self.is_configured:
            return []

        url = _tavily_search_url(self.settings.tavily_base_url)
        payload = {
            "api_key": self.settings.tavily_api_key,
            "query": query.query,
            "search_depth": "basic",
            "max_results": query.max_results,
            "include_answer": False,
            "include_raw_content": False,
        }
        self.tracer.log(
            f"[search] tavily query='{query.query}' max_results={query.max_results} "
            f"timeout={self.timeout_seconds}s"
        )
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=self.timeout_seconds,
                context=default_ssl_context(),
            ) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            self.tracer.log(f"[search] failed {type(exc).__name__}: {str(exc)[:200]}")
            return []

        results = body.get("results", [])
        evidence: list[EvidenceItem] = []
        for item in results[: query.max_results]:
            title = str(item.get("title") or "").strip()
            content = str(item.get("content") or item.get("snippet") or "").strip()
            url_value = str(item.get("url") or "").strip() or None
            if not title and not content:
                continue
            evidence.append(
                EvidenceItem(
                    source_type="external",
                    title=title or query.purpose,
                    content=content,
                    url=url_value,
                    confidence="medium",
                )
            )
        self.tracer.log(f"[search] tavily results={len(evidence)}")
        return evidence


def _tavily_search_url(base_url: str | None) -> str:
    if not base_url:
        return "https://api.tavily.com/search"
    trimmed = base_url.rstrip("/")
    if trimmed.endswith("/search"):
        return trimmed
    return f"{trimmed}/search"
