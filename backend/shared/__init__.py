# --- Shared Module Function/Class Map ---
# Module: skill_manager
#   Role: Upload and manage skills with Anthropic's Native Skills API.
#   Called from: conversational_analytics.native_skills_client, generative_ui.agent_v2
#   Invokes: anthropic.beta.skills.create, anthropic.beta.skills.list
#   Why: Centralized skill upload/cache infrastructure for both projects.
# --- End Shared Module Function/Class Map ---
"""
Shared utilities for the AI Portfolio backend.
"""

from .skill_manager import (
    SkillManager,
    SkillUploadResult,
    SkillCacheEntry,
    get_skill_manager,
)

__all__ = [
    "SkillManager",
    "SkillUploadResult",
    "SkillCacheEntry",
    "get_skill_manager",
]
