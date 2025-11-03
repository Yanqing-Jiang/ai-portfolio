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

    async def fake_expand_prompt(user_prompt: str, image) -> str:
        assert user_prompt == "polished leadership vibe"
        return "Polished studio portrait with balanced lighting and confident posture."

    async def fake_generate_image(image, expanded_prompt: str) -> Tuple[bytes, str]:
        assert "Polished studio portrait" in expanded_prompt
        return b"\x89PNG\r\n\x1a\nheadshot", "image/png"

    monkeypatch.setattr(service, "_expand_prompt", fake_expand_prompt)
    monkeypatch.setattr(service, "_generate_image", fake_generate_image)
    monkeypatch.setattr(service, "_measure_dimensions", lambda *_: (1024, 1024))

    result = await service.generate(upload, "polished leadership vibe")

    assert result.expanded_prompt.startswith("Polished studio portrait")
    assert result.image_mime_type == "image/png"
    assert result.width == 1024
    assert result.height == 1024
    assert result.image_base64  # base64 encoded bytes
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
