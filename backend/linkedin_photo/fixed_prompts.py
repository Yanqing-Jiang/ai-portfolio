from __future__ import annotations

from functools import lru_cache
from typing import Dict, Optional

FIXED_PROMPTS: Dict[str, str] = {
    "creative_director": (
        "The Creative Director: Create a single editorial portrait in a clean, soft beige studio. "
        "The subject matches the reference 100% and wears a lightweight dark navy shirt with ivory trousers, barefoot "
        "to keep the styling disarmingly simple. Lighting: large diffused key light camera front-right, silver "
        "reflector camera-left, and a faint rim from overhead to sculpt the hairline. Composition: intimate "
        "three-quarter head-and-shoulders crop with a subtle high-to-low camera angle, one hand partially in frame to "
        "add visual rhythm, negative space preserved along the long edge. Capture in RAW with professional muted "
        "grading, smooth tonal contrast, and a whisper of cinematic grain to maintain an introspective, fabric-led "
        "editorial mood. Output a single polished portrait—no grids, no contact sheet layout."
    ),
    "silicon_valley": (
        "The Silicon Valley Founder: Use the uploaded user portrait as the subject. Do not change identity, age, or facial "
        "geometry. Goal: produce one hyper-realistic, cinematic studio headshot. Composition: subject wears a minimalist "
        "grey hoodie or casual tech-founder attire; shot uses a subtle low angle to emphasize confidence without feeling staged. "
        "Wardrobe: stylish dark layers; harmonize tones if the source image differs (no logos). "
        "Background: blurred modern tech-office with soft bokeh or pure black seamless. Lighting: soft, layered, moody—gentle "
        "specular highlights while preserving shadow detail. Detail: 8K-level sharpness highlighting clothing texture, "
        "hair strands, and eye clarity without sharpening halos. Framing: head-and-shoulders or half-body crop with "
        "clean negative space. Output constraints: lifelike, approachable, innovative; no text, graphics, watermark, or "
        "logos."
    ),
    "fortune_500": (
        "The Fortune 500: Use the uploaded portrait as source. Preserve identity, age, facial structure, and "
        "key features—no invented details. Deliver a single high-resolution corporate headshot. Framing: chest-up, "
        "with generous negative space above the head so nothing is cropped. Expression: confident, professional, "
        "approachable—relaxed jaw, subtle smile, direct gaze into lens. Pose: shoulders angled three-quarters toward "
        "camera, chin slightly lowered, posture upright. Styling: studio wardrobe consisting of a tailored charcoal "
        "blazer over a crisp white shirt, both logo-free and pressed. Background: soft gradient transitioning from "
        "light gray to white, uniformly lit and uncluttered. Camera and focus: simulated 85 mm at f/1.8 with shallow "
        "depth of field and precise focus on the eyes. Lighting: bright, diffused studio light wrapping evenly across "
        "the face, balanced catchlights, no blown highlights, and preserved shadow detail. Detail & texture: 8K "
        "clarity capturing blazer weave, hair strands, and natural skin texture without over-smoothing. Grade: clean, "
        "modern, slightly warm tonality for a polished finish. Output constraints: lifelike, refined, and modern; no "
        "text, logos, or watermarks."
    ),
}


def _normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n")


def _normalize_prompt(text: str) -> str:
    normalized = _normalize_newlines(text)
    lines = [line.rstrip() for line in normalized.strip().split("\n")]
    return "\n".join(lines)


@lru_cache()
def load_fixed_prompts() -> Dict[str, str]:
    # Return a shallow copy to protect the canonical definitions.
    return FIXED_PROMPTS.copy()


@lru_cache()
def _normalized_fixed_prompts() -> Dict[str, str]:
    return {key: _normalize_prompt(value) for key, value in FIXED_PROMPTS.items()}


def match_fixed_prompt(user_prompt: str) -> Optional[str]:
    if not user_prompt:
        return None
    normalized = _normalize_prompt(user_prompt)
    for key, canonical in _normalized_fixed_prompts().items():
        if normalized == canonical:
            return FIXED_PROMPTS[key]
    return None
