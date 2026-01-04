from pydantic import BaseModel, Field
from typing import List


class ImageVariation(BaseModel):
    """Single image variation."""

    id: str = Field(
        ...,
        description="Unique identifier for this variation."
    )
    image_base64: str = Field(
        ...,
        description="Base64-encoded professional headshot returned by the image model."
    )
    image_mime_type: str = Field(
        "image/png",
        description="Mime type of the generated image."
    )
    width: int = Field(
        ...,
        ge=1,
        description="Width in pixels of the generated image."
    )
    height: int = Field(
        ...,
        ge=1,
        description="Height in pixels of the generated image."
    )


class LinkedInPhotoResponse(BaseModel):
    """Response payload for the LinkedIn photo generator."""

    expanded_prompt: str = Field(
        ...,
        description="The enriched prompt produced by the LLM for transparency."
    )
    variations: List[ImageVariation] = Field(
        ...,
        description="List of generated image variations."
    )
    processing_ms: int = Field(
        ...,
        ge=0,
        description="Total processing time for the request in milliseconds."
    )


class PhotoScores(BaseModel):
    """AI Quality Scorecard scores for a portrait photo."""

    lighting: int = Field(
        ...,
        ge=1,
        le=10,
        description="Lighting quality score (1-10). Evaluates even lighting, shadows, and highlights."
    )
    angle: int = Field(
        ...,
        ge=1,
        le=10,
        description="Camera angle score (1-10). Evaluates flattering angle and lens distortion."
    )
    background: int = Field(
        ...,
        ge=1,
        le=10,
        description="Background cleanliness score (1-10). Evaluates clutter-free, professional setting."
    )
    expression: int = Field(
        ...,
        ge=1,
        le=10,
        description="Facial expression and outfit score (1-10). Evaluates confidence, approachability, and attire."
    )
    overall: int = Field(
        ...,
        ge=1,
        le=10,
        description="Overall professional readiness score (1-10). The main headline score."
    )


class PhotoAnalysisResponse(BaseModel):
    """Response payload for the AI Quality Scorecard analysis."""

    scores: PhotoScores = Field(
        ...,
        description="Detailed quality scores for the uploaded photo."
    )
    tips: List[str] = Field(
        ...,
        description="List of 2-3 improvement suggestions or affirmations."
    )
    processing_ms: int = Field(
        ...,
        ge=0,
        description="Total processing time for the analysis in milliseconds."
    )

