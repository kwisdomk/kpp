"""Runtime configuration with safe local-development defaults."""

import os
from pathlib import Path

SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "jenga_session")
SESSION_ENGINEER_IDLE_MINUTES = int(os.getenv("SESSION_ENGINEER_IDLE_MINUTES", "20"))
SESSION_CUSTOMER_IDLE_MINUTES = int(os.getenv("SESSION_CUSTOMER_IDLE_MINUTES", "45"))
SESSION_ABSOLUTE_HOURS = int(os.getenv("SESSION_ABSOLUTE_HOURS", "8"))
MAX_MEDIA_BYTES = 8 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_AUDIO_TYPES = {"audio/wav", "audio/x-wav", "audio/wave"}
MAX_IMAGE_PIXELS = 4_000_000
MAX_IMAGE_EDGE = 4096
IMAGE_TTL_MINUTES = 60
MEDIA_STORAGE_DIR = Path(os.getenv("MEDIA_STORAGE_DIR", str(Path(__file__).resolve().parents[3] / "data" / "uploads")))
