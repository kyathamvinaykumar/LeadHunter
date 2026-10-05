"""Input validation for business searches."""

from __future__ import annotations

from app.services.places_service import MAX_RESULTS


def validate_search_input(city: str, niche: str) -> tuple[str, str]:
    city = city.strip()
    niche = niche.strip()
    if not city:
        raise ValueError("City cannot be empty.")
    if not niche:
        raise ValueError("Business niche cannot be empty.")
    return city, niche


def validate_max_results(max_results: int) -> int:
    if not 1 <= max_results <= MAX_RESULTS:
        raise ValueError(f"--max-results must be between 1 and {MAX_RESULTS}.")
    return max_results
