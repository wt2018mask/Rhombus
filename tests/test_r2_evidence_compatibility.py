from __future__ import annotations

import json
from pathlib import Path

import pytest

from rhombus.evidence import (
    Applicability,
    ClaimRecord,
    DomainStatus,
    EvidenceRecord,
    OperationalStatus,
    ScientificVerdict,
    adapt_legacy_evidence,
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
