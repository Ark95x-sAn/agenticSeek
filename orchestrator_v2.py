"""Async orchestrator wiring all components."""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from active_income_optimizer import (
    ClientAcquisitionPipeline,
    FreelanceTask,
    FreelanceTaskRouter,
    Lead,
    PricingEngine,
    ProjectPipeline,
)
from n8n_workflow_router import N8NWorkflowManager
from passive_income_engine import (
    AffiliateCampaign,
    AffiliateMarketingManager,
    ArbitrageScanner,
    AvatarChargeDecoder,
    ContentSyndication,
    DCABot,
    RevenueTracker,
)
from quantum_engine_v2 import ModelSignal, QuantumDecisionEngine


@dataclass
class AIIntegrityVerifier:
    """Verifies the integrity of AI decision outputs."""

    tolerance: float = 0.25

    def verify(self, probability: float) -> bool:
        return 0.0 <= probability <= 1.0 and probability >= self.tolerance


@dataclass
class AgencyHandoffProtocol:
    """Executes A->B->C->A handoff routing."""

    loop: List[str] = field(default_factory=lambda: ["Agency-A", "Agency-B", "Agency-C"])

    def next_agent(self, current: str) -> str:
        if current not in self.loop:
            return self.loop[0]
        idx = self.loop.index(current)
        return self.loop[(idx + 1) % len(self.loop)]


@dataclass
class OrchestratorV2:
    """Main orchestrator coordinating modules."""

    decision_engine: QuantumDecisionEngine = field(default_factory=QuantumDecisionEngine)
    workflow_manager: N8NWorkflowManager = field(default_factory=N8NWorkflowManager)
    arbitrage_scanner: ArbitrageScanner = field(default_factory=ArbitrageScanner)
    affiliate_manager: AffiliateMarketingManager = field(
        default_factory=lambda: AffiliateMarketingManager(
            campaigns=[AffiliateCampaign(name="core", link="https://example.com/ref")]
        )
    )
    content_syndication: ContentSyndication = field(default_factory=ContentSyndication)
    revenue_tracker: RevenueTracker = field(default_factory=RevenueTracker)
    dca_bot: DCABot = field(default_factory=DCABot)
    avatar_decoder: AvatarChargeDecoder = field(default_factory=AvatarChargeDecoder)
    task_router: FreelanceTaskRouter = field(default_factory=FreelanceTaskRouter)
    acquisition_pipeline: ClientAcquisitionPipeline = field(default_factory=ClientAcquisitionPipeline)
    pricing_engine: PricingEngine = field(default_factory=PricingEngine)
    project_pipeline: ProjectPipeline = field(default_factory=ProjectPipeline)
    integrity_verifier: AIIntegrityVerifier = field(default_factory=AIIntegrityVerifier)
    handoff_protocol: AgencyHandoffProtocol = field(default_factory=AgencyHandoffProtocol)

    async def run_decision_cycle(self, output_dir: Path) -> Path:
        signals = [
            ModelSignal(model="DeepSeek", confidence=0.62, rationale="macro alignment"),
            ModelSignal(model="Kimi", confidence=0.58, rationale="flow signals"),
            ModelSignal(model="Gemini", confidence=0.54, rationale="sentiment"),
            ModelSignal(model="GPT-4", confidence=0.66, rationale="risk models"),
        ]
        feed = {"macro": 0.4, "order_flow": 0.3, "sentiment": 0.1, "alt_data": 0.2}
        result = self.decision_engine.consensus(signals, feed)
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / "decision_matrix.json"
        self.decision_engine.export_decision_matrix(result, path)
        return path

    async def run_workflow_cycle(self, output_dir: Path) -> List[Path]:
        return self.workflow_manager.generate_bundle(output_dir)

    async def run_income_cycle(self) -> dict:
        opportunities = self.arbitrage_scanner.scan({"polymarket": 0.05, "kalshi": 0.02})
        affiliate_link = self.affiliate_manager.rotate_link()
        syndication = self.content_syndication.syndicate("content-001")
        revenue = self.revenue_tracker.record(revenue=1200.0, costs=350.0)
        dca_orders = self.dca_bot.generate_orders(capital=1000.0)
        avatar_charge = self.avatar_decoder.decode(engagement_score=1.4)
        return {
            "opportunities": [o.market for o in opportunities],
            "affiliate_link": affiliate_link,
            "syndication": syndication,
            "profit": self.revenue_tracker.profit(),
            "dca_orders": dca_orders,
            "avatar_charge": avatar_charge,
            "latest_revenue": revenue,
        }

    async def run_active_income_cycle(self) -> dict:
        task = FreelanceTask(task_id="task-001", category="ai", value=2400)
        route = self.task_router.route(task)
        leads = [
            Lead(lead_id="lead-1", score=0.72, source="referral"),
            Lead(lead_id="lead-2", score=0.48, source="inbound"),
        ]
        qualified = self.acquisition_pipeline.qualify(leads)
        rate = self.pricing_engine.rate(complexity=0.4, urgency=0.2)
        stage = self.project_pipeline.advance("proposal")
        return {
            "route": route,
            "qualified_leads": [lead.lead_id for lead in qualified],
            "rate": rate,
            "stage": stage,
        }

    async def run_handoff_cycle(self) -> List[str]:
        current = "Agency-A"
        hops = [current]
        for _ in range(3):
            current = self.handoff_protocol.next_agent(current)
            hops.append(current)
        return hops

    async def run(self, output_dir: Path) -> dict:
        decision_task = self.run_decision_cycle(output_dir)
        workflow_task = self.run_workflow_cycle(output_dir / "n8n")
        income_task = self.run_income_cycle()
        active_task = self.run_active_income_cycle()
        handoff_task = self.run_handoff_cycle()
        decision_path, workflow_paths, income, active, handoffs = await asyncio.gather(
            decision_task, workflow_task, income_task, active_task, handoff_task
        )
        integrity_ok = self.integrity_verifier.verify(income["avatar_charge"])
        return {
            "decision_matrix": str(decision_path),
            "workflow_exports": [str(path) for path in workflow_paths],
            "income": income,
            "active_income": active,
            "handoffs": handoffs,
            "integrity_ok": integrity_ok,
        }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Orchestrator v2 CLI")
    parser.add_argument("--output", default="outputs", help="Output directory")
    parser.add_argument("--emit", default="summary.json", help="Summary JSON file")
    return parser


async def main_async(output: str, emit: str) -> None:
    orchestrator = OrchestratorV2()
    result = await orchestrator.run(Path(output))
    Path(emit).write_text(json.dumps(result, indent=2))


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    asyncio.run(main_async(args.output, args.emit))


if __name__ == "__main__":
    main()

