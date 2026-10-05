"""Canonical, read-only assembly of retained pipeline evidence and OUT.

The release record binds existing scientific assessments; it never makes a
scientific measurement or chooses an acceptance rule. Local ingestion receipts
are integrity evidence, not a claim of Git or scientific qualification.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping, Sequence

from rudeus.execution.contracts import ArtifactManifest, ExecutionAttempt, ExecutionError, TaskSpec
from rudeus.science.claims import final_claim_vector
from rudeus.science.contracts import ClaimAssessment, ClaimSpec, Record, Verdict, digest, require_hash
from rudeus.science.downstream import CLAIM_IDS, StageAssessment, make_out
from rudeus.science.evidence import inside, verify_ingested_artifact

STAGES = ("P1", "P2", "P2.5", "P3")
DOWNSTREAM = ("X", "N", "S", "APPLICATION")


@dataclass(frozen=True, kw_only=True)
class RunIdentity(Record):
    candidate_id: str
    source_hash: str
    pipeline_protocol_hash: str
    code_revision: str

    def validate(self):
        super().validate()
        if not self.candidate_id or not self.code_revision:
            raise ValueError("run identity incomplete")
        require_hash(self.source_hash)
        require_hash(self.pipeline_protocol_hash)

    @property
    def run_id(self):
        return self.content_hash


@dataclass(frozen=True, kw_only=True)
class RetainedOutput(Record):
    logical_name: str
    manifest: ArtifactManifest
    ingestion_receipt: str

    @classmethod
    def from_dict(cls, value):
        return cls(logical_name=value["logical_name"],
                   manifest=ArtifactManifest.from_dict(value["manifest"]),
                   ingestion_receipt=value["ingestion_receipt"])

    def validate(self):
        super().validate()
        if not self.logical_name or not isinstance(self.manifest, ArtifactManifest):
            raise ValueError("typed retained output required")
        require_hash(self.ingestion_receipt)


@dataclass(frozen=True, kw_only=True)
class StageReceipt(Record):
    task: TaskSpec
    attempts: tuple[ExecutionAttempt, ...]
    outputs: tuple[RetainedOutput, ...]

    @classmethod
    def from_dict(cls, value):
        return cls(task=TaskSpec.from_dict(value["task"]),
                   attempts=tuple(ExecutionAttempt.from_dict(v) for v in value["attempts"]),
                   outputs=tuple(RetainedOutput.from_dict(v) for v in value["outputs"]))

    def validate(self):
        super().validate()
        if not isinstance(self.task, TaskSpec) or any(not isinstance(a, ExecutionAttempt) for a in self.attempts):
            raise ValueError("typed task and attempts required")
        if any(not isinstance(o, RetainedOutput) for o in self.outputs):
            raise ValueError("typed outputs required")
        if len({a.attempt_id for a in self.attempts}) != len(self.attempts):
            raise ValueError("duplicate attempt")
        if len({o.logical_name for o in self.outputs}) != len(self.outputs):
            raise ValueError("duplicate output")


@dataclass(frozen=True, kw_only=True)
class ReleaseRecord(Record):
    run: RunIdentity
    stage_receipts: Mapping[str, tuple[StageReceipt, ...]]
    code_revisions: Mapping[str, str]
    claim_assessment_hashes: tuple[str, ...]
    followup_hashes: tuple[str, ...]
    downstream: Mapping[str, StageAssessment]
    p3_series_hash: str | None
    p3_series_receipt: str | None
    evidence_index: Mapping[str, str]
    release_evidence: Mapping[str, tuple[str, ...]]
    limitations: tuple[str, ...]
    out_hash: str
    qualification: Mapping[str, bool]

    @classmethod
    def from_dict(cls, value):
        value = dict(value)
        value["run"] = RunIdentity.from_dict(value["run"])
        value["stage_receipts"] = {k: tuple(StageReceipt.from_dict(item) for item in v)
                                   for k, v in value["stage_receipts"].items()}
        value["downstream"] = {k: StageAssessment.from_dict(v)
                               for k, v in value["downstream"].items()}
        return cls(**value)

    def validate(self):
        super().validate()
        if not isinstance(self.run, RunIdentity):
            raise ValueError("typed run required")
        if not all(self.code_revisions.values()):
            raise ValueError("stage code revision missing")
        for h in (*self.claim_assessment_hashes, *self.followup_hashes,
                  self.out_hash, *self.evidence_index, *self.evidence_index.values(),
                  *(v for values in self.release_evidence.values() for v in values)):
            require_hash(h)
        if self.p3_series_hash is not None:
            require_hash(self.p3_series_hash)
        if self.p3_series_receipt is not None:
            require_hash(self.p3_series_receipt)


def assemble_release(*, run: RunIdentity, source: RetainedOutput | None,
                     stages: Mapping[str, StageReceipt | Sequence[StageReceipt]], artifact_root,
                     claim_specs: Mapping[str, ClaimSpec],
                     assessments: Sequence[ClaimAssessment],
                     downstream: Mapping[str, StageAssessment],
                     followup_hashes: Sequence[str] = (),
                     p3_series: Mapping | None = None,
                     p3_series_output: RetainedOutput | None = None,
                     retained_evidence: Sequence[RetainedOutput] = (),
                     software_regression_hashes: Sequence[str] = (),
                     synthetic_e2e_hashes: Sequence[str] = (),
                     production_evidence_hashes: Sequence[str] = (),
                     limitations: Sequence[str] = ()):
    """Return a deterministic release record and the existing immutable OUT.

    Every stage output is re-read from its append-only archive. Missing evidence
    produces UNKNOWN and an OUT; corrupt or mismatched evidence raises INTEGRITY.
    """
    if set(stages) - set(STAGES) or set(downstream) - set(DOWNSTREAM):
        raise ValueError("unknown pipeline stage")
    stage_groups = {stage: (value,) if isinstance(value, StageReceipt) else tuple(value)
                    for stage, value in stages.items()}
    if any(not receipts or any(not isinstance(receipt, StageReceipt) or
               stage != receipt.task.stage for receipt in receipts)
           for stage, receipts in stage_groups.items()):
        raise ExecutionError("stage receipt/task mismatch", "INTEGRITY")
    source_value = None
    if source is not None:
        if source.manifest.logical_hash != run.source_hash:
            raise ExecutionError("source identity mismatch", "INTEGRITY")
        source_value = verify_ingested_artifact(artifact_root, source.manifest,
                                                source.ingestion_receipt)
        if (not isinstance(source_value, Mapping)
                or source_value.get("candidate_id") != run.candidate_id):
            raise ExecutionError("source candidate identity mismatch", "INTEGRITY")
        if source_value.get("p0_state") not in ("PLAUSIBLE", "SUPPORTED", "FAIL"):
            raise ExecutionError("P0 disposition unresolved", "INTEGRITY")
        if source_value["p0_state"] == "FAIL" and stages:
            raise ExecutionError("P0 FAIL cannot enter P1", "INTEGRITY")
    verified = {}
    values = {}
    tasks = {}
    all_attempts = []
    if stages:
        from rudeus.science.pipeline_handoff import verify_output
    for stage in STAGES:
        if stage not in stages:
            continue
        values[stage] = {}
        verified[stage] = []
        for receipt in sorted(stage_groups[stage], key=lambda item: item.task.task_id):
            task = receipt.task
            if task.task_id in tasks or task.candidate_id != run.candidate_id:
                raise ExecutionError("duplicate or mismatched task run identity", "INTEGRITY")
            if any(dependency not in tasks for dependency in task.dependencies):
                raise ExecutionError("missing task ancestry", "INTEGRITY")
            known = {run.source_hash} | {o.manifest.logical_hash
                for outputs in verified.values() for o in outputs}
            if not set(task.input_artifact_hashes) <= known:
                raise ExecutionError("missing input artifact ancestry", "INTEGRITY")
            if set(task.expected_outputs) != {o.logical_name for o in receipt.outputs}:
                raise ExecutionError("missing declared stage output", "INTEGRITY")
            values[stage][task.task_id] = {}
            for output in receipt.outputs:
                verify_ingested_artifact(artifact_root, output.manifest, output.ingestion_receipt)
                # Preserve the historical task/attempt/manifest binding.
                raw = inside(artifact_root, f"blobs/{output.manifest.raw_hash}").read_bytes()
                values[stage][task.task_id][output.logical_name] = verify_output(
                    task, receipt.attempts, output.manifest, raw, output.logical_name).value
            verified[stage].extend(receipt.outputs)
            tasks[task.task_id] = task
            all_attempts.extend(receipt.attempts)
    if len({a.attempt_id for a in all_attempts}) != len(all_attempts):
        raise ExecutionError("attempt identity reused across stages", "INTEGRITY")
    if "P3" in stages and "P2.5" not in stages:
        raise ExecutionError("P3 lacks P2.5 admission", "INTEGRITY")
    p25_states = {}
    for task_id, outputs in values.get("P2.5", {}).items():
        p25 = outputs.get("p25.json")
        if not isinstance(p25, Mapping) or not isinstance(p25.get("result"), Mapping):
            raise ExecutionError("P2.5 result unavailable", "INTEGRITY")
        p25_states[task_id] = p25["result"].get("transport_state")
    for receipt in stage_groups.get("P3", ()):
        parents = set(receipt.task.dependencies) & set(p25_states)
        if not parents or any(p25_states[parent] != "DIFFUSIVE" for parent in parents):
            raise ExecutionError("P2.5 did not admit P3", "INTEGRITY")
    if "NONDIFFUSIVE" in p25_states.values():
        limitations = tuple(limitations) + ("p25_nondiffusive_terminal",)
    if (p3_series is None) != (p3_series_output is None):
        raise ExecutionError("P3 series and retained output must be paired", "INTEGRITY")
    if p3_series is not None:
        if (p3_series.get("candidate_id") != run.candidate_id
                or p3_series.get("series_version") != "p3-series-v1" or "P3" not in stages):
            raise ExecutionError("P3 series has no matching retained stage", "INTEGRITY")
        if (p3_series_output.manifest.logical_hash != digest(p3_series)
                or digest(verify_ingested_artifact(artifact_root, p3_series_output.manifest,
                                                   p3_series_output.ingestion_receipt)) != digest(p3_series)
                or len({p["p3_result_hash"] for p in p3_series["replicates"]}) != len(
                    p3_series["replicates"])
                or {p["p3_result_hash"] for p in p3_series["replicates"]} != {
                    o.manifest.logical_hash for o in verified["P3"]}
                or not {o.manifest.logical_hash for o in verified["P3"]} <= set(
                    p3_series_output.manifest.parent_artifact_hashes)):
            raise ExecutionError("P3 series retained artifact binding mismatch", "INTEGRITY")
    evidence_index = {}
    indexed_hashes = ({run.source_hash} if source else set()) | {
        o.manifest.logical_hash for outputs in verified.values() for o in outputs}
    if p3_series_output is not None:
        indexed_hashes.add(p3_series_output.manifest.logical_hash)
    for output in retained_evidence:
        if output.manifest.logical_hash in set(evidence_index) | indexed_hashes:
            raise ExecutionError("duplicate retained evidence", "INTEGRITY")
        verify_ingested_artifact(artifact_root, output.manifest, output.ingestion_receipt)
        evidence_index[output.manifest.logical_hash] = output.ingestion_receipt
    upstream = final_claim_vector(tuple(claim_specs.values()), tuple(assessments))
    claims = {row["claim_id"]: row["verdict"] for row in upstream["claims"]}
    for assessment in assessments:
        if assessment.verdict in (Verdict.PASS, Verdict.FAIL) and not (
                assessment.supporting_evidence or assessment.conflicting_evidence):
            raise ExecutionError("resolved claim lacks retained evidence references", "INTEGRITY")
    retained_hashes = ({run.source_hash} if source else set()) | {
        o.manifest.logical_hash for outputs in verified.values() for o in outputs}
    if p3_series_output is not None:
        retained_hashes.add(p3_series_output.manifest.logical_hash)
    retained_hashes.update(evidence_index)
    required_evidence = {h for a in assessments if a.verdict in (Verdict.PASS, Verdict.FAIL)
                         for h in a.supporting_evidence + a.conflicting_evidence}
    required_evidence.update(h for stage in downstream.values() for h in stage.evidence_hashes)
    if p3_series is not None:
        required_evidence.update(p["trajectory_sha256"] for p in p3_series["replicates"])
        required_evidence.update(p3_series["calibration_applicability"]["held_out_evidence_hashes"])
    if not required_evidence <= retained_hashes:
        raise ExecutionError("assessment refers to unretained evidence", "INTEGRITY")
    if set(claims) - set(CLAIM_IDS):
        raise ValueError("noncanonical claim identity")
    required_stage = {"structural_energetic_validity": "P1", "dynamic_stability": "P2",
                      "diffusion": "P2.5", "transport_p3": "P3",
                      "uncertainty_qualification": "P3"}
    for claim, stage in required_stage.items():
        if stage not in stages and claims.get(claim) != "FAIL":
            claims[claim] = "UNKNOWN"
    if source_value is None and claims.get("existence") != "FAIL":
        claims["existence"] = "UNKNOWN"
    elif source_value is not None and source_value["p0_state"] == "FAIL":
        claims["existence"] = "FAIL"
    if "P3" not in stages or p3_series is None:
        claims["transport_p3"] = "UNKNOWN" if claims.get("transport_p3") != "FAIL" else "FAIL"
    if "P2.5" in stages:
        if p25_states and all(state == "NONDIFFUSIVE" for state in p25_states.values()):
            claims["diffusion"] = "FAIL"
            claims["transport_p3"] = "UNKNOWN"
        elif not any(state == "DIFFUSIVE" for state in p25_states.values()) and claims.get("diffusion") != "FAIL":
            claims["diffusion"] = "UNKNOWN"
    if "P3" in stages and p3_series is not None and claims.get("transport_p3") == "PASS":
        series_verdict = p3_series.get("assessment", {}).get("verdict")
        if series_verdict != "PASS":
            claims["transport_p3"] = series_verdict if series_verdict in (
                "FAIL", "UNKNOWN", "INDETERMINATE") else "UNKNOWN"
    if (p3_series is None or p3_series.get("calibration_applicability", {}).get("status") != "APPLICABLE"):
        if claims.get("uncertainty_qualification") == "PASS":
            claims["uncertainty_qualification"] = "UNKNOWN"
    if any(stage not in stages for stage in STAGES):
        limitations = tuple(limitations) + ("missing_pipeline_stage",)
    all_outputs = tuple(o.manifest.logical_hash for stage in STAGES for o in verified.get(stage, ()))
    if p3_series_output is not None:
        all_outputs += (p3_series_output.manifest.logical_hash,)
    all_outputs += tuple(evidence_index)
    all_inputs = (run.source_hash,) if source else ()
    all_inputs += tuple(h for task in tasks.values() for h in task.input_artifact_hashes)
    all_receipts = ((source.ingestion_receipt,) if source else ()) + tuple(
        o.ingestion_receipt for stage in STAGES for o in verified.get(stage, ()))
    if p3_series_output is not None:
        all_receipts += (p3_series_output.ingestion_receipt,)
    all_receipts += tuple(evidence_index.values())
    hashes = {"software_regression": tuple(software_regression_hashes),
              "synthetic_e2e": tuple(synthetic_e2e_hashes),
              "production_science": tuple(production_evidence_hashes)}
    for values in hashes.values():
        for value in values:
            require_hash(value)
    completeness = bool(source and p3_series_output and all(stage in stages for stage in STAGES) and
                        all(stage in downstream for stage in DOWNSTREAM) and not limitations)
    claims["provenance_sufficiency"] = "PASS" if completeness else "UNKNOWN"
    out = make_out(candidate_id=run.candidate_id if source else None, claims=claims,
        stages=downstream, applicability={},
        protocol_hashes={task_id: task.protocol_hash for task_id, task in tasks.items()},
        config_hashes={task_id: task.config_hash for task_id, task in tasks.items()},
        input_artifact_hashes=tuple(sorted(set(all_inputs))),
        output_artifact_hashes=tuple(sorted(set(all_outputs))),
        execution_references=tuple(sorted(a.content_hash for a in all_attempts)),
        provenance_references=tuple(sorted(all_receipts)),
        scientific_limitations=tuple(sorted(set(limitations))))
    qualification = {"software_regression_reference_present": bool(hashes["software_regression"]),
                     "canonical_synthetic_e2e_reference_present": bool(hashes["synthetic_e2e"]),
                     "production_scientific_reference_present": bool(hashes["production_science"]),
                     "provenance_complete": completeness,
                     "durable_artifacts_complete": bool(source and p3_series_output and
                        all(stage in stages for stage in STAGES)),
                     "downstream_complete": all(stage in downstream for stage in DOWNSTREAM),
                     "known_limitations_frozen": True, "out_available": True}
    record = ReleaseRecord(run=run, stage_receipts=stage_groups,
        code_revisions={task_id: task.code_revision for task_id, task in tasks.items()},
        claim_assessment_hashes=tuple(sorted(a.content_hash for a in assessments)),
        followup_hashes=tuple(sorted(followup_hashes)), downstream=out.stage_assessments,
        p3_series_hash=digest(p3_series) if p3_series is not None else None,
        p3_series_receipt=p3_series_output.ingestion_receipt if p3_series_output else None,
        evidence_index=evidence_index,
        release_evidence=hashes, limitations=tuple(sorted(set(limitations))),
        out_hash=out.content_hash, qualification=qualification)
    return record, out
