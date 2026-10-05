"""Tests for explicitly invoked website audits."""

from __future__ import annotations

import unittest
from unittest.mock import Mock

import requests

from app.services.website_audit import WebsiteAuditError, WebsiteAuditResult, WebsiteAuditor


class WebsiteAuditorTests(unittest.TestCase):
    def test_audits_requested_checks_and_returns_grade(self) -> None:
        session = Mock()
        response = Mock()
        response.url = "https://example.com"
        response.status_code = 200
        response.text = """
        <html><head><title>Example</title>
        <meta name="description" content="An example site">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        </head><body><form action="/contact"><input type="email"><textarea></textarea></form>
        <a href="https://instagram.com/example">Social</a></body></html>
        """
        response.raise_for_status.return_value = None
        session.get.return_value = response
        auditor = WebsiteAuditor(session=session)

        result = auditor.audit("https://example.com")

        self.assertEqual(result.score, 10)
        self.assertEqual(result.grade, "Excellent")
        self.assertTrue(all(result.checks().values()))
        self.assertEqual(result.social_links, ("instagram.com",))
        self.assertEqual(result.page_title, "Example")
        self.assertEqual(result.meta_description_text, "An example site")
        self.assertEqual(result.website_builder, "Unknown")
        self.assertTrue(result.reachable)
        self.assertGreaterEqual(result.response_time_ms, 0)
        self.assertEqual(result.response_status_code, 200)
        self.assertEqual(result.quality_status, "Excellent")
        self.assertIn("website_audit_score", result.to_export_dict())
        self.assertEqual(session.get.call_count, 1)
        self.assertIn("User-Agent", session.get.call_args.kwargs["headers"])

    def test_no_signals_scores_zero_and_grade_poor(self) -> None:
        session = Mock()
        response = Mock()
        response.url = "http://example.com"
        response.text = "<html><body>Nothing useful</body></html>"
        response.raise_for_status.return_value = None
        session.get.return_value = response

        result = WebsiteAuditor(session=session).audit("http://example.com")

        self.assertEqual(result.score, 0)
        self.assertEqual(result.grade, "Poor")
        self.assertEqual(result.summary, "0 of 6 checks passed.")

    def test_grade_boundaries(self) -> None:
        cases = [
            (True, True, True, True, True, False, 9, "Excellent"),
            (True, True, True, False, True, False, 7, "Good"),
            (True, True, False, False, True, False, 5, "Average"),
            (True, True, False, False, False, False, 4, "Poor"),
        ]
        for https, title, description, form, viewport, socials, points, expected_grade in cases:
            result = WebsiteAuditResult(
                url="https://example.com",
                https=https,
                meta_title=title,
                meta_description=description,
                contact_form=form,
                mobile_viewport=viewport,
                social_links=("linkedin.com",) if socials else (),
            )
            with self.subTest(score=points):
                self.assertEqual(result.score, points)
                self.assertEqual(result.grade, expected_grade)
                expected_quality = (
                    "Excellent" if points >= 9
                    else "Good" if points >= 7
                    else "Needs Improvement"
                )
                self.assertEqual(result.quality_status, expected_quality)

    def test_rejects_non_http_url_without_request(self) -> None:
        session = Mock()

        with self.assertRaisesRegex(ValueError, "HTTP or HTTPS"):
            WebsiteAuditor(session=session).audit("javascript:alert(1)")

        session.get.assert_not_called()

    def test_reports_network_failure_without_inventing_content_checks(self) -> None:
        session = Mock()
        session.get.side_effect = requests.ConnectionError("offline")

        result = WebsiteAuditor(session=session).audit("https://example.com")

        self.assertFalse(result.reachable)
        self.assertIsNone(result.meta_title)
        self.assertIsNone(result.meta_description)
        self.assertIsNone(result.score)
        self.assertEqual(result.website_builder, "Unknown")

    def test_detects_known_builders_from_observed_signatures(self) -> None:
        samples = {
            "Wix": '<script src="https://static.wixstatic.com/site.js"></script>',
            "WordPress": '<link href="/wp-content/themes/site.css">',
            "Squarespace": '<script src="https://static1.squarespace.com/site.js"></script>',
            "Shopify": '<script src="https://cdn.shopify.com/shop.js"></script>',
            "Webflow": '<script src="https://cdn.webflow.com/webflow.js"></script>',
            "Unknown": '<html><body>Custom site</body></html>',
        }
        for expected, html in samples.items():
            session = Mock()
            response = Mock()
            response.url = "https://example.test"
            response.status_code = 200
            response.text = html
            session.get.return_value = response

            with self.subTest(builder=expected):
                result = WebsiteAuditor(session=session).audit("https://example.test")
                self.assertEqual(result.website_builder, expected)


if __name__ == "__main__":
    unittest.main()