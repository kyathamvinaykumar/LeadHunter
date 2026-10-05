"""Tests for city coordinate resolution without network access."""

from __future__ import annotations

import unittest
import tempfile
from pathlib import Path
from unittest.mock import Mock

import requests

from app.services.geocoding_service import GeocodingError, GeocodingService


class GeocodingServiceTests(unittest.TestCase):
    def test_resolves_city_with_identifying_user_agent(self) -> None:
        session = Mock()
        session.get.return_value = self._response([{"lat": "17.385", "lon": "78.4867"}])

        with tempfile.TemporaryDirectory() as temporary_directory:
            service = GeocodingService(
                session=session,
                cache_path=Path(temporary_directory) / "nominatim.json",
                user_agent="LeadHunter-test/1.0 (test@example.invalid)",
                request_interval=0,
            )
            coordinates = service.resolve_city(" Hyderabad  India ")

        self.assertEqual(coordinates, (17.385, 78.4867))
        self.assertEqual(session.get.call_args.kwargs["params"], {
            "q": "Hyderabad India", "format": "jsonv2", "limit": 1
        })
        self.assertEqual(
            session.get.call_args.kwargs["headers"]["User-Agent"],
            "LeadHunter-test/1.0 (test@example.invalid)",
        )

    def test_persistent_cache_avoids_second_request(self) -> None:
        session = Mock()
        session.get.return_value = self._response([{"lat": "17.385", "lon": "78.4867"}])
        with tempfile.TemporaryDirectory() as temporary_directory:
            cache_path = Path(temporary_directory) / "nested" / "nominatim.json"
            first = GeocodingService(session=session, cache_path=cache_path, request_interval=0)
            second = GeocodingService(session=Mock(), cache_path=cache_path, request_interval=0)

            self.assertEqual(first.resolve_city("Hyderabad"), (17.385, 78.4867))
            self.assertEqual(second.resolve_city(" hyderabad "), (17.385, 78.4867))

        session.get.assert_called_once()

    def test_reports_no_matching_city(self) -> None:
        session = Mock()
        session.get.return_value = self._response([])
        with tempfile.TemporaryDirectory() as temporary_directory:
            service = GeocodingService(
                session=session,
                cache_path=Path(temporary_directory) / "nominatim.json",
                request_interval=0,
            )

            with self.assertRaisesRegex(GeocodingError, "found no matching location"):
                service.resolve_city("Unknown place")

    def test_reports_network_failure(self) -> None:
        session = Mock()
        session.get.side_effect = requests.ConnectionError("offline")
        with tempfile.TemporaryDirectory() as temporary_directory:
            service = GeocodingService(
                session=session,
                cache_path=Path(temporary_directory) / "nominatim.json",
                request_interval=0,
            )

            with self.assertRaisesRegex(GeocodingError, "Nominatim request failed"):
                service.resolve_city("Hyderabad")

    @staticmethod
    def _response(payload: dict) -> Mock:
        response = Mock()
        response.json.return_value = payload
        response.raise_for_status.return_value = None
        return response


if __name__ == "__main__":
    unittest.main()