"""
Shared helpers to load Claude Agent SDK project assets (.claude/*).

Function: SDK helper functions for both A2UI and Conversational Analytics.
Called from: backend.generative_ui.agent_v2, backend.conversational_analytics.agent
Invokes: File system operations on .claude directory.
Purpose: Centralize SDK asset loading so both projects can use it without coupling.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

# Paths - resolve from shared_tools location
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CLAUDE_DIR = PROJECT_ROOT / ".claude"


@lru_cache(maxsize=1)
def should_use_sdk_assets(enable_flag: bool = True) -> bool:
    """
    Function: should_use_sdk_assets — determines whether SDK assets should be loaded.
    Called from: agent and supervisor initialization.
    Invokes: filesystem existence checks on `.claude`.
    Purpose: Feature-gates SDK asset usage so we can fall back cleanly when missing.
    """
    return bool(enable_flag and CLAUDE_DIR.exists())


@lru_cache(maxsize=1)
def load_project_settings() -> Dict[str, Any]:
    """
    Function: load_project_settings — reads `project-settings.json` for hooks/allowlists/timeouts.
    Called from: agent and supervisor to align tool allowlists and budgets.
    Invokes: json.load on the project settings file.
    Purpose: Centralizes SDK settings consumption across the backend.
    """
    settings_path = PROJECT_ROOT / "project-settings.json"
    if not settings_path.exists():
        return {}
    try:
        return json.loads(settings_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


@lru_cache(maxsize=1)
def load_project_guide() -> Optional[str]:
    """
    Function: load_project_guide — loads project-level CLAUDE.md guidance for prompts.
    Called from: agent to augment base system prompt; supervisor for specialist prompts.
    Invokes: filesystem reads, preferring `.claude/CLAUDE.md` then root `CLAUDE.md`.
    Purpose: Injects shared schema/guardrails without duplicating prompt text.
    """
    for path in [CLAUDE_DIR / "CLAUDE.md", PROJECT_ROOT / "CLAUDE.md"]:
        if path.exists():
            try:
                return path.read_text(encoding="utf-8")
            except Exception:
                continue
    return None


@lru_cache(maxsize=None)
def load_agent_prompt(agent_key: str) -> Optional[str]:
    """
    Function: load_agent_prompt — fetches specialist prompt markdown from `.claude/agents`.
    Called from: supervisor prompt builder and agent when agent_mode is set.
    Invokes: file read based on agent_key (e.g., `database_admin.md`).
    Purpose: Keeps specialist prompts in the SDK filesystem for easier edits.
    """
    if not agent_key:
        return None
    candidate = CLAUDE_DIR / "agents" / f"{agent_key}.md"
    if candidate.exists():
        try:
            return candidate.read_text(encoding="utf-8")
        except Exception:
            return None
    return None


@lru_cache(maxsize=None)
def load_command_prompt(command_key: str) -> Optional[str]:
    """
    Function: load_command_prompt — loads command templates from `.claude/commands`.
    Called from: supervisor/agent (future) to seed common flows.
    Invokes: file read based on command_key (e.g., `revenue_comparison.md`).
    Purpose: Makes common flows reusable without hand-coded prompts.
    """
    if not command_key:
        return None
    candidate = CLAUDE_DIR / "commands" / f"{command_key}.md"
    if candidate.exists():
        try:
            return candidate.read_text(encoding="utf-8")
        except Exception:
            return None
    return None


def load_skill_override(filename: str) -> Optional[str]:
    """
    Function: load_skill_override — loads mirrored skills from `.claude/skills` if present.
    Called from: skills.load_skill_content to prefer SDK assets.
    Invokes: file read of mirrored skill markdown.
    Purpose: Ensures SDK filesystem is the single source of truth for skill content.
    """
    candidate = CLAUDE_DIR / "skills" / filename
    if candidate.exists():
        try:
            return candidate.read_text(encoding="utf-8")
        except Exception:
            return None
    return None


def get_allowed_tools(default_tools: List[str]) -> List[str]:
    """
    Function: get_allowed_tools — merges settings.json allowlist with defaults.
    Called from: agent tool selection.
    Invokes: load_project_settings to read allowlists.
    Purpose: Keeps runtime allowlist aligned with SDK configuration.
    """
    settings = load_project_settings()
    configured = settings.get("allowlists", {}).get("tools") if settings else None
    if configured:
        return list(dict.fromkeys([t for t in configured if t in default_tools]))
    return default_tools


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
