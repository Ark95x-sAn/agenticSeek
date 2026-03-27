from integrity_monitor import AIIntegrityVerifier, ConsensusResult


def test_build_consensus_reaches_threshold():
    verifier = AIIntegrityVerifier()
    responses = ["Approved", "approved", "approved", "reject"]

    result = verifier.build_consensus(responses, threshold=3)

    assert result["consensus_reached"] is True
    assert result["agreed_output"] == "approved"
    assert result["agreement_count"] == 3
    assert result["total_models"] == 4


def test_build_consensus_fails_when_threshold_not_met():
    verifier = AIIntegrityVerifier()
    responses = ["yes", "no", "maybe"]

    result = verifier.build_consensus(responses, threshold=2)

    assert result["consensus_reached"] is False
    assert result["agreement_count"] == 1


def test_detect_drift_flags_key_and_value_changes():
    verifier = AIIntegrityVerifier()
    baseline = {"policy": "strict", "version": 1, "region": "us"}
    current = {"policy": "lenient", "version": 2, "team": "ops"}

    drift = verifier.detect_drift(baseline, current)

    assert drift["drift_detected"] is True
    assert "region" in drift["removed_keys"]
    assert "team" in drift["added_keys"]
    assert "policy" in drift["changed_values"]
    assert "version" in drift["changed_values"]


def test_cross_check_outputs_returns_consensus_result_and_audit_logs():
    verifier = AIIntegrityVerifier()
    responses = {
        "model-a": "Critical risk identified in clause 5",
        "model-b": "critical risk identified in clause 5",
        "model-c": "critical risk identified in clause 5",
        "model-d": "n/a",
    }

    result = verifier.cross_check_outputs(responses)

    assert isinstance(result, ConsensusResult)
    assert result.consensus_reached is True
    assert result.agreed_output == "critical risk identified in clause 5"
    assert "model-d" in result.omission_flags
    assert len(verifier.audit_logs) == len(responses)
    assert all(log.model_version in responses for log in verifier.audit_logs)
