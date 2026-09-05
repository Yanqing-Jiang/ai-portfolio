"""Regression contracts for Fortune's model tiering and trace privacy."""

from __future__ import annotations

from fortune.agents import FortuneRunContext, _model_settings, _run_config
from fortune.config import FortuneSettings


def test_luna_max_interpreter_lane_is_bounded() -> None:
    settings = FortuneSettings()

    assert settings.narrative_model == "gpt-5.6-luna"
    assert settings.interpretation_reasoning == "max"
    assert settings.interpretation_max_tokens == 20000


def test_existing_customer_reasoning_tiers_remain_unchanged() -> None:
    settings = FortuneSettings()

    assert settings.narrative_reasoning_compatibility == "low"
    assert settings.narrative_reasoning_occasion == "low"
    assert settings.narrative_reasoning_luck_cycle == "low"
    assert settings.narrative_reasoning_wish == "low"
    assert settings.ask_reasoning == "low"
    assert settings.guardrail_reasoning == "low"
    assert settings.narrative_reasoning == "medium"


def test_interpreter_model_settings_and_run_trace_are_explicit() -> None:
    model_settings = _model_settings(
        "interpretation_reasoning", "interpretation_max_tokens",
    )
    ctx = FortuneRunContext(
        fortune_id="fortune-1",
        surface_id="fortune_main",
        run_id="run-1",
    )
    run_config = _run_config(ctx)

    assert model_settings.reasoning is not None
    assert model_settings.reasoning.effort == "max"
    assert model_settings.max_tokens == 20000
    assert model_settings.store is False
    assert "reasoning.encrypted_content" in (model_settings.response_include or [])
    assert run_config.workflow_name == "Ming Engine Fortune Agent"
    assert run_config.trace_include_sensitive_data is False

