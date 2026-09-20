from dataclasses import replace
import copy
import json
import subprocess
import sys

import pytest

from rudeus.execution.contracts import TaskSpec, ExecutionError
from rudeus.science.contracts import canonical_bytes, digest, UNRESOLVED
from rudeus.science.evidence import EvidenceStore
from rudeus.science.followups import FollowupRequest, generate_followups
from tests.test_evidence import fixture


def requested(tmp_path, verdict="UNKNOWN"):
    request, result = fixture(tmp_path/"source", verdict)
    source_task = TaskSpec.from_dict(request["task"])
    record = result["p3_scientific_record"]
    followup = FollowupRequest(scientific_record_hash=digest(record),
        assessment_hash=digest(record["assessment"]), reason="Explicit synthetic reanalysis request",
        task=source_task)
    request["followups"] = [followup.to_dict()]
    return request, followup, record


@pytest.mark.parametrize("verdict", ["UNKNOWN", "INDETERMINATE"])
def test_verified_evidence_to_immutable_task_and_provenance(tmp_path, verdict):
    request, followup, record = requested(tmp_path, verdict)
    before = copy.deepcopy(request)
    source_bytes = {p: p.read_bytes() for p in (tmp_path/"source").iterdir()}
    store = EvidenceStore(tmp_path/"archive")
    evidence = store.publish(request, source_root=tmp_path/"source")
    output = generate_followups(store, evidence.logical_hash)
    assert output == generate_followups(store, evidence.logical_hash)
    assert output["status"] == "GENERATED"
    assert output["scientific_verdict"] == verdict
    assert output["scientific_qualification"] == UNRESOLVED
    task = TaskSpec.from_dict(output["tasks"][0]["task"])
    assert task.task_id == output["tasks"][0]["task_id"]
    assert task.config == followup.task.config
    assert task.protocol_hash == followup.task.protocol_hash
    assert task.dependencies == (followup.task.task_id,)
    assert task.provenance["evidence_hash"] == evidence.logical_hash
    assert task.provenance["assessment_hash"] == digest(record["assessment"])
    assert task.to_dict()["provenance"]["scope"] == record["claim_spec"]["scope"]
    with pytest.raises(TypeError):
        task.provenance["evidence_hash"] = "changed"
    assert request == before
    assert all(p.read_bytes() == data for p, data in source_bytes.items())


def test_changed_scientific_inputs_change_identity_transient_execution_does_not(tmp_path):
    request, followup, _ = requested(tmp_path)
    store = EvidenceStore(tmp_path/"archive")
    def generate(req):
        manifest = store.publish(req, source_root=tmp_path/"source")
        return generate_followups(store, manifest.logical_hash)["tasks"][0]
    first = generate(request)
    transient = copy.deepcopy(request)
    for attempt in transient["attempts"]:
        attempt.update(backend="different-backend", remote_session_id="another-session",
                       started_at="different-time", ended_at="different-time", runtime_s=99)
    second = generate(transient)
    assert first["task_id"] == second["task_id"]
    assert first["task"]["provenance"]["evidence_hash"] != second["task"]["provenance"]["evidence_hash"]
    changed = copy.deepcopy(request)
    changed["followups"] = [replace(followup, task=replace(followup.task, seed=23)).to_dict()]
    assert generate(changed)["task_id"] != first["task_id"]


@pytest.mark.parametrize("kind,reason", [("absent", "no_explicit_followup_request"),
    ("null", "task_definition_unresolved"), ("stage", "stage_not_supported_in_this_slice"),
    ("inputs", "task_inputs_not_verified"), ("candidate", "candidate_scope_mismatch"),
    ("protocol", "protocol_hash_mismatch")])
def test_no_inferred_policy_or_fabricated_tasks(tmp_path, kind, reason):
    request, followup, _ = requested(tmp_path)
    if kind == "absent":
        del request["followups"]
    else:
        task = followup.task
        if kind == "null":
            task = None
        elif kind == "stage":
            task = replace(task, stage="P2")
        elif kind == "inputs":
            task = replace(task, input_artifact_hashes=(digest("missing"),))
        elif kind == "candidate":
            task = replace(task, candidate_id="other")
        elif kind == "protocol":
            task = replace(task, protocol_hash=digest("other-protocol"))
        request["followups"] = [replace(followup, task=task).to_dict()]
    store = EvidenceStore(tmp_path/"archive")
    manifest = store.publish(request, source_root=tmp_path/"source")
    result = generate_followups(store, manifest.logical_hash)
    assert result["tasks"] == [] and result["status"] == UNRESOLVED
    assert result["unresolved"][0]["reason"] == reason


def test_wrong_assessment_and_corrupt_evidence_are_rejected(tmp_path):
    request, followup, _ = requested(tmp_path)
    store = EvidenceStore(tmp_path/"archive")
    invalid = copy.deepcopy(request)
    invalid["followups"] = [replace(followup, assessment_hash=digest("other-assessment")).to_dict()]
    with pytest.raises(ExecutionError, match="follow-up does not refer"):
        store.publish(invalid, source_root=tmp_path/"source")
    manifest = store.publish(request, source_root=tmp_path/"source")
    store.path(manifest.durable_locator).write_bytes(b"corrupt")
    with pytest.raises(ExecutionError):
        generate_followups(store, manifest.logical_hash)


def test_legacy_task_serialization_is_unchanged_and_cli_is_executable(tmp_path):
    request, followup, _ = requested(tmp_path)
    legacy = followup.task.to_dict()
    assert "provenance" not in legacy
    assert canonical_bytes(followup.task) == canonical_bytes(legacy)
    assert followup.task.content_hash == digest(legacy)
    enriched = replace(followup.task, provenance={"evidence_hash": digest("archive")})
    assert enriched.task_id == followup.task.task_id
    store = EvidenceStore(tmp_path/"archive")
    manifest = store.publish(request, source_root=tmp_path/"source")
    output = tmp_path/"followups.json"
    run = subprocess.run([sys.executable, "-B", "-m", "rudeus.science.followups", manifest.logical_hash,
        "--store-root", str(store.root), "--output", str(output)], capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stdout + run.stderr
    assert json.loads(run.stdout)["task_count"] == 1
    assert json.loads(output.read_bytes()) == generate_followups(store, manifest.logical_hash)
