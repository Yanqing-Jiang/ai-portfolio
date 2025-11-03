from __future__ import annotations

import asyncio
import base64
import logging
import os
import time
import uuid
from dataclasses import dataclass
from io import BytesIO
from typing import Optional, Tuple

from fastapi import HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError

try:  # pragma: no cover - optional dependency validated at runtime
    from google import genai as google_genai  # type: ignore
    from google.genai import types as genai_types  # type: ignore
except ImportError:  # pragma: no cover - optional dependency validated at runtime
    google_genai = None  # type: ignore
    genai_types = None  # type: ignore

try:
    from ..gemini_service import gemini_service  # type: ignore
except ImportError:  # pragma: no cover - running as top-level module
    from gemini_service import gemini_service  # type: ignore
from .prompt_templates import SYSTEM_PROMPT, PROMPT_EXPANSION_TEMPLATE
from .schemas import LinkedInPhotoResponse, ImageVariation

MAX_FILE_SIZE_BYTES = 8 * 1024 * 1024  # 8 MB upload cap to prevent abuse
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png"}
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG"}

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DEFAULT_IMAGE_MODEL = os.getenv("LINKEDIN_PHOTO_IMAGE_MODEL", "gemini-2.5-flash-image")


@dataclass(slots=True)
class ValidatedImage:
    """Result of validating and parsing the uploaded reference portrait."""

    raw_bytes: bytes
    mime_type: str
    width: int
    height: int


class LinkedInPhotoService:
    """Co-ordinates prompt expansion and image generation for LinkedIn headshots."""

    def __init__(self) -> None:
        self._image_client: Optional["google_genai.Client"] = None
        self._image_model: str = DEFAULT_IMAGE_MODEL
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def generate(self, photo: UploadFile, user_prompt: str) -> LinkedInPhotoResponse:
        """Entry point invoked by the FastAPI router."""
        start = time.perf_counter()
        request_id = uuid.uuid4().hex[:8]
        ctx = f"[req:{request_id}] "

        self._logger.info(
            "%sReceived LinkedIn photo request (filename=%s, content_type=%s)",
            ctx,
            getattr(photo, "filename", "<unknown>"),
            getattr(photo, "content_type", "<missing>"),
        )

        user_prompt = (user_prompt or "").strip()
        if not user_prompt:
            self._logger.warning("%sRejected request: empty style prompt supplied", ctx)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Describe the style or setting to generate your LinkedIn headshot.",
            )

        try:
            validated = await self._read_and_validate_image(photo, request_id=request_id)
            self._logger.debug(
                "%sReference photo validated (%s, %dx%d, %d bytes)",
                ctx,
                validated.mime_type,
                validated.width,
                validated.height,
                len(validated.raw_bytes),
            )

            self._logger.debug("%sExpanding style prompt (length=%d)", ctx, len(user_prompt))
            expanded_prompt = await self._expand_prompt(
                user_prompt,
                validated,
                request_id=request_id,
            )
            self._logger.debug(
                "%sExpanded prompt ready (length=%d)",
                ctx,
                len(expanded_prompt),
            )

            num_variations = 3
            self._logger.debug(
                "%sDispatching %d variation tasks using model '%s'",
                ctx,
                num_variations,
                self._image_model,
            )
            variation_tasks = [
                self._generate_single_variation(
                    validated,
                    expanded_prompt,
                    i,
                    request_id=request_id,
                )
                for i in range(num_variations)
            ]
            variations = await asyncio.gather(*variation_tasks)
        except HTTPException as exc:
            self._logger.warning(
                "%sRequest failed with HTTP %s: %s",
                ctx,
                exc.status_code,
                exc.detail,
            )
            raise
        except Exception:
            self._logger.exception("%sUnexpected error during photo generation", ctx)
            raise

        processing_ms = int((time.perf_counter() - start) * 1000)
        self._logger.info(
            "%sCompleted LinkedIn photo request in %d ms (variations=%d)",
            ctx,
            processing_ms,
            len(variations),
        )

        return LinkedInPhotoResponse(
            expanded_prompt=expanded_prompt,
            variations=variations,
            processing_ms=processing_ms,
        )

    async def _generate_single_variation(
        self,
        image: ValidatedImage,
        expanded_prompt: str,
        index: int,
        *,
        request_id: Optional[str] = None,
    ) -> ImageVariation:
        """Generate a single image variation."""
        ctx = f"[req:{request_id}] " if request_id else ""
        self._logger.debug("%sGenerating variation %d", ctx, index + 1)

        generated_bytes, mime_type = await self._generate_image(
            image,
            expanded_prompt,
            request_id=request_id,
            variation_index=index,
        )
        width, height = self._measure_dimensions(generated_bytes)
        encoded = base64.b64encode(generated_bytes).decode("utf-8")

        return ImageVariation(
            id=f"var-{index + 1}-{uuid.uuid4().hex[:8]}",
            image_base64=encoded,
            image_mime_type=mime_type,
            width=width,
            height=height,
        )

    async def _read_and_validate_image(
        self,
        photo: UploadFile,
        *,
        request_id: Optional[str] = None,
    ) -> ValidatedImage:
        """Load the uploaded portrait into memory and enforce basic policies."""
        ctx = f"[req:{request_id}] " if request_id else ""
        self._logger.debug(
            "%sValidating uploaded portrait (filename=%s, content_type=%s)",
            ctx,
            getattr(photo, "filename", "<unknown>"),
            getattr(photo, "content_type", "<missing>"),
        )

        if photo.content_type not in ALLOWED_CONTENT_TYPES:
            self._logger.warning(
                "%sRejected upload with unsupported content type: %s",
                ctx,
                photo.content_type,
            )
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Only JPEG and PNG portrait uploads are supported.",
            )

        raw_bytes = await photo.read()
        await photo.close()
        size_bytes = len(raw_bytes)

        if not raw_bytes:
            self._logger.warning("%sRejected upload: no bytes received", ctx)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Upload a portrait image to begin.",
            )

        if size_bytes > MAX_FILE_SIZE_BYTES:
            self._logger.warning(
                "%sRejected upload: %d bytes exceeds limit of %d",
                ctx,
                size_bytes,
                MAX_FILE_SIZE_BYTES,
            )
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Portrait file exceeds the 8 MB size limit.",
            )

        try:
            with Image.open(BytesIO(raw_bytes)) as img:
                img.verify()
        except (UnidentifiedImageError, OSError) as exc:
            self._logger.warning("%sUploaded file failed Pillow verification: %s", ctx, exc)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is not a valid image.",
            ) from exc

        # Re-open to inspect metadata because verify() closes the file pointer.
        with Image.open(BytesIO(raw_bytes)) as img:
            fmt = (img.format or "").upper()
            if fmt not in ALLOWED_IMAGE_FORMATS:
                self._logger.warning(
                    "%sRejected upload: image format %s not allowed",
                    ctx,
                    fmt or "<unknown>",
                )
                raise HTTPException(
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    detail="Unsupported image format. Use JPEG or PNG.",
                )
            width, height = img.size

        mime_type = "image/jpeg" if fmt == "JPEG" else "image/png"
        self._logger.debug(
            "%sValidated portrait (format=%s, size=%d bytes, dimensions=%dx%d)",
            ctx,
            fmt,
            size_bytes,
            width,
            height,
        )
        return ValidatedImage(
            raw_bytes=raw_bytes,
            mime_type=mime_type,
            width=width,
            height=height,
        )

    async def _expand_prompt(
        self,
        user_prompt: str,
        image: ValidatedImage,
        *,
        request_id: Optional[str] = None,
    ) -> str:
        """Call Gemini text model to expand the short style description."""
        ctx = f"[req:{request_id}] " if request_id else ""
        session_id = str(uuid.uuid4())
        self._logger.debug("%sCreating prompt expansion session %s", ctx, session_id)
        gemini_service.create_chat(session_id, system_instruction=SYSTEM_PROMPT)

        photo_summary = self._summarize_photo(image)
        payload = PROMPT_EXPANSION_TEMPLATE.format(
            user_prompt=user_prompt.strip(),
            photo_summary=photo_summary,
        )

        try:
            expanded_prompt = await asyncio.to_thread(
                gemini_service.send_message_sync,
                session_id,
                payload,
            )
            self._logger.debug("%sPrompt expansion response received", ctx)
        except HTTPException as exc:
            self._logger.warning(
                "%sPrompt expansion returned HTTP error %s: %s",
                ctx,
                exc.status_code,
                exc.detail,
            )
            raise
        except Exception as exc:
            self._logger.exception("%sPrompt expansion failed", ctx)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Unable to expand style prompt. Try again in a moment.",
            ) from exc
        finally:
            gemini_service.delete_chat(session_id)
            self._logger.debug("%sClosed prompt expansion session %s", ctx, session_id)

        expanded_prompt = (expanded_prompt or "").strip()
        if not expanded_prompt or expanded_prompt.lower().startswith("error"):
            snippet = expanded_prompt[:120] if expanded_prompt else "<empty>"
            self._logger.warning(
                "%sPrompt expansion returned invalid content: %s",
                ctx,
                snippet,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Unable to expand style prompt. Try again in a moment.",
            )
        return expanded_prompt

    async def _generate_image(
        self,
        image: ValidatedImage,
        expanded_prompt: str,
        *,
        request_id: Optional[str] = None,
        variation_index: Optional[int] = None,
    ) -> Tuple[bytes, str]:
        """Send the prompt + reference photo to Gemini image model."""
        ctx = f"[req:{request_id}] " if request_id else ""
        variation_label = (
            f"variation {variation_index + 1}"
            if variation_index is not None
            else "variation"
        )

        client = self._ensure_image_client()

        if not expanded_prompt:
            self._logger.error(
                "%sExpanded prompt unexpectedly missing before image generation",
                ctx,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Expanded prompt missing when attempting image generation.",
            )

        self._logger.debug(
            "%sSubmitting %s to Gemini image model '%s'",
            ctx,
            variation_label,
            self._image_model,
        )

        def _run_generation():
            with Image.open(BytesIO(image.raw_bytes)) as pil_image:
                pil_image.load()
                return client.models.generate_content(
                    model=self._image_model,
                    contents=[expanded_prompt, pil_image],
                )

        try:
            response = await asyncio.to_thread(_run_generation)
        except Exception as exc:
            self._logger.exception("%sGemini image generation failed for %s", ctx, variation_label)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Gemini image generation failed. Check backend logs for details.",
            ) from exc

        image_bytes, mime_type, fallback_text = self._extract_image_bytes(response)
        if not image_bytes:
            self._logger.warning(
                "%sGemini returned no inline image data for %s (fallback text present=%s)",
                ctx,
                variation_label,
                bool(fallback_text),
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=fallback_text or "Image model returned no content. Please try again.",
            )

        self._logger.debug(
            "%sReceived %d bytes for %s (mime=%s)",
            ctx,
            len(image_bytes),
            variation_label,
            mime_type or "image/png",
        )
        return image_bytes, mime_type or "image/png"

    def _ensure_image_client(self) -> "google_genai.Client":
        if google_genai is None or genai_types is None:
            self._logger.error(
                "google-genai package not installed; cannot use Gemini image models"
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="google-genai package is required for image generation.",
            )

        if not GEMINI_API_KEY:
            self._logger.error("GEMINI_API_KEY is not configured; image generation disabled")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Configure GEMINI_API_KEY to enable image generation.",
            )

        if self._image_client is None:
            self._logger.debug("Creating new Google GenAI client for LinkedIn photo service")
            self._image_client = google_genai.Client(api_key=GEMINI_API_KEY)
        else:
            self._logger.debug("Reusing cached Google GenAI client for LinkedIn photo service")
        return self._image_client

    def _extract_image_bytes(self, response: object) -> Tuple[Optional[bytes], Optional[str], Optional[str]]:
        """Pull inline image data from the Gemini response structure."""
        candidates = getattr(response, "candidates", None)
        fallback_text: Optional[str] = None
        if not candidates:
            return None, None, fallback_text

        for candidate in candidates:
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", None) if content else None
            if not parts:
                continue
            for part in parts:
                text_content = getattr(part, "text", None)
                if isinstance(text_content, str) and text_content.strip():
                    fallback_text = text_content
                inline = getattr(part, "inline_data", None)
                if not inline:
                    continue
                mime_type = getattr(inline, "mime_type", None)
                data = getattr(inline, "data", None)
                if isinstance(data, bytes):
                    return data, mime_type, fallback_text
                if isinstance(data, str):
                    try:
                        return base64.b64decode(data), mime_type, fallback_text
                    except base64.binascii.Error:
                        continue
        if fallback_text is None and candidates:
            first = candidates[0]
            content = getattr(first, "content", None)
            parts = getattr(content, "parts", None) if content else None
            if isinstance(parts, list):
                for part in parts:
                    text_content = getattr(part, "text", None)
                    if isinstance(text_content, str) and text_content.strip():
                        fallback_text = text_content
                        break
        return None, None, fallback_text

    def _measure_dimensions(self, image_bytes: bytes) -> Tuple[int, int]:
        with Image.open(BytesIO(image_bytes)) as img:
            width, height = img.size
        return width, height

    def _summarize_photo(self, image: ValidatedImage) -> str:
        orientation = "portrait" if image.height >= image.width else "landscape"
        aspect_ratio = (image.width / image.height) if image.height else 1.0
        return (
            f"{orientation} orientation portrait at {image.width}x{image.height}px "
            f"(aspect ratio ≈ {aspect_ratio:.2f}) with the subject centered and facing camera. "
            "Preserve facial identity, skin tone, and eye color."
        )
