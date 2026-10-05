"""Domain models used by LeadHunter."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Business:
    name: str
    address: str
    rating: float | None
    reviews_count: int
    website: str | None
    phone: str | None
    maps_url: str | None
    place_id: str
    latitude: float | None = None
    longitude: float | None = None

    @property
    def lead_score(self) -> int:
        score = 60 if not self.website else 0
        if self.rating is not None and self.rating >= 4.0:
            score += 15
        if self.reviews_count >= 100:
            score += 15
        if self.phone:
            score += 10
        return score

    @property
    def is_best_lead(self) -> bool:
        return (
            not self.website
            and self.rating is not None
            and self.rating >= 4.0
            and self.reviews_count >= 100
            and bool(self.phone)
        )

    @property
    def opportunity_reasons(self) -> tuple[str, ...]:
        reasons: list[str] = []
        if not self.website:
            reasons.append("No Website")
        if self.rating is not None and self.rating >= 4.0:
            reasons.append("Rating 4.0 or higher")
        if self.reviews_count >= 100:
            reasons.append("100+ Reviews")
        if self.phone:
            reasons.append("Phone Available")
        return tuple(reasons)

    @property
    def opportunity_score(self) -> int:
        score = 50 if not self.website else 0
        if self.rating is not None and self.rating >= 4.5:
            score += 20
        if self.reviews_count >= 100:
            score += 20
        if self.phone:
            score += 10
        return score

    @property
    def opportunity_label(self) -> str:
        score = self.opportunity_score
        if score >= 90:
            return "HOT LEAD"
        if score >= 70:
            return "HIGH OPPORTUNITY"
        if score >= 50:
            return "MEDIUM"
        return "LOW"

    def to_dict(self) -> dict[str, str | float | int | None]:
        record = asdict(self)
        record.pop("latitude")
        record.pop("longitude")
        record["opportunity_score"] = self.opportunity_score
        record["opportunity_label"] = self.opportunity_label
        record["lead_score"] = self.lead_score
        record["opportunity_reasons"] = list(self.opportunity_reasons)
        return record
