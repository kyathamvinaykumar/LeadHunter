"""Tests for business result exports."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from app.models import Business
from app.services.exporter import Exporter


class ExporterTests(unittest.TestCase):
    def test_exports_businesses_to_csv_and_json(self) -> None:
        business = Business(
            name="Northside Furniture",
            address="Hyderabad",
            rating=4.6,
            reviews_count=23,
            website="https://example.com",
            phone=None,
            maps_url="https://maps.example/place",
            place_id="place-1",
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            paths = Exporter(Path(temporary_directory)).export(
                [business], city="Hyderabad", niche="Furniture Stores"
            )

            self.assertTrue(paths["csv"].is_file())
            self.assertTrue(paths["json"].is_file())
            self.assertEqual(json.loads(paths["json"].read_text(encoding="utf-8"))[0]["name"], business.name)
            csv_record = pd.read_csv(paths["csv"]).iloc[0]
            self.assertEqual(csv_record["place_id"], business.place_id)
            self.assertEqual(csv_record["reviews_count"], business.reviews_count)
            self.assertEqual(csv_record["opportunity_score"], business.opportunity_score)
            self.assertEqual(csv_record["opportunity_label"], business.opportunity_label)


if __name__ == "__main__":
    unittest.main()
