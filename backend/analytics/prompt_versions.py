from __future__ import annotations

from typing import Dict

# Central registry for prompt versioning so telemetry can surface changes.
_PROMPT_VERSIONS: Dict[str, str] = {
    "schema_clarifier": "2025-10-16",
    "multi_agent.supervisor": "2025-10-16",
}


def get_prompt_versions() -> Dict[str, str]:
    """Return a shallow copy of the prompt version registry."""
    return dict(_PROMPT_VERSIONS)

