"""Configuration for the standalone BP screening project."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    llm_base_url: str | None
    llm_api_key: str | None
    llm_model: str | None
    tavily_api_key: str | None
    tavily_base_url: str | None
    output_root: Path

    @classmethod
    def from_env(cls) -> "Settings":
        _load_env_file()
        return cls(
            llm_base_url=os.getenv("LLM_BASE_URL"),
            llm_api_key=os.getenv("LLM_API_KEY"),
            llm_model=os.getenv("LLM_MODEL"),
            tavily_api_key=os.getenv("TAVILY_API_KEY"),
            tavily_base_url=os.getenv("TAVILY_BASE_URL"),
            output_root=Path(os.getenv("BP_SCREENING_OUTPUT_ROOT", "data/outputs")),
        )


def _load_env_file() -> None:
    env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
