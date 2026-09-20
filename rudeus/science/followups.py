"""Explicit evidence requests -> immutable tasks. No inferred follow-up policy."""
from __future__ import annotations

from dataclasses import dataclass, replace
from rudeus.execution.contracts import TaskSpec, ExecutionError
from rudeus.science.contracts import Record, digest, require_hash, UNRESOLVED, canonical_bytes


@dataclass(frozen=True, kw_only=True)
class FollowupRequest(Record):
    """Scientific owner annotation, bound to an exact record and assessment.

    A null task records missing scientific instructions. Neither the publisher
    nor the generator supplies a protocol, fit window, seed or acceptance rule.
    """
    scientific_record_hash: str
    assessment_hash: str
    reason: str
    task: TaskSpec | None = None

    @classmethod
    def from_dict(cls, value):
        value = dict(value)
        if value.get("task") is not None:
            value["task"] = TaskSpec.from_dict(value["task"])
        return cls(**value)

    def validate(self):
        super().validate()
        require_hash(self.scientific_record_hash)
        require_hash(self.assessment_hash)
        if not self.reason or (self.task is not None and not isinstance(self.task, TaskSpec)):
            raise ValueError("follow-up requires an explicit reason and a typed task or null")

    def verify_binding(self, record):
        if self.scientific_record_hash != digest(record) or self.assessment_hash != digest(record["assessment"]):
            raise ExecutionError("follow-up does not refer to this scientific assessment", "INTEGRITY")


def generate_followups(store, evidence_hash, *, qualification_registry=None):
    """Always reverify evidence. Unsupported/missing instructions yield no task.

    Only P3 analysis task specifications are supported in this narrow slice.
    Request annotations must already be part of the verified evidence archive.
    """
    payload = store.verify(evidence_hash, qualification_registry=qualification_registry)
    record = payload["scientific_record"]
    provenance = payload["provenance"]
    source_task = TaskSpec.from_dict(provenance["task"])
    known_inputs = {m["logical_hash"] for m in provenance["manifests"]}
    requests = provenance.get("followups", [])
    result = {"evidence_hash": evidence_hash, "scientific_verdict": record["assessment"]["verdict"],
              "scientific_qualification": payload["scientific_qualification"], "tasks": [],
              "unresolved": [], "status": UNRESOLVED}
    if not requests:
        result["unresolved"].append({"reason": "no_explicit_followup_request"})
    for value in requests:
        request = FollowupRequest.from_dict(value)
        request.verify_binding(record)
        template = request.task
        reason = None
        if template is None:
            reason = "task_definition_unresolved"
        elif template.stage != "P3":
            reason = "stage_not_supported_in_this_slice"
        elif template.candidate_id != source_task.candidate_id:
            reason = "candidate_scope_mismatch"
        elif not template.input_artifact_hashes or not set(template.input_artifact_hashes) <= known_inputs:
            reason = "task_inputs_not_verified"
        elif template.provenance is not None:
            reason = "reserved_provenance_already_set"
        elif len(template.code_revision) not in (40, 64) or any(c not in "0123456789abcdef" for c in template.code_revision):
            reason = "explicit_code_commit_required"
        else:
            from rudeus.science.p3 import P3Protocol
            try:
                protocol = P3Protocol.from_dict(template.config)
                if protocol.content_hash != template.protocol_hash:
                    reason = "protocol_hash_mismatch"
                elif any(getattr(protocol, name) is None for name in ("lag_steps", "fit_window_ps", "reference_frame")):
                    reason = "analysis_protocol_unresolved"
                elif protocol.reference_frame != "simulation_cell":
                    reason = "reference_frame_not_supported"
            except (ValueError, TypeError):
                reason = "unsupported_protocol_definition"
        if reason:
            result["unresolved"].append({"request_hash": request.content_hash, "reason": reason})
            continue
        # Only bookkeeping fields are added. Scientific parameters remain exactly
        # as requested; operational archive hashes stay outside scientific ID.
        task = replace(template,
                       dependencies=tuple(sorted(set(template.dependencies) | {source_task.task_id})),
                       provenance={"evidence_hash": evidence_hash, "request_hash": request.content_hash,
                                   "assessment_hash": request.assessment_hash,
                                   "scientific_record_hash": request.scientific_record_hash,
                                   "scope": record["claim_spec"]["scope"]})
        result["tasks"].append({"task_id": task.task_id, "task": task.to_dict()})
    result["tasks"].sort(key=lambda row: (row["task_id"], digest(row["task"])))
    if result["tasks"]:
        result["status"] = "GENERATED_WITH_UNRESOLVED" if result["unresolved"] else "GENERATED"
    return result


def main(argv=None):
    import argparse
    import json
    from pathlib import Path
    from rudeus.science.evidence import EvidenceStore, append_file, integrity_errors
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence_hash")
    parser.add_argument("--store-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        with integrity_errors():
            result = generate_followups(EvidenceStore(args.store_root), args.evidence_hash)
            append_file(Path(args.output), canonical_bytes(result))
    except ExecutionError as exc:
        print(json.dumps({"status": "FAILED", "failure_class": exc.failure_class.value, "reason": str(exc)}))
        return 1
    print(json.dumps({"status": result["status"], "task_count": len(result["tasks"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
