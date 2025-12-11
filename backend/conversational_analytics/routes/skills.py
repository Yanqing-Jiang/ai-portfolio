"""Skill routes for Conversational Analytics."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse

from ..skills import SKILL_INDEX
from rate_limiter import conversational_analytics_rate_limit

router = APIRouter(prefix="/api/conv-analytics/skills", tags=["conversational-analytics-skills"])


def _find_skill(skill_id: str):
    """Function: _find_skill — locate a skill by id."""
    for skill in SKILL_INDEX:
        if skill.skill_id == skill_id:
            return skill
    return None


@router.get("")
async def list_skills(_: None = Depends(conversational_analytics_rate_limit)):
    """Function: list_skills — returns basic metadata for available skills."""
    return [
        {
            "id": skill.skill_id,
            "name": skill.name,
            "description": skill.description,
            "download_url": f"/api/conv-analytics/skills/{skill.skill_id}",
        }
        for skill in SKILL_INDEX
    ]


@router.get("/{skill_id}")
async def download_skill(skill_id: str, _: None = Depends(conversational_analytics_rate_limit)):
    """Function: download_skill — serves the skill markdown for transparency/download."""
    skill = _find_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    return FileResponse(
        path=skill.path,
        media_type="text/markdown",
        filename=f"{skill.skill_id}.md",
    )


@router.get("/showcase")
async def serve_showcase(_: None = Depends(conversational_analytics_rate_limit)):
    """Function: serve_showcase — called from the showcase tool and frontend to deliver the static project showcase HTML.
    Called from: open_showcase_page tool and any direct browser hits to /api/conv-analytics/showcase.
    Invokes: FileResponse to stream the static HTML artifact.
    Purpose: Provide a safe, non-data endpoint for demos and architecture explanations."""
    static_path = Path(__file__).parent.parent / "static" / "showcase.html"
    if not static_path.exists():
        raise HTTPException(status_code=404, detail="Showcase not found")
    return FileResponse(path=static_path, media_type="text/html")

