"""Compatibility adapters from immutable legacy evidence into v2 records.

Adapters are one-way views. They never rewrite historical files and never
upgrade a legacy scientific claim beyond what the source explicitly authorizes.
"""

from __future__ import annotations

from typing import Any, Mapping

from .identity import ArtifactBinding, Limitation, SourceBinding
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


def _artifact_bindings(record: Mapping[str, Any]) -> tuple[ArtifactBinding, ...]:
    rows: list[ArtifactBinding] = []
    direct_id = record.get("artifact_id")
    direct_sha = record.get("artifact_zip_sha256")
    if direct_id is not None:
        rows.append(
            ArtifactBinding(
                artifact_id=f"github-actions-artifact:{direct_id}",
                sha256=str(direct_sha) if direct_sha else None,
                media_type="application/zip",
            )
        )

    source = record.get("source")
    if isinstance(source, Mapping) and source.get("artifact_id") is not None:
        digest = source.get("artifact_zip_sha256")
        rows.append(
            ArtifactBinding(
                artifact_id=f"github-actions-artifact:{source['artifact_id']}",
                sha256=str(digest) if digest else None,
                media_type="application/zip",
            )
        )

    for prefix in ("source_extension", "source_reclassify"):
        artifact_id = record.get(f"{prefix}_artifact_id")
        digest = record.get(f"{prefix}_artifact_digest")
        sha256: str | None = None
        if isinstance(digest, str) and digest.startswith("sha256:"):
            sha256 = digest.removeprefix("sha256:")
        if artifact_id is not None:
            rows.append(
                ArtifactBinding(
                    artifact_id=f"github-actions-artifact:{artifact_id}",
                    sha256=sha256,
                    media_type="application/zip",
                )
            )
    return tuple(rows)


def _source_bindings(
    record: Mapping[str, Any],
    *,
    source_path: str,
) -> tuple[SourceBinding, ...]:
    rows = [
        SourceBinding(
            source_type="legacy_repository_evidence",
            source_id=f"path:{source_path}",
            uri=source_path,
        )
    ]
    workflow_id = record.get("workflow_run_id")
    if workflow_id is not None:
        rows.append(
            SourceBinding(
                source_type="github-actions-run",
                source_id=f"github-actions-run:{workflow_id}",
            )
        )
    for key in ("source_extension_run_id", "source_reclassify_run_id"):
        value = record.get(key)
        if value is not None:
            rows.append(
                SourceBinding(
                    source_type="github-actions-run",
                    source_id=f"github-actions-run:{value}",
                )
            )
    source = record.get("source")
    if isinstance(source, Mapping) and source.get("workflow_run_id") is not None:
        rows.append(
            SourceBinding(
                source_type="github-actions-run",
                source_id=f"github-actions-run:{source['workflow_run_id']}",
            )
        )
    return tuple(rows)


def _provenance(
    record: Mapping[str, Any],
    *,
    source_path: str,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "adapter": "rhombus.evidence.legacy.adapt_legacy_evidence_records",
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


def _limitation_records(record: Mapping[str, Any]) -> tuple[Limitation, ...]:
    return tuple(
        Limitation(code=f"LEGACY_LIMITATION_{index}", statement=statement)
        for index, statement in enumerate(_limitations(record), start=1)
    )


def _common_typed_bindings(
    record: Mapping[str, Any],
    *,
    source_path: str,
) -> dict[str, Any]:
    return {
        "source_bindings": _source_bindings(record, source_path=source_path),
        "artifact_bindings": _artifact_bindings(record),
        "limitation_records": _limitation_records(record),
    }


def _adapt_p1_aggregate(
    record: Mapping[str, Any],
    *,
    source_path: str,
) -> tuple[EvidenceRecord, ...]:
    rows = record.get("results")
    if not isinstance(rows, list) or not rows:
        raise ValueError("legacy P1 evidence is missing results")

    workflow_success = record.get("workflow_conclusion") == "success"
    artifact_ids = _artifact_ids(record)
    bindings = _common_typed_bindings(record, source_path=source_path)
    adapted: list[EvidenceRecord] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("legacy P1 result row must be an object")
        legacy_verdict = str(row.get("p1_verdict", "")).strip()
        converged = bool(row.get("converged", False))
        if workflow_success and converged and legacy_verdict == "KEEP_FOR_P2":
            verdict = ScientificVerdict.PASS
        else:
            verdict = ScientificVerdict.INDETERMINATE

        row_record = dict(row)
        adapted.append(
            EvidenceRecord.create(
                candidate_id=_candidate_id(row_record),
                evidence_kind="relaxation_result",
                capability="relax_structure",
                operational_status=(
                    OperationalStatus.SUCCEEDED
                    if workflow_success
                    else OperationalStatus.ERROR
                ),
                scientific_verdict=verdict,
                applicability=Applicability(
                    claim_kind="legacy_p1_retention",
                    domain_status=DomainStatus.UNQUALIFIED,
                ),
                uncertainty=Uncertainty(
                    status="LEGACY_NOT_CALIBRATED",
                    reason="legacy P1 did not carry v2 uncertainty/domain evidence",
                ),
                limitations=(
                    "PASS here preserves only the legacy KEEP_FOR_P2 retention "
                    "decision; it is not a general material-property claim.",
                    *_limitations(record),
                ),
                artifact_ids=artifact_ids,
                protocol_id=None,
                provenance={
                    **_provenance(record, source_path=source_path),
                    "row_batch_id": row.get("batch_id"),
                },
                payload={
                    "legacy_p1_verdict": legacy_verdict,
                    "converged": converged,
                    "input_structure_sha256": row.get("input_structure_sha256"),
                    "relaxed_structure_sha256": row.get(
                        "relaxed_structure_sha256"
                    ),
                    "qualification_evidence_authorized": record.get(
                        "qualification_evidence_authorized"
                    ),
                    "held_out_execution_authorized": record.get(
                        "held_out_execution_authorized"
                    ),
                    "production_search_authorized": record.get(
                        "production_search_authorized"
                    ),
                },
                legacy_stage="P1",
                **bindings,
            )
        )
    return tuple(adapted)


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
        **_common_typed_bindings(record, source_path=source_path),
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
        **_common_typed_bindings(record, source_path=source_path),
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
            status=(
                "SUFFICIENT"
                if verdict is ScientificVerdict.PASS
                else "INSUFFICIENT"
            ),
            reason=(
                None
                if verdict is ScientificVerdict.PASS
                else "claim not authorized"
            ),
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
        **_common_typed_bindings(record, source_path=source_path),
    )


def adapt_legacy_evidence_records(
    record: Mapping[str, Any],
    *,
    source_path: str,
) -> tuple[EvidenceRecord, ...]:
    """Return content-addressed v2 compatibility views of known legacy evidence.

    The source record is not modified. Aggregate legacy evidence may yield more
    than one v2 record. Unknown schemas fail closed.
    """

    schema = str(record.get("schema_version", ""))
    evidence_version = str(record.get("evidence_version", ""))
    if evidence_version == "known-material-b5-p1-real-evidence-v1":
        return _adapt_p1_aggregate(record, source_path=source_path)
    if schema == "known-material-b5-p2-corrected-pilot-evidence-v1":
        return (_adapt_p2(record, source_path=source_path),)
    if schema == "known-material-b5-gamma-transport-regime-evidence-v1":
        return (_adapt_transport_classification(record, source_path=source_path),)
    if schema == "known-material-b5-gamma-transport-extension-evidence-v1":
        return (_adapt_transport_extension(record, source_path=source_path),)
    raise ValueError(
        "unsupported legacy evidence schema: "
        f"schema_version={schema!r}, evidence_version={evidence_version!r}"
    )


def adapt_legacy_evidence(
    record: Mapping[str, Any],
    *,
    source_path: str,
) -> EvidenceRecord:
    """Adapt one legacy evidence object that maps to exactly one v2 record."""

    rows = adapt_legacy_evidence_records(record, source_path=source_path)
    if len(rows) != 1:
        raise ValueError(
            "legacy evidence maps to multiple records; "
            "use adapt_legacy_evidence_records"
        )
    return rows[0]
