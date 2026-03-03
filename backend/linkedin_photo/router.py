from typing import Dict

from fastapi import APIRouter, File, Form, UploadFile, Request, HTTPException

try:
    from rate_limiter import smart_rate_limit, RateLimitScope, who_am_i, redis_pool, is_superuser
except ImportError:  # pragma: no cover - support module execution
    from ..rate_limiter import smart_rate_limit, RateLimitScope, who_am_i, redis_pool, is_superuser  # type: ignore
from .schemas import LinkedInPhotoResponse, PhotoAnalysisResponse
from .service import LinkedInPhotoService
from .fixed_prompts import load_fixed_prompts

# --- Function/Class Map ---
# Function: list_linkedin_prompts — called by frontend preset loader; returns canonical style prompts.
# Function: generate_linkedin_photo — called by POST /generate; enforces auth + credits, rate limits, then delegates to LinkedInPhotoService.generate.
# Function: generate_linkedin_photo_variation — called by POST /variation; enforces auth + credits, rate limits, then delegates to LinkedInPhotoService.generate_variation.
# Function: get_linkedin_credits — used by frontend to show remaining lifetime LinkedIn photo credits for authenticated users.
# Helper: _require_authenticated_user — ensures Supabase JWT present; returns user id.
# Helper: _get_credit_usage/_consume_credit_if_available — Redis/in-memory tracking of lifetime 2-credit allowance.
# Purpose: API surface for LinkedIn photo generation with auth gating, quota enforcement, and preset hydration.

router = APIRouter(prefix="/api/headshot-studio", tags=["headshot-studio"])
service = LinkedInPhotoService()
LINKEDIN_PROMPT_WEIGHT = 10
LINKEDIN_CREDIT_LIMIT = 2
LINKEDIN_FOLLOW_URL = "https://www.linkedin.com/in/jiangyanqing/"

_in_memory_credits: Dict[str, int] = {}


def _credit_key(user_id: str) -> str:
    return f"headshot-studio:credits:{user_id}"


async def _require_authenticated_user(request: Request) -> str:
    identifier = await who_am_i(request)
    if identifier.startswith("ip:"):
        raise HTTPException(
            status_code=401,
            detail="Sign in to generate or edit LinkedIn photos.",
        )
    return identifier.split("user:", 1)[-1] if ":" in identifier else identifier


async def _get_credit_usage(user_id: str) -> int:
    if redis_pool is not None:
        try:
            raw = await redis_pool.get(_credit_key(user_id))
            return int(raw) if raw is not None else 0
        except Exception as exc:  # pragma: no cover - network issues
            print(f"[LINKEDIN_CREDITS] Redis get failed: {exc}")
    return _in_memory_credits.get(user_id, 0)


async def _consume_credit_if_available(user_id: str) -> None:
    used = await _get_credit_usage(user_id)
    if used >= LINKEDIN_CREDIT_LIMIT:
        raise HTTPException(
            status_code=403,
            detail=(
                "You've used all available LinkedIn photo credits. "
                f"Follow Yanqing on LinkedIn ({LINKEDIN_FOLLOW_URL}) to get more credits."
            ),
        )

    new_used = used + 1

    if redis_pool is not None:
        try:
            await redis_pool.set(_credit_key(user_id), new_used)
            return
        except Exception as exc:  # pragma: no cover - network issues
            print(f"[LINKEDIN_CREDITS] Redis set failed, falling back: {exc}")

    _in_memory_credits[user_id] = new_used


async def _get_credit_response(user_id: str) -> Dict[str, int]:
    used = await _get_credit_usage(user_id)
    remaining = max(0, LINKEDIN_CREDIT_LIMIT - used)
    return {
        "used": used,
        "remaining": remaining,
        "limit": LINKEDIN_CREDIT_LIMIT,
    }


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


@router.get(
    "/credits",
    summary="Get remaining LinkedIn photo credits for the authenticated user",
)
async def get_linkedin_credits(request: Request) -> Dict[str, int]:
    user_id = await _require_authenticated_user(request)
    if is_superuser(request):
        return {"used": 0, "remaining": 999999, "limit": 999999}
    return await _get_credit_response(user_id)


@router.post(
    "/analyze",
    response_model=PhotoAnalysisResponse,
    summary="Analyze a portrait for LinkedIn-readiness",
)
async def analyze_photo(
    request: Request,
    photo: UploadFile = File(..., description="Portrait image to analyze (JPEG or PNG)"),
) -> PhotoAnalysisResponse:
    """
    Analyze an uploaded portrait and return quality scores for LinkedIn-readiness.

    This powers the AI Quality Scorecard feature, providing scores for lighting,
    angle, background, expression, and overall professional readiness.
    """
    await smart_rate_limit(request, scope=RateLimitScope.GLOBAL, weight=2)
    return await service.analyze_photo(photo)


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
    user_id = await _require_authenticated_user(request)
    await smart_rate_limit(request, scope=RateLimitScope.GLOBAL, weight=LINKEDIN_PROMPT_WEIGHT)
    response = await service.generate(photo, prompt, prompt_mode=prompt_mode)
    if not is_superuser(request):
        await _consume_credit_if_available(user_id)
    return response


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
    user_id = await _require_authenticated_user(request)
    await smart_rate_limit(request, scope=RateLimitScope.GLOBAL, weight=LINKEDIN_PROMPT_WEIGHT)
    response = await service.generate_variation(
        photo,
        base_prompt,
        background=background,
        expression=expression,
        pose=pose,
        prop=prop,
    )
    if not is_superuser(request):
        await _consume_credit_if_available(user_id)
    return response
