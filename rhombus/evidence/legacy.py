"""Compatibility adapters from immutable legacy evidence into v2 records.

Adapters are one-way views.  They never rewrite historical files and never
upgrade a legacy scientific claim beyond what the source explicitly authorizes.
"""

from __future__ import annotations

from typing import Any, Mapping

from .schema import (
    Applicability,
    DomainStatus,
    EvidenceRecord,
    OperationalStatus,
    ScientificVerdict,
    Uncertainty,
)


def _candidate_id(record: Mapping[str, Any]) -> str:
    material = str(record.get("material_key", "")).strip()
    component = str(record.get("component_label", "")).strip()
    if not material:
        raise ValueError("legacy evidence is missing material_key")
    return f"{material}:{component}" if component else material


def _artifact_ids(record: Mapping[str, Any]) -> tuple[str, ...]:
    ids: list[str] = []
    for key in (
        "artifact_id",
        "source_extension_artifact_id",
        "source_reclassify_artifact_id",
    ):
        value = record.get(key)
        if value is not None:
            ids.append(f"github-actions-artifact:{value}")
    source = record.get("source")
    if isinstance(source, Mapping) and source.get("artifact_id") is not None:
        ids.append(f"github-actions-artifact:{source['artifact_id']}")
    return tuple(ids)


def _provenance(
    record: Mapping[str, Any],
    *,
    source_path: str,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "adapter": "rhombus.evidence.legacy.adapt_legacy_evidence",
        "source_path": source_path,
        "source_schema_version": record.get("schema_version"),
    }
    for key in (
        "workflow_run_id",
        "source_extension_run_id",
        "source_reclassify_run_id",
        "batch_id",
        "backend",
    ):
        if key in record:
            result[key] = record[key]
    source = record.get("source")
    if isinstance(source, Mapping):
        result["source"] = dict(source)
    return result


def _limitations(record: Mapping[str, Any]) -> tuple[str, ...]:
    rows: list[str] = []
    explicit = record.get("limitations")
    if isinstance(explicit, list):
        rows.extend(str(item) for item in explicit if str(item).strip())
    interpretation = record.get("interpretation")
    if isinstance(interpretation, Mapping):
        note = interpretation.get("note")
        if note:
            rows.append(str(note))
    rows.append(
        "Legacy evidence compatibility view; applicability remains UNQUALIFIED "
        "until independent v2 domain evidence is attached."
    )
    return tuple(rows)


def _adapt_p2(
    record: Mapping[str, Any],
    *,
    source_path: str,
) -> EvidenceRecord:
    result = record.get("result")
    if not isinstance(result, Mapping):
        raise ValueError("legacy P2 evidence is missing result")

    raw_verdict = str(result.get("p2_verdict", result.get("dynamic_state", "")))
    try:
        verdict = ScientificVerdict(raw_verdict)
    except ValueError as exc:
        raise ValueError(f"unsupported legacy P2 verdict: {raw_verdict!r}") from exc

    operational = (
        OperationalStatus.ERROR
        if result.get("numerical_abort") is not None
        else OperationalStatus.SUCCEEDED
    )
    protocol_id = record.get("protocol_version")
    return EvidenceRecord.create(
        candidate_id=_candidate_id(record),
        evidence_kind="finite_temperature_stability",
        capability="assess_finite_temperature_stability",
        operational_status=operational,
        scientific_verdict=verdict,
        applicability=Applicability(
            claim_kind="finite_temperature_stability",
            domain_status=DomainStatus.UNQUALIFIED,
        ),
        uncertainty=Uncertainty(
            status="LEGACY_NOT_CALIBRATED",
            reason="no v2 claim-specific uncertainty/domain assessment attached",
        ),
        limitations=_limitations(record),
        artifact_ids=_artifact_ids(record),
        protocol_id=str(protocol_id) if protocol_id else None,
        provenance=_provenance(record, source_path=source_path),
        payload={
            "legacy_result": dict(result),
            "legacy_interpretation": dict(record.get("interpretation", {})),
            "trajectory_sha256": record.get("trajectory_sha256"),
        },
        legacy_stage="P2",
    )


def _adapt_transport_classification(
    record: Mapping[str, Any],
    *,
    source_path: str,
) -> EvidenceRecord:
    result = record.get("result")
    if not isinstance(result, Mapping):
        raise ValueError("legacy transport evidence is missing result")
    raw_verdict = str(result.get("scientific_verdict", "INDETERMINATE"))
    try:
        verdict = ScientificVerdict(raw_verdict)
    except ValueError as exc:
        raise ValueError(
            f"unsupported legacy transport scientific verdict: {raw_verdict!r}"
        ) from exc

    uncertainty = Uncertainty(
        status=str(result.get("uncertainty_status", "UNKNOWN")).upper(),
        reason=(
            str(result["uncertainty_reason"])
            if result.get("uncertainty_reason") is not None
            else None
        ),
        metrics={
            key: result[key]
            for key in ("n_origin_blocks", "min_origin_blocks", "n_valid_lags")
            if key in result
        },
    )
    return EvidenceRecord.create(
        candidate_id=_candidate_id(record),
        evidence_kind="transport_regime_classification",
        capability="classify_transport_regime",
        operational_status=OperationalStatus(
            str(result.get("operational_status", "SUCCEEDED"))
        ),
        scientific_verdict=verdict,
        applicability=Applicability(
            claim_kind="transport_regime",
            domain_status=DomainStatus.UNQUALIFIED,
        ),
        uncertainty=uncertainty,
        limitations=_limitations(record),
        artifact_ids=_artifact_ids(record),
        protocol_id=None,
        provenance=_provenance(record, source_path=source_path),
        payload={
            "transport_state": result.get("transport_state"),
            "point_transport_state": result.get("point_transport_state"),
            "legacy_result": dict(result),
            "legacy_interpretation": dict(record.get("interpretation", {})),
        },
        legacy_stage="P2.5",
    )


def _adapt_transport_extension(
    record: Mapping[str, Any],
    *,
    source_path: str,
) -> EvidenceRecord:
    claims = record.get("claims")
    if not isinstance(claims, Mapping):
        raise ValueError("legacy transport extension evidence is missing claims")

    transport_state = str(record.get("transport_state", "")).strip()
    nondiffusive_authorized = bool(
        claims.get("nondiffusive_regime_claim_authorized", False)
    )
    diffusive_authorized = bool(
        claims.get("diffusive_regime_claim_authorized", False)
    )
    if nondiffusive_authorized or diffusive_authorized:
        verdict = ScientificVerdict.PASS
    else:
        verdict = ScientificVerdict.INDETERMINATE

    sufficiency = record.get("sufficiency")
    metrics = dict(sufficiency) if isinstance(sufficiency, Mapping) else {}
    return EvidenceRecord.create(
        candidate_id=_candidate_id(record),
        evidence_kind="transport_regime_classification",
        capability="classify_transport_regime",
        operational_status=OperationalStatus(
            str(record.get("operational_status", "SUCCEEDED"))
        ),
        scientific_verdict=verdict,
        applicability=Applicability(
            claim_kind="transport_regime",
            domain_status=DomainStatus.UNQUALIFIED,
        ),
        uncertainty=Uncertainty(
            status="SUFFICIENT" if verdict is ScientificVerdict.PASS else "INSUFFICIENT",
            reason=None if verdict is ScientificVerdict.PASS else "claim not authorized",
            metrics=metrics,
        ),
        limitations=_limitations(record),
        artifact_ids=_artifact_ids(record),
        protocol_id=(
            str(record["extension_protocol_hash"])
            if record.get("extension_protocol_hash")
            else None
        ),
        provenance=_provenance(record, source_path=source_path),
        payload={
            "transport_state": transport_state,
            "stability_verdict": record.get("stability_verdict"),
            "claims": dict(claims),
            "sufficiency": metrics,
            "transport_metrics": dict(record.get("transport_metrics", {})),
        },
        legacy_stage="P2.5",
    )


def adapt_legacy_evidence(
    record: Mapping[str, Any],
    *,
    source_path: str,
) -> EvidenceRecord:
    """Return a content-addressed v2 compatibility view of known legacy evidence.

    The source record is not modified.  Unknown legacy schemas fail closed.
    """

    schema = str(record.get("schema_version", ""))
    if schema == "known-material-b5-p2-corrected-pilot-evidence-v1":
        return _adapt_p2(record, source_path=source_path)
    if schema == "known-material-b5-gamma-transport-regime-evidence-v1":
        return _adapt_transport_classification(record, source_path=source_path)
    if schema == "known-material-b5-gamma-transport-extension-evidence-v1":
        return _adapt_transport_extension(record, source_path=source_path)
    raise ValueError(f"unsupported legacy evidence schema: {schema!r}")
