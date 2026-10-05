"""OpenStreetMap Nominatim client for resolving city search centers."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import requests


NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
DEFAULT_USER_AGENT = "LeadHunter/0.1"
DEFAULT_CACHE_PATH = Path(__file__).resolve().parents[2] / "data" / "cache" / "nominatim_geocoding.json"
REQUEST_INTERVAL_SECONDS = 1.0
logger = logging.getLogger(__name__)
_request_lock = threading.Lock()
_last_request_at: float | None = None


class GeocodingError(Exception):
    """Raised when a city cannot be resolved or geocoding fails."""


class GeocodingService:
    def __init__(
        self,
        *,
        timeout: float = 15.0,
        session: requests.Session | None = None,
        cache_path: Path = DEFAULT_CACHE_PATH,
        user_agent: str | None = None,
        request_interval: float = REQUEST_INTERVAL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._timeout = timeout
        self._session = session or requests.Session()
        self._cache_path = Path(cache_path)
        self._user_agent = (
            user_agent or os.getenv("NOMINATIM_USER_AGENT") or DEFAULT_USER_AGENT
        ).strip()
        if not self._user_agent:
            raise ValueError("A descriptive Nominatim User-Agent is required.")
        if request_interval < 0:
            raise ValueError("request_interval cannot be negative.")
        self._request_interval = request_interval
        self._clock = clock
        self._sleep = sleep

    def resolve_city(self, city: str) -> tuple[float, float]:
        """Return coordinates for a city, using the persistent cache when available."""
        query = " ".join(city.split())
        if not query:
            raise ValueError("City cannot be empty.")
        cache_key = query.casefold()
        cache = self._read_cache()
        cached = cache.get(cache_key)
        if cached is not None:
            try:
                return self._coordinates(cached)
            except GeocodingError:
                logger.warning("Ignoring invalid cached coordinates for %s.", query)

        global _last_request_at
        with _request_lock:
            # Recheck after taking the lock in case another request filled the cache.
            cache = self._read_cache()
            cached = cache.get(cache_key)
            if cached is not None:
                try:
                    return self._coordinates(cached)
                except GeocodingError:
                    logger.warning("Refreshing invalid cached coordinates for %s.", query)

            if _last_request_at is not None:
                elapsed = self._clock() - _last_request_at
                remaining = self._request_interval - elapsed
                if remaining > 0:
                    self._sleep(remaining)
            _last_request_at = self._clock()
            payload = self._request(query)
            coordinates = self._extract_coordinates(payload)
            cache[cache_key] = {"latitude": coordinates[0], "longitude": coordinates[1]}
            self._write_cache(cache)
            return coordinates

    def _request(self, query: str) -> Any:
        try:
            response = self._session.get(
                NOMINATIM_URL,
                params={"q": query, "format": "jsonv2", "limit": 1},
                headers={"User-Agent": self._user_agent},
                timeout=self._timeout,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as error:
            raise GeocodingError(f"OpenStreetMap Nominatim request failed: {error}") from error
        except ValueError as error:
            raise GeocodingError("OpenStreetMap Nominatim returned invalid JSON.") from error

    @staticmethod
    def _extract_coordinates(payload: Any) -> tuple[float, float]:
        if not isinstance(payload, list) or not payload:
            raise GeocodingError("OpenStreetMap Nominatim found no matching location.")
        try:
            latitude = float(payload[0]["lat"])
            longitude = float(payload[0]["lon"])
        except (KeyError, TypeError, ValueError) as error:
            raise GeocodingError("OpenStreetMap Nominatim returned unusable coordinates.") from error
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            raise GeocodingError("OpenStreetMap Nominatim returned out-of-range coordinates.")
        return latitude, longitude

    def _read_cache(self) -> dict[str, Any]:
        try:
            cache = json.loads(self._cache_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, json.JSONDecodeError) as error:
            logger.warning("Unable to read Nominatim cache %s: %s", self._cache_path, error)
            return {}
        return cache if isinstance(cache, dict) else {}

    def _write_cache(self, cache: dict[str, Any]) -> None:
        temporary_path = self._cache_path.with_suffix(self._cache_path.suffix + ".tmp")
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path.write_text(
                json.dumps(cache, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temporary_path.replace(self._cache_path)
        except OSError as error:
            logger.warning("Unable to write Nominatim cache %s: %s", self._cache_path, error)
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass

    @staticmethod
    def _coordinates(value: Any) -> tuple[float, float]:
        try:
            latitude = float(value["latitude"])
            longitude = float(value["longitude"])
        except (KeyError, TypeError, ValueError) as error:
            raise GeocodingError("The cached city coordinates are invalid.") from error
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            raise GeocodingError("The cached city coordinates are out of range.")
        return latitude, longitude
