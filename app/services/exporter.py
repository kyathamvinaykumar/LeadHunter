"""CSV and JSON export for discovered businesses."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import pandas as pd

from app.models import Business


class Exporter:
    """Write business records to CSV and JSON files."""

    def __init__(self, export_dir: Path) -> None:
        self._export_dir = export_dir

    def export(
        self,
        businesses: list[Business],
        *,
        city: str,
        niche: str,
    ) -> dict[str, Path]:
        self._export_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stem = "_".join((self._slug(city), self._slug(niche), timestamp))
        csv_path = self._export_dir / f"{stem}.csv"
        json_path = self._export_dir / f"{stem}.json"
        records = [business.to_dict() for business in businesses]

        pd.DataFrame(records).to_csv(csv_path, index=False, encoding="utf-8-sig")
        json_path.write_text(
            json.dumps(records, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return {"csv": csv_path, "json": json_path}

    @staticmethod
    def _slug(value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
        return slug or "search"
