"""Tests for on-demand desktop and mobile screenshot provider."""

from __future__ import annotations

import unittest
from unittest.mock import Mock

import requests

from app.services.screenshot_provider import (
    ScreenshotError,
    ThumIoScreenshotProvider,
)


class ScreenshotProviderTests(unittest.TestCase):
    def test_captures_desktop_and_mobile_views(self) -> None:
        for mode, marker in (("desktop", "width/1200/crop/900"), ("mobile", "width/390/viewportWidth/390")):
            session = Mock()
            response = Mock()
            response.headers = {"Content-Type": "image/png"}
            response.content = b"image-bytes"
            response.raise_for_status.return_value = None
            session.get.return_value = response

            with self.subTest(mode=mode):
                image = ThumIoScreenshotProvider(session=session).capture(
                    "https://example.com/page", mode
                )
                self.assertEqual(image, b"image-bytes")
                self.assertIn(marker, session.get.call_args.args[0])

    def test_rejects_non_image_response(self) -> None:
        session = Mock()
        response = Mock()
        response.headers = {"Content-Type": "text/html"}
        response.content = b"not an image"
        response.raise_for_status.return_value = None
        session.get.return_value = response

        with self.assertRaisesRegex(ScreenshotError, "non-image"):
            ThumIoScreenshotProvider(session=session).capture("https://example.com", "desktop")

    def test_reports_provider_network_error(self) -> None:
        session = Mock()
        session.get.side_effect = requests.Timeout("timeout")

        with self.assertRaisesRegex(ScreenshotError, "capture failed"):
            ThumIoScreenshotProvider(session=session).capture("https://example.com", "mobile")


if __name__ == "__main__":
    unittest.main()