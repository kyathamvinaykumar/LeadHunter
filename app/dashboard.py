"""Data preparation and filtering helpers for the Streamlit dashboard."""

from __future__ import annotations

import json
from collections.abc import Mapping

import pandas as pd

from app.models import Business


TABLE_COLUMNS = [
    "Business Name",
    "Rating",
    "Reviews",
    "Lead Score",
    "Opportunity Score",
    "Opportunity Label",
    "Phone Number",
    "Website",
    "Website Status",
    "Address",
    "Google Maps Link",
]


def business_record(business: Business) -> dict[str, str | float | int | None]:
    return {
        "Business Name": business.name,
        "Rating": business.rating,
        "Reviews": business.reviews_count,
        "Lead Score": business.lead_score,
        "Opportunity Score": business.opportunity_score,
        "Opportunity Label": business.opportunity_label,
        "Phone Number": business.phone,
        "Website": business.website,
        "Website Status": "Has Website" if business.website else "No Website",
        "Address": business.address,
        "Google Maps Link": business.maps_url,
        "place_id": business.place_id,
    }


def businesses_frame(businesses: list[Business]) -> pd.DataFrame:
    return pd.DataFrame([business_record(business) for business in businesses])


def filter_businesses(
    businesses: list[Business],
    *,
    website_filter: str = "Show All",
    high_opportunity_only: bool = False,
    hot_leads_only: bool = False,
    high_score_only: bool = False,
    no_website_only: bool = False,
    best_leads_only: bool = False,
    minimum_rating: float = 0.0,
    minimum_reviews: int = 0,
    sort_by: str = "Highest Opportunity Score",
) -> list[Business]:
    filtered: list[Business] = []
    for business in businesses:
        has_website = bool(business.website)
        if website_filter == "No Website Only" and has_website:
            continue
        if website_filter == "Has Website Only" and not has_website:
            continue
        if high_opportunity_only and has_website:
            continue
        if hot_leads_only and business.opportunity_label != "HOT LEAD":
            continue
        if high_score_only and business.opportunity_label != "HIGH OPPORTUNITY":
            continue
        if no_website_only and has_website:
            continue
        if best_leads_only and not business.is_best_lead:
            continue
        if business.rating is None or business.rating < minimum_rating:
            continue
        if business.reviews_count < minimum_reviews:
            continue
        filtered.append(business)
    sort_keys = {
        "Highest Opportunity Score": lambda business: (
            -business.opportunity_score,
            business.name.casefold(),
        ),
        "Highest Rating": lambda business: (
            -(business.rating if business.rating is not None else -1.0),
            business.name.casefold(),
        ),
        "Most Reviews": lambda business: (-business.reviews_count, business.name.casefold()),
        "No Website First": lambda business: (
            bool(business.website),
            -business.opportunity_score,
            business.name.casefold(),
        ),
    }
    return sorted(filtered, key=sort_keys.get(sort_by, sort_keys["Highest Opportunity Score"]))


def summary_metrics(businesses: list[Business]) -> dict[str, float | int]:
    rated = [business.rating for business in businesses if business.rating is not None]
    with_website = sum(bool(business.website) for business in businesses)
    return {
        "total": len(businesses),
        "with_website": with_website,
        "without_website": len(businesses) - with_website,
        "average_rating": sum(rated) / len(rated) if rated else 0.0,
        "best_leads": sum(business.is_best_lead for business in businesses),
    }


def competitor_snapshot(
    selected: Business,
    search_results: list[Business],
) -> dict[str, int | float | None]:
    """Summarize website coverage among the other businesses in this search."""
    competitors = [business for business in search_results if business.place_id != selected.place_id]
    total = len(competitors)
    with_website = sum(bool(business.website) for business in competitors)
    without_website = total - with_website
    penetration = (with_website / total * 100) if total else None
    market_opportunity = (100 - penetration) if penetration is not None else None
    return {
        "total_competitors": total,
        "with_website": with_website,
        "without_website": without_website,
        "website_penetration": penetration,
        "market_opportunity": market_opportunity,
    }


def _export_records(
    businesses: list[Business],
    audits: Mapping[str, Mapping[str, object]] | None = None,
) -> list[dict[str, object]]:
    audits = audits or {}
    records: list[dict[str, object]] = []
    for business in businesses:
        record: dict[str, object] = business_record(business)
        audit = audits.get(business.place_id)
        if audit is not None:
            record.update(audit)
        records.append(record)
    return records


def businesses_csv(
    businesses: list[Business],
    audits: Mapping[str, Mapping[str, object]] | None = None,
) -> bytes:
    frame = pd.DataFrame(_export_records(businesses, audits)).drop(columns=["place_id"], errors="ignore")
    return frame.to_csv(index=False).encode("utf-8-sig")


def businesses_json(
    businesses: list[Business],
    audits: Mapping[str, Mapping[str, object]] | None = None,
) -> bytes:
    records = [
        {key: value for key, value in record.items() if key != "place_id"}
        for record in _export_records(businesses, audits)
    ]
    return json.dumps(records, ensure_ascii=False, indent=2).encode("utf-8")