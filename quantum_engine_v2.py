"""Quantum decision engine with multi-model consensus and adaptive learning."""

from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


@dataclass
class ModelSignal:
    """Represents a model's signal contribution."""

    model: str
    confidence: float
    rationale: str


@dataclass
class DecisionResult:
    """Represents a consolidated decision outcome."""

    decision: str
    score: float
    probability: float
    signals: List[ModelSignal]
    timestamp: str


@dataclass
class SignalProcessor:
    """Processes CRUCIX-style intelligence feeds into normalized signals."""

    weight_map: Dict[str, float] = field(default_factory=lambda: {
        "macro": 0.4,
        "order_flow": 0.3,
        "sentiment": 0.2,
        "alt_data": 0.1,
    })

    def process(self, feed: Dict[str, float]) -> float:
        """Aggregate feed values into a weighted signal."""
        total = 0.0
        for key, value in feed.items():
            weight = self.weight_map.get(key, 0.05)
            total += weight * value
        return max(min(total, 1.0), -1.0)


@dataclass
class StrategyOptimizer:
    """Monte Carlo optimizer for strategy selection."""

    simulations: int = 250
    volatility: float = 0.12

    def run(self, base_score: float) -> Tuple[float, float]:
        """Return mean and downside risk from Monte Carlo trials."""
        outcomes = []
        for _ in range(self.simulations):
            shock = random.gauss(0, self.volatility)
            outcomes.append(base_score + shock)
        mean = sum(outcomes) / len(outcomes)
        downside = min(outcomes)
        return mean, downside


@dataclass
class AdaptiveLearner:
    """Adaptive learning loop that adjusts model weights."""

    weights: Dict[str, float] = field(default_factory=lambda: {
        "DeepSeek": 0.25,
        "Kimi": 0.25,
        "Gemini": 0.25,
        "GPT-4": 0.25,
    })

    def update(self, model: str, performance: float) -> None:
        """Update weights based on performance feedback."""
        delta = max(min(performance, 1.0), -1.0) * 0.05
        self.weights[model] = max(self.weights.get(model, 0.1) + delta, 0.05)
        total = sum(self.weights.values())
        for key in list(self.weights.keys()):
            self.weights[key] /= total


@dataclass
class QuantumDecisionEngine:
    """Decision engine using quantum-inspired probability weighting."""

    learner: AdaptiveLearner = field(default_factory=AdaptiveLearner)
    signal_processor: SignalProcessor = field(default_factory=SignalProcessor)
    optimizer: StrategyOptimizer = field(default_factory=StrategyOptimizer)

    def _quantum_weight(self, score: float) -> float:
        amplitude = math.tanh(score)
        probability = amplitude**2
        return max(min(probability, 1.0), 0.0)

    def consensus(self, signals: Iterable[ModelSignal], feed: Dict[str, float]) -> DecisionResult:
        """Generate a decision with multi-model consensus."""
        signal_list = list(signals)
        base_score = 0.0
        for signal in signal_list:
            weight = self.learner.weights.get(signal.model, 0.1)
            base_score += weight * signal.confidence
        feed_score = self.signal_processor.process(feed)
        combined_score = (base_score + feed_score) / 2
        mean, downside = self.optimizer.run(combined_score)
        probability = self._quantum_weight(mean)
        decision = "approve" if mean > 0.15 and downside > -0.4 else "hold"
        timestamp = datetime.utcnow().isoformat()
        return DecisionResult(
            decision=decision,
            score=mean,
            probability=probability,
            signals=signal_list,
            timestamp=timestamp,
        )

    def export_decision_matrix(self, result: DecisionResult, path: Path) -> None:
        """Export decision matrix to JSON."""
        payload = {
            "decision": result.decision,
            "score": result.score,
            "probability": result.probability,
            "timestamp": result.timestamp,
            "signals": [
                {"model": s.model, "confidence": s.confidence, "rationale": s.rationale}
                for s in result.signals
            ],
        }
        path.write_text(json.dumps(payload, indent=2))

