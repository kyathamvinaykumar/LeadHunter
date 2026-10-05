"""Tests for deterministic opportunity score and labels."""

from __future__ import annotations

import unittest

from app.models import Business


def make_business(*, website=None, rating=None, reviews=0, phone=None) -> Business:
    return Business(
        name="Example business",
        address="Example address",
        rating=rating,
        reviews_count=reviews,
        website=website,
        phone=phone,
        maps_url=None,
        place_id="example",
    )


class OpportunityScoreTests(unittest.TestCase):
    def test_all_rules_combine_to_hot_lead(self) -> None:
        business = make_business(website=None, rating=4.5, reviews=100, phone="+1 555 0100")

        self.assertEqual(business.opportunity_score, 100)
        self.assertEqual(business.opportunity_label, "HOT LEAD")
        self.assertEqual(business.to_dict()["opportunity_score"], 100)

    def test_labels_cover_all_score_bands(self) -> None:
        examples = [
            (make_business(website=None, rating=4.5), "HIGH OPPORTUNITY"),
            (make_business(website=None), "MEDIUM"),
            (make_business(website="https://example.com"), "LOW"),
        ]
        for business, label in examples:
            with self.subTest(label=label):
                self.assertEqual(business.opportunity_label, label)

    def test_score_is_capped_by_rule_total(self) -> None:
        business = make_business(website=None, rating=5.0, reviews=1000, phone="123")

        self.assertLessEqual(business.opportunity_score, 100)

    def test_phase_one_lead_score_examples(self) -> None:
        examples = [
            (make_business(website=None, rating=4.0, reviews=100, phone="555"), 100),
            (make_business(website=None, rating=4.0, reviews=100), 90),
            (make_business(website=None, rating=4.0, reviews=0, phone="555"), 85),
            (make_business(website="https://site.example", rating=4.0, reviews=100), 30),
        ]
        for business, expected in examples:
            with self.subTest(expected=expected):
                self.assertEqual(business.lead_score, expected)
                self.assertEqual(business.to_dict()["lead_score"], expected)

    def test_best_lead_requires_all_four_criteria(self) -> None:
        qualified = make_business(website=None, rating=4.0, reviews=100, phone="555")
        rejected = [
            make_business(website="https://site.example", rating=5.0, reviews=500, phone="555"),
            make_business(website=None, rating=3.9, reviews=100, phone="555"),
            make_business(website=None, rating=4.0, reviews=99, phone="555"),
            make_business(website=None, rating=4.0, reviews=100),
        ]

        self.assertTrue(qualified.is_best_lead)
        self.assertTrue(all(not business.is_best_lead for business in rejected))

    def test_opportunity_reasons_match_score_criteria(self) -> None:
        business = make_business(website=None, rating=4.2, reviews=150, phone="555")

        self.assertEqual(
            business.opportunity_reasons,
            ("No Website", "Rating 4.0 or higher", "100+ Reviews", "Phone Available"),
        )
        self.assertEqual(business.to_dict()["opportunity_reasons"], list(business.opportunity_reasons))


if __name__ == "__main__":
    unittest.main()