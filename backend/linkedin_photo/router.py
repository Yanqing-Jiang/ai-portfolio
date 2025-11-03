from fastapi import APIRouter, File, Form, UploadFile

from .schemas import LinkedInPhotoResponse
from .service import LinkedInPhotoService

router = APIRouter(prefix="/api/linkedin-photo", tags=["linkedin-photo"])
service = LinkedInPhotoService()


@router.post(
    "/generate",
    response_model=LinkedInPhotoResponse,
    summary="Generate a LinkedIn-ready headshot from a casual portrait",
)
async def generate_linkedin_photo(
    photo: UploadFile = File(..., description="Reference portrait image (JPEG or PNG)"),
    prompt: str = Form(..., description="Short description of the desired LinkedIn style"),
) -> LinkedInPhotoResponse:
    """
    Turn an uploaded portrait into a polished LinkedIn photo.

    The backend expands the user's prompt via LLM, invokes Gemini image generation,
    and returns both the transparent expanded prompt and the generated image bytes.
    """
    return await service.generate(photo, prompt)
