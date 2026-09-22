from dataclasses import replace
import hashlib
import json
import subprocess
import sys

import pytest

from rudeus.execution import local
from rudeus.execution.contracts import ArtifactManifest, TaskSpec
from rudeus.science.claims import evaluate_claim
from rudeus.science.contracts import (AcceptanceRegion, ClaimSpec, Observation, Uncertainty,
    canonical_bytes, digest, UNRESOLVED)
from rudeus.science.evidence import EvidenceStore, verified_bytes
from rudeus.science.followups import generate_followups
from tests.test_followups import requested


def setup_task(tmp_path, verdict="UNKNOWN", **changes):
    request, followup, record = requested(tmp_path, verdict)
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    template = replace(followup.task, code_revision=revision, **changes)
    request["followups"] = [replace(followup, task=template).to_dict()]
    store = EvidenceStore(tmp_path/"archive")
    evidence = store.publish(request, source_root=tmp_path/"source")
    task = TaskSpec.from_dict(generate_followups(store, evidence.logical_hash)["tasks"][0]["task"])
    return task, store, record


def _make_source_verdict(tmp_path, expected):
    """Build a replay-valid synthetic PASS/FAIL source record."""
    request, followup, result = requested(tmp_path)
    record = result["p3_scientific_record"]
    base_spec = ClaimSpec.from_dict(record["claim_spec"])
    base_obs = Observation.from_dict(record["observation"])
    spec = replace(base_spec,
        assumptions=(), applicability_requirements=(),
        sufficiency_requirements=(), independence_requirements=(),
        acceptance=AcceptanceRegion(kind="exact", expected=expected,
            justification="synthetic transport regression only"),
        uncertainty_requirements=None)
    observation = replace(base_obs, value=expected)
    uncertainty = Uncertainty(observation_hash=observation.content_hash)
    assessment = evaluate_claim(spec, observation, uncertainty)
    scientific_record = {
        "claim_spec": spec.to_dict(),
        "observation": observation.to_dict(),
        "uncertainty": uncertainty.to_dict(),
        "assessment": assessment.to_dict(),
    }
    result["p3_scientific_record"] = scientific_record
    result["p3_assessment"] = {
        **result["p3_assessment"],
        "verdict": assessment.verdict.value,
        "reason_codes": list(assessment.reason_codes),
    }
    result["p3_provenance"] = {
        **result["p3_provenance"],
        "scientific_record_hash": digest(scientific_record),
    }

    source = tmp_path/"source"
    old = ArtifactManifest.from_dict(request["manifests"][0])
    data = canonical_bytes(result)
    updated = replace(old,
        logical_hash=digest(scientific_record),
        raw_hash=hashlib.sha256(data).hexdigest(),
        size_bytes=len(data))
    (source/"p3.json").write_bytes(data)
    request["manifests"][0] = updated.to_dict()
    request["record_manifest"] = updated.content_hash
    request["attempts"][0]["output_manifest"]["p3.json"] = updated.content_hash
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    task = replace(followup.task, code_revision=revision)
    request["task"] = task.to_dict()
    request["followups"] = [replace(followup, task=task).to_dict()]
    return request, scientific_record


@pytest.mark.parametrize("verdict,expected", [("PASS", True), ("FAIL", False)])
def test_pass_and_fail_verdicts_survive_followup_execution_and_git_receipt(
        tmp_path, verdict, expected):
    request, source_record = _make_source_verdict(tmp_path/"source-evidence", expected)
    source_store = EvidenceStore(tmp_path/"repository"/"data"/"batches"/"evidence")

    source_manifest = source_store.publish(
        request, source_root=tmp_path/"source-evidence")
    generated = generate_followups(source_store, source_manifest.logical_hash)
    assert generated["scientific_verdict"] == verdict
    task = TaskSpec.from_dict(generated["tasks"][0]["task"])

    result = local.execute_local(task, source_store)
    assert result["artifact_status"] == "VERIFIED_LOCAL", result
    assert result["scientific_verdict"] == verdict

    payload = source_store.verify(result["evidence_hash"])
    assert payload["scientific_record"] == source_record
    assert payload["scientific_record"]["assessment"]["verdict"] == verdict
    assert payload["provenance"]["task"] == task.to_dict()

    repository = tmp_path/"repository"
    subprocess.run(["git", "init", str(repository)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repository), "add", "data"], check=True,
                   capture_output=True)
    subprocess.run([
        "git", "-C", str(repository), "-c", "user.name=Evidence Test",
        "-c", "user.email=evidence@example.invalid", "commit", "-m",
        "Synthetic PASS/FAIL evidence archive"], check=True, capture_output=True)

    receipt = source_store.acknowledge_git(
        result["evidence_hash"], git_root=repository, revision="HEAD")
    assert receipt["artifact_status"] == "DURABLY_INGESTED"
    assert receipt["scientific_verdict"] == verdict

    verified = source_store.verify_git_receipt(
        digest(receipt), git_root=repository)
    assert verified == receipt
    assert verified["scientific_verdict"] == verdict


@pytest.mark.parametrize("verdict", ["UNKNOWN", "INDETERMINATE"])
def test_real_execution_verified_ingestion_identity_and_immutable_history(tmp_path, verdict):
    task, store, record = setup_task(tmp_path, verdict)
    before = canonical_bytes(task)
    historical = {p: p.read_bytes() for p in (tmp_path/"source").iterdir()}
    archived = {p: p.read_bytes() for p in store.root.rglob("*") if p.is_file()}
    first = local.execute_local(task, store)
    assert first["artifact_status"] == "VERIFIED_LOCAL", first
    second = local.execute_local(task, store)
    assert second["artifact_status"] == "VERIFIED_LOCAL", second
    assert first["artifact"]["logical_hash"] == second["artifact"]["logical_hash"] == digest(record)
    assert first["artifact"]["raw_hash"] == second["artifact"]["raw_hash"]
    assert first["attempt"]["attempt_id"] != second["attempt"]["attempt_id"]
    assert first["evidence_hash"] != second["evidence_hash"]
    payload = store.verify(first["evidence_hash"])
    assert payload["scientific_record"] == record
    assert payload["scientific_qualification"] == UNRESOLVED
    assert first["scientific_verdict"] == verdict
    assert payload["provenance"]["task"] == task.to_dict()
    attempt = first["attempt"]
    assert attempt["task_content_hash"] == task.content_hash
    assert attempt["status"] == "COMPLETED" and attempt["failure_class"] is None
    assert attempt["runtime_s"] > 0 and attempt["started_at"] < attempt["ended_at"]
    assert attempt["environment"]["git_revision"] == task.code_revision
    assert attempt["hardware"]["logical_cpu_count"] > 0
    assert first["artifact"]["producer_attempt"] == attempt["attempt_id"]
    assert first["artifact"]["parent_artifact_hashes"] == list(task.input_artifact_hashes)
    assert json.loads(store.path(f"attempts/{attempt['attempt_id']}.json").read_bytes()) == attempt
    assert canonical_bytes(task) == before
    with pytest.raises(TypeError):
        task.config["target_species"] = "Na"
    assert all(p.read_bytes() == data for p, data in {**historical, **archived}.items())


@pytest.mark.parametrize("damage", ["missing", "corrupt", "forged_task", "no_provenance", "revision"])
def test_invalid_inputs_fail_closed(tmp_path, damage):
    task, store, _ = setup_task(tmp_path)
    if damage in ("missing", "corrupt"):
        blob = store.path(f"blobs/{task.provenance['evidence_hash']}")
        if damage == "missing":
            blob.unlink()
        else:
            blob.write_bytes(b"corrupt")
    elif damage == "forged_task":
        task = replace(task, input_artifact_hashes=(digest("missing"),))
    elif damage == "no_provenance":
        task = replace(task, provenance=None)
    else:
        task = replace(task, code_revision="f"*40)
    result = local.execute_local(task, store)
    assert result["artifact_status"] == "FAILED"
    assert result["failure_class"] == "INTEGRITY"
    assert result["scientific_verdict"] is None
    assert result["attempt"]["status"] == "FAILED"
    assert "evidence_hash" not in result


@pytest.mark.parametrize("error,classification", [(FloatingPointError("numerical"), "NUMERICAL"),
    (MemoryError("resource"), "RESOURCE"), (RuntimeError("software"), "SOFTWARE")])
def test_execution_failure_is_not_a_scientific_failure(tmp_path, monkeypatch, error, classification):
    task, store, record = setup_task(tmp_path)
    def fail(*args, **kwargs):
        raise error
    monkeypatch.setattr(local, "analyze_p3", fail)
    result = local.execute_local(task, store)
    assert result["failure_class"] == classification
    assert result["scientific_verdict"] is None
    assert result["attempt"]["output_manifest"] == {}
    assert store.verify(task.provenance["evidence_hash"])["scientific_record"] == record


def test_output_verification_failure_never_publishes_success(tmp_path, monkeypatch):
    task, store, _ = setup_task(tmp_path)
    def verify(manifest, data):
        if manifest.durable_locator.startswith("blobs/"):
            return verified_bytes(manifest, b"corrupt")
        return verified_bytes(manifest, data)
    monkeypatch.setattr(local, "verified_bytes", verify)
    result = local.execute_local(task, store)
    assert result["failure_class"] == "INTEGRITY"
    assert result["scientific_verdict"] is None
    assert len(list(store.root.glob("evidence/*.json"))) == 1


@pytest.mark.parametrize("changes", [{"seed": 23}, {"temperature": 999}, {"replica": "extra"},
    {"dependencies": (digest("missing dependency"),)}, {"expected_outputs": ("one", "two")}])
def test_unsupported_execution_fields_are_not_silently_ignored(tmp_path, changes):
    task, store, _ = setup_task(tmp_path, **changes)
    result = local.execute_local(task, store)
    assert result["failure_class"] == "UNSUPPORTED_INPUT", result
    assert result["scientific_verdict"] is None


def test_cli_runs_from_archived_inputs_without_original_sources(tmp_path):
    task, store, record = setup_task(tmp_path)
    for path in (tmp_path/"source").iterdir():
        path.unlink()
    path = tmp_path/"task.json"
    path.write_bytes(canonical_bytes(task))
    run = subprocess.run([sys.executable, "-B", "-m", "rudeus.execution.local", str(path),
        "--store-root", str(store.root)], capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stdout+run.stderr
    result = json.loads(run.stdout)
    assert store.verify(result["evidence_hash"])["scientific_record"] == record
    path.write_text("{}")
    run = subprocess.run([sys.executable, "-B", "-m", "rudeus.execution.local", str(path),
        "--store-root", str(store.root)], capture_output=True, text=True, timeout=60)
    assert run.returncode == 1
    assert json.loads(run.stdout)["scientific_verdict"] is None
