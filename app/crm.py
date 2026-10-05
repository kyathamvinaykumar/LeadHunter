"""Session-only prospect CRM helpers."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, replace
from datetime import date
from typing import Mapping

from app.models import Business


PROSPECT_STATUSES = (
    "New",
    "Contacted",
    "Interested",
    "Follow Up",
    "Closed Won",
    "Closed Lost",
)


@dataclass(frozen=True)
class Prospect:
    place_id: str
    business_name: str
    phone: str | None
    website: str | None
    address: str
    rating: float | None
    reviews: int
    maps_url: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    status: str = "New"
    notes: str = ""
    contacted_date: date | None = None
    followup_date: date | None = None

    @classmethod
    def from_business(cls, business: Business) -> Prospect:
        return cls(
            place_id=business.place_id,
            business_name=business.name,
            phone=business.phone,
            website=business.website,
            address=business.address,
            rating=business.rating,
            reviews=business.reviews_count,
            maps_url=business.maps_url,
            latitude=business.latitude,
            longitude=business.longitude,
        )

    def to_business(self) -> Business:
        return Business(
            name=self.business_name,
            address=self.address,
            rating=self.rating,
            reviews_count=self.reviews,
            website=self.website,
            phone=self.phone,
            maps_url=self.maps_url,
            place_id=self.place_id,
            latitude=self.latitude,
            longitude=self.longitude,
        )

    @property
    def lead_score(self) -> int:
        return self.to_business().lead_score


def normalize_prospects(values: Mapping[str, Business | Prospect]) -> dict[str, Prospect]:
    """Upgrade existing session shortlist values while retaining their ids."""
    normalized: dict[str, Prospect] = {}
    for place_id, value in values.items():
        normalized[place_id] = value if isinstance(value, Prospect) else Prospect.from_business(value)
    return normalized


def filter_prospects(
    prospects: list[Prospect],
    *,
    status: str = "All Leads",
    no_website_only: bool = False,
    hot_leads_only: bool = False,
) -> list[Prospect]:
    result = []
    for prospect in prospects:
        if status != "All Leads" and prospect.status != status:
            continue
        if no_website_only and prospect.website:
            continue
        if hot_leads_only and prospect.lead_score < 80:
            continue
        result.append(prospect)
    return result


def crm_summary(prospects: list[Prospect], *, today: date | None = None) -> dict[str, int]:
    today = today or date.today()
    return {
        "total": len(prospects),
        "contacted": sum(prospect.status == "Contacted" for prospect in prospects),
        "interested": sum(prospect.status == "Interested" for prospect in prospects),
        "followups_due": sum(
            prospect.status == "Follow Up"
            and prospect.followup_date is not None
            and prospect.followup_date <= today
            for prospect in prospects
        ),
        "closed_won": sum(prospect.status == "Closed Won" for prospect in prospects),
    }


def crm_export_csv(prospects: list[Prospect]) -> bytes:
    output = io.StringIO(newline="")
    fieldnames = [
        "place_id",
        "business_name",
        "phone",
        "website",
        "website_status",
        "address",
        "rating",
        "reviews",
        "lead_score",
        "status",
        "notes",
        "contacted_date",
        "followup_date",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for prospect in prospects:
        writer.writerow(
            {
                "place_id": prospect.place_id,
                "business_name": prospect.business_name,
                "phone": prospect.phone or "",
                "website": prospect.website or "",
                "website_status": "Has Website" if prospect.website else "No Website",
                "address": prospect.address,
                "rating": prospect.rating if prospect.rating is not None else "",
                "reviews": prospect.reviews,
                "lead_score": prospect.lead_score,
                "status": prospect.status,
                "notes": prospect.notes,
                "contacted_date": prospect.contacted_date.isoformat() if prospect.contacted_date else "",
                "followup_date": prospect.followup_date.isoformat() if prospect.followup_date else "",
            }
        )
    return output.getvalue().encode("utf-8-sig")


def update_prospect(prospect: Prospect, **fields: object) -> Prospect:
    """Return a CRM copy with validated editable fields."""
    if "status" in fields and fields["status"] not in PROSPECT_STATUSES:
        raise ValueError("Unknown prospect status.")
    allowed = {"status", "notes", "contacted_date", "followup_date"}
    if fields.keys() - allowed:
        raise ValueError("Only CRM tracking fields can be updated.")
    return replace(prospect, **fields)