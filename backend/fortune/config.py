"""Configuration for Ming Engine fortune service."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

_MODULE_DIR = Path(__file__).resolve().parent
load_dotenv(dotenv_path=_MODULE_DIR.parent / ".env", override=False)
load_dotenv(dotenv_path=_MODULE_DIR / ".env", override=False)

DEFAULT_OPENAI_MODEL = "gpt-5-mini-2025-08-07"


class FortuneSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FORTUNE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: Optional[str] = (
        os.getenv("FORTUNE_OPENAI_API_KEY")
        or os.getenv("OPENAI_API_KEY")
    )

    # A2UI
    catalog_id: str = "ming-fortune-v1"
    standard_catalog_id: str = (
        "https://github.com/google/A2UI/blob/main/specification/0.8/json/standard_catalog_definition.json"
    )
    default_surface_id: str = "fortune_main"
    default_timezone: str = "UTC"

    # Models
    intake_model: str = DEFAULT_OPENAI_MODEL
    chart_model: str = DEFAULT_OPENAI_MODEL
    classics_model: str = DEFAULT_OPENAI_MODEL
    narrative_model: str = DEFAULT_OPENAI_MODEL
    guardrail_model: str = DEFAULT_OPENAI_MODEL

    # Reasoning effort ("minimal" | "low" | "medium" | "high" | "xhigh").
    # Default = medium to match the gpt-5-mini-2025-08-07 medium-thinking
    # baseline the agent browser is benchmarked against. Override per-stage
    # via FORTUNE_NARRATIVE_REASONING etc. in .env if you need to trade
    # depth for latency. Guardrail stays low — it's a small safety pass and
    # medium reasoning would dominate end-to-end stream latency.
    intake_reasoning: str = "medium"
    chart_reasoning: str = "medium"
    classics_reasoning: str = "medium"
    narrative_reasoning: str = "medium"
    guardrail_reasoning: str = "low"

    # Limits
    max_classical_references: int = 4
    max_sections: int = 6

    # Corpus
    classics_corpus_path: str = str(_MODULE_DIR / "data" / "classics.json")

    # Debug
    debug_mode: bool = True


_settings: FortuneSettings | None = None


def get_settings() -> FortuneSettings:
    global _settings
    if _settings is None:
        _settings = FortuneSettings()
    return _settings
