from typing import Dict

from fastapi import APIRouter, File, Form, UploadFile, Request

try:
    from rate_limiter import smart_rate_limit, RateLimitScope
except ImportError:  # pragma: no cover - support module execution
    from ..rate_limiter import smart_rate_limit, RateLimitScope  # type: ignore
from .schemas import LinkedInPhotoResponse
from .service import LinkedInPhotoService
from .fixed_prompts import load_fixed_prompts

router = APIRouter(prefix="/api/linkedin-photo", tags=["linkedin-photo"])
service = LinkedInPhotoService()
LINKEDIN_PROMPT_WEIGHT = 10


@router.get(
    "/prompts",
    response_model=Dict[str, str],
    summary="List canonical LinkedIn photo style prompts",
)
async def list_linkedin_prompts() -> Dict[str, str]:
    """
    Provide the fixed style prompts used by the Professional, Creative, and Warm presets.

    Frontend clients can call this endpoint to hydrate their preset lists without hard-coding copies.
    """
    return load_fixed_prompts()


@router.post(
    "/generate",
    response_model=LinkedInPhotoResponse,
    summary="Generate a LinkedIn-ready headshot from a casual portrait",
)
async def generate_linkedin_photo(
    request: Request,
    photo: UploadFile = File(..., description="Reference portrait image (JPEG or PNG)"),
    prompt: str = Form(..., description="Short description of the desired LinkedIn style"),
    prompt_mode: str = Form(
        "auto",
        description="Prompt handling mode. Use 'fixed' to bypass LLM expansion when supplying a canonical preset.",
    ),
) -> LinkedInPhotoResponse:
    """
    Turn an uploaded portrait into a polished LinkedIn photo.

    The backend expands the user's prompt via LLM, invokes Gemini image generation,
    and returns both the transparent expanded prompt and the generated image bytes.
    """
    await smart_rate_limit(request, scope=RateLimitScope.GLOBAL, weight=LINKEDIN_PROMPT_WEIGHT)
    return await service.generate(photo, prompt, prompt_mode=prompt_mode)


@router.post(
    "/variation",
    response_model=LinkedInPhotoResponse,
    summary="Create a guided variation of an existing LinkedIn portrait",
)
async def generate_linkedin_photo_variation(
    request: Request,
    photo: UploadFile = File(..., description="Original reference portrait (JPEG or PNG)"),
    base_prompt: str = Form(..., description="Expanded prompt from a previous generation"),
    background: str = Form(
        "original",
        description="Background adjustment such as 'charcoal gradient' or 'keep original'.",
    ),
    expression: str = Form(
        "original",
        description="Facial expression guidance such as 'confident smile' or 'keep original'.",
    ),
    pose: str = Form(
        "original",
        description="Pose refinement such as 'three-quarter stance with arms crossed'.",
    ),
    prop: str = Form(
        "none",
        description="Optional prop interaction such as 'holding a tablet' or 'none'.",
    ),
) -> LinkedInPhotoResponse:
    """
    Apply structured adjustments to the previous expanded prompt and generate a single follow-up image.

    This keeps the LinkedIn-ready polish while letting designers iteratively nudge background, expression,
    pose, or props—mirroring the multi-turn workflows recommended in Gemini Nano Banana guidance.
    """
    await smart_rate_limit(request, scope=RateLimitScope.GLOBAL, weight=LINKEDIN_PROMPT_WEIGHT)
    return await service.generate_variation(
        photo,
        base_prompt,
        background=background,
        expression=expression,
        pose=pose,
        prop=prop,
    )
