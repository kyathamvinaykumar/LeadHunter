"""Google Places API (New) Text Search integration."""

from __future__ import annotations

import logging
from typing import Any

import requests

from app.models import Business
from app.utils.helpers import build_search_query


logger = logging.getLogger(__name__)
TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
NEARBY_SEARCH_URL = "https://places.googleapis.com/v1/places:searchNearby"
MAX_RESULTS = 60
PAGE_SIZE = 20
FIELD_MASK = ",".join(
    (
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.rating",
        "places.userRatingCount",
        "places.websiteUri",
        "places.nationalPhoneNumber",
        "places.googleMapsUri",
        "nextPageToken",
    )
)
DASHBOARD_FIELD_MASK = FIELD_MASK.replace("nextPageToken", "places.location,nextPageToken")


class PlacesAPIError(Exception):
    """Raised when Google Places returns an API or network error."""


class PlacesService:
    """Search for local businesses using the Google Places API."""

    def __init__(
        self,
        api_key: str,
        *,
        timeout: float = 15.0,
        session: requests.Session | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("A Google Places API key is required.")
        self._api_key = api_key
        self._timeout = timeout
        self._session = session or requests.Session()

    def search_businesses(
        self,
        city: str,
        niche: str,
        max_results: int = MAX_RESULTS,
    ) -> list[Business]:
        """Return up to 60 businesses matching a niche and city."""
        if not 1 <= max_results <= MAX_RESULTS:
            raise ValueError(f"max_results must be between 1 and {MAX_RESULTS}.")

        query = build_search_query(city, niche)
        businesses: list[Business] = []
        page_token: str | None = None

        while len(businesses) < max_results:
            payload = self._fetch_search_page(query, page_token, min(PAGE_SIZE, max_results))
            for place in payload.get("places", []):
                place_id = place.get("id")
                if not place_id:
                    logger.warning("Skipping a Places result without an id.")
                    continue
                businesses.append(self._to_business(place))
                if len(businesses) >= max_results:
                    return businesses

            page_token = payload.get("nextPageToken")
            if not page_token:
                break

        return businesses

    def search_nearby(
        self,
        *,
        included_types: list[str],
        latitude: float,
        longitude: float,
        radius_km: float,
        max_results: int,
    ) -> list[Business]:
        """Search a Google-supported type within a strict API radius, up to 20."""
        if not included_types:
            raise ValueError("At least one supported Google place type is required.")
        if not 1 <= max_results <= 20:
            raise ValueError("Nearby Search supports between 1 and 20 results.")
        self._validate_location(latitude, longitude, radius_km)
        body: dict[str, Any] = {
            "includedTypes": included_types,
            "maxResultCount": max_results,
            "rankPreference": "DISTANCE",
            "locationRestriction": {
                "circle": {
                    "center": {"latitude": latitude, "longitude": longitude},
                    "radius": radius_km * 1000,
                }
            },
        }
        payload = self._post(NEARBY_SEARCH_URL, body, DASHBOARD_FIELD_MASK)
        return [self._to_business(place) for place in payload.get("places", []) if place.get("id")]

    def search_businesses_biased(
        self,
        *,
        city: str,
        niche: str,
        latitude: float,
        longitude: float,
        radius_km: float,
        max_results: int,
    ) -> list[Business]:
        """Search with Text Search's circular location bias and up to 60 results."""
        if not 1 <= max_results <= MAX_RESULTS:
            raise ValueError(f"max_results must be between 1 and {MAX_RESULTS}.")
        self._validate_location(latitude, longitude, radius_km)
        query = build_search_query(city, niche)
        businesses: list[Business] = []
        page_token: str | None = None

        while len(businesses) < max_results:
            body: dict[str, Any] = {
                "textQuery": query,
                "pageSize": min(PAGE_SIZE, max_results - len(businesses)),
                "locationBias": {
                    "circle": {
                        "center": {"latitude": latitude, "longitude": longitude},
                        "radius": radius_km * 1000,
                    }
                },
            }
            if page_token:
                body["pageToken"] = page_token
            payload = self._post(TEXT_SEARCH_URL, body, DASHBOARD_FIELD_MASK)
            for place in payload.get("places", []):
                if place.get("id"):
                    businesses.append(self._to_business(place))
                    if len(businesses) >= max_results:
                        return businesses
            page_token = payload.get("nextPageToken")
            if not page_token:
                break
        return businesses

    def _fetch_search_page(
        self,
        query: str,
        page_token: str | None,
        page_size: int,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"textQuery": query, "pageSize": page_size}
        if page_token:
            body["pageToken"] = page_token
        return self._post(TEXT_SEARCH_URL, body)

    def _post(
        self,
        url: str,
        body: dict[str, Any],
        field_mask: str = FIELD_MASK,
    ) -> dict[str, Any]:
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self._api_key,
            "X-Goog-FieldMask": field_mask,
        }
        return self._request_json(url, body, headers)

    def _request_json(
        self,
        url: str,
        body: dict[str, Any],
        headers: dict[str, str],
    ) -> dict[str, Any]:
        try:
            response = self._session.post(
                url,
                json=body,
                headers=headers,
                timeout=self._timeout,
            )
            response.raise_for_status()
        except requests.HTTPError as error:
            self._raise_http_error(error)
        except requests.RequestException as error:
            raise PlacesAPIError(f"Google Places network request failed: {error}") from error

        try:
            payload = response.json()
        except ValueError as error:
            raise PlacesAPIError("Google Places returned an invalid JSON response.") from error

        if not isinstance(payload, dict):
            raise PlacesAPIError("Google Places returned an unexpected response format.")
        return payload

    @staticmethod
    def _raise_http_error(error: requests.HTTPError) -> None:
        response = error.response
        status_code = response.status_code if response is not None else "unknown"
        error_info: dict[str, Any] = {}
        if response is not None:
            try:
                error_info = response.json().get("error", {})
            except (AttributeError, ValueError):
                pass

        status = error_info.get("status", status_code)
        message = error_info.get("message") or str(error)
        if status_code in {401, 403} or status in {"UNAUTHENTICATED", "PERMISSION_DENIED"}:
            hint = " Check the API key and ensure Places API (New) is enabled."
        elif status_code == 429 or status == "RESOURCE_EXHAUSTED":
            hint = " Google Places quota or billing limits may have been reached."
        else:
            hint = ""
        raise PlacesAPIError(f"Google Places request failed ({status}): {message}{hint}") from error

    @staticmethod
    def _to_business(place: dict[str, Any]) -> Business:
        rating = place.get("rating")
        display_name = place.get("displayName", {})
        location = place.get("location", {})
        return Business(
            name=display_name.get("text", "Unknown"),
            address=place.get("formattedAddress", ""),
            rating=float(rating) if rating is not None else None,
            reviews_count=int(place.get("userRatingCount", 0)),
            website=place.get("websiteUri"),
            phone=place.get("nationalPhoneNumber"),
            maps_url=place.get("googleMapsUri"),
            place_id=place["id"],
            latitude=(float(location["latitude"]) if location.get("latitude") is not None else None),
            longitude=(float(location["longitude"]) if location.get("longitude") is not None else None),
        )

    @staticmethod
    def _validate_location(latitude: float, longitude: float, radius_km: float) -> None:
        if not -90 <= latitude <= 90:
            raise ValueError("Latitude must be between -90 and 90.")
        if not -180 <= longitude <= 180:
            raise ValueError("Longitude must be between -180 and 180.")
        if not 0 < radius_km <= 50:
            raise ValueError("Search radius must be greater than 0 and at most 50 km.")
