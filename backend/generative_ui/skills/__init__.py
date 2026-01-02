# --- A2UI Skill Function/Class Map ---
# Dataclass: A2UISkillMeta
#   Role: Stores parsed A2UI skill metadata + content for routing and layout.
#   Called from: backend.generative_ui.skills.load_a2ui_skill, backend.generative_ui.agent_v2.A2UIAgent
#   Invokes: n/a
#   Why: Centralizes skill metadata for selection and rendering.
# Function: load_a2ui_skill
#   Role: Parse YAML frontmatter + body from a skill markdown file into A2UISkillMeta.
#   Called from: backend.generative_ui.skills.load_a2ui_skills
#   Invokes: yaml.safe_load, A2UISkillMeta
#   Why: Provides a single parser for skill.md files.
# Function: load_a2ui_skills
#   Role: Load all A2UI skill markdown files from the skills directory.
#   Called from: backend.generative_ui.skills.get_a2ui_skills
#   Invokes: backend.generative_ui.skills.load_a2ui_skill, pathlib.Path.glob
#   Why: Builds the skill registry used by the agent.
# Function: get_a2ui_skills
#   Role: Return cached list of skills for reuse across requests.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent
#   Invokes: backend.generative_ui.skills.load_a2ui_skills
#   Why: Avoids re-reading skill files on every request.
# Function: get_a2ui_skill
#   Role: Look up a skill by id from the cached registry.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent
#   Invokes: backend.generative_ui.skills.get_a2ui_skills
#   Why: Validates selections against known skills.
# Function: build_a2ui_skill_catalog
#   Role: Format skill metadata into a router prompt for model selection.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent
#   Invokes: n/a
#   Why: Supplies the selection model with consistent skill summaries.
# --- End A2UI Skill Function/Class Map ---
"""
A2UI skill registry and loader utilities.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

import yaml

_SKILL_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class A2UISkillMeta:
    """Metadata + content parsed from an A2UI skill markdown file."""

    skill_id: str
    name: str
    description: str
    widgets: List[str]
    layout: str
    layout_variants: List[str]
    default_variant: str
    source_path: Path
    body: str


def load_a2ui_skill(path: Path) -> A2UISkillMeta:
    """Parse a single skill markdown file into A2UISkillMeta."""
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith("---"):
        raise ValueError(f"Skill file missing YAML frontmatter: {path}")

    parts = raw.split("---", 2)
    if len(parts) < 3:
        raise ValueError(f"Skill file has incomplete frontmatter: {path}")

    frontmatter = parts[1].strip()
    body = parts[2].lstrip("\n")
    meta = yaml.safe_load(frontmatter) or {}

    skill_id = str(meta.get("skill_id", "")).strip()
    name = str(meta.get("name", "")).strip()
    description = str(meta.get("description", "")).strip()
    widgets_raw = meta.get("widgets", [])
    layout = str(meta.get("layout", "")).strip()
    layout_variants_raw = meta.get("layout_variants", []) or []
    default_variant = str(meta.get("default_variant", "")).strip()

    if not skill_id or not name:
        raise ValueError(f"Skill file missing required fields: {path}")
    if not description:
        raise ValueError(f"Skill file missing description: {path}")
    if not layout:
        raise ValueError(f"Skill file missing layout: {path}")

    if isinstance(widgets_raw, str):
        widgets = [widgets_raw]
    elif isinstance(widgets_raw, Iterable):
        widgets = [str(item) for item in widgets_raw]
    else:
        raise ValueError(f"Skill file widgets must be list or string: {path}")

    if isinstance(layout_variants_raw, str):
        layout_variants = [layout_variants_raw]
    elif isinstance(layout_variants_raw, Iterable):
        layout_variants = [str(item) for item in layout_variants_raw]
    else:
        layout_variants = []

    return A2UISkillMeta(
        skill_id=skill_id,
        name=name,
        description=description,
        widgets=widgets,
        layout=layout,
        layout_variants=layout_variants,
        default_variant=default_variant,
        source_path=path,
        body=body,
    )


def load_a2ui_skills(directory: Path | None = None) -> List[A2UISkillMeta]:
    """Load all A2UI skill markdown files from disk."""
    directory = directory or _SKILL_DIR
    skill_files = sorted(directory.glob("a2ui_skill_*.md"))
    if not skill_files:
        raise ValueError(f"No A2UI skill files found in {directory}")
    return [load_a2ui_skill(path) for path in skill_files]


@lru_cache(maxsize=1)
def get_a2ui_skills() -> List[A2UISkillMeta]:
    """Return cached list of parsed A2UI skills."""
    return load_a2ui_skills()


def get_a2ui_skill(skill_id: str) -> A2UISkillMeta:
    """Fetch a single skill from the registry by skill_id."""
    for skill in get_a2ui_skills():
        if skill.skill_id == skill_id:
            return skill
    raise KeyError(f"Unknown A2UI skill_id: {skill_id}")


def build_a2ui_skill_catalog(skills: Sequence[A2UISkillMeta]) -> str:
    """Format skills into a compact catalog prompt for routing."""
    lines = ["A2UI Skill Catalog:"]
    for skill in skills:
        lines.append(f"- {skill.name} ({skill.skill_id})")
        lines.append(f"  Description: {skill.description}")
        lines.append(f"  Widgets: {', '.join(skill.widgets)}")
        lines.append(f"  Layout: {skill.layout}")
        if skill.layout_variants:
            lines.append(f"  Layout Variants: {', '.join(skill.layout_variants)}")
    return "\n".join(lines)


__all__ = [
    "A2UISkillMeta",
    "load_a2ui_skill",
    "load_a2ui_skills",
    "get_a2ui_skills",
    "get_a2ui_skill",
    "build_a2ui_skill_catalog",
]
