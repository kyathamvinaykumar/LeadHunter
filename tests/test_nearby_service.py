"""Tests for dashboard-only location-aware Places searches."""

from __future__ import annotations

import unittest
from unittest.mock import Mock

from app.services.places_service import NEARBY_SEARCH_URL, TEXT_SEARCH_URL, PlacesService


class LocationSearchTests(unittest.TestCase):
    def test_nearby_search_uses_google_circle_restriction(self) -> None:
        session = Mock()
        session.post.return_value = self._response(
            {
                "places": [
                    {
                        "id": "store-1",
                        "displayName": {"text": "City Furniture"},
                        "location": {"latitude": 17.4, "longitude": 78.5},
                    }
                ]
            }
        )
        service = PlacesService("test-key", session=session)

        results = service.search_nearby(
            included_types=["furniture_store"],
            latitude=17.385,
            longitude=78.4867,
            radius_km=5,
            max_results=12,
        )

        self.assertEqual(len(results), 1)
        self.assertEqual((results[0].latitude, results[0].longitude), (17.4, 78.5))
        call = session.post.call_args
        self.assertEqual(call.args[0], NEARBY_SEARCH_URL)
        self.assertEqual(call.kwargs["json"]["includedTypes"], ["furniture_store"])
        self.assertEqual(call.kwargs["json"]["maxResultCount"], 12)
        circle = call.kwargs["json"]["locationRestriction"]["circle"]
        self.assertEqual(circle["radius"], 5000)
        self.assertIn("places.location", call.kwargs["headers"]["X-Goog-FieldMask"])

    def test_text_search_fallback_uses_location_bias_and_pagination(self) -> None:
        session = Mock()
        session.post.side_effect = [
            self._response(
                {
                    "places": [{"id": "first", "displayName": {"text": "First"}}],
                    "nextPageToken": "next-page",
                }
            ),
            self._response({"places": [{"id": "second", "displayName": {"text": "Second"}}]}),
        ]
        service = PlacesService("test-key", session=session)

        results = service.search_businesses_biased(
            city="Hyderabad",
            niche="Independent repair specialists",
            latitude=17.385,
            longitude=78.4867,
            radius_km=8,
            max_results=2,
        )

        self.assertEqual([business.place_id for business in results], ["first", "second"])
        first_call, second_call = session.post.call_args_list
        self.assertEqual(first_call.args[0], TEXT_SEARCH_URL)
        body = first_call.kwargs["json"]
        self.assertEqual(body["textQuery"], "Independent repair specialists in Hyderabad")
        circle = body["locationBias"]["circle"]
        self.assertEqual(circle["radius"], 8000)
        self.assertEqual(second_call.kwargs["json"]["pageToken"], "next-page")

    def test_nearby_search_rejects_more_than_twenty_results(self) -> None:
        service = PlacesService("test-key", session=Mock())

        with self.assertRaisesRegex(ValueError, "between 1 and 20"):
            service.search_nearby(
                included_types=["restaurant"],
                latitude=0,
                longitude=0,
                radius_km=1,
                max_results=21,
            )

    @staticmethod
    def _response(payload: dict) -> Mock:
        response = Mock()
        response.json.return_value = payload
        response.raise_for_status.return_value = None
        return response


if __name__ == "__main__":
    unittest.main()