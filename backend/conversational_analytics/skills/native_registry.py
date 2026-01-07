"""
Native Agent Skills registry for Anthropic API container.skills field.

Function: NativeSkillRegistry — Loads and manages skills from .claude/skills/ directory.
Called from: NativeSkillsClient to build container.skills array for API calls.
Invokes: yaml.safe_load for parsing skill.md frontmatter.
Purpose: Enables Claude-native skill routing without hardcoded keyword detection.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

logger = logging.getLogger(__name__)

# Project root and skills directory
PROJECT_ROOT = Path(__file__).resolve().parents[3]
CLAUDE_SKILLS_DIR = PROJECT_ROOT / ".claude" / "skills"


@dataclass
class NativeSkill:
    """
    Represents a skill for the container.skills API.
    
    Function: NativeSkill — Data container for skill metadata and content.
    Called from: NativeSkillRegistry.load_skills
    Purpose: Holds skill information for API requests and UI display.
    """
    skill_id: str
    name: str
    description: str
    source_path: Path
    tools: List[str] = field(default_factory=list)
    version: Optional[str] = None
    
    def to_container_skill(self) -> Dict[str, Any]:
        """
        Convert to container.skills format for Anthropic API.
        
        Returns format expected by client.beta.messages.create(container={skills: [...]})
        """
        skill_dict: Dict[str, Any] = {
            "type": "custom",
            "skill_id": self.skill_id,
        }
        if self.version:
            skill_dict["version"] = self.version
        return skill_dict
    
    def load_content(self) -> str:
        """Load full skill.md content for display or code execution context."""
        return self.source_path.read_text(encoding="utf-8")
    
    def load_instructions(self) -> str:
        """Load skill content without YAML frontmatter (just instructions)."""
        content = self.load_content()
        return _strip_yaml_frontmatter(content)


def _parse_yaml_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
    """
    Parse YAML frontmatter from skill markdown content.
    
    Returns: (frontmatter_dict, remaining_content)
    """
    if not content.startswith("---"):
        return {}, content
    
    # Find the closing ---
    end_idx = content.find("---", 3)
    if end_idx == -1:
        return {}, content
    
    yaml_block = content[3:end_idx].strip()
    remaining = content[end_idx + 3:].strip()
    
    try:
        frontmatter = yaml.safe_load(yaml_block) or {}
    except yaml.YAMLError as e:
        logger.warning(f"Failed to parse YAML frontmatter: {e}")
        frontmatter = {}
    
    return frontmatter, remaining


def _strip_yaml_frontmatter(content: str) -> str:
    """Remove YAML frontmatter from content, returning just the body."""
    _, body = _parse_yaml_frontmatter(content)
    return body


def _extract_skill_id(frontmatter: Dict[str, Any], file_path: Path) -> str:
    """
    Extract skill_id from frontmatter or derive from filename.
    
    Priority:
    1. 'name' field in frontmatter (converted to snake_case)
    2. Filename without extension (converted to snake_case)
    """
    name = frontmatter.get("name", "")
    if name:
        # Convert hyphenated name to snake_case skill_id
        return re.sub(r"[- ]", "_", name.lower())
    
    # Fallback to filename
    filename = file_path.stem
    if filename.startswith("skill_"):
        return filename[6:]  # Remove "skill_" prefix
    return filename.replace("-", "_")


def _extract_display_name(frontmatter: Dict[str, Any], skill_id: str) -> str:
    """Extract display name from frontmatter or derive from skill_id."""
    name = frontmatter.get("name", "")
    if name:
        # Convert to Title Case for display
        return name.replace("_", " ").replace("-", " ").title()
    
    # Derive from skill_id
    return skill_id.replace("_", " ").title()


def load_skill_from_file(skill_path: Path) -> Optional[NativeSkill]:
    """
    Load a skill from a flat .md file (e.g., skill_revenue_growth.md).
    
    Function: load_skill_from_file — Parses a single skill.md file.
    Called from: load_all_native_skills
    Invokes: yaml.safe_load for frontmatter parsing.
    Purpose: Supports both flat files and nested directory skills.
    """
    if not skill_path.exists() or not skill_path.suffix == ".md":
        return None
    
    try:
        content = skill_path.read_text(encoding="utf-8")
        frontmatter, _ = _parse_yaml_frontmatter(content)
        
        if not frontmatter:
            logger.warning(f"Skill file missing YAML frontmatter: {skill_path}")
            return None
        
        if "description" not in frontmatter:
            logger.warning(f"Skill file missing description in frontmatter: {skill_path}")
            return None
        
        skill_id = _extract_skill_id(frontmatter, skill_path)
        display_name = _extract_display_name(frontmatter, skill_id)
        
        # Parse tools list
        tools_raw = frontmatter.get("tools", [])
        if isinstance(tools_raw, str):
            tools = [tools_raw]
        elif isinstance(tools_raw, list):
            tools = [str(t) for t in tools_raw]
        else:
            tools = []
        
        return NativeSkill(
            skill_id=skill_id,
            name=display_name,
            description=frontmatter.get("description", ""),
            source_path=skill_path,
            tools=tools,
            version=frontmatter.get("version"),
        )
    except Exception as e:
        logger.error(f"Failed to load skill from {skill_path}: {e}")
        return None


def load_skill_from_directory(skill_dir: Path) -> Optional[NativeSkill]:
    """
    Load a skill from a directory containing skill.md (official format).
    
    Expected structure:
    .claude/skills/<skill-name>/
        skill.md          # Required
        claude_assets/    # Optional
    """
    skill_md = skill_dir / "skill.md"
    if not skill_md.exists():
        return None
    
    return load_skill_from_file(skill_md)


def load_all_native_skills(
    skills_dir: Optional[Path] = None,
    prefix_filter: Optional[str] = None,
) -> List[NativeSkill]:
    """
    Load all native skills from .claude/skills/ directory.
    
    Function: load_all_native_skills — Loads all skills for conversational analytics.
    Called from: NativeSkillsClient initialization, get_native_skills.
    Invokes: load_skill_from_file and load_skill_from_directory.
    Purpose: Populates the skill registry for API container.skills field.
    
    Args:
        skills_dir: Override skills directory (default: .claude/skills/)
        prefix_filter: Only load skills whose filename starts with this prefix
                      (e.g., "skill_" for conv analytics flat files)
    
    Returns: List of NativeSkill objects
    """
    skills_dir = skills_dir or CLAUDE_SKILLS_DIR
    if not skills_dir.exists():
        logger.warning(f"Skills directory does not exist: {skills_dir}")
        return []
    
    skills: List[NativeSkill] = []
    
    for item in sorted(skills_dir.iterdir()):
        # Skip A2UI skills (they have their own loader)
        if item.name.startswith("a2ui-"):
            continue
        
        # Handle flat .md files (e.g., skill_revenue_growth.md)
        if item.is_file() and item.suffix == ".md":
            if prefix_filter and not item.name.startswith(prefix_filter):
                continue
            
            skill = load_skill_from_file(item)
            if skill:
                skills.append(skill)
        
        # Handle nested directories (e.g., revenue-growth/skill.md)
        elif item.is_dir():
            if prefix_filter:
                continue  # Skip directories when using prefix filter
            
            skill = load_skill_from_directory(item)
            if skill:
                skills.append(skill)
    
    logger.info(f"Loaded {len(skills)} native skills from {skills_dir}")
    return skills


@lru_cache(maxsize=1)
def get_native_skills() -> List[NativeSkill]:
    """
    Get cached list of native skills for conversational analytics.
    
    Only loads flat file skills (skill_*.md) to avoid A2UI skills.
    """
    return load_all_native_skills(prefix_filter="skill_")


def get_native_skill_by_id(skill_id: str) -> Optional[NativeSkill]:
    """Look up a skill by its ID."""
    for skill in get_native_skills():
        if skill.skill_id == skill_id:
            return skill
    return None


def build_native_skill_descriptions() -> str:
    """
    Build a formatted catalog of skill descriptions for debugging/logging.
    
    Note: With native container.skills, Claude receives skill metadata
    automatically - this is just for visibility.
    """
    skills = get_native_skills()
    lines = ["Native Skills Catalog:", ""]
    
    for skill in skills:
        lines.append(f"### {skill.name}")
        lines.append(f"**ID**: `{skill.skill_id}`")
        lines.append(f"**Tools**: {', '.join(skill.tools) if skill.tools else 'None'}")
        lines.append(f"**Description**:")
        lines.append(skill.description)
        lines.append("")
    
    return "\n".join(lines)


__all__ = [
    "NativeSkill",
    "load_all_native_skills",
    "get_native_skills",
    "get_native_skill_by_id",
    "build_native_skill_descriptions",
    "CLAUDE_SKILLS_DIR",
]
