from __future__ import annotations

# --- Function/Class Map ---
# Function: _normalize_variation_value
#   Role: Normalize variation directives from form fields to either cleaned strings or None.
#   Called from: LinkedInPhotoService.generate_variation
#   Invokes: None
#   Why: Prevents empty or placeholder directives from polluting variation prompts.
# Dataclass: ValidatedImage
#   Role: Container for validated upload bytes and dimensions.
#   Called from: LinkedInPhotoService._read_and_validate_image
#   Invokes: None
#   Why: Carries validated image metadata through generation steps.
# Dataclass: VariationDirectives
#   Role: Holds optional variation tweaks (background, expression, pose, prop).
#   Called from: LinkedInPhotoService.generate_variation
#   Invokes: None
#   Why: Keeps variation inputs organized for prompt assembly.
# Class: LinkedInPhotoService
#   Role: Orchestrates prompt expansion and image generation for LinkedIn headshots.
#   Called from: backend.linkedin_photo.router via module-level service instance.
#   Invokes: gemini_service, google.genai Client, Pillow helpers.
#   Why: Central service layer behind /api/linkedin-photo endpoints.
# Method: __init__
#   Role: Initialize Gemini image client cache and model selection.
#   Called from: LinkedInPhotoService instantiation in router.
#   Invokes: None
#   Why: Capture chosen image model and logger once per process.
# Method: generate
#   Role: Main generation flow from upload -> prompt expansion -> single variation.
#   Called from: router.generate_linkedin_photo
#   Invokes: _read_and_validate_image, _expand_prompt, _generate_single_variation
#   Why: Provide first-try LinkedIn-ready portrait output.
# Method: generate_variation
#   Role: Variation flow reusing prior prompt with guided tweaks.
#   Called from: router.generate_linkedin_photo_variation
#   Invokes: _read_and_validate_image, _build_variation_prompt, _generate_single_variation
#   Why: Support iterative nudges without recreating prompts.
# Method: _generate_single_variation
#   Role: Convert prompt + reference into one image and package metadata.
#   Called from: generate, generate_variation
#   Invokes: _generate_image, _measure_dimensions
#   Why: Standardize single-output assembly and IDs.
# Method: _build_variation_prompt
#   Role: Merge base prompt with variation directives.
#   Called from: generate_variation
#   Invokes: None
#   Why: Keep variation prompt construction consistent and logged.
# Method: _read_and_validate_image
#   Role: Load, verify, and enforce policy on uploaded portraits.
#   Called from: generate, generate_variation
#   Invokes: Pillow verification, ValidatedImage creation
#   Why: Protect downstream model calls from invalid or oversized files.
# Method: _expand_prompt
#   Role: Call Gemini text model to expand user style guidance.
#   Called from: generate
#   Invokes: gemini_service chat session, _summarize_photo
#   Why: Produce detailed prompt the image model needs.
# Method: _generate_image
#   Role: Run Gemini image model with prompt + reference portrait.
#   Called from: _generate_single_variation
#   Invokes: _ensure_image_client, client.models.generate_content, _extract_image_bytes
#   Why: Bridge expanded prompt to actual rendered image bytes.
# Method: _ensure_image_client
#   Role: Create or reuse the google.genai client.
#   Called from: _generate_image
#   Invokes: google_genai.Client
#   Why: Hold a single client instance and enforce API key presence.
# Method: _extract_image_bytes
#   Role: Pull inline image data from Gemini response parts.
#   Called from: _generate_image
#   Invokes: base64 decoding
#   Why: Convert API response into usable bytes/mime for the frontend.
# Method: _measure_dimensions
#   Role: Determine width/height of generated image bytes.
#   Called from: _generate_single_variation
#   Invokes: PIL.Image.open
#   Why: Send dimensions to the frontend for layout hints.
# Method: _summarize_photo
#   Role: Describe uploaded portrait for prompt expansion context.
#   Called from: _expand_prompt
#   Invokes: None
#   Why: Give the text model structured photo cues.
# --- End Function/Class Map ---

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
from .fixed_prompts import match_fixed_prompt
from .prompt_templates import SYSTEM_PROMPT, PROMPT_EXPANSION_TEMPLATE
from .schemas import LinkedInPhotoResponse, ImageVariation, PhotoAnalysisResponse, PhotoScores

MAX_FILE_SIZE_BYTES = 8 * 1024 * 1024  # 8 MB upload cap to prevent abuse
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png"}
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG"}

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DEFAULT_IMAGE_MODEL = os.getenv("LINKEDIN_PHOTO_IMAGE_MODEL", "gemini-3-pro-image-preview")


def _normalize_variation_value(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None

    lowered = normalized.lower()
    if lowered in {"none", "no change", "original", "keep", "unchanged", "default"}:
        return None
    return normalized


@dataclass(slots=True)
class ValidatedImage:
    """Result of validating and parsing the uploaded reference portrait."""

    raw_bytes: bytes
    mime_type: str
    width: int
    height: int


@dataclass(slots=True)
class VariationDirectives:
    background: Optional[str] = None
    expression: Optional[str] = None
    pose: Optional[str] = None
    prop: Optional[str] = None


class LinkedInPhotoService:
    """Co-ordinates prompt expansion and image generation for LinkedIn headshots."""

    def __init__(self) -> None:
        self._image_client: Optional["google_genai.Client"] = None
        self._image_model: str = DEFAULT_IMAGE_MODEL
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def analyze_photo(
        self,
        photo: UploadFile,
    ) -> PhotoAnalysisResponse:
        """
        Analyze a portrait photo and return quality scores for LinkedIn readiness.
        
        Uses gemini-2.5-flash-lite multimodal model to analyze the actual uploaded image,
        providing scores for lighting, angle, background, expression, and outfit.
        Called from: router.analyze_photo
        Invokes: _read_and_validate_image, _ensure_image_client, google.genai generate_content
        Why: Powers the AI Quality Scorecard feature in The Headshot Studio.
        """
        start = time.perf_counter()
        request_id = uuid.uuid4().hex[:8]
        ctx = f"[req:{request_id}] "

        self._logger.info(
            "%sReceived photo analysis request (filename=%s)",
            ctx,
            getattr(photo, "filename", "<unknown>"),
        )

        try:
            validated = await self._read_and_validate_image(photo, request_id=request_id)
            self._logger.debug(
                "%sPhoto validated for analysis (%dx%d, %d bytes)",
                ctx,
                validated.width,
                validated.height,
                len(validated.raw_bytes),
            )

            # Use Gemini multimodal to analyze the actual photo
            client = self._ensure_image_client()
            
            # Analysis prompt for the AI Quality Scorecard - STRICT SCORING
            analysis_prompt = """You are an EXTREMELY STRICT professional headshot photographer evaluating this portrait for LinkedIn corporate readiness.

CRITICAL SCORING GUIDELINES (be harsh - this is professional assessment):
- Score 8-10: Only for ACTUAL professional studio headshots with perfect lighting, clean backdrop, professional attire
- Score 5-7: Decent attempts but missing key professional elements  
- Score 1-4: Casual photos, selfies, vacation pics, informal settings - these should score LOW

Analyze this uploaded portrait and provide strict scores from 1-10:

1. **LIGHTING** (1-10): 
   - 8-10: Professional studio lighting, soft even illumination, no shadows
   - 5-7: Decent natural light but not studio quality
   - 1-4: Harsh shadows, unflattering light, indoor/restaurant lighting, flash photos

2. **ANGLE** (1-10):
   - 8-10: Professional eye-level shot, properly centered, slight 3/4 turn
   - 5-7: Acceptable but not ideal angle
   - 1-4: Selfie angle, looking down/up, distorted, too close/far

3. **BACKGROUND** (1-10):
   - 8-10: Clean studio backdrop, professional office, neutral colors
   - 5-7: Simple but not professional background
   - 1-4: Busy restaurant, cluttered room, people in background, outdoor casual

4. **EXPRESSION** (1-10):
   - 8-10: Confident, warm professional smile, engaging eyes
   - 5-7: Pleasant but casual expression
   - 1-4: Casual laugh, candid moment, not looking at camera

5. **OUTFIT** (1-10):
   - 8-10: Business formal, tailored blazer, crisp shirt
   - 5-7: Business casual, polo, clean casual
   - 1-4: T-shirt, casual wear, hoodie, visible logos, wrinkled

The OVERALL score should reflect: "Would a Fortune 500 recruiter take this person seriously based on this photo?"
- If this looks like a casual/personal photo, the overall should be 3-5
- If this looks semi-professional, overall should be 5-7
- Only actual professional headshots should score 8-10

Provide 2-3 actionable tips (15 words max each).

Respond ONLY with valid JSON:
{"lighting": 4, "angle": 3, "background": 2, "expression": 6, "outfit": 3, "overall": 4, "tips": ["This casual setting won't work for LinkedIn", "Book a professional headshot session", "Invest in proper studio lighting"]}"""

            self._logger.debug(
                "%sSubmitting photo to gemini-2.5-flash-lite for analysis",
                ctx,
            )

            def _run_analysis():
                from PIL import Image as PILImage
                from io import BytesIO as IOBytesIO
                with PILImage.open(IOBytesIO(validated.raw_bytes)) as pil_image:
                    pil_image.load()
                    return client.models.generate_content(
                        model="gemini-2.5-flash-lite",
                        contents=[pil_image, analysis_prompt],
                    )

            try:
                response = await asyncio.to_thread(_run_analysis)
                self._logger.debug("%sPhoto analysis response received from gemini-2.5-flash-lite", ctx)
            except Exception as exc:
                self._logger.exception("%sPhoto analysis with gemini-2.5-flash-lite failed", ctx)
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Unable to analyze photo. Try again in a moment.",
                ) from exc

            # Extract text from response
            response_text = ""
            if hasattr(response, "text"):
                response_text = response.text or ""
            elif hasattr(response, "candidates") and response.candidates:
                for candidate in response.candidates:
                    content = getattr(candidate, "content", None)
                    parts = getattr(content, "parts", None) if content else None
                    if parts:
                        for part in parts:
                            text = getattr(part, "text", None)
                            if text:
                                response_text = text
                                break
                    if response_text:
                        break

            response_text = response_text.strip()
            self._logger.debug("%sRaw analysis response: %s", ctx, response_text[:300])

            # Remove markdown code block if present
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                # Find json start and end
                start_idx = 1 if lines[0].startswith("```") else 0
                end_idx = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
                response_text = "\n".join(lines[start_idx:end_idx])

            # Parse JSON response
            import json
            try:
                data = json.loads(response_text)
            except json.JSONDecodeError:
                self._logger.warning("%sFailed to parse analysis JSON: %s", ctx, response_text[:200])
                # Return default scores if parsing fails
                data = {
                    "lighting": 7,
                    "angle": 7,
                    "background": 7,
                    "expression": 7,
                    "outfit": 7,
                    "overall": 7,
                    "tips": ["Upload a clear, well-lit portrait for best results."]
                }

            # Map outfit to expression for backward compatibility with schema
            # The schema has expression, but we prompted for outfit - use outfit score
            outfit_score = data.get("outfit", data.get("expression", 7))
            expression_score = data.get("expression", 7)
            
            scores = PhotoScores(
                lighting=max(1, min(10, int(data.get("lighting", 7)))),
                angle=max(1, min(10, int(data.get("angle", 7)))),
                background=max(1, min(10, int(data.get("background", 7)))),
                expression=max(1, min(10, int(expression_score))),
                overall=max(1, min(10, int(data.get("overall", 7)))),
            )

            tips = data.get("tips", ["Looking great for a professional headshot!"])
            if not isinstance(tips, list):
                tips = [str(tips)]
            tips = [str(t) for t in tips[:3]]  # Max 3 tips

        except HTTPException:
            raise
        except Exception:
            self._logger.exception("%sUnexpected error during photo analysis", ctx)
            raise

        processing_ms = int((time.perf_counter() - start) * 1000)
        self._logger.info(
            "%sCompleted photo analysis in %d ms (overall_score=%d)",
            ctx,
            processing_ms,
            scores.overall,
        )

        return PhotoAnalysisResponse(
            scores=scores,
            tips=tips,
            processing_ms=processing_ms,
        )

    async def generate(
        self,
        photo: UploadFile,
        user_prompt: str,
        prompt_mode: Optional[str] = None,
    ) -> LinkedInPhotoResponse:
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

        prompt_mode_normalized = (prompt_mode or "auto").strip().lower()
        matched_fixed_prompt = match_fixed_prompt(user_prompt)
        should_passthrough = prompt_mode_normalized in {"fixed", "passthrough"}

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

            if should_passthrough or matched_fixed_prompt:
                expanded_prompt = matched_fixed_prompt or user_prompt
                reason = (
                    "prompt_mode-fixed"
                    if should_passthrough
                    else "matched-canonical-fixed-prompt"
                )
                self._logger.debug(
                    "%sBypassing prompt expansion (%s, length=%d)",
                    ctx,
                    reason,
                    len(expanded_prompt),
                )
            else:
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

            num_variations = 1
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

    async def generate_variation(
        self,
        photo: UploadFile,
        base_prompt: str,
        *,
        background: Optional[str] = None,
        expression: Optional[str] = None,
        pose: Optional[str] = None,
        prop: Optional[str] = None,
    ) -> LinkedInPhotoResponse:
        """Generate a follow-up portrait variation based on an existing prompt."""
        start = time.perf_counter()
        request_id = uuid.uuid4().hex[:8]
        ctx = f"[req:{request_id}] "

        self._logger.info("%sReceived LinkedIn photo variation request", ctx)

        normalized_base = (base_prompt or "").strip()
        if not normalized_base:
            self._logger.warning("%sRejected variation: base prompt missing", ctx)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provide the previous expanded prompt to create a variation.",
            )

        directives = VariationDirectives(
            background=_normalize_variation_value(background),
            expression=_normalize_variation_value(expression),
            pose=_normalize_variation_value(pose),
            prop=_normalize_variation_value(prop),
        )

        try:
            validated = await self._read_and_validate_image(photo, request_id=request_id)
            self._logger.debug(
                "%sVariation portrait validated (%dx%d)",
                ctx,
                validated.width,
                validated.height,
            )
            variation_prompt = self._build_variation_prompt(
                normalized_base,
                directives,
                request_id=request_id,
            )
            self._logger.debug(
                "%sVariation prompt ready (length=%d)",
                ctx,
                len(variation_prompt),
            )
            variation = await self._generate_single_variation(
                validated,
                variation_prompt,
                0,
                request_id=request_id,
            )
        except HTTPException:
            raise
        except Exception:
            self._logger.exception("%sUnexpected error during variation generation", ctx)
            raise

        processing_ms = int((time.perf_counter() - start) * 1000)
        self._logger.info(
            "%sCompleted variation request in %d ms",
            ctx,
            processing_ms,
        )

        return LinkedInPhotoResponse(
            expanded_prompt=variation_prompt,
            variations=[variation],
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

    def _build_variation_prompt(
        self,
        base_prompt: str,
        directives: VariationDirectives,
        *,
        request_id: Optional[str] = None,
    ) -> str:
        """Blend the base prompt with guided adjustments for a new iteration."""
        ctx = f"[req:{request_id}] " if request_id else ""
        adjustments: list[str] = []

        if directives.background:
            adjustments.append(f"Adjust the background to {directives.background}.")
        if directives.expression:
            adjustments.append(f"Guide the facial expression toward {directives.expression}.")
        if directives.pose:
            adjustments.append(f"Refine the pose to {directives.pose}.")
        if directives.prop:
            adjustments.append(f"Introduce the following prop interaction: {directives.prop}.")

        if not adjustments:
            adjustments.append(
                "Refresh the portrait subtly while preserving the previous lighting balance and professional polish."
            )

        adjustments.append(
            "Maintain the subject's identity, proportions, and wardrobe while keeping the image LinkedIn-ready."
        )
        adjustments.append(
            "Render exactly one finished portrait image—do not create grids, diptychs, or multiple outputs."
        )

        variation_prompt = (
            f"{base_prompt.strip()}\n\nVariation directives:\n- " + "\n- ".join(adjustments)
        )
        self._logger.debug("%sConstructed variation prompt", ctx)
        return variation_prompt

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
                    config=genai_types.GenerateContentConfig(
                        response_modalities=["IMAGE"],
                    ),
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
