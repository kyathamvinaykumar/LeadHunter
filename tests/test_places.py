"""Tests for Google Places discovery without network access."""

from __future__ import annotations

import unittest
from unittest.mock import Mock

import requests

from app.services.places_service import PlacesAPIError, PlacesService


class PlacesServiceTests(unittest.TestCase):
    def test_searches_multiple_pages_and_maps_details(self) -> None:
        session = Mock()
        session.post.side_effect = [
            self._response(
                {
                    "places": [
                        {
                            "id": "p1",
                            "displayName": {"text": "Alpha"},
                            "formattedAddress": "A",
                            "rating": 4.5,
                            "userRatingCount": 12,
                            "websiteUri": "https://alpha.example",
                            "nationalPhoneNumber": "+1 555 0100",
                            "googleMapsUri": "https://maps.example/p1",
                        },
                        {"id": "p2", "displayName": {"text": "Beta"}, "formattedAddress": "B"},
                    ],
                    "nextPageToken": "page-2",
                },
            ),
            self._response(
                {
                    "places": [
                        {"id": "p3", "displayName": {"text": "Gamma"}, "formattedAddress": "C"}
                    ]
                },
            ),
        ]
        service = PlacesService("test-key", session=session)

        businesses = service.search_businesses("Hyderabad", "Furniture Stores")

        self.assertEqual(len(businesses), 3)
        self.assertEqual(businesses[0].name, "Alpha")
        self.assertEqual(businesses[0].reviews_count, 12)
        self.assertEqual(businesses[0].website, "https://alpha.example")
        self.assertEqual(businesses[0].phone, "+1 555 0100")
        self.assertEqual(businesses[0].maps_url, "https://maps.example/p1")
        self.assertIsNone(businesses[1].website)
        self.assertEqual(session.post.call_count, 2)
        first_request = session.post.call_args_list[0].kwargs
        next_request = session.post.call_args_list[1].kwargs
        self.assertEqual(first_request["json"], {"textQuery": "Furniture Stores in Hyderabad", "pageSize": 20})
        self.assertEqual(next_request["json"]["pageToken"], "page-2")
        self.assertIn("places.websiteUri", first_request["headers"]["X-Goog-FieldMask"])

    def test_invalid_api_key_is_reported(self) -> None:
        session = Mock()
        session.post.return_value = self._response(
            {"error": {"code": 403, "status": "PERMISSION_DENIED", "message": "Invalid API key"}},
            status_code=403,
        )
        service = PlacesService("bad-key", session=session)

        with self.assertRaisesRegex(PlacesAPIError, "PERMISSION_DENIED"):
            service.search_businesses("Hyderabad", "Furniture Stores")

    def test_quota_error_is_reported(self) -> None:
        session = Mock()
        session.post.return_value = self._response(
            {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED", "message": "Quota exceeded"}},
            status_code=429,
        )
        service = PlacesService("test-key", session=session)

        with self.assertRaisesRegex(PlacesAPIError, "quota or billing limits"):
            service.search_businesses("Hyderabad", "Furniture Stores")

    def test_empty_results_return_empty_list(self) -> None:
        session = Mock()
        session.post.return_value = self._response({"places": []})
        service = PlacesService("test-key", session=session)

        self.assertEqual(service.search_businesses("Hyderabad", "Furniture Stores"), [])

    def test_network_failure_is_reported(self) -> None:
        session = Mock()
        session.post.side_effect = requests.ConnectionError("offline")
        service = PlacesService("test-key", session=session)

        with self.assertRaisesRegex(PlacesAPIError, "network request failed"):
            service.search_businesses("Hyderabad", "Furniture Stores")

    @staticmethod
    def _response(payload: dict, *, status_code: int = 200) -> Mock:
        response = Mock()
        response.status_code = status_code
        response.json.return_value = payload
        if status_code >= 400:
            response.raise_for_status.side_effect = requests.HTTPError(response=response)
        else:
            response.raise_for_status.return_value = None
        return response


if __name__ == "__main__":
    unittest.main()
