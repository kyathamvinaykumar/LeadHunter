"""Tests for session CRM records and exports."""

from __future__ import annotations

import csv
import io
import unittest
from datetime import date, timedelta

from app.crm import (
    Prospect,
    crm_export_csv,
    crm_summary,
    filter_prospects,
    normalize_prospects,
    update_prospect,
)
from app.models import Business


def make_prospect(
    place_id: str,
    *,
    website: str | None = None,
    score_rating: float | None = 4.5,
    reviews: int = 120,
    status: str = "New",
    followup_date: date | None = None,
) -> Prospect:
    return Prospect(
        place_id=place_id,
        business_name=f"Business {place_id}",
        phone="555-0100",
        website=website,
        address="Example address",
        rating=score_rating,
        reviews=reviews,
        status=status,
        followup_date=followup_date,
    )


class ProspectCrmTests(unittest.TestCase):
    def test_normalizes_existing_shortlist_business(self) -> None:
        business = Business(
            name="Existing lead",
            address="Address",
            rating=4.3,
            reviews_count=150,
            website=None,
            phone="555",
            maps_url="https://maps.example",
            place_id="existing",
        )

        prospect = normalize_prospects({"existing": business})["existing"]

        self.assertEqual(prospect.business_name, "Existing lead")
        self.assertEqual(prospect.status, "New")
        self.assertEqual(prospect.to_business(), business)

    def test_updates_only_crm_fields_and_validates_status(self) -> None:
        prospect = make_prospect("a")
        updated = update_prospect(
            prospect,
            status="Contacted",
            notes="Owner answered call",
            contacted_date=date(2026, 10, 2),
        )

        self.assertEqual(updated.status, "Contacted")
        self.assertEqual(updated.notes, "Owner answered call")
        self.assertEqual(updated.contacted_date, date(2026, 10, 2))
        with self.assertRaises(ValueError):
            update_prospect(prospect, status="Archived")
        with self.assertRaises(ValueError):
            update_prospect(prospect, phone="new number")

    def test_filters_by_status_no_website_and_hot_score(self) -> None:
        leads = [
            make_prospect("hot"),
            make_prospect("site", website="https://site.example"),
            make_prospect("contacted", status="Contacted"),
        ]

        self.assertEqual(
            [lead.place_id for lead in filter_prospects(leads, status="Contacted")],
            ["contacted"],
        )
        self.assertEqual(
            [lead.place_id for lead in filter_prospects(leads, no_website_only=True)],
            ["hot", "contacted"],
        )
        self.assertEqual(
            [lead.place_id for lead in filter_prospects(leads, hot_leads_only=True)],
            ["hot", "contacted"],
        )

    def test_crm_summary_counts_followups_due_and_closed_won(self) -> None:
        today = date(2026, 10, 2)
        leads = [
            make_prospect("contacted", status="Contacted"),
            make_prospect("interested", status="Interested"),
            make_prospect("due", status="Follow Up", followup_date=today),
            make_prospect("late", status="Follow Up", followup_date=today - timedelta(days=1)),
            make_prospect("future", status="Follow Up", followup_date=today + timedelta(days=1)),
            make_prospect("won", status="Closed Won"),
        ]

        self.assertEqual(
            crm_summary(leads, today=today),
            {"total": 6, "contacted": 1, "interested": 1, "followups_due": 2, "closed_won": 1},
        )

    def test_crm_csv_contains_business_and_tracking_fields(self) -> None:
        prospect = update_prospect(
            make_prospect("a"),
            status="Interested",
            notes="Asked to call next week",
            contacted_date=date(2026, 10, 1),
            followup_date=date(2026, 10, 8),
        )

        rows = list(csv.DictReader(io.StringIO(crm_export_csv([prospect]).decode("utf-8-sig"))))

        self.assertEqual(rows[0]["business_name"], "Business a")
        self.assertEqual(rows[0]["lead_score"], "100")
        self.assertEqual(rows[0]["status"], "Interested")
        self.assertEqual(rows[0]["notes"], "Asked to call next week")
        self.assertEqual(rows[0]["contacted_date"], "2026-10-01")
        self.assertEqual(rows[0]["followup_date"], "2026-10-08")


if __name__ == "__main__":
    unittest.main()