"""Command-line entry point for LeadHunter business discovery."""

from __future__ import annotations

import argparse
import logging

import pandas as pd

from app.config import ConfigurationError, load_settings
from app.models import Business
from app.services.exporter import Exporter
from app.services.places_service import PlacesAPIError, PlacesService
from app.utils.validators import validate_max_results, validate_search_input


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Find local businesses with Google Places."
    )
    parser.add_argument("--city", help="City to search, for example Hyderabad")
    parser.add_argument("--niche", help='Business niche, for example "Furniture Stores"')
    parser.add_argument(
        "--max-results",
        type=int,
        default=60,
        help="Maximum businesses to return (1-60; default: 60)",
    )
    return parser.parse_args()


def display_results(businesses: list[Business]) -> None:
    rows = [business.to_dict() for business in businesses]
    print(pd.DataFrame(rows).to_string(index=False, na_rep="N/A"))


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logger = logging.getLogger("leadhunter")
    args = parse_args()

    city = args.city if args.city is not None else input("City: ")
    niche = args.niche if args.niche is not None else input("Business niche: ")

    try:
        city, niche = validate_search_input(city, niche)
        max_results = validate_max_results(args.max_results)
        settings = load_settings()
        businesses = PlacesService(settings.google_maps_api_key).search_businesses(
            city=city,
            niche=niche,
            max_results=max_results,
        )
    except (ValueError, ConfigurationError, PlacesAPIError) as error:
        logger.error("%s", error)
        return 1

    if not businesses:
        print("No businesses found.")
        return 0

    display_results(businesses)
    exports = Exporter(settings.export_dir).export(businesses, city=city, niche=niche)
    print(f"\nCSV: {exports['csv']}")
    print(f"JSON: {exports['json']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
