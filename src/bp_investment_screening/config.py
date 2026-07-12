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
    output_root: Path

    @classmethod
    def from_env(cls) -> "Settings":
        try:
            from dotenv import load_dotenv
        except ImportError:
            load_dotenv = None
        if load_dotenv:
            load_dotenv()
        return cls(
            llm_base_url=os.getenv("LLM_BASE_URL"),
            llm_api_key=os.getenv("LLM_API_KEY"),
            llm_model=os.getenv("LLM_MODEL"),
            output_root=Path(os.getenv("BP_SCREENING_OUTPUT_ROOT", "data/outputs")),
        )
