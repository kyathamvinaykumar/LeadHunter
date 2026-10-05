"""Replaceable website screenshot providers for on-demand previews."""

from __future__ import annotations

from typing import Literal, Protocol
from urllib.parse import quote, urlsplit, urlunsplit

import requests


ScreenshotMode = Literal["desktop", "mobile"]
THUM_IO_URL = "https://image.thum.io/get"


class ScreenshotError(Exception):
    """Raised when a screenshot provider cannot produce a preview."""


class ScreenshotProvider(Protocol):
    def capture(self, website_url: str, mode: ScreenshotMode) -> bytes:
        """Return a PNG or JPEG preview for one viewport mode."""


class ThumIoScreenshotProvider:
    """Capture a page through Thum.io's no-key screenshot endpoint."""

    def __init__(
        self,
        *,
        timeout: float = 30.0,
        session: requests.Session | None = None,
    ) -> None:
        self._timeout = timeout
        self._session = session or requests.Session()

    def capture(self, website_url: str, mode: ScreenshotMode) -> bytes:
        parsed = urlsplit(website_url.strip())
        if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Website URL must be a valid HTTP or HTTPS URL.")
        if mode not in {"desktop", "mobile"}:
            raise ValueError("Screenshot mode must be desktop or mobile.")

        normalized_url = urlunsplit(parsed._replace(fragment=""))
        viewport = "width/1200/crop/900" if mode == "desktop" else "width/390/viewportWidth/390"
        request_url = f"{THUM_IO_URL}/{viewport}/{quote(normalized_url, safe=':/?=&%') }"
        try:
            response = self._session.get(
                request_url,
                headers={"User-Agent": "LeadHunter/0.1 (website screenshot preview)"},
                timeout=self._timeout,
            )
            response.raise_for_status()
        except requests.RequestException as error:
            raise ScreenshotError(f"Screenshot capture failed: {error}") from error

        content_type = response.headers.get("Content-Type", "").casefold()
        if not content_type.startswith("image/"):
            raise ScreenshotError("Screenshot provider returned a non-image response.")
        if not response.content:
            raise ScreenshotError("Screenshot provider returned an empty image.")
        return response.content