# --- Skill Manager Function/Class Map ---
# Dataclass: SkillCacheEntry
#   Role: Store cached skill upload metadata (anthropic_id, version, hash).
#   Called from: SkillManager.get_cached_skills, SkillManager._save_cache
#   Why: Enables efficient cache persistence and lookup.
# Dataclass: SkillUploadResult
#   Role: Return result of skill upload operation.
#   Called from: SkillManager.upload_skill
#   Why: Provides structured response with anthropic_id and version.
# Class: SkillManager
#   Role: Upload and manage skills with Anthropic's Native Skills API.
#   Called from: conversational_analytics.native_skills_client, generative_ui.agent_v2
#   Invokes: anthropic.beta.skills.create, anthropic.beta.skills.list
#   Why: Centralized skill upload/cache infrastructure for both projects.
# Function: get_skill_manager
#   Role: Singleton factory for SkillManager.
#   Called from: conversational_analytics.native_skills_client, generative_ui.agent_v2
#   Why: Reuse single manager instance across requests.
# --- End Skill Manager Function/Class Map ---
"""
Skill Manager for Anthropic Native Skills API.

Handles uploading custom skills to Anthropic and caching their IDs.
Skills must be uploaded before they can be referenced in container.skills.

Usage:
    manager = get_skill_manager()
    await manager.upload_all_skills()
    anthropic_id = manager.get_anthropic_id("a2ui-explain-move")
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import anthropic
    from anthropic.lib import files_from_dir
except ImportError:
    anthropic = None  # type: ignore
    files_from_dir = None  # type: ignore

import yaml

logger = logging.getLogger(__name__)

# Beta headers for Skills API
SKILLS_BETA_HEADERS = ["skills-2025-10-02"]

# Default paths
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_SKILLS_DIR = _PROJECT_ROOT / ".claude" / "skills"
_DEFAULT_CACHE_PATH = _PROJECT_ROOT / ".claude" / ".skill_cache.json"


@dataclass
class SkillCacheEntry:
    """
    Cached skill upload metadata.

    Dataclass: SkillCacheEntry - stores anthropic_id, version, hash for cache lookup.
    Called from: SkillManager.get_cached_skills, SkillManager._save_cache
    Why: Enables efficient cache persistence without re-uploading unchanged skills.
    """
    anthropic_id: str
    version: str
    md5_hash: str
    uploaded_at: str
    display_title: str


@dataclass
class SkillUploadResult:
    """
    Result of skill upload operation.

    Dataclass: SkillUploadResult - returns anthropic_id and version after upload.
    Called from: SkillManager.upload_skill
    Why: Provides structured response for callers.
    """
    local_id: str
    anthropic_id: str
    version: str
    display_title: str
    was_cached: bool = False


class SkillManager:
    """
    Manager for uploading and caching skills with Anthropic's Native Skills API.

    Class: SkillManager - uploads skills via client.beta.skills.create().
    Called from: conversational_analytics.native_skills_client, generative_ui.agent_v2
    Invokes: anthropic.beta.skills.create, anthropic.beta.skills.list
    Why: Skills must be uploaded to Anthropic before use in container.skills.

    Usage:
        manager = SkillManager(api_key="sk-ant-...")
        await manager.upload_all_skills()

        # Get Anthropic ID for use in API calls
        anthropic_id = manager.get_anthropic_id("a2ui-explain-move")

        # Use in container.skills
        container = {
            "skills": [{"type": "custom", "skill_id": anthropic_id, "version": "latest"}]
        }
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        skills_dir: Optional[Path] = None,
        cache_path: Optional[Path] = None,
        auto_reupload: bool = True,
    ):
        """
        Initialize the skill manager.

        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            skills_dir: Directory containing skill subdirectories (defaults to .claude/skills/)
            cache_path: Path to cache file (defaults to .claude/.skill_cache.json)
            auto_reupload: Re-upload skills when SKILL.md changes (dev mode)
        """
        if anthropic is None:
            raise RuntimeError(
                "SkillManager requires the 'anthropic' package. "
                "Install with: pip install anthropic>=0.40.0"
            )

        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")
        if not self.api_key:
            raise ValueError("Anthropic API key required (set ANTHROPIC_API_KEY env var)")

        self.skills_dir = skills_dir or _DEFAULT_SKILLS_DIR
        self.cache_path = cache_path or Path(os.getenv("SKILLS_CACHE_PATH", str(_DEFAULT_CACHE_PATH)))
        self.auto_reupload = auto_reupload

        self._client = anthropic.Anthropic(api_key=self.api_key)
        self._cache: Dict[str, SkillCacheEntry] = {}
        self._local_to_anthropic: Dict[str, str] = {}  # local_id -> anthropic_id

        # Load cache from disk
        self._load_cache()

        logger.info(
            f"SkillManager initialized: skills_dir={self.skills_dir}, "
            f"cache_path={self.cache_path}, cached_skills={len(self._cache)}"
        )

    def _load_cache(self) -> None:
        """Load skill cache from disk."""
        if not self.cache_path.exists():
            logger.debug("No skill cache file found, starting fresh")
            return

        try:
            with open(self.cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            for local_id, entry_data in data.items():
                entry = SkillCacheEntry(**entry_data)
                self._cache[local_id] = entry
                self._local_to_anthropic[local_id] = entry.anthropic_id

            logger.info(f"Loaded {len(self._cache)} skills from cache")
        except Exception as e:
            logger.warning(f"Failed to load skill cache: {e}")

    def _save_cache(self) -> None:
        """Save skill cache to disk."""
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                local_id: asdict(entry)
                for local_id, entry in self._cache.items()
            }

            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            logger.debug(f"Saved {len(self._cache)} skills to cache")
        except Exception as e:
            logger.warning(f"Failed to save skill cache: {e}")

    def _compute_skill_hash(self, skill_dir: Path) -> str:
        """Compute MD5 hash of SKILL.md content for change detection."""
        skill_md_path = skill_dir / "SKILL.md"
        if not skill_md_path.exists():
            # Fallback to lowercase (pre-migration)
            skill_md_path = skill_dir / "skill.md"

        if not skill_md_path.exists():
            return ""

        content = skill_md_path.read_bytes()
        return hashlib.md5(content).hexdigest()

    def _parse_skill_metadata(self, skill_dir: Path) -> Dict[str, Any]:
        """Parse SKILL.md frontmatter for name and description."""
        skill_md_path = skill_dir / "SKILL.md"
        if not skill_md_path.exists():
            skill_md_path = skill_dir / "skill.md"

        if not skill_md_path.exists():
            raise ValueError(f"No SKILL.md found in {skill_dir}")

        content = skill_md_path.read_text(encoding="utf-8")

        if not content.startswith("---"):
            raise ValueError(f"SKILL.md missing YAML frontmatter: {skill_md_path}")

        parts = content.split("---", 2)
        if len(parts) < 3:
            raise ValueError(f"SKILL.md incomplete frontmatter: {skill_md_path}")

        frontmatter = yaml.safe_load(parts[1].strip()) or {}

        name = str(frontmatter.get("name", "")).strip()
        description = str(frontmatter.get("description", "")).strip()

        if not name:
            raise ValueError(f"SKILL.md missing name: {skill_md_path}")
        if not description:
            raise ValueError(f"SKILL.md missing description: {skill_md_path}")

        return {
            "name": name,
            "description": description,
            "display_title": name.replace("-", " ").title(),
        }

    def _needs_reupload(self, local_id: str, skill_dir: Path) -> bool:
        """Check if skill needs to be re-uploaded (hash changed)."""
        if not self.auto_reupload:
            return local_id not in self._cache

        if local_id not in self._cache:
            return True

        current_hash = self._compute_skill_hash(skill_dir)
        cached_hash = self._cache[local_id].md5_hash

        return current_hash != cached_hash

    async def upload_skill(self, skill_dir: Path) -> SkillUploadResult:
        """
        Upload a single skill to Anthropic.

        Function: upload_skill - uploads skill via client.beta.skills.create().
        Called from: SkillManager.upload_all_skills
        Invokes: anthropic.beta.skills.create with files_from_dir
        Why: Skills must be uploaded before use in container.skills.

        Args:
            skill_dir: Path to skill directory containing SKILL.md

        Returns:
            SkillUploadResult with anthropic_id and version
        """
        metadata = self._parse_skill_metadata(skill_dir)
        local_id = metadata["name"]

        # Check cache
        if not self._needs_reupload(local_id, skill_dir):
            cached = self._cache[local_id]
            logger.debug(f"Skill {local_id} unchanged, using cached ID: {cached.anthropic_id}")
            return SkillUploadResult(
                local_id=local_id,
                anthropic_id=cached.anthropic_id,
                version=cached.version,
                display_title=cached.display_title,
                was_cached=True,
            )

        logger.info(f"Uploading skill: {local_id} from {skill_dir}")

        try:
            # Upload to Anthropic
            if files_from_dir is None:
                raise RuntimeError("files_from_dir not available - update anthropic package")

            response = self._client.beta.skills.create(
                display_title=metadata["display_title"],
                files=files_from_dir(str(skill_dir)),
                betas=SKILLS_BETA_HEADERS,
            )

            anthropic_id = response.id
            version = str(response.latest_version) if hasattr(response, 'latest_version') else "latest"

            # Update cache
            entry = SkillCacheEntry(
                anthropic_id=anthropic_id,
                version=version,
                md5_hash=self._compute_skill_hash(skill_dir),
                uploaded_at=datetime.utcnow().isoformat(),
                display_title=metadata["display_title"],
            )
            self._cache[local_id] = entry
            self._local_to_anthropic[local_id] = anthropic_id
            self._save_cache()

            logger.info(f"Uploaded skill {local_id}: anthropic_id={anthropic_id}")

            return SkillUploadResult(
                local_id=local_id,
                anthropic_id=anthropic_id,
                version=version,
                display_title=metadata["display_title"],
                was_cached=False,
            )

        except Exception as e:
            logger.error(f"Failed to upload skill {local_id}: {e}")
            raise

    async def upload_all_skills(self) -> Dict[str, str]:
        """
        Upload all skills from the skills directory.

        Function: upload_all_skills - iterates skill dirs and uploads each.
        Called from: conversational_analytics.native_skills_client init
        Invokes: SkillManager.upload_skill for each skill directory
        Why: Ensures all skills are available before API calls.

        Returns:
            Dict mapping local_id -> anthropic_id
        """
        if not self.skills_dir.exists():
            logger.warning(f"Skills directory not found: {self.skills_dir}")
            return {}

        results: Dict[str, str] = {}

        for skill_dir in sorted(self.skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue

            # Skip CLI skills (agent-*, cli-*) - these are for Claude Code, not Anthropic API
            if skill_dir.name.startswith("agent-") or skill_dir.name.startswith("cli-"):
                logger.debug(f"Skipping CLI skill: {skill_dir.name}")
                continue

            # Check for SKILL.md or skill.md
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                skill_md = skill_dir / "skill.md"

            if not skill_md.exists():
                logger.debug(f"Skipping {skill_dir.name}: no SKILL.md found")
                continue

            try:
                result = await self.upload_skill(skill_dir)
                results[result.local_id] = result.anthropic_id
            except Exception as e:
                logger.error(f"Failed to upload skill from {skill_dir}: {e}")
                continue

        logger.info(f"Uploaded {len(results)} skills: {list(results.keys())}")
        return results

    def get_anthropic_id(self, local_id: str) -> str:
        """
        Get Anthropic skill ID for a local skill ID.

        Function: get_anthropic_id - looks up cached anthropic_id by local_id.
        Called from: native_skills_client._build_container_skills
        Why: Container.skills requires the Anthropic-assigned skill ID.

        Args:
            local_id: Local skill identifier (e.g., "a2ui-explain-move")

        Returns:
            Anthropic skill ID (e.g., "skill_01AbCdEfGhIjKlMnOpQrStUv")

        Raises:
            KeyError: If skill not found in cache
        """
        if local_id not in self._local_to_anthropic:
            raise KeyError(
                f"Skill '{local_id}' not found. "
                f"Available skills: {list(self._local_to_anthropic.keys())}. "
                "Run upload_all_skills() first."
            )
        return self._local_to_anthropic[local_id]

    def get_version(self, local_id: str) -> str:
        """Get cached version for a skill."""
        if local_id in self._cache:
            return self._cache[local_id].version
        return "latest"

    def get_cached_skills(self) -> Dict[str, SkillCacheEntry]:
        """Get all cached skill entries."""
        return dict(self._cache)

    def invalidate(self, local_id: str) -> None:
        """Remove a skill from cache to force re-upload."""
        if local_id in self._cache:
            del self._cache[local_id]
        if local_id in self._local_to_anthropic:
            del self._local_to_anthropic[local_id]
        self._save_cache()

    def invalidate_all(self) -> None:
        """Clear all cached skills."""
        self._cache.clear()
        self._local_to_anthropic.clear()
        self._save_cache()

    async def list_remote_skills(self) -> List[Dict[str, Any]]:
        """
        List all skills uploaded to Anthropic.

        Function: list_remote_skills - calls client.beta.skills.list().
        Called from: diagnostic/debugging tools
        Why: Verify which skills are available on Anthropic's side.
        """
        try:
            response = self._client.beta.skills.list(
                source="custom",
                betas=SKILLS_BETA_HEADERS,
            )

            return [
                {
                    "id": skill.id,
                    "display_title": skill.display_title,
                    "source": skill.source,
                    "created_at": str(skill.created_at) if hasattr(skill, 'created_at') else None,
                }
                for skill in response.data
            ]
        except Exception as e:
            logger.error(f"Failed to list remote skills: {e}")
            return []


# Singleton instance
_skill_manager_instance: Optional[SkillManager] = None


def get_skill_manager(
    api_key: Optional[str] = None,
    skills_dir: Optional[Path] = None,
) -> SkillManager:
    """
    Get or create the singleton SkillManager instance.

    Function: get_skill_manager - singleton factory for SkillManager.
    Called from: conversational_analytics.native_skills_client, generative_ui.agent_v2
    Why: Reuse single manager instance across requests.
    """
    global _skill_manager_instance

    if _skill_manager_instance is None:
        _skill_manager_instance = SkillManager(
            api_key=api_key,
            skills_dir=skills_dir,
        )

    return _skill_manager_instance


__all__ = [
    "SkillManager",
    "SkillUploadResult",
    "SkillCacheEntry",
    "get_skill_manager",
    "SKILLS_BETA_HEADERS",
]
