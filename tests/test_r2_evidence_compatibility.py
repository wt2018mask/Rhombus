from __future__ import annotations

import json
from pathlib import Path

import pytest

from rhombus.evidence import (
    Applicability,
    ArtifactBinding,
    ClaimRecord,
    DomainStatus,
    EvidenceRecord,
    Limitation,
    ModelIdentity,
    ModelLineage,
    OperationalStatus,
    ProtocolIdentity,
    ScientificVerdict,
    SourceBinding,
    adapt_legacy_evidence,
    adapt_legacy_evidence_records,
)


ROOT = Path(__file__).resolve().parents[1]


def _load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_evidence_identity_is_deterministic_and_content_addressed() -> None:
    kwargs = dict(
        candidate_id="candidate:test",
        evidence_kind="structure_validation",
        capability="validate_candidate_structure",
        operational_status=OperationalStatus.SUCCEEDED,
        scientific_verdict=ScientificVerdict.INDETERMINATE,
        applicability=Applicability(
            claim_kind="structure_validity",
            domain_status=DomainStatus.UNQUALIFIED,
        ),
        provenance={"source": "unit-test"},
        payload={"value": 1},
    )
    first = EvidenceRecord.create(**kwargs)
    second = EvidenceRecord.create(**kwargs)

    assert first.evidence_id == second.evidence_id
    assert first.evidence_id.startswith("evidence:sha256:")
    assert len(first.evidence_id.split(":")[-1]) == 64

    changed = EvidenceRecord.create(**{**kwargs, "payload": {"value": 2}})
    assert changed.evidence_id != first.evidence_id


def test_pass_claim_fails_closed_without_evidence_or_domain_support() -> None:
    unqualified = Applicability(
        claim_kind="finite_temperature_stability",
        domain_status=DomainStatus.UNQUALIFIED,
    )
    with pytest.raises(ValueError, match="supporting evidence"):
        ClaimRecord.create(
            candidate_id="candidate:test",
            claim_kind="finite_temperature_stability",
            scientific_verdict=ScientificVerdict.PASS,
            evidence_ids=(),
            applicability=unqualified,
        )

    with pytest.raises(ValueError, match="qualified applicability"):
        ClaimRecord.create(
            candidate_id="candidate:test",
            claim_kind="finite_temperature_stability",
            scientific_verdict=ScientificVerdict.PASS,
            evidence_ids=("evidence:sha256:" + "a" * 64,),
            applicability=unqualified,
        )


def test_adapter_preserves_corrected_p2_semantics_without_domain_promotion() -> None:
    path = "data/benchmarks/known_material/b5_p2_corrected_pilot_evidence_v1.json"
    legacy = _load(path)
    adapted = adapt_legacy_evidence(legacy, source_path=path)

    assert adapted.candidate_id == "lialo2-gamma:direct"
    assert adapted.capability == "assess_finite_temperature_stability"
    assert adapted.legacy_stage == "P2"
    assert adapted.operational_status is OperationalStatus.SUCCEEDED
    assert adapted.scientific_verdict is ScientificVerdict.PASS
    assert adapted.applicability.domain_status is DomainStatus.UNQUALIFIED
    assert adapted.payload["trajectory_sha256"] == legacy["trajectory_sha256"]
    assert legacy["result"]["p2_verdict"] == "PASS"


def test_adapter_preserves_insufficient_transport_as_indeterminate() -> None:
    path = "data/benchmarks/known_material/b5_gamma_transport_regime_evidence_v1.json"
    legacy = _load(path)
    adapted = adapt_legacy_evidence(legacy, source_path=path)

    assert adapted.capability == "classify_transport_regime"
    assert adapted.legacy_stage == "P2.5"
    assert adapted.scientific_verdict is ScientificVerdict.INDETERMINATE
    assert adapted.payload["point_transport_state"] == "NONDIFFUSIVE"
    assert adapted.uncertainty.status == "INSUFFICIENT"
    assert adapted.applicability.domain_status is DomainStatus.UNQUALIFIED


def test_extension_maps_authorized_regime_to_pass_not_new_verdict_vocabulary() -> None:
    path = "data/benchmarks/known_material/b5_gamma_transport_extension_evidence_v1.json"
    legacy = _load(path)
    adapted = adapt_legacy_evidence(legacy, source_path=path)

    assert adapted.scientific_verdict is ScientificVerdict.PASS
    assert adapted.payload["transport_state"] == "NONDIFFUSIVE"
    assert adapted.payload["claims"]["nondiffusive_regime_claim_authorized"] is True
    assert adapted.payload["claims"]["conductivity_claim_authorized"] is False
    assert adapted.applicability.domain_status is DomainStatus.UNQUALIFIED
    assert adapted.protocol_id == legacy["extension_protocol_hash"]


def test_unknown_legacy_schema_fails_closed() -> None:
    with pytest.raises(ValueError, match="unsupported legacy evidence schema"):
        adapt_legacy_evidence(
            {"schema_version": "unknown-v1", "material_key": "x"},
            source_path="unknown.json",
        )


def test_identity_and_binding_schemas_validate_provenance_contracts() -> None:
    source = SourceBinding(
        source_type="github-actions",
        source_id="run:123",
        uri="https://example.invalid/run/123",
        sha256="a" * 64,
    )
    artifact = ArtifactBinding(
        artifact_id="artifact:456",
        sha256="b" * 64,
        media_type="application/zip",
        source_id=source.source_id,
    )
    model = ModelIdentity(
        model_id="model:test",
        name="Test MLIP",
        version="1",
        checkpoint_sha256="c" * 64,
        dtype="float32",
    )
    lineage = ModelLineage(
        model_id=model.model_id,
        parent_model_ids=("model:parent",),
        training_source_ids=("dataset:test",),
    )
    protocol = ProtocolIdentity(
        protocol_id="protocol:test-v1",
        capability="assess_finite_temperature_stability",
        version="v1",
        config_hash="deadbeef",
    )
    limitation = Limitation(
        code="SINGLE_TEMPERATURE",
        statement="Evidence is limited to one temperature.",
    )

    assert artifact.source_id == source.source_id
    assert lineage.model_id == model.model_id
    assert protocol.immutable is True
    assert limitation.code == "SINGLE_TEMPERATURE"

    with pytest.raises(ValueError, match="SHA-256"):
        ArtifactBinding(artifact_id="bad", sha256="not-a-sha")

    with pytest.raises(ValueError, match="itself"):
        ModelLineage(model_id="model:x", parent_model_ids=("model:x",))

    with pytest.raises(ValueError, match="immutable"):
        ProtocolIdentity(
            protocol_id="protocol:mutable",
            capability="test",
            version="v1",
            immutable=False,
        )


def test_p1_aggregate_adapter_preserves_only_legacy_retention_meaning() -> None:
    path = "data/benchmarks/known_material/b5_p1_real_evidence_v1.json"
    legacy = _load(path)
    adapted = adapt_legacy_evidence_records(legacy, source_path=path)

    assert len(adapted) == 3
    assert {row.candidate_id for row in adapted} == {
        "lialo2-gamma:direct",
        "libh4-phase-transition-pair:hexagonal",
        "libh4-phase-transition-pair:orthorhombic",
    }
    assert all(row.capability == "relax_structure" for row in adapted)
    assert all(row.legacy_stage == "P1" for row in adapted)
    assert all(row.scientific_verdict is ScientificVerdict.PASS for row in adapted)
    assert all(
        row.applicability.claim_kind == "legacy_p1_retention" for row in adapted
    )
    assert all(
        row.applicability.domain_status is DomainStatus.UNQUALIFIED
        for row in adapted
    )
    assert all(row.source_bindings for row in adapted)
    assert all(row.artifact_bindings for row in adapted)
    assert all(
        row.payload["qualification_evidence_authorized"] is False
        for row in adapted
    )

    with pytest.raises(ValueError, match="multiple records"):
        adapt_legacy_evidence(legacy, source_path=path)


def test_adapter_populates_typed_bindings_without_changing_flat_public_ids() -> None:
    path = "data/benchmarks/known_material/b5_gamma_transport_extension_evidence_v1.json"
    adapted = adapt_legacy_evidence(_load(path), source_path=path)

    typed_ids = {item.artifact_id for item in adapted.artifact_bindings}
    assert typed_ids == set(adapted.artifact_ids)
    assert any(
        item.source_type == "legacy_repository_evidence"
        for item in adapted.source_bindings
    )
    assert adapted.limitation_records
    assert adapted.to_dict()["artifact_ids"] == list(adapted.artifact_ids)
