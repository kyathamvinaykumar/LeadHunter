"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class ConfigurationError(Exception):
    """Raised when required application configuration is missing or invalid."""


@dataclass(frozen=True)
class Settings:
    google_maps_api_key: str
    export_dir: Path = PROJECT_ROOT / "data" / "exports"


def load_settings() -> Settings:
    load_dotenv(PROJECT_ROOT / ".env")
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
    if not api_key or api_key == "your_google_places_api_key_here":
        raise ConfigurationError(
            "GOOGLE_MAPS_API_KEY is missing. Add your Google Places API key to .env."
        )
    return Settings(google_maps_api_key=api_key)
