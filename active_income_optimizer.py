"""Active income optimization components."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class FreelanceTask:
    """Represents a freelance task assignment."""

    task_id: str
    category: str
    value: float


@dataclass
class FreelanceTaskRouter:
    """Routes freelance tasks to the best-fit lane."""

    lane_map: Dict[str, str] = field(default_factory=lambda: {"ai": "Lane-A", "ops": "Lane-B", "design": "Lane-C"})

    def route(self, task: FreelanceTask) -> str:
        return self.lane_map.get(task.category, "Lane-Default")


@dataclass
class Lead:
    """Represents a client acquisition lead."""

    lead_id: str
    score: float
    source: str


@dataclass
class ClientAcquisitionPipeline:
    """Pipeline with lead scoring and qualification."""

    minimum_score: float = 0.6

    def qualify(self, leads: List[Lead]) -> List[Lead]:
        return [lead for lead in leads if lead.score >= self.minimum_score]


@dataclass
class PricingEngine:
    """Dynamic rate pricing engine."""

    base_rate: float = 120.0

    def rate(self, complexity: float, urgency: float) -> float:
        return self.base_rate * (1 + complexity) * (1 + urgency)


@dataclass
class ProjectPipeline:
    """Manages active project pipeline stages."""

    stages: List[str] = field(default_factory=lambda: ["lead", "proposal", "negotiation", "delivery", "retainer"])

    def advance(self, current_stage: str) -> str:
        if current_stage not in self.stages:
            return self.stages[0]
        idx = self.stages.index(current_stage)
        return self.stages[min(idx + 1, len(self.stages) - 1)]

