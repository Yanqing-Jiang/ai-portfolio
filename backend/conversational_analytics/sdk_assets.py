"""Shared helpers to load Claude Agent SDK project assets (.claude/*).

This module re-exports SDK helpers from backend.shared_tools for backward compatibility.
New code should import directly from shared_tools.
"""
from __future__ import annotations

# Re-export all SDK helpers from shared_tools
from shared_tools.sdk_helpers import (
    CLAUDE_DIR,
    PROJECT_ROOT,
    should_use_sdk_assets,
    load_project_settings,
    load_project_guide,
    load_agent_prompt,
    load_command_prompt,
    load_skill_override,
    get_allowed_tools,
)

__all__ = [
    "CLAUDE_DIR",
    "PROJECT_ROOT",
    "should_use_sdk_assets",
    "load_project_settings",
    "load_project_guide",
    "load_agent_prompt",
    "load_command_prompt",
    "load_skill_override",
    "get_allowed_tools",
]

