from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from .config import AppConfig
from .utils import read_json, utc_timestamp, write_json


@dataclass(slots=True)
class RevenueRecord:
    account: str
    amount: float
    category: str
    status: str
    source: str


class RevenueIntelligence:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def _load_state(self) -> dict[str, Any]:
        return read_json(self.config.revenue_state_file, default={"records": [], "updated_at": None})

    def add_record(self, record: RevenueRecord) -> dict[str, Any]:
        state = self._load_state()
        rows = state.get("records", [])
        rows.append(
            {
                "account": record.account,
                "amount": float(record.amount),
                "category": record.category,
                "status": record.status,
                "source": record.source,
                "created_at": utc_timestamp(),
            }
        )
        state["records"] = rows
        state["updated_at"] = utc_timestamp()
        write_json(self.config.revenue_state_file, state)
        return {"saved": True, "total_records": len(rows), "state_file": str(self.config.revenue_state_file)}

    def summary(self) -> dict[str, Any]:
        state = self._load_state()
        records = state.get("records", [])

        total = sum(float(r.get("amount", 0.0)) for r in records)
        by_status: dict[str, float] = defaultdict(float)
        by_category: dict[str, float] = defaultdict(float)

        for r in records:
            by_status[r.get("status", "unknown")] += float(r.get("amount", 0.0))
            by_category[r.get("category", "uncategorized")] += float(r.get("amount", 0.0))

        return {
            "updated_at": state.get("updated_at"),
            "record_count": len(records),
            "total_amount": round(total, 2),
            "by_status": dict(sorted(by_status.items())),
            "by_category": dict(sorted(by_category.items())),
            "state_file": str(self.config.revenue_state_file),
        }
