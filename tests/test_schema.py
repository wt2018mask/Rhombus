"""Unit tests for the three-state-machine dataclasses and append-only evidence log."""

from rudeus.schema import (
    CandidateMaterial,
    DynamicState,
    EvidenceEvent,
    ExistenceState,
    TransportState,
)


def test_state_enum_values():
    """Verify all required state values are present and correct."""
    assert ExistenceState.UNKNOWN.value == "UNKNOWN"
    assert ExistenceState.FAIL.value == "FAIL"
    assert ExistenceState.PLAUSIBLE.value == "PLAUSIBLE"
    assert ExistenceState.SUPPORTED.value == "SUPPORTED"

    assert DynamicState.NOT_RUN.value == "NOT_RUN"
    assert DynamicState.FAIL.value == "FAIL"
    assert DynamicState.INDETERMINATE.value == "INDETERMINATE"
    assert DynamicState.PASS.value == "PASS"

    assert TransportState.NOT_RUN.value == "NOT_RUN"
    assert TransportState.NONDIFFUSIVE.value == "NONDIFFUSIVE"
    assert TransportState.INDETERMINATE.value == "INDETERMINATE"
    assert TransportState.DIFFUSIVE.value == "DIFFUSIVE"


def test_candidate_initialization_defaults():
    """Verify default tri-state fields for a new candidate."""
    candidate = CandidateMaterial(
        material_id="mat_test_001",
        formula="Li10GeP2S12",
    )
    assert candidate.existence_state == ExistenceState.UNKNOWN
    assert candidate.dynamic_state == DynamicState.NOT_RUN
    assert candidate.transport_state == TransportState.NOT_RUN
    assert len(candidate.evidence_log) == 0


def test_append_only_evidence_log():
    """Verify that adding evidence updates verdicts without destroying log history."""
    candidate = CandidateMaterial(
        material_id="mat_test_002",
        formula="Li7La3Zr2O12",
    )

    ev1 = EvidenceEvent(
        level="P0",
        method="smact_neutrality",
        conditions={"tolerance": 1e-4},
        uncertainty=None,
        source="p0_filter_v1",
        artifact_hash="abc123hash",
        model_or_data_version="smact_v2",
    )
    candidate.add_evidence(ev1, new_existence_state=ExistenceState.PLAUSIBLE)

    assert candidate.existence_state == ExistenceState.PLAUSIBLE
    assert len(candidate.evidence_log) == 1

    ev2 = EvidenceEvent(
        level="P1",
        method="mace_relax",
        conditions={"fmax": 0.01, "checkpoint": "medium-mpa-0"},
        uncertainty=0.005,
        source="kaggle_shard_1",
        artifact_hash="def456hash",
        model_or_data_version="medium-mpa-0",
    )
    candidate.add_evidence(ev2, new_existence_state=ExistenceState.SUPPORTED)

    assert candidate.existence_state == ExistenceState.SUPPORTED
    assert len(candidate.evidence_log) == 2
    assert candidate.evidence_log[0].level == "P0"
    assert candidate.evidence_log[1].level == "P1"


def test_candidate_serialization():
    """Verify to_dict and from_dict roundtrip preserves all fields."""
    candidate = CandidateMaterial(
        material_id="mat_test_003",
        formula="Li3InCl6",
        existence_state=ExistenceState.PLAUSIBLE,
        dynamic_state=DynamicState.PASS,
        transport_state=TransportState.DIFFUSIVE,
    )
    ev = EvidenceEvent(
        level="P3",
        method="arrhenius_fit",
        conditions={"t_range": [600, 800, 1000]},
        uncertainty=0.03,
        source="colab_worker_0",
        artifact_hash="ghi789hash",
        model_or_data_version="medium-mpa-0",
    )
    candidate.add_evidence(ev)

    serialized = candidate.to_dict()
    restored = CandidateMaterial.from_dict(serialized)

    assert restored.material_id == candidate.material_id
    assert restored.formula == candidate.formula
    assert restored.existence_state == candidate.existence_state
    assert restored.dynamic_state == candidate.dynamic_state
    assert restored.transport_state == candidate.transport_state
    assert len(restored.evidence_log) == 1
    assert restored.evidence_log[0].artifact_hash == "ghi789hash"
