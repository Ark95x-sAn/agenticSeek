"""Tests for orchestrator v2 stack."""

from __future__ import annotations

import asyncio
from pathlib import Path

from orchestrator_v2 import OrchestratorV2
from quantum_engine_v2 import ModelSignal, QuantumDecisionEngine
from n8n_workflow_router import N8NWorkflowManager


def test_quantum_engine_consensus(tmp_path: Path) -> None:
    engine = QuantumDecisionEngine()
    signals = [
        ModelSignal(model="DeepSeek", confidence=0.7, rationale="macro"),
        ModelSignal(model="Kimi", confidence=0.6, rationale="flow"),
        ModelSignal(model="Gemini", confidence=0.55, rationale="sentiment"),
        ModelSignal(model="GPT-4", confidence=0.65, rationale="risk"),
    ]
    feed = {"macro": 0.3, "order_flow": 0.2, "sentiment": 0.1, "alt_data": 0.05}
    result = engine.consensus(signals, feed)
    assert 0.0 <= result.probability <= 1.0
    path = tmp_path / "decision_matrix.json"
    engine.export_decision_matrix(result, path)
    assert path.exists()


def test_workflow_manager_exports(tmp_path: Path) -> None:
    manager = N8NWorkflowManager()
    paths = manager.generate_bundle(tmp_path)
    assert paths
    for path in paths:
        assert path.exists()


def test_orchestrator_run(tmp_path: Path) -> None:
    orchestrator = OrchestratorV2()
    result = asyncio.run(orchestrator.run(tmp_path))
    assert result["decision_matrix"].endswith("decision_matrix.json")
    assert result["workflow_exports"]
    assert "income" in result

