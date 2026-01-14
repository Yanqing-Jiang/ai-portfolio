"""
Native Agent Skills client wrapper for Anthropic beta API.

Function: NativeSkillsClient — Wraps Anthropic beta API with container.skills support.
Called from: ConversationalAnalyticsAgent.run_with_tools (when native skills enabled).
Invokes: anthropic.beta.messages.stream with skills-2025 beta headers.
Purpose: Enables Claude-native skill routing without hardcoded keyword detection.

Updated to use SkillManager for uploading skills to Anthropic before use.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import anthropic
except ImportError:
    anthropic = None  # type: ignore

from .skills.native_registry import (
    NativeSkill,
    get_native_skills,
    get_native_skill_by_id,
    load_all_native_skills,
    CLAUDE_SKILLS_DIR,
)
from .config import settings

# Import SkillManager for uploading skills to Anthropic
try:
    from shared.skill_manager import SkillManager, get_skill_manager
except ImportError:
    # Fallback if shared module not available
    SkillManager = None  # type: ignore
    get_skill_manager = None  # type: ignore

logger = logging.getLogger(__name__)

# Beta headers for Agent Skills (December 2025)
# These enable the container.skills field in the Messages API
SKILLS_BETA_HEADERS = [
    "skills-2025-10-02",           # Enables Agent Skills
    "code-execution-2025-08-25",   # Required for skills execution
    "files-api-2025-04-14",        # Required for file handling
]

# Code execution tool required by Skills beta API
# This must be included in every request that uses container.skills
# The type must match the beta header version (code-execution-2025-08-25 -> code_execution_20250825)
CODE_EXECUTION_TOOL = {
    "type": "code_execution_20250825",
    "name": "code_execution",
}


@dataclass
class SkillUseInfo:
    """Information about which skill was used in a response."""
    skill_id: str
    skill_name: str
    used: bool


class NativeSkillsClient:
    """
    Client for Anthropic API with native Agent Skills support.
    
    Function: NativeSkillsClient — Manages native skills API calls with beta headers.
    Called from: ConversationalAnalyticsAgent when use_native_skills is enabled.
    Invokes: anthropic.Anthropic.beta.messages.stream with container.skills.
    Purpose: Enables Claude to autonomously route to skills based on descriptions
             without hardcoded keyword matching in the backend.
    
    Usage:
        client = NativeSkillsClient(api_key="sk-ant-...")
        
        # Streaming with native skills
        with client.stream_with_skills(
            messages=messages,
            system=system_prompt,
            tools=tools,
        ) as stream:
            for event in stream:
                # Handle streaming events
                pass
            response = stream.get_final_message()
        
        # Extract which skill was used
        skill_id = client.extract_skill_from_response(response)
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        skills_dir: Optional[str] = None,
    ):
        """
        Initialize the native skills client.

        Args:
            api_key: Anthropic API key (defaults to settings.claude_api_key)
            model: Model to use (defaults to settings.claude_model)
            skills_dir: Override skills directory (defaults to .claude/skills/)
        """
        if anthropic is None:
            raise RuntimeError(
                "Native Skills Client requires the 'anthropic' package. "
                "Install with: pip install anthropic>=0.40.0"
            )

        self.api_key = api_key or settings.claude_api_key
        self.model = model or settings.claude_model
        self.client = anthropic.Anthropic(api_key=self.api_key)

        # Initialize skill manager for uploading skills to Anthropic
        self.skill_manager: Optional[SkillManager] = None
        self._skills_uploaded = False
        self._anthropic_skill_ids: Dict[str, str] = {}  # local_id -> anthropic_id

        skills_path = Path(skills_dir) if skills_dir else CLAUDE_SKILLS_DIR

        if SkillManager is not None:
            try:
                self.skill_manager = SkillManager(
                    api_key=self.api_key,
                    skills_dir=skills_path,
                )
                logger.info("SkillManager initialized for skill uploads")
            except Exception as e:
                logger.warning(f"Failed to initialize SkillManager: {e}")
                self.skill_manager = None

        # Load skills from directory (for local metadata)
        if skills_dir:
            self.skills = load_all_native_skills(skills_path, prefix_filter=None)
        else:
            self.skills = get_native_skills()

        # Build skill ID to skill mapping for quick lookup
        self._skill_map: Dict[str, NativeSkill] = {
            skill.skill_id: skill for skill in self.skills
        }

        logger.info(
            f"NativeSkillsClient initialized with {len(self.skills)} skills: "
            f"{[s.skill_id for s in self.skills]}"
        )

    async def upload_skills(self) -> Dict[str, str]:
        """
        Upload all skills to Anthropic.

        Function: upload_skills — Uploads skills via SkillManager.
        Called from: NativeSkillsClient.stream_with_skills (on first use).
        Invokes: SkillManager.upload_all_skills.
        Purpose: Skills must be uploaded before use in container.skills.

        Returns:
            Dict mapping local_id -> anthropic_id
        """
        if self._skills_uploaded:
            return self._anthropic_skill_ids

        if self.skill_manager is None:
            logger.warning("SkillManager not available, skills won't be uploaded")
            self._skills_uploaded = True
            return {}

        try:
            self._anthropic_skill_ids = await self.skill_manager.upload_all_skills()
            self._skills_uploaded = True
            logger.info(f"Uploaded {len(self._anthropic_skill_ids)} skills to Anthropic")
            return self._anthropic_skill_ids
        except Exception as e:
            logger.error(f"Failed to upload skills: {e}")
            self._skills_uploaded = True
            return {}

    def _ensure_skills_uploaded(self) -> None:
        """Synchronously ensure skills are uploaded (for sync API calls)."""
        if not self._skills_uploaded and self.skill_manager is not None:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Already in async context, create a task
                    asyncio.create_task(self.upload_skills())
                else:
                    loop.run_until_complete(self.upload_skills())
            except RuntimeError:
                # No event loop, create one
                asyncio.run(self.upload_skills())
    
    def _build_container_skills(self) -> List[Dict[str, Any]]:
        """
        Build container.skills array for API call.

        Uses Anthropic skill IDs from SkillManager if available,
        otherwise falls back to local skill IDs (which won't work without upload).

        Returns format: [{"type": "custom", "skill_id": "sk_xxx", "version": "latest"}, ...]
        """
        # Ensure skills are uploaded before building container
        self._ensure_skills_uploaded()

        container_skills = []
        for skill in self.skills:
            local_id = skill.skill_id

            # Use uploaded Anthropic ID if available
            if local_id in self._anthropic_skill_ids:
                container_skills.append({
                    "type": "custom",
                    "skill_id": self._anthropic_skill_ids[local_id],
                    "version": "latest",
                })
            else:
                # Fallback to local ID (won't work without upload)
                logger.warning(f"Skill {local_id} not uploaded, using local ID")
                container_skills.append(skill.to_container_skill())

        return container_skills
    
    def get_skill_by_id(self, skill_id: str) -> Optional[NativeSkill]:
        """Look up a skill by its ID."""
        return self._skill_map.get(skill_id)
    
    @property
    def skill_ids(self) -> List[str]:
        """Get list of all loaded skill IDs."""
        return list(self._skill_map.keys())
    
    def stream_with_skills(
        self,
        messages: List[Dict[str, Any]],
        system: Any,  # Can be string or list of content blocks
        tools: List[Dict[str, Any]],
        max_tokens: int = 4096,
    ):
        """
        Stream a message with native skills support.
        
        Function: stream_with_skills — Creates streaming API call with container.skills.
        Called from: ConversationalAnalyticsAgent._run_with_native_skills.
        Invokes: anthropic.beta.messages.stream with beta headers.
        Purpose: Enables Claude to autonomously select skills based on descriptions.
        
        Args:
            messages: Conversation messages
            system: System prompt (string or list of content blocks)
            tools: Tool definitions
            max_tokens: Maximum tokens in response
        
        Returns:
            Context manager for streaming response
        
        Example:
            with client.stream_with_skills(...) as stream:
                for event in stream:
                    if hasattr(event, 'delta') and hasattr(event.delta, 'text'):
                        yield content_event(event.delta.text)
                response = stream.get_final_message()
        """
        container_skills = self._build_container_skills()
        
        # Skills beta requires code_execution tool to be present
        tools_with_code_exec = list(tools) + [CODE_EXECUTION_TOOL]
        
        logger.debug(
            f"Calling beta.messages.stream with {len(container_skills)} skills, "
            f"{len(tools_with_code_exec)} tools (including code_execution), model={self.model}"
        )
        
        return self.client.beta.messages.stream(
            model=self.model,
            max_tokens=max_tokens,
            betas=SKILLS_BETA_HEADERS,
            container={
                "skills": container_skills,
            },
            system=system,
            tools=tools_with_code_exec,
            messages=messages,
        )
    
    def create_with_skills(
        self,
        messages: List[Dict[str, Any]],
        system: Any,
        tools: List[Dict[str, Any]],
        max_tokens: int = 4096,
    ) -> Any:
        """
        Create a message (non-streaming) with native skills support.
        
        Args:
            messages: Conversation messages
            system: System prompt
            tools: Tool definitions
            max_tokens: Maximum tokens in response
        
        Returns:
            anthropic.types.Message response
        """
        container_skills = self._build_container_skills()
        
        # Skills beta requires code_execution tool to be present
        tools_with_code_exec = list(tools) + [CODE_EXECUTION_TOOL]
        
        return self.client.beta.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            betas=SKILLS_BETA_HEADERS,
            container={
                "skills": container_skills,
            },
            system=system,
            tools=tools_with_code_exec,
            messages=messages,
        )
    
    def extract_skill_from_response(self, response: Any) -> Optional[str]:
        """
        Extract the skill ID from response metadata.
        
        Function: extract_skill_from_response — Gets skill ID from native API response.
        Called from: ConversationalAnalyticsAgent after streaming completes.
        Invokes: Response object attribute inspection.
        Purpose: Reliably detects which skill Claude used without text parsing.
        
        With native skills, Claude includes skill usage information in the response
        metadata rather than requiring text parsing of [SKILL:] markers.
        
        Args:
            response: The Message response from Claude
        
        Returns:
            skill_id if a skill was used, None otherwise
        """
        # Check for skill_use in response (native skills API structure)
        # Note: The exact field name may vary - we check multiple possibilities
        
        # Option 1: Direct skill_use attribute
        if hasattr(response, 'skill_use') and response.skill_use:
            skill_use = response.skill_use
            if hasattr(skill_use, 'skill_id'):
                return skill_use.skill_id
            if isinstance(skill_use, dict):
                return skill_use.get('skill_id')
        
        # Option 2: Check content blocks for skill_use type
        if hasattr(response, 'content'):
            for block in response.content:
                if hasattr(block, 'type') and block.type == 'skill_use':
                    return getattr(block, 'skill_id', None)
        
        # Option 3: Check metadata
        if hasattr(response, 'metadata'):
            metadata = response.metadata
            if isinstance(metadata, dict) and 'skill_id' in metadata:
                return metadata['skill_id']
        
        # Option 4: Fallback to text parsing for backward compatibility
        # This handles the case where native skills aren't available
        if hasattr(response, 'content'):
            import re
            for block in response.content:
                if hasattr(block, 'text'):
                    match = re.search(r'\[SKILL:\s*(\w+)\]', block.text)
                    if match:
                        return match.group(1)
        
        return None
    
    def get_skill_info(self, skill_id: str) -> Optional[SkillUseInfo]:
        """
        Get displayable information about a skill.
        
        Args:
            skill_id: The skill ID
        
        Returns:
            SkillUseInfo with display name and metadata
        """
        skill = self.get_skill_by_id(skill_id)
        if not skill:
            return None
        
        return SkillUseInfo(
            skill_id=skill.skill_id,
            skill_name=skill.name,
            used=True,
        )


def create_native_skills_client(
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> NativeSkillsClient:
    """
    Factory function to create a NativeSkillsClient.
    
    Args:
        api_key: Anthropic API key (defaults to settings)
        model: Model to use (defaults to settings)
    
    Returns:
        Configured NativeSkillsClient instance
    """
    return NativeSkillsClient(
        api_key=api_key,
        model=model,
    )


__all__ = [
    "NativeSkillsClient",
    "SkillUseInfo",
    "create_native_skills_client",
    "SKILLS_BETA_HEADERS",
    "CODE_EXECUTION_TOOL",
]
