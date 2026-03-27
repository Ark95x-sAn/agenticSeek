"""Passive income automation stack components."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List


@dataclass
class ArbitrageOpportunity:
    """Represents an arbitrage opportunity between markets."""

    market: str
    spread: float
    liquidity: float


@dataclass
class ArbitrageScanner:
    """Scans Polymarket and Kalshi spread opportunities."""

    threshold: float = 0.03

    def scan(self, market_data: Dict[str, float]) -> List[ArbitrageOpportunity]:
        opportunities = []
        for market, spread in market_data.items():
            if spread >= self.threshold:
                opportunities.append(
                    ArbitrageOpportunity(market=market, spread=spread, liquidity=spread * 10000)
                )
        return opportunities


@dataclass
class AffiliateCampaign:
    """Tracks affiliate campaign metadata."""

    name: str
    link: str
    conversions: int = 0
    revenue: float = 0.0


@dataclass
class AffiliateMarketingManager:
    """Manages affiliate campaigns and rotating links."""

    campaigns: List[AffiliateCampaign] = field(default_factory=list)
    rotation_index: int = 0

    def rotate_link(self) -> str:
        if not self.campaigns:
            return ""
        self.rotation_index = (self.rotation_index + 1) % len(self.campaigns)
        return self.campaigns[self.rotation_index].link

    def track_conversion(self, campaign_name: str, revenue: float) -> None:
        for campaign in self.campaigns:
            if campaign.name == campaign_name:
                campaign.conversions += 1
                campaign.revenue += revenue
                return


@dataclass
class ContentSyndication:
    """Handles multi-platform content distribution."""

    platforms: List[str] = field(default_factory=lambda: ["x", "linkedin", "medium", "substack"])

    def syndicate(self, content_id: str) -> Dict[str, str]:
        return {platform: f"{content_id}:{platform}" for platform in self.platforms}


@dataclass
class RevenueSnapshot:
    """Represents a revenue snapshot for P&L."""

    timestamp: str
    revenue: float
    costs: float


@dataclass
class RevenueTracker:
    """Tracks revenue and costs for a P&L dashboard."""

    snapshots: List[RevenueSnapshot] = field(default_factory=list)

    def record(self, revenue: float, costs: float) -> RevenueSnapshot:
        snapshot = RevenueSnapshot(
            timestamp=datetime.utcnow().isoformat(),
            revenue=revenue,
            costs=costs,
        )
        self.snapshots.append(snapshot)
        return snapshot

    def profit(self) -> float:
        return sum(s.revenue - s.costs for s in self.snapshots)


@dataclass
class DCABot:
    """Dollar-cost averaging bot for crypto purchases."""

    allocations: Dict[str, float] = field(default_factory=lambda: {"BTC": 0.5, "ETH": 0.3, "SOL": 0.2})

    def generate_orders(self, capital: float) -> Dict[str, float]:
        return {asset: capital * allocation for asset, allocation in self.allocations.items()}


@dataclass
class AvatarChargeDecoder:
    """Maps engagement signals to monetization triggers."""

    base_rate: float = 0.02

    def decode(self, engagement_score: float) -> float:
        multiplier = 1 + max(engagement_score, 0)
        return self.base_rate * multiplier

