"""Real P3 record -> verified archive -> Git commit -> fresh-checkout recovery."""
from dataclasses import replace
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from rudeus.execution.contracts import ArtifactManifest, ExecutionAttempt, ExecutionError, TaskSpec
from rudeus.science.contracts import AcceptanceRegion, ClaimSpec, Observation, canonical_bytes, digest
from rudeus.science.evidence import EvidenceStore
from rudeus.science.p3 import P3Protocol, analyze_p3
from tests.test_p3_scientific_slice import protocol
from tests.test_scientific_transport import bound_inputs


def make_attempt(identity, task_id, outputs, *, task_content_hash=None):
    return ExecutionAttempt(attempt_id=identity, task_id=task_id, backend="local-test",
        remote_session_id=None, started_at="2026-09-20T00:00:00Z", ended_at="2026-09-20T00:00:01Z",
        runtime_s=1, hardware={"scope": "synthetic-test"}, environment={"test": "evidence"},
        precision="float64", exit_status=0, status="COMPLETED", termination_reason="completed",
        failure_class=None, logs=(), output_manifest=outputs, task_content_hash=task_content_hash)


def write_manifest(root, name, value, producer, *, parents=(), trajectory_hash=None):
    data = value if isinstance(value, bytes) else canonical_bytes(value)
    (root/name).write_bytes(data)
    return ArtifactManifest(logical_hash=trajectory_hash or digest(value),
        canonicalization_version="p2-traj-v1" if trajectory_hash else "canonical-json-v1",
        raw_hash=hashlib.sha256(data).hexdigest(), format="p2-traj" if trajectory_hash else "json",
        format_version="p2-traj-v1" if trajectory_hash else "scientific-freeze-v1",
        size_bytes=len(data), durable_locator=name, producer_attempt=producer,
        parent_artifact_hashes=parents, retrieval_verification={"status": "NOT_TRUSTED_BY_PUBLISHER"})


def fixture(root, verdict="UNKNOWN", proto=None):
    root.mkdir(parents=True, exist_ok=True)
    p2, p25 = bound_inputs(root)
    proto = proto or protocol()
    result = analyze_p3(p2, p25, proto, artifact_root=root, timestamp="fixed")
    if verdict == "INDETERMINATE":
        spec = ClaimSpec.from_dict(result["p3_scientific_record"]["claim_spec"])
        spec = replace(spec, acceptance=AcceptanceRegion(kind="interval", lower=0,
                       justification="PROVISIONAL synthetic contract test only"),
                       uncertainty_requirements={"qualification": "required"})
        result = analyze_p3(p2, p25, proto, artifact_root=root, timestamp="fixed", claim_spec=spec)
    upstream, producing = digest("input-writer"), digest(["P3-attempt", verdict])
    traj = write_manifest(root, "trajectory.npz", (root/"trajectory.npz").read_bytes(), upstream,
                          trajectory_hash=p2["result"]["trajectory_artifact"]["sha256"])
    configuration = write_manifest(root, "protocol.json", proto.to_dict(), upstream)
    provenance = write_manifest(root, "provenance.json", {"p2": p2, "p25": p25}, upstream,
                                parents=(traj.logical_hash,))
    inputs = (traj.logical_hash, configuration.logical_hash, provenance.logical_hash)
    task = TaskSpec(candidate_id="candidate", stage="P3", protocol_hash=proto.content_hash,
                    config=proto.to_dict(), input_artifact_hashes=inputs, dependencies=(),
                    code_revision="0c61ee524b1486ca18e5ad7466d2c0d4d327b39d",
                    resource_requirements={"kind": "analysis"}, expected_outputs=("p3.json",), retry_policy={})
    output = write_manifest(root, "p3.json", result, producing, parents=inputs)
    prior = make_attempt(upstream, digest("input-writing-task"),
                         {"trajectory.npz": traj.content_hash, "protocol.json": configuration.content_hash,
                          "provenance.json": provenance.content_hash})
    attempt = make_attempt(producing, task.task_id, {"p3.json": output.content_hash},
                           task_content_hash=task.content_hash)
    return {"task": task.to_dict(), "attempts": [attempt.to_dict(), prior.to_dict()],
            "manifests": [m.to_dict() for m in (output, traj, configuration, provenance)],
            "record_manifest": output.content_hash}, result


@pytest.mark.parametrize("verdict", ["UNKNOWN", "INDETERMINATE"])
def test_determinism_provenance_uncertainty_and_append_only(tmp_path, verdict):
    request, result = fixture(tmp_path/"source", verdict)
    before = copy.deepcopy(request)
    store = EvidenceStore(tmp_path/"archive")
    first = store.publish(request, source_root=tmp_path/"source")
    files = {p: p.read_bytes() for p in store.root.rglob("*") if p.is_file()}
    reordered = {**request, "manifests": list(reversed(request["manifests"])),
                 "attempts": list(reversed(request["attempts"]))}
    assert store.publish(reordered, source_root=tmp_path/"source") == first
    assert {p: p.read_bytes() for p in files} == files
    payload = store.verify(first.logical_hash)
    assert request == before
    assert payload["scientific_record"] == result["p3_scientific_record"]
    assert payload["scientific_record"]["assessment"]["verdict"] == verdict
    assert payload["scientific_record"]["uncertainty"]["bounds"] is None
    assert payload["scientific_qualification"] == "UNKNOWN / NEEDS EVIDENCE"
    assert first.logical_hash == first.raw_hash == digest(payload)
    assert EvidenceStore(tmp_path/"second-store").publish(request, source_root=tmp_path/"source") == first
    assert first.producer_attempt == request["attempts"][0]["attempt_id"]
    assert len(first.parent_artifact_hashes) == 4
    assert not list(store.root.glob("receipts/*"))
    # Fresh process/store needs only archived bytes, not ephemeral source files.
    for p in (tmp_path/"source").iterdir():
        p.unlink()
    assert EvidenceStore(store.root).verify(first.logical_hash) == payload


@pytest.mark.parametrize("damage", ["missing", "corrupt", "wrong_logical_hash", "missing_parent",
                                    "missing_attempt", "wrong_output", "uncertainty_binding", "forged_pass"])
def test_invalid_sources_or_assessments_never_publish(tmp_path, damage):
    request, result = fixture(tmp_path/"source")
    if damage == "missing":
        (tmp_path/"source"/"trajectory.npz").unlink()
    elif damage == "corrupt":
        (tmp_path/"source"/"trajectory.npz").write_bytes(b"interrupted upload")
    elif damage == "wrong_logical_hash":
        request["manifests"][1]["logical_hash"] = digest("wrong")
    elif damage == "missing_parent":
        request["manifests"].pop()
    elif damage == "missing_attempt":
        request["attempts"].pop()
    elif damage == "wrong_output":
        request["attempts"][0]["output_manifest"]["p3.json"] = digest("not an output")
    else:
        record = result["p3_scientific_record"]
        if damage == "forged_pass":
            record["assessment"]["verdict"] = "PASS"
        else:
            record["uncertainty"]["observation_hash"] = digest("another observation")
        result["p3_provenance"]["scientific_record_hash"] = digest(record)
        old = request["manifests"][0]
        updated = write_manifest(tmp_path/"source", "p3.json", result, old["producer_attempt"],
                                 parents=tuple(old["parent_artifact_hashes"]))
        request["manifests"][0] = updated.to_dict()
        request["record_manifest"] = updated.content_hash
        request["attempts"][0]["output_manifest"]["p3.json"] = updated.content_hash
    store = EvidenceStore(tmp_path/"archive")
    with pytest.raises(ExecutionError) as exc:
        store.publish(request, source_root=tmp_path/"source")
    assert exc.value.failure_class == "INTEGRITY"
    assert not list(store.root.rglob("*.json"))


def test_conflicting_producer_outputs_are_both_addressable(tmp_path):
    request, result = fixture(tmp_path/"source")
    store = EvidenceStore(tmp_path/"archive")
    first = store.publish(request, source_root=tmp_path/"source")
    # Distinct execution output for the SAME scientific task. No last-writer-wins.
    record = result["p3_scientific_record"]
    record["observation"]["value"] *= 2
    record["uncertainty"]["observation_hash"] = Observation.from_dict(record["observation"]).content_hash
    result["p3_provenance"]["scientific_record_hash"] = digest(record)
    result["quantitative_transport"]["self_diffusion"]["observation"] = copy.deepcopy(record["observation"])
    result["quantitative_transport"]["self_diffusion"]["D_m2_per_s"] = record["observation"]["value"]
    producer = digest("second-P3-attempt")
    output = write_manifest(tmp_path/"source", "second.json", result, producer,
                             parents=tuple(request["task"]["input_artifact_hashes"]))
    request["manifests"][0] = output.to_dict()
    request["record_manifest"] = output.content_hash
    request["attempts"][0] = make_attempt(producer, request["attempts"][0]["task_id"],
        {"p3.json": output.content_hash}, task_content_hash=digest(request["task"])).to_dict()
    second = store.publish(request, source_root=tmp_path/"source")
    assert second.logical_hash != first.logical_hash
    assert len(list(store.path("evidence").glob("*.json"))) == 2
    original = store.verify(first.logical_hash)["scientific_record"]
    conflict = store.verify(second.logical_hash)["scientific_record"]
    assert original["observation"]["value"] * 2 == conflict["observation"]["value"]
    assert original["assessment"] == conflict["assessment"]


def replace_manifest(request, index, updated):
    old = ArtifactManifest.from_dict(request["manifests"][index]).content_hash
    request["manifests"][index] = updated.to_dict()
    for attempt in request["attempts"]:
        attempt["output_manifest"] = {k: updated.content_hash if h == old else h
                                       for k, h in attempt["output_manifest"].items()}
    if request["record_manifest"] == old:
        request["record_manifest"] = updated.content_hash


def test_logical_trajectory_hash_is_not_replaced_by_container_hash(tmp_path):
    from rudeus.mlip.p2_traj import load_traj_artifact, write_traj_artifact
    request, _ = fixture(tmp_path/"source")
    path = tmp_path/"source/trajectory.npz"
    trajectory = load_traj_artifact(path)
    trajectory["positions"][0, 0, 0] += 1
    write_traj_artifact(path, trajectory)
    data = path.read_bytes()
    manifest = ArtifactManifest.from_dict(request["manifests"][1])
    # A self-consistent raw container and manifest still fail the original
    # scientific logical hash, which remains the bound trajectory identity.
    replace_manifest(request, 1, replace(manifest, raw_hash=hashlib.sha256(data).hexdigest(), size_bytes=len(data)))
    with pytest.raises(ExecutionError, match="SHA256 mismatch"):
        EvidenceStore(tmp_path/"archive").publish(request, source_root=tmp_path/"source")


def test_paths_and_interrupted_publication_fail_closed(tmp_path, monkeypatch):
    import rudeus.science.evidence as evidence
    request, _ = fixture(tmp_path/"source")
    escaped = copy.deepcopy(request)
    replace_manifest(escaped, 1, replace(ArtifactManifest.from_dict(escaped["manifests"][1]),
                                        durable_locator="../trajectory.npz"))
    store = EvidenceStore(tmp_path/"archive")
    with pytest.raises(ExecutionError, match="escapes root"):
        store.publish(escaped, source_root=tmp_path/"source")
    original = evidence.append_file
    def interrupted(path, data):
        if path.parent.name == "evidence":
            raise OSError("injected interruption before manifest publication")
        return original(path, data)
    monkeypatch.setattr(evidence, "append_file", interrupted)
    with pytest.raises(ExecutionError):
        store.publish(request, source_root=tmp_path/"source")
    assert not list(store.path("evidence").glob("*.json"))
    monkeypatch.setattr(evidence, "append_file", original)
    manifest = store.publish(request, source_root=tmp_path/"source")
    assert store.verify(manifest.logical_hash)["scientific_record"]["assessment"]["verdict"] == "UNKNOWN"


def test_existing_corrupt_blob_is_not_overwritten(tmp_path):
    request, _ = fixture(tmp_path/"source")
    store = EvidenceStore(tmp_path/"archive")
    path = store.path(f"blobs/{request['manifests'][1]['raw_hash']}")
    path.parent.mkdir(parents=True)
    path.write_bytes(b"preexisting corrupt artifact")
    with pytest.raises(ExecutionError, match="append-only"):
        store.publish(request, source_root=tmp_path/"source")
    assert path.read_bytes() == b"preexisting corrupt artifact"
    assert not list(store.path("evidence").glob("*.json"))
    assert not list(store.root.rglob(".evidence-pending-*"))


def test_unavailable_observation_is_preserved_without_inventing_uncertainty(tmp_path):
    request, result = fixture(tmp_path/"source", proto=P3Protocol(target_species="Li"))
    store = EvidenceStore(tmp_path/"archive")
    manifest = store.publish(request, source_root=tmp_path/"source")
    record = store.verify(manifest.logical_hash)["scientific_record"]
    assert record == result["p3_scientific_record"]
    assert record["observation"] is None
    assert record["uncertainty"]["bounds"] is None
    assert record["assessment"]["verdict"] == "UNKNOWN"


def test_unverified_calibration_reference_is_rejected(tmp_path):
    request, result = fixture(tmp_path/"source")
    result["p3_scientific_record"]["uncertainty"]["calibration_reference"] = digest("unverified registry")
    result["p3_provenance"]["scientific_record_hash"] = digest(result["p3_scientific_record"])
    old = ArtifactManifest.from_dict(request["manifests"][0])
    updated = write_manifest(tmp_path/"source", "p3.json", result, old.producer_attempt,
                             parents=old.parent_artifact_hashes)
    replace_manifest(request, 0, updated)
    with pytest.raises(ExecutionError, match="calibration registry entry unavailable"):
        EvidenceStore(tmp_path/"archive").publish(request, source_root=tmp_path/"source")


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True,
                           capture_output=True, text=True).stdout.strip()


def test_git_durability_and_fresh_checkout_recovery(tmp_path):
    repository = tmp_path/"repo"
    repository.mkdir()
    git(repository, "init")
    request, _ = fixture(tmp_path/"source")
    store = EvidenceStore(repository/"data/batches/evidence")
    manifest = store.publish(request, source_root=tmp_path/"source")
    with pytest.raises(ExecutionError):
        store.acknowledge_git(manifest.logical_hash, git_root=repository, revision="HEAD")
    git(repository, "add", "data")
    git(repository, "-c", "user.name=Evidence Test", "-c", "user.email=evidence@example.invalid",
        "commit", "-m", "Synthetic evidence archive")
    receipt = store.acknowledge_git(manifest.logical_hash, git_root=repository, revision="HEAD")
    assert receipt["artifact_status"] == "DURABLY_INGESTED"
    assert receipt["scientific_verdict"] == "UNKNOWN"
    assert receipt["remote_replication"] == "NOT_ATTESTED"
    clone = tmp_path/"recovered"
    subprocess.run(["git", "clone", "--no-hardlinks", str(repository), str(clone)], check=True,
                    capture_output=True)
    recovered = EvidenceStore(clone/"data/batches/evidence")
    assert recovered.verify(manifest.logical_hash) == store.verify(manifest.logical_hash)
    assert recovered.acknowledge_git(manifest.logical_hash, git_root=clone, revision="HEAD") == receipt
    recovered.path(manifest.durable_locator).write_bytes(b"damaged after ingestion")
    with pytest.raises(ExecutionError):
        recovered.acknowledge_git(manifest.logical_hash, git_root=clone, revision="HEAD")


def test_cli_real_publication_and_verification(tmp_path):
    request, _ = fixture(tmp_path/"source")
    request_file = tmp_path/"request.json"
    request_file.write_bytes(canonical_bytes(request))
    def cli(*args):
        run = subprocess.run([sys.executable, "-B", "-m", "rudeus.science.evidence", *args,
                              "--store-root", str(tmp_path/"archive")], capture_output=True,
                             text=True, timeout=60)
        assert run.returncode == 0, run.stdout + run.stderr
        return json.loads(run.stdout)
    published = cli("publish", str(request_file), "--source-root", str(tmp_path/"source"))
    assert published["git_ingestion"] == "NOT_ATTESTED"
    checked = cli("verify", published["evidence_hash"])
    assert checked["scientific_verdict"] == "UNKNOWN"
