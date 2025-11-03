# LinkedIn Photo Generator – End-to-End Flow

This document traces a request from the React wizard at `/project/linkedin-photo` through the FastAPI backend and back, highlighting the data structures, dependencies, and key failure modes you should know when diagnosing or extending the feature.

## 1. High-Level Architecture
- **Frontend**: Vite + React wizard (`components/linkedinPhoto/Page.tsx`) orchestrates a three-step flow—upload portrait → pick style prompt → request generations. Supporting UI pieces live in the same folder (`StylePresetCard`, `ImageVariationGallery`, `QualityTipsCard`, etc.).
- **Backend**: FastAPI router (`backend/linkedin_photo/router.py`) exposes `POST /api/linkedin-photo/generate`. The heavy lifting happens inside `LinkedInPhotoService` (`service.py`) which validates uploads, expands prompts via Gemini text, and fans out to Gemini image generation.
- **Shared Contracts**: Pydantic models in `schemas.py` ensure the response is shaped as
  ```jsonc
  {
    "expanded_prompt": "...",
    "variations": [
      {
        "id": "var-1-3f8a1c2d",
        "image_base64": "<base64 png>",
        "image_mime_type": "image/png",
        "width": 1024,
        "height": 1024
      }
    ],
    "processing_ms": 17475
  }
  ```

## 2. Frontend Request Lifecycle
1. **Upload Step** – `handleFileChange` in `Page.tsx` accepts only JPEG/PNG files. The preview URL lives in state so the user sees their original portrait immediately.
2. **Style Selection** – Selecting a preset from `StylePresetCard` seeds `stylePrompt`; a custom prompt can also be typed in.
3. **Generate Click** (`handleGenerate`):
   - Builds a `FormData` payload with `photo` (the original `File`) and `prompt` (trimmed text).
   - Resolves the target API URL using `configService.getBackendUrl()` so it behaves in local + deployed environments.
   - Shows optimistic progress (increments every 500 ms until completion).
   - On success, normalises `payload.variations` into camelCase (`imageBase64`, `imageMimeType`) before passing them to `ImageVariationGallery` for rendering, downloading, and Web Share actions.
   - On failure, extracts `detail` / `error` from the backend JSON (or falls back to status text) and surfaces it inline while logging to the browser console.

## 3. Backend Processing Pipeline
### 3.1 Entry Point
`router.py` wires `POST /api/linkedin-photo/generate` to `LinkedInPhotoService.generate`. Dependencies like rate limiting are intentionally omitted for this MVP endpoint so uploads remain fast during development.

### 3.2 Request-Level Logging
- Every call gets a short request ID (`req:<hex>`) logged at INFO level:  
  `2025-11-02 21:45:35,877 [INFO] ... [req:0a64ea50] Received LinkedIn photo request (filename=Profile pic.jpg, content_type=image/jpeg)`
- Set `ANALYTICS_LOG_LEVEL=DEBUG` (in `backend/.env`) to see the deeper debug logs we added: prompt expansion, individual variation dispatch, byte sizes, etc.

### 3.3 Upload Validation (`_read_and_validate_image`)
- Accepts only `image/jpeg` and `image/png`; anything else yields HTTP 415.
- Enforces `MAX_FILE_SIZE_BYTES = 8 MB` (HTTP 413 on breach).
- Uses Pillow to verify the file, detect format, and read dimensions. Invalid or corrupt files raise HTTP 400.
- Returns a `ValidatedImage` dataclass (`raw_bytes`, `mime_type`, `width`, `height`) used downstream. A debug log confirms the format, byte size, and dimensions.

### 3.4 Prompt Expansion (`_expand_prompt`)
- Creates a short-lived Gemini chat session via `backend/gemini_service.py`, seeding the system prompt in `prompt_templates.py`.
- Constructs a paragraph prompt using `PROMPT_EXPANSION_TEMPLATE`, incorporating the user’s style request and a generated summary of the reference photo (orientation, dimensions, aspect ratio).
- Calls `gemini_service.send_message_sync` in a background thread (`asyncio.to_thread`). Failures bubble up as HTTP 502 with logs explaining the cause.
- Ensures the result is non-empty and not an error token; otherwise, another HTTP 502 is raised with context.

### 3.5 Image Generation (`_generate_single_variation` → `_generate_image`)
- Fans out `num_variations = 3` concurrent tasks via `asyncio.gather`.
- `_ensure_image_client` lazily instantiates `google_genai.Client` with the environment-provided `GEMINI_API_KEY`; missing keys produce HTTP 503.
- Invokes `client.models.generate_content` with `LINKEDIN_PHOTO_IMAGE_MODEL` (default `gemini-2.5-flash-image`) passing both the expanded textual prompt and the PIL image instance.
- `_extract_image_bytes` walks the Gemini response to pull inline binary data; if the model falls back to text-only output, we surface HTTP 502 along with whatever fallback text Gemini sent.
- Each variation records its width/height via `_measure_dimensions` and emits debug logs listing byte counts and mime types.

### 3.6 Response Assembly
- `LinkedInPhotoResponse` packages the expanded prompt, the list of `ImageVariation` entries, and total `processing_ms` (computed from `time.perf_counter()`).
- Variations carry stable IDs (`var-{index+1}-{uuid}`) so the frontend can track selection state.

## 4. Error Codes & Retry Guidance
| HTTP Code | Source | Trigger | Suggested Fix |
|-----------|--------|---------|---------------|
| 400 | `_read_and_validate_image` | Empty upload / invalid bytes | Ask user to re-upload a real portrait |
| 413 | `_read_and_validate_image` | > 8 MB file | Prompt user to compress/resample |
| 415 | `_read_and_validate_image` | Wrong content type/format | Restrict file chooser to JPEG/PNG |
| 500 | `_generate_image` | Expanded prompt unexpectedly missing | Investigate server logs; should never happen unless code regression |
| 502 | `_expand_prompt` / `_generate_image` | Gemini rejected request or returned text only | Retry; inspect backend log for fallback text |
| 503 | `_ensure_image_client` | Missing `GEMINI_API_KEY` or `google-genai` install | Set env var / install dependency |

## 5. Configuration & Dependencies
- **Environment** (in `backend/.env`):
  - `GEMINI_API_KEY` (required) – Google AI Studio key with Tier 1 image access.
  - `LINKEDIN_PHOTO_IMAGE_MODEL` (optional) – override the default Gemini image model ID.
  - `ANALYTICS_LOG_LEVEL` – bump to `DEBUG` for verbose tracing.
- **Python deps**: `Pillow`, `google-genai`, `python-multipart` (file uploads), plus FastAPI stack (see `backend/requirements.txt`).
- **Frontend env**: `VITE_BACKEND_URL` ensures the wizard targets the correct backend origin in prod.

## 6. Frontend Rendering & UX Details
- `ImageVariationGallery` renders the generated results with compare vs. single view modes, dimension badges, and inline download/share actions. Recent bugfixes normalise the backend’s snake_case keys to the camelCase shape the gallery expects.
- Error state surfaces near the Generate button, resets progress bar, and clears variations so the user can adjust input without reloading.
- “All Variations” thumbnails keep selection state via the stable IDs coming from the backend response.

## 7. Local Testing & Tooling
- **Automated tests**: `backend/tests/test_linkedin_photo_service.py` uses `pytest` + Pillow to sanity-check validation and prompt expansion hooks. Note that the test still expects the legacy single-image response—update it if you need coverage for the new variations array.
- **Manual smoke tests**:
  - `scripts/run_linkedin_photo_demo.py` spins up FastAPI’s `TestClient` and posts a synthetic portrait to verify the entire pipeline without hitting Google’s API.
  - `scripts/temp_send_request.py` issues a raw HTTP POST against `http://127.0.0.1:8000/api/linkedin-photo/generate`—handy for cURL parity.
- **Example cURL**:
  ```powershell
  curl -F "photo=@portrait.jpg" ^
       -F "prompt=executive linkedin headshot with navy blazer" ^
       http://127.0.0.1:8000/api/linkedin-photo/generate
  ```
- **Example success response** (truncated):
  ```jsonc
  {
    "expanded_prompt": "Professional headshot of the same individual, soft key lighting...",
    "variations": [
      { "id": "var-1-3f8a1c2d", "image_base64": "iVBORw0KGgoAAA...", "image_mime_type": "image/png", "width": 1024, "height": 1024 },
      { "id": "var-2-9120ab44", "image_base64": "iVBORw0KGgoBBB...", "image_mime_type": "image/png", "width": 1024, "height": 1024 },
      { "id": "var-3-41ce0099", "image_base64": "iVBORw0KGgoCCC...", "image_mime_type": "image/png", "width": 1024, "height": 1024 }
    ],
    "processing_ms": 17475
  }
  ```

## 8. Observability Cheat Sheet
- **Enable verbose logging**: set `ANALYTICS_LOG_LEVEL=DEBUG` and restart `uvicorn` to capture prompt expansion + variation-level logs.
- **Identify a request**: use the `[req:xxxx]` token printed at INFO level across validation, prompt expansion, and completion messages.
- **Gemini responses**: if `_extract_image_bytes` fails, the warning log includes whether Gemini returned fallback text—handy for debugging API quota or safety filter trips.

## 9. Next Steps / Known Gaps
- Update the legacy pytest to assert the new `variations` array shape to match what the frontend expects.
- Consider persisting generation logs or metadata if you plan to store usage analytics beyond console logs.
- When promoting to production, tighten rate limiting or auth by adding dependencies back into the router (e.g., the shared `smart_rate_limit` utilities). For now, the endpoint is intentionally open for local experimentation.

With this overview you should be able to trace any request from the React wizard, understand what the FastAPI service does at each stage, and know where to add logging or defensive checks when expanding the LinkedIn photo generator.
