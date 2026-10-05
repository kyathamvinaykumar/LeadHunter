"""Streamlit workflow tests for explicit, session-cached website audits."""

from __future__ import annotations

import base64
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from streamlit.testing.v1 import AppTest

from app.models import Business


class StreamlitAuditTests(unittest.TestCase):
    def test_audit_only_runs_when_clicked_and_is_cached(self) -> None:
        business = Business(
            name="Auditable business",
            address="Example address",
            rating=4.7,
            reviews_count=120,
            website="https://example.com",
            phone="+1 555 0100",
            maps_url="https://maps.google.com/?q=example",
            place_id="audit-place",
            latitude=37.0,
            longitude=-122.0,
        )
        response = Mock()
        response.url = business.website
        response.status_code = 200
        response.text = "<html><head><title>Example</title></head><body></body></html>"
        response.raise_for_status.return_value = None

        transparent_png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/pV8AAAAASUVORK5CYII="
        )
        with (
            patch("requests.Session.get", return_value=response) as get_request,
            patch(
                "app.services.screenshot_provider.ThumIoScreenshotProvider.capture",
                return_value=transparent_png,
            ) as screenshot,
        ):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"))
            app.session_state["businesses"] = [business]
            app.run()

            self.assertFalse(app.exception)
            self.assertEqual(get_request.call_count, 0)
            screenshot.assert_not_called()
            self.assertEqual(app.session_state["website_audits"], {})

            app.button(key="details_audit-place").click().run()
            self.assertTrue(
                any("Website audit not performed yet." in str(item.value) for item in app.info)
            )
            detail_text = " ".join(str(item.value) for item in app.markdown)
            self.assertIn("Website Builder", detail_text)
            self.assertIn("Unknown", detail_text)
            self.assertIn("Response Time", detail_text)

            self.assertEqual(len(app.get("image")), 0)
            screenshot.assert_not_called()
            app.button(key="dialog_audit_audit-place").click().run()

            self.assertFalse(app.exception)
            self.assertEqual(get_request.call_count, 1)
            self.assertIn("https://example.com", app.session_state["website_audits"])
            self.assertTrue(any(metric.label == "Website Score" for metric in app.metric))

            app.run()

            self.assertFalse(app.exception)
            self.assertEqual(get_request.call_count, 1)
            self.assertEqual(screenshot.call_count, 0)

            app.button(key="screenshot_desktop_audit-place").click().run()
            self.assertFalse(app.exception)
            screenshot.assert_called_once_with(business.website, "desktop")

            app.run()
            self.assertEqual(screenshot.call_count, 1)

            app.button(key="screenshot_mobile_audit-place").click().run()
            self.assertFalse(app.exception)
            self.assertEqual(screenshot.call_count, 2)


if __name__ == "__main__":
    unittest.main()