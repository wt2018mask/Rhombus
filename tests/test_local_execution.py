from dataclasses import replace
import json
import subprocess
import sys

import pytest

from rudeus.execution import local
from rudeus.execution.contracts import TaskSpec
from rudeus.science.contracts import canonical_bytes, digest, UNRESOLVED
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
