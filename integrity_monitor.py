from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class AuditLog:
    timestamp: str
    model_version: str
    confidence_score: float
    consensus_reached: bool


@dataclass
class ConsensusResult:
    consensus_reached: bool
    agreed_output: Optional[str]
    agreement_count: int
    total_models: int
    confidence_score: float
    dissenting_models: List[str]
    omission_flags: List[str]


class AIIntegrityVerifier:
    """Cross-model integrity verification with drift and consensus checks."""

    def __init__(self) -> None:
        self.audit_logs: List[AuditLog] = []

    def cross_check_outputs(self, responses: Dict[str, Any]) -> ConsensusResult:
        if not responses:
            result = ConsensusResult(
                consensus_reached=False,
                agreed_output=None,
                agreement_count=0,
                total_models=0,
                confidence_score=0.0,
                dissenting_models=[],
                omission_flags=[],
            )
            return result

        normalized_map = {
            model: self._normalize_output(str(output)) for model, output in responses.items()
        }
        normalized_outputs = list(normalized_map.values())

        consensus_data = self.build_consensus(normalized_outputs, threshold=3)
        agreed_output = consensus_data["agreed_output"]
        agreement_count = consensus_data["agreement_count"]
        total = consensus_data["total_models"]
        confidence = consensus_data["confidence_score"]
        consensus_reached = consensus_data["consensus_reached"]

        dissenting_models = [
            model for model, output in normalized_map.items() if output != agreed_output
        ] if agreed_output is not None else list(normalized_map.keys())

        omission_flags = [
            model
            for model, output in normalized_map.items()
            if self._is_potential_omission(output)
        ]

        timestamp = datetime.now(timezone.utc).isoformat()
        for model in responses.keys():
            self.audit_logs.append(
                AuditLog(
                    timestamp=timestamp,
                    model_version=model,
                    confidence_score=confidence,
                    consensus_reached=consensus_reached,
                )
            )

        return ConsensusResult(
            consensus_reached=consensus_reached,
            agreed_output=agreed_output,
            agreement_count=agreement_count,
            total_models=total,
            confidence_score=confidence,
            dissenting_models=dissenting_models,
            omission_flags=omission_flags,
        )

    def detect_drift(self, baseline: Dict[str, Any], current: Dict[str, Any]) -> Dict[str, Any]:
        baseline_keys = set(baseline.keys())
        current_keys = set(current.keys())

        removed_keys = sorted(baseline_keys - current_keys)
        added_keys = sorted(current_keys - baseline_keys)

        changed_values: Dict[str, Dict[str, Any]] = {}
        for key in sorted(baseline_keys & current_keys):
            if baseline[key] != current[key]:
                changed_values[key] = {"baseline": baseline[key], "current": current[key]}

        comparisons = max(1, len(baseline_keys | current_keys))
        drift_points = len(removed_keys) + len(added_keys) + len(changed_values)
        drift_score = drift_points / comparisons

        return {
            "drift_detected": drift_points > 0,
            "drift_score": drift_score,
            "added_keys": added_keys,
            "removed_keys": removed_keys,
            "changed_values": changed_values,
        }

    def build_consensus(self, responses: List[Any], threshold: int = 3) -> Dict[str, Any]:
        normalized = [self._normalize_output(str(r)) for r in responses if r is not None]
        total = len(normalized)

        if total == 0:
            return {
                "consensus_reached": False,
                "agreed_output": None,
                "agreement_count": 0,
                "total_models": 0,
                "confidence_score": 0.0,
            }

        counts = Counter(normalized)
        agreed_output, agreement_count = counts.most_common(1)[0]
        confidence = agreement_count / total

        return {
            "consensus_reached": agreement_count >= threshold,
            "agreed_output": agreed_output,
            "agreement_count": agreement_count,
            "total_models": total,
            "confidence_score": confidence,
        }

    @staticmethod
    def _normalize_output(text: str) -> str:
        return " ".join(text.strip().lower().split())

    @staticmethod
    def _is_potential_omission(text: str) -> bool:
        if not text:
            return True
        minimal_markers = {"n/a", "none", "no issues", "ok", "unknown"}
        return text in minimal_markers or len(text) < 10
