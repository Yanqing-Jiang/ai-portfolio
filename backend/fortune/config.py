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

DEFAULT_OPENAI_MODEL = "gpt-5.4-mini"


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
    narrative_model: str = DEFAULT_OPENAI_MODEL
    guardrail_model: str = DEFAULT_OPENAI_MODEL

    # Reasoning effort ("none" | "minimal" | "low" | "medium" | "high" | "xhigh").
    # Default = medium for narrative quality. Override per-stage via
    # FORTUNE_NARRATIVE_REASONING etc. in .env if you need to trade depth
    # for latency. Guardrail stays low because it's a small safety pass.
    narrative_reasoning: str = "medium"
    guardrail_reasoning: str = "low"
    # Follow-up Ask turns are inherently lighter (one focused question
    # against an already-computed foundation) so they default to "low" —
    # roughly 30% faster than medium, which dominates perceived latency on
    # the Ask tab. The initial reading still uses narrative_reasoning.
    ask_reasoning: str = "low"

    # PR3 (latency refactor) — per-mode reasoning effort.
    # Compatibility flipped from "medium" → "low" on 2026-05-10 after the
    # PR-1B judge harness (scripts/run_compat_judge_harness.py) confirmed
    # 3/3 fixtures pass authenticity ≥ 6.5/10 at low (medians 8.2, 9.5,
    # 10.0; p25 floor 8.2). Combined with the smoke samples covering
    # compat_001/002/003 across two prior runs (medians 8.5/9.5/10.0 at
    # low), the verdict was robust across judge variance.
    # Latency drop: compat 65s → 15-22s (3-4x faster), with no observed
    # mechanism-floor regression because PR-1A's Pydantic min_length now
    # rejects sub-floor outputs at the schema layer regardless of effort.
    # Rollback: ``FORTUNE_NARRATIVE_REASONING_COMPATIBILITY=medium`` +
    # ``docker compose restart backend`` (sub-second effective).
    # The other three modes default to "low" because:
    #   - occasion: deterministic prefilter narrows 60+ days to top 21,
    #     so the model only ranks/explains a curated set;
    #   - luck_cycle: small UI payload (current_window + mechanisms) and
    #     timeline is deterministic;
    #   - wish: bounded verdict + anchors + mechanisms.
    narrative_reasoning_compatibility: str = "low"
    narrative_reasoning_occasion: str = "low"
    narrative_reasoning_luck_cycle: str = "low"
    narrative_reasoning_wish: str = "low"

    # PR3 — per-mode max_tokens caps. ``None`` means no cap (the OpenAI
    # per-request budget governs). Compatibility stays uncapped while
    # effort was ``medium`` because that path truncated below 10k; once
    # PR-3 dropped reasoning to ``low``, total tokens fell to ~3-4k and a
    # 10k cap is safe headroom against runaway-reasoning tails.
    narrative_max_tokens_compatibility: Optional[int] = 10000
    narrative_max_tokens_occasion: Optional[int] = 9000
    narrative_max_tokens_luck_cycle: Optional[int] = 4500
    narrative_max_tokens_wish: Optional[int] = 6000
    guardrail_max_tokens: Optional[int] = 1200

    # PR-2 — compat service_tier + store flags.
    #
    # ``narrative_service_tier_compatibility`` accepts ``"priority"`` (10-25%
    # tail-flattening on eligible OpenAI accounts) or ``None`` (default
    # queue). Off by default until OpenAI account eligibility is verified.
    #
    # ``narrative_store_compatibility`` opts the compat response in to
    # OpenAI's response store, addressable later via ``previous_response_id``.
    # Defaults to ``False`` until PR-4 wires the Redis-backed chain map.
    narrative_service_tier_compatibility: Optional[str] = None
    narrative_store_compatibility: bool = False

    # Rollout flags for Day 0 migrations.
    active_luck_window_enabled: bool = True
    current_annual_window_enabled: bool = True
    snapshot_schema_versions_enabled: bool = True
    annual_prompt_horizon_years: int = 10

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
