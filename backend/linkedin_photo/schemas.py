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
