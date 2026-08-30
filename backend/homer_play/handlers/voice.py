from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass

from tts import MODEL_ID, get_voice_bytes

from ..models import VoiceData, VoiceRequest
from ..spend import estimate_voice_micro


MP3_BITS_PER_SECOND = 128_000


@dataclass(frozen=True)
class VoiceHandlerResult:
    data: dict
    charged_micro_usd: int


def estimate_mp3_duration_ms(byte_count: int) -> int:
    return max(1, round(byte_count * 8 * 1_000 / MP3_BITS_PER_SECOND))


async def run_voice(payload: VoiceRequest) -> VoiceHandlerResult:
    audio_bytes = await asyncio.to_thread(get_voice_bytes, payload.message)
    if not isinstance(audio_bytes, bytes) or not audio_bytes:
        raise ValueError("TTS provider returned no audio")

    data = VoiceData.model_validate(
        {
            "text": payload.message,
            "audio": {
                "mime_type": "audio/mpeg",
                "encoding": "base64",
                "data": base64.b64encode(audio_bytes).decode("ascii"),
                "bytes": len(audio_bytes),
                "duration_ms": estimate_mp3_duration_ms(len(audio_bytes)),
                "duration_estimated": True,
            },
            "voice": {
                "provider": "elevenlabs",
                "class": "portfolio_goggins_persona",
                "model": MODEL_ID,
            },
            "characters_billed": len(payload.message),
        }
    )
    return VoiceHandlerResult(
        data=data.model_dump(mode="json", by_alias=True),
        charged_micro_usd=estimate_voice_micro(len(payload.message)),
    )
