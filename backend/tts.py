import os
from typing import List
import requests

# Read Eleven Labs API key from environment (e.g. set in backend/.env)
ELEVEN_LABS_API_KEY = os.getenv("ELEVEN_LABS_API_KEY")
VOICE_ID = os.getenv("ELEVEN_LABS_VOICE_ID")

MODEL_ID = "eleven_multilingual_v2"  # Use multilingual v2 model 


def get_voice_bytes(message: str) -> bytes:
    """Return MP3 bytes for the supplied message using ElevenLabs TTS."""
    if not ELEVEN_LABS_API_KEY:
        raise RuntimeError("ELEVEN_LABS_API_KEY not set in environment")

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}/stream"

    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": ELEVEN_LABS_API_KEY,
    }

    payload = {
        "text": message,
        "model_id": MODEL_ID,
        "voice_settings": {
            "stability": 0.7,
            "similarity_boost": 0.75,
        },
    }

    response = requests.post(url, json=payload, headers=headers, stream=True, timeout=30)
    if response.status_code != 200:
        # Attempt to log error details
        try:
            err_json = response.json()
            err_msg = err_json.get("detail") or err_json.get("message") or str(err_json)
        except Exception:
            err_msg = response.text
        raise RuntimeError(f"ElevenLabs API error {response.status_code}: {err_msg}")

    audio_chunks: List[bytes] = []
    for chunk in response.iter_content(chunk_size=1024):
        if chunk:
            audio_chunks.append(chunk)

    return b"".join(audio_chunks) 