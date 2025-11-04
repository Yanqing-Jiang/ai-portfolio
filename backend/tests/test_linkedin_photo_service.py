from __future__ import annotations

from io import BytesIO
from typing import Tuple
from unittest.mock import AsyncMock

import pytest
from PIL import Image
from fastapi import HTTPException, status
from starlette.datastructures import Headers, UploadFile

from backend.linkedin_photo.service import LinkedInPhotoService
from backend.linkedin_photo import service as linkedin_service_module
from backend.linkedin_photo.fixed_prompts import load_fixed_prompts


def _make_upload(content_type: str = "image/jpeg") -> UploadFile:
    buffer = BytesIO()
    Image.new("RGB", (128, 128), color=(210, 180, 150)).save(buffer, format="JPEG")
    buffer.seek(0)
    upload = UploadFile(filename="portrait.jpg", file=BytesIO(buffer.read()))
    upload.headers = Headers({"content-type": content_type})
    return upload


@pytest.mark.asyncio
async def test_generate_returns_transparent_response(monkeypatch):
    service = LinkedInPhotoService()
    upload = _make_upload()

    async def fake_expand_prompt(user_prompt: str, image, **kwargs) -> str:
        assert user_prompt == "polished leadership vibe"
        return "Polished studio portrait with balanced lighting and confident posture."

    async def fake_generate_image(image, expanded_prompt: str, **kwargs) -> Tuple[bytes, str]:
        assert "Polished studio portrait" in expanded_prompt
        return b"\x89PNG\r\n\x1a\nheadshot", "image/png"

    monkeypatch.setattr(service, "_expand_prompt", fake_expand_prompt)
    monkeypatch.setattr(service, "_generate_image", fake_generate_image)
    monkeypatch.setattr(service, "_measure_dimensions", lambda *_: (1024, 1024))

    result = await service.generate(upload, "polished leadership vibe")

    assert result.expanded_prompt.startswith("Polished studio portrait")
    assert len(result.variations) == 1
    first_variation = result.variations[0]
    assert first_variation.image_mime_type == "image/png"
    assert first_variation.width == 1024
    assert first_variation.height == 1024
    assert first_variation.image_base64  # base64 encoded bytes
    assert result.processing_ms >= 0


@pytest.mark.asyncio
async def test_generate_rejects_large_file(monkeypatch):
    monkeypatch.setattr(linkedin_service_module, "MAX_FILE_SIZE_BYTES", 10)
    service = LinkedInPhotoService()
    # keep prompt expansion from running
    monkeypatch.setattr(service, "_expand_prompt", AsyncMock())
    monkeypatch.setattr(service, "_generate_image", AsyncMock())

    upload = UploadFile(filename="oversize.jpg", file=BytesIO(b"x" * 64))
    upload.headers = Headers({"content-type": "image/jpeg"})

    with pytest.raises(HTTPException) as exc:
        await service.generate(upload, "sleek tech leader")

    assert exc.value.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE


@pytest.mark.asyncio
async def test_generate_skips_expansion_for_fixed_prompt(monkeypatch):
    service = LinkedInPhotoService()
    upload = _make_upload()

    canonical_prompt = load_fixed_prompts()["creative"]

    async def fake_expand_prompt(user_prompt: str, image, **kwargs) -> str:
        raise AssertionError("Prompt expansion should be skipped for fixed prompts")

    async def fake_generate_image(image, expanded_prompt: str, **kwargs) -> Tuple[bytes, str]:
        assert expanded_prompt == canonical_prompt
        return b"\x89PNG\r\n\x1a\nfixed", "image/png"

    monkeypatch.setattr(service, "_expand_prompt", fake_expand_prompt)
    monkeypatch.setattr(service, "_generate_image", fake_generate_image)
    monkeypatch.setattr(service, "_measure_dimensions", lambda *_: (768, 768))

    result = await service.generate(upload, canonical_prompt, prompt_mode="fixed")

    assert result.expanded_prompt == canonical_prompt
    assert len(result.variations) == 1
    assert all(variation.image_mime_type == "image/png" for variation in result.variations)


@pytest.mark.asyncio
async def test_generate_variation_builds_augmented_prompt(monkeypatch):
    service = LinkedInPhotoService()
    upload = _make_upload()
    base_prompt = "Clean corporate portrait with balanced lighting."

    async def fake_generate_image(image, expanded_prompt: str, **kwargs) -> Tuple[bytes, str]:
        assert "Variation directives" in expanded_prompt
        assert "Adjust the background to charcoal gradient." in expanded_prompt
        assert "Guide the facial expression toward confident smile." in expanded_prompt
        assert "Render exactly one finished portrait image" in expanded_prompt
        assert "Refine the pose to three-quarter stance with relaxed shoulders." in expanded_prompt
        return b"\x89PNG\r\n\x1a\nvariation", "image/png"

    monkeypatch.setattr(service, "_generate_image", fake_generate_image)
    monkeypatch.setattr(service, "_measure_dimensions", lambda *_: (900, 900))

    result = await service.generate_variation(
        upload,
        base_prompt,
        background="charcoal gradient",
        expression="confident smile",
        pose="three-quarter stance with relaxed shoulders",
        prop="holding a tablet at waist height",
    )

    assert result.expanded_prompt.startswith(base_prompt)
    assert len(result.variations) == 1
    variation = result.variations[0]
    assert variation.image_mime_type == "image/png"
    assert variation.width == 900
    assert variation.height == 900
