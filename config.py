"""
Veauido configuration.

Centralizes model, video processing, and server settings. The cache and video
directories are created on import so CLI and server runs have a predictable
place to store generated artifacts.
"""

from __future__ import annotations

import os
from pathlib import Path


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


# Model
MODEL_NAME: str = os.getenv("VEAUIDO_MODEL_NAME", "nlpconnect/vit-gpt2-image-captioning")
DEVICE: str = os.getenv("VEAUIDO_DEVICE", "cpu")

# Paths
BASE_DIR: Path = Path(__file__).resolve().parent
VIDEOS_DIR: Path = BASE_DIR / "videos"
CACHE_DIR: Path = BASE_DIR / ".cache"

# Scene detection
SCENE_THRESHOLD: float = _get_float("VEAUIDO_SCENE_THRESHOLD", 0.4)
MIN_SCENE_DURATION: float = _get_float("VEAUIDO_MIN_SCENE_DURATION", 1.5)
SAMPLE_FPS: int = max(1, _get_int("VEAUIDO_SAMPLE_FPS", 2))

# Frame extraction
MAX_FRAMES_PER_SCENE: int = max(1, _get_int("VEAUIDO_MAX_FRAMES_PER_SCENE", 3))
FRAME_SIZE: tuple[int, int] = (224, 224)

# Caption generation
MAX_CAPTION_LENGTH: int = max(1, _get_int("VEAUIDO_MAX_CAPTION_LENGTH", 50))
NUM_BEAMS: int = max(1, _get_int("VEAUIDO_NUM_BEAMS", 4))

# Download limits
MAX_DOWNLOAD_SIZE: str = os.getenv("VEAUIDO_MAX_DOWNLOAD_SIZE", "100M")

# Server
HOST: str = os.getenv("VEAUIDO_HOST", "0.0.0.0")
PORT: int = _get_int("VEAUIDO_PORT", _get_int("PORT", 8000))

# Public site URL (used for deploy links, canonical tags, and sharing).
# Render sets RENDER_EXTERNAL_URL automatically; override with VEAUIDO_PUBLIC_URL.
_default_public_url = f"http://localhost:{PORT}"
PUBLIC_URL: str = (
    os.getenv("VEAUIDO_PUBLIC_URL")
    or os.getenv("RENDER_EXTERNAL_URL")
    or os.getenv("RAILWAY_PUBLIC_DOMAIN")  # prepend https if needed
    or _default_public_url
).rstrip("/")
if PUBLIC_URL and not PUBLIC_URL.startswith(("http://", "https://")):
    PUBLIC_URL = f"https://{PUBLIC_URL}"


for directory in (VIDEOS_DIR, CACHE_DIR):
    directory.mkdir(parents=True, exist_ok=True)
