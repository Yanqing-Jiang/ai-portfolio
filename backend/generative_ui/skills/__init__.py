# --- A2UI Skill Function/Class Map ---
# Dataclass: A2UISkillMeta
#   Role: Stores parsed A2UI skill metadata + content for routing and layout.
#   Called from: backend.generative_ui.skills.load_a2ui_skill, backend.generative_ui.agent_v2.A2UIAgent
#   Invokes: n/a
#   Why: Centralizes skill metadata for selection and rendering.
# Function: load_claude_skill
#   Role: Parse skill.md from official .claude/skills/<name>/skill.md format.
#   Called from: backend.generative_ui.skills.load_claude_skills
#   Invokes: yaml.safe_load, json.load, A2UISkillMeta
#   Why: Supports the official Claude Agent Skills format.
# Function: load_all_skills
#   Role: Load skills from both .claude/skills/ and legacy directories.
#   Called from: backend.generative_ui.skills.get_a2ui_skills
#   Invokes: load_claude_skills, load_legacy_skills
#   Why: Enables gradual migration to new format while maintaining backward compat.
# Function: get_a2ui_skills
#   Role: Return cached list of skills for reuse across requests.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent
#   Invokes: backend.generative_ui.skills.load_all_skills
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

Supports both:
1. Official Claude Agent Skills format: .claude/skills/<name>/skill.md
2. Legacy A2UI format: backend/generative_ui/skills/a2ui_skill_*.md
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

import yaml

logger = logging.getLogger(__name__)

# Directory paths
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_CLAUDE_SKILLS_DIR = _PROJECT_ROOT / ".claude" / "skills"

@dataclass(frozen=True)
class A2UISkillMeta:
    """
    Metadata + content parsed from an A2UI skill markdown file.
    
    Dataclass: A2UISkillMeta - stores parsed A2UI skill metadata for routing and layout.
    Called from: backend.generative_ui.skills.load_a2ui_skill, backend.generative_ui.agent_v2.A2UIAgent
    Invokes: n/a
    Why: Centralizes skill metadata including data schemas for LLM component selection.
    """

    skill_id: str
    name: str
    description: str
    widgets: List[str]
    layout: str
    layout_variants: List[str]
    default_variant: str
    source_path: Path
    body: str
    tools: List[str] = None  # type: ignore  # Tools declared in skill.md
    layout_config: Optional[Dict[str, Any]] = None  # From claude_assets/layout.json

    @property
    def data_schema(self) -> Dict[str, Any]:
        """
        Return the skill's data schema for LLM prompts.
        
        Property: data_schema - provides data path structure for LLM component selection.
        Called from: component_selector, build_a2ui_skill_catalog
        Why: Enables LLM to know valid data paths before layout generation.
        """
        if self.layout_config:
            return self.layout_config.get("data_schema", {})
        return {}

    @property
    def widget_bindings(self) -> Dict[str, Any]:
        """
        Return valid widget-to-path bindings.
        
        Property: widget_bindings - maps widget types to valid data paths.
        Called from: component_validator, component_selector
        Why: Constrains LLM widget selection to valid data bindings.
        """
        if self.layout_config:
            return self.layout_config.get("widget_bindings", {})
        return {}

    @property
    def data_paths(self) -> Dict[str, str]:
        """
        Return top-level data paths.
        
        Property: data_paths - basic path mapping like {kpis: /data/kpis}.
        Called from: emitter, skill catalog
        Why: Provides quick access to primary data locations.
        """
        if self.layout_config:
            return self.layout_config.get("data_paths", {})
        return {}

    @property
    def all_data_paths(self) -> List[str]:
        """
        Flatten all valid data paths for enum constraints in tool schemas.
        
        Property: all_data_paths - complete list of valid binding paths.
        Called from: component_selector.build_component_selection_tool
        Why: Provides enum list for strict tool schema validation.
        """
        paths = set()
        
        # Add top-level paths
        for path in self.data_paths.values():
            paths.add(path)
        
        # Add nested paths from data_schema
        for base_path, schema in self.data_schema.items():
            paths.add(base_path)
            if isinstance(schema, dict) and "properties" in schema:
                for prop in schema["properties"]:
                    paths.add(f"{base_path}/{prop}")
        
        # Add paths from widget_bindings
        for widget_rules in self.widget_bindings.values():
            if isinstance(widget_rules, dict):
                for key, value in widget_rules.items():
                    if isinstance(value, list):
                        paths.update(value)
                    elif isinstance(value, str) and value.startswith("/"):
                        paths.add(value)
        
        return sorted(paths)


def _parse_yaml_frontmatter(raw_content: str, file_path: Path) -> tuple[Dict[str, Any], str]:
    """Parse YAML frontmatter from markdown content."""
    if not raw_content.startswith("---"):
        raise ValueError(f"Skill file missing YAML frontmatter: {file_path}")

    parts = raw_content.split("---", 2)
    if len(parts) < 3:
        raise ValueError(f"Skill file has incomplete frontmatter: {file_path}")

    frontmatter = parts[1].strip()
    body = parts[2].lstrip("\n")
    meta = yaml.safe_load(frontmatter) or {}
    return meta, body


def _parse_widgets(widgets_raw: Any, file_path: Path) -> List[str]:
    """Parse widgets field which can be a list or string."""
    if isinstance(widgets_raw, str):
        return [widgets_raw]
    elif isinstance(widgets_raw, Iterable):
        return [str(item) for item in widgets_raw]
    else:
        raise ValueError(f"Skill file widgets must be list or string: {file_path}")


def _parse_list_field(field_raw: Any) -> List[str]:
    """Parse a field that should be a list of strings."""
    if isinstance(field_raw, str):
        return [field_raw]
    elif isinstance(field_raw, Iterable):
        return [str(item) for item in field_raw]
    return []


def load_claude_skill(skill_dir: Path) -> A2UISkillMeta:
    """
    Parse a skill from the official Claude Agent Skills format.
    
    Expected structure:
    .claude/skills/<skill-name>/
        skill.md          # Required: skill definition
        claude_assets/    # Optional: additional assets
            layout.json   # Optional: A2UI layout configuration
    
    The skill.md frontmatter uses:
    - name: skill name (matches directory name, hyphenated)
    - description: skill description
    - tools: list of tools the skill uses
    """
    skill_md_path = skill_dir / "skill.md"
    if not skill_md_path.exists():
        raise ValueError(f"Missing skill.md in skill directory: {skill_dir}")

    raw = skill_md_path.read_text(encoding="utf-8")
    meta, body = _parse_yaml_frontmatter(raw, skill_md_path)

    # Claude Agent Skills uses 'name' field for the skill name (hyphenated)
    name_raw = str(meta.get("name", "")).strip()
    if not name_raw:
        raise ValueError(f"Skill file missing name: {skill_md_path}")
    
    # Convert hyphenated name to skill_id format (a2ui_<name> with underscores)
    # e.g., "a2ui-explain-move" -> "a2ui_explain_move"
    skill_id = name_raw.replace("-", "_")
    
    # For display, convert to Title Case
    name_display = name_raw.replace("a2ui-", "").replace("-", " ").title()
    
    description = str(meta.get("description", "")).strip()
    if not description:
        raise ValueError(f"Skill file missing description: {skill_md_path}")
    
    # Tools is a new field in Claude Agent Skills format
    tools = _parse_list_field(meta.get("tools", []))

    # Try to load layout configuration from claude_assets/layout.json
    layout_config = None
    layout_json_path = skill_dir / "claude_assets" / "layout.json"
    if layout_json_path.exists():
        try:
            with open(layout_json_path, "r", encoding="utf-8") as f:
                layout_config = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load layout.json for {skill_dir}: {e}")

    # Extract A2UI-specific fields from layout_config or use defaults
    if layout_config:
        widgets = layout_config.get("widgets", [])
        layout = layout_config.get("layout", "standard")
        layout_variants = layout_config.get("layout_variants", [layout])
        default_variant = layout_config.get("default_variant", layout)
        # Use skill_id from layout.json if present (canonical)
        if layout_config.get("skill_id"):
            skill_id = layout_config["skill_id"]
    else:
        # Fallback defaults
        widgets = []
        layout = "standard"
        layout_variants = ["standard"]
        default_variant = "standard"

    return A2UISkillMeta(
        skill_id=skill_id,
        name=name_display,
        description=description,
        widgets=widgets,
        layout=layout,
        layout_variants=layout_variants,
        default_variant=default_variant,
        source_path=skill_md_path,
        body=body,
        tools=tools,
        layout_config=layout_config,
    )


def load_legacy_skills(directory: Path | None = None) -> List[A2UISkillMeta]:
    """Legacy loader removed after full SDK adoption."""
    raise RuntimeError("Legacy skill format is no longer supported.")


def load_claude_skills(directory: Path | None = None) -> List[A2UISkillMeta]:
    """Load all skills from .claude/skills/ directory."""
    directory = directory or _CLAUDE_SKILLS_DIR
    if not directory.exists():
        return []
    
    skills = []
    for skill_dir in sorted(directory.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "skill.md"
        if skill_md.exists():
            try:
                skills.append(load_claude_skill(skill_dir))
            except Exception as e:
                logger.warning(f"Failed to load skill from {skill_dir}: {e}")
    
    return skills


def load_all_skills() -> List[A2UISkillMeta]:
    """
    Load skills from .claude/skills/ directory only (authoritative source).
    """
    claude_skills = load_claude_skills()
    if claude_skills:
        logger.info(f"Loaded {len(claude_skills)} skills from .claude/skills/")
        return claude_skills

    raise ValueError("No A2UI skills found in .claude/skills/")


@lru_cache(maxsize=1)
def get_a2ui_skills() -> List[A2UISkillMeta]:
    """Return cached list of parsed A2UI skills."""
    return load_all_skills()


def get_a2ui_skill(skill_id: str) -> A2UISkillMeta:
    """Fetch a single skill from the registry by skill_id."""
    for skill in get_a2ui_skills():
        if skill.skill_id == skill_id:
            return skill
    raise KeyError(f"Unknown A2UI skill_id: {skill_id}")


def build_a2ui_skill_catalog(skills: Sequence[A2UISkillMeta]) -> str:
    """
    Format skills into a compact catalog prompt for routing.
    
    Function: build_a2ui_skill_catalog - formats skill metadata for LLM selection.
    Called from: backend.generative_ui.agent_v2.A2UIAgent
    Invokes: n/a
    Why: Supplies the selection model with skill summaries including data path constraints.
    """
    lines = ["A2UI Skill Catalog:"]
    for skill in skills:
        lines.append(f"\n## {skill.name} ({skill.skill_id})")
        lines.append(f"Description: {skill.description}")
        lines.append(f"Widgets: {', '.join(skill.widgets)}")
        lines.append(f"Layout: {skill.layout}")
        if skill.layout_variants:
            lines.append(f"Layout Variants: {', '.join(skill.layout_variants)}")
        if skill.tools:
            lines.append(f"Tools: {', '.join(skill.tools)}")
        
        # Include data paths for LLM component selection context
        if skill.data_paths:
            lines.append("\nData Paths Available:")
            for name, path in skill.data_paths.items():
                lines.append(f"  - {name}: {path}")
        
        # Include data schema summary
        if skill.data_schema:
            lines.append("\nData Schema:")
            for path, schema in skill.data_schema.items():
                if isinstance(schema, dict) and "properties" in schema:
                    props = list(schema["properties"].keys())
                    lines.append(f"  {path}: {', '.join(props)}")
        
        # Include widget binding rules
        if skill.widget_bindings:
            lines.append("\nWidget Binding Rules:")
            for widget, rules in skill.widget_bindings.items():
                if isinstance(rules, dict):
                    for prop, paths in rules.items():
                        if isinstance(paths, list) and paths:
                            lines.append(f"  {widget}.{prop}: {paths}")
                        elif isinstance(paths, str):
                            lines.append(f"  {widget}.{prop}: {paths}")
    
    return "\n".join(lines)


__all__ = [
    "A2UISkillMeta",
    "load_claude_skill",
    "load_claude_skills",
    "load_all_skills",
    "get_a2ui_skills",
    "get_a2ui_skill",
    "build_a2ui_skill_catalog",
]
