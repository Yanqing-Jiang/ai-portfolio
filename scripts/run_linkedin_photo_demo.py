import base64
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
backend_path = ROOT / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

load_dotenv(ROOT / "backend" / ".env")

from backend.main import app  # noqa: E402


def build_demo_portrait() -> bytes:
    """Create a simple placeholder portrait to exercise the pipeline."""
    img = Image.new("RGB", (768, 1024), color="#d9c7b8")
    draw = ImageDraw.Draw(img)
    # simple bust silhouette
    draw.ellipse((200, 120, 568, 520), fill="#f4e2d3")
    draw.ellipse((276, 240, 356, 320), fill="#4a4a4a")  # left eye
    draw.ellipse((412, 240, 492, 320), fill="#4a4a4a")  # right eye
    draw.arc((288, 360, 480, 500), start=200, end=-20, fill="#4a4a4a", width=6)
    draw.rectangle((220, 460, 548, 780), fill="#1f2a44")  # blazer
    draw.rectangle((320, 510, 448, 700), fill="#f8f5f2")  # shirt
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer.getvalue()


def main() -> None:
    portrait_bytes = build_demo_portrait()
    client = TestClient(app)

    files = {
        "photo": ("demo-portrait.png", portrait_bytes, "image/png"),
    }
    data = {
        "prompt": "executive linkedin headshot with navy blazer and soft studio lighting",
    }

    response = client.post("/api/linkedin-photo/generate", files=files, data=data, timeout=180)
    if response.status_code >= 400:
        print("Request failed:", response.status_code, response.text)
        response.raise_for_status()

    payload = response.json()
    encoded = payload.get("image_base64")
    if not encoded:
        raise RuntimeError("API response missing generated image.")

    output_path = Path("generated-linkedin-photo.png")
    output_path.write_bytes(base64.b64decode(encoded))

    print("Expanded prompt:\n", payload.get("expanded_prompt", ""))
    print("Image saved to:", output_path.resolve())
    print("Dimensions:", payload.get("width"), "x", payload.get("height"))
    print("Processing time (ms):", payload.get("processing_ms"))


if __name__ == "__main__":
    main()
