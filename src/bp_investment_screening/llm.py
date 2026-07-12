"""Minimal OpenAI-compatible LLM client."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from bp_investment_screening.config import Settings
from bp_investment_screening.http import default_ssl_context
from bp_investment_screening.tracing import NullTracer, Tracer


@dataclass(frozen=True, slots=True)
class LLMResult:
    text: str


class LLMClient:
    """Small client for chat-completions-compatible APIs.

    The project can run without this client. If LLM settings are missing, callers
    should fall back to deterministic behavior.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        timeout_seconds: int = 660,
        tracer: Tracer | None = None,
    ) -> None:
        self.settings = settings or Settings.from_env()
        self.timeout_seconds = timeout_seconds
        self.tracer = tracer or NullTracer()

    @property
    def is_configured(self) -> bool:
        return bool(
            self.settings.llm_base_url
            and self.settings.llm_api_key
            and self.settings.llm_model
        )

    def complete(self, system_prompt: str, user_prompt: str) -> LLMResult | None:
        if not self.is_configured:
            return None

        url = _chat_completions_url(self.settings.llm_base_url or "")
        payload = {
            "model": self.settings.llm_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }
        self.tracer.log(
            f"[llm] request model={self.settings.llm_model} timeout={self.timeout_seconds}s "
            f"prompt_chars={len(system_prompt) + len(user_prompt)}"
        )
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.settings.llm_api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=self.timeout_seconds,
                context=default_ssl_context(),
            ) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            self.tracer.log(f"[llm] failed {type(exc).__name__}: {str(exc)[:200]}")
            return None

        content = (
            body.get("choices", [{}])[0]
            .get("message", {})
            .get("content")
        )
        if not isinstance(content, str) or not content.strip():
            self.tracer.log("[llm] empty response")
            return None
        self.tracer.log(f"[llm] response chars={len(content.strip())}")
        return LLMResult(text=content.strip())


def _chat_completions_url(base_url: str) -> str:
    trimmed = base_url.rstrip("/")
    if trimmed.endswith("/chat/completions"):
        return trimmed
    if trimmed.endswith("/v1"):
        return f"{trimmed}/chat/completions"
    return f"{trimmed}/v1/chat/completions"
