"""Verified, append-only evidence archives. Git remains the durable record.

Publication archives an existing scientific record; it never changes a verdict.
The producer is the recorded scientific execution, not a fabricated archival run.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

from rudeus.execution.contracts import ArtifactManifest, ExecutionAttempt, ExecutionError, TaskSpec
from rudeus.science.claims import evaluate_claim
from rudeus.science.contracts import (ClaimAssessment, ClaimSpec, Observation, Uncertainty,
                                      canonical_bytes, digest, require_hash)

VERSION = "claim-evidence-v1"


@contextmanager
def integrity_errors():
    try:
        yield
    except ExecutionError:
        raise
    except (OSError, ValueError, TypeError, KeyError, subprocess.CalledProcessError) as exc:
        raise ExecutionError(f"evidence verification failed: {exc}", "INTEGRITY") from exc


def require(condition, message):
    if not condition:
        raise ExecutionError(message, "INTEGRITY")


def inside(root, relative):
    root = Path(root).resolve()
    require(not Path(relative).is_absolute(), "artifact locator must be relative")
    path = (root / relative).resolve()
    require(path.is_relative_to(root), "artifact locator escapes root")
    return path


def append_file(path, data):
    """Flushed temporary file -> exclusive atomic hard link; never replace.

    Unsupported filesystems fail closed. Interrupted publication may leave orphan
    blobs but cannot expose a partial evidence manifest as a completed archive.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".evidence-pending-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            require(path.read_bytes() == data, "append-only content collision")
    finally:
        Path(temporary).unlink(missing_ok=True)


def verified_bytes(manifest, data):
    require(len(data) == manifest.size_bytes, "artifact size mismatch")
    require(hashlib.sha256(data).hexdigest() == manifest.raw_hash, "artifact raw hash mismatch")
    if manifest.format == "json" and manifest.canonicalization_version == "canonical-json-v1":
        decoded = json.loads(data)
        require(digest(decoded) == manifest.logical_hash, "artifact logical hash mismatch")
        return decoded
    if (manifest.format == "p2-traj" and manifest.format_version == "p2-traj-v1"
            and manifest.canonicalization_version == "p2-traj-v1"):
        # Verify a snapshot of the exact hashed bytes with the existing canonical
        # trajectory implementation, not a newly defined NPZ hash convention.
        from rudeus.mlip.p2_traj import verify_traj_artifact, TrajectoryArtifactError
        with tempfile.TemporaryDirectory(prefix="rhombus-evidence-") as temporary:
            path = Path(temporary) / "trajectory.npz"
            path.write_bytes(data)
            try:
                verify_traj_artifact(path, manifest.logical_hash)
            except TrajectoryArtifactError as exc:
                raise ExecutionError(str(exc), "INTEGRITY") from exc
        return None
    raise ExecutionError("unsupported artifact canonicalization", "UNSUPPORTED_INPUT")


def validate_request(request, reader, qualification_registry=None):
    """Recompute assessment using the existing engine and verified provenance.

    Registry trust is supplied by the caller, never by the archived request.
    Current P3 records replay with empty checks and an empty registry.
    """
    require(set(request) <= {"task", "attempts", "manifests", "record_manifest", "checks", "followups"},
            "unknown evidence request field")
    task = TaskSpec.from_dict(request["task"])
    attempts = [ExecutionAttempt.from_dict(v) for v in request["attempts"]]
    require(len({a.attempt_id for a in attempts}) == len(attempts), "ambiguous producer attempt")
    producers = {a.attempt_id: a for a in attempts}
    manifest_list = [ArtifactManifest.from_dict(v) for v in request["manifests"]]
    manifests = {m.content_hash: m for m in manifest_list}
    require(len(manifests) == len(manifest_list), "duplicate manifest entry")
    root = manifests[request["record_manifest"]]
    producer = producers[root.producer_attempt]
    require(producer.task_id == task.task_id and producer.status == "COMPLETED"
            and producer.exit_status == 0, "scientific producer did not complete this task")
    require(set(producer.output_manifest) == set(task.expected_outputs), "task output set mismatch")
    require(root.content_hash in producer.output_manifest.values(), "record not bound to producing attempt")
    require(set(root.parent_artifact_hashes) == set(task.input_artifact_hashes), "task inputs differ from record parents")
    logical = {m.logical_hash for m in manifest_list}
    require(set(producers) == {m.producer_attempt for m in manifest_list}, "unrelated execution attempt")
    decoded, blobs = {}, {}
    for manifest_hash, manifest in sorted(manifests.items()):
        parent = producers[manifest.producer_attempt]
        require(parent.status == "COMPLETED" and parent.exit_status == 0,
                "source producer is not a successful execution")
        require(manifest_hash in parent.output_manifest.values(), "source not bound to producer outputs")
        require(set(manifest.parent_artifact_hashes) <= logical, "missing parent artifact")
        data = reader(manifest)
        decoded[manifest_hash] = verified_bytes(manifest, data)
        blobs[manifest.raw_hash] = data
    # Every declared producer output must be available, with matching attribution.
    for attempt in attempts:
        for output in attempt.output_manifest.values():
            require(output in manifests and manifests[output].producer_attempt == attempt.attempt_id,
                    "unverified or misattributed execution output")
    # Traverse logical ancestry, rejecting cycles; logical aliases may have
    # distinct raw container hashes, but must agree on their parent identities.
    parents = {}
    for m in manifest_list:
        ps = set(m.parent_artifact_hashes)
        require(m.logical_hash not in parents or parents[m.logical_hash] == ps,
                "ambiguous logical artifact ancestry")
        parents[m.logical_hash] = ps
    visited, active = set(), set()
    def visit(value):
        require(value not in active, "cyclic artifact ancestry")
        if value in visited:
            return
        active.add(value)
        for parent in sorted(parents[value]):
            visit(parent)
        active.remove(value)
        visited.add(value)
    visit(root.logical_hash)
    require(visited == logical, "unrelated artifacts in evidence request")
    record = decoded[root.content_hash]
    require(isinstance(record, dict), "scientific record must be JSON")
    p3_provenance = None
    if "p3_scientific_record" in record:
        p3_provenance = record["p3_provenance"]
        require(record["p3_provenance"]["scientific_record_hash"] == digest(record["p3_scientific_record"]),
                "P3 scientific record hash mismatch")
        record = record["p3_scientific_record"]
    require(set(record) == {"claim_spec", "observation", "uncertainty", "assessment"},
            "incomplete scientific record")
    spec = ClaimSpec.from_dict(record["claim_spec"])
    obs = Observation.from_dict(record["observation"]) if record["observation"] is not None else None
    uncertainty = Uncertainty.from_dict(record["uncertainty"])
    assessment = ClaimAssessment.from_dict(record["assessment"])
    require(task.protocol_hash == spec.protocol_hash, "task/claim protocol mismatch")
    require(spec.scope.get("candidate_id") == task.candidate_id, "task/claim candidate mismatch")
    require(uncertainty.observation_hash == (obs.content_hash if obs else None),
            "uncertainty is not bound to this observation")
    required = {spec.protocol_hash, spec.provenance_identity, *assessment.supporting_evidence,
                *assessment.conflicting_evidence}
    if obs:
        required.update(obs.artifact_hashes)
        required.add(obs.protocol_hash)
    if uncertainty.calibration_reference:
        cert = (qualification_registry or {}).get(uncertainty.calibration_reference)
        require(cert is not None, "calibration registry entry unavailable")
        require(cert.content_hash == uncertainty.calibration_reference, "calibration registry identity mismatch")
        required.update((cert.content_hash, *cert.evidence_hashes))
    require(required <= visited - {root.logical_hash}, "scientific provenance is unavailable or unverified")
    if p3_provenance is not None:
        by_logical = {m.logical_hash: decoded[h] for h, m in manifests.items()}
        provenance = by_logical[spec.provenance_identity]
        require(p3_provenance["p3_config_hash"] == spec.protocol_hash
                and digest(p3_provenance["protocol"]) == spec.protocol_hash,
                "P3 protocol provenance mismatch")
        require(digest(provenance["p2"]) == p3_provenance["p2_result_hash"]
                and digest(provenance["p25"]) == p3_provenance["p25_result_hash"],
                "P3 input-result provenance mismatch")
        require(p3_provenance["trajectory_sha256"] in visited,
                "P3 trajectory provenance unavailable")
    replay = evaluate_claim(spec, obs, uncertainty, checks=request.get("checks", {}),
                            qualification_registry=qualification_registry,
                            conflicting_evidence=assessment.conflicting_evidence)
    require(replay.to_dict() == assessment.to_dict(), "assessment does not reproduce; refusing verdict change")
    normalized = {"task": task.to_dict(), "record_manifest": root.content_hash,
                  "manifests": [manifests[h].to_dict() for h in sorted(manifests)],
                  "attempts": [producers[h].to_dict() for h in sorted(producers)],
                  "checks": request.get("checks", {})}
    if "followups" in request:
        from rudeus.science.followups import FollowupRequest
        followups = [FollowupRequest.from_dict(value) for value in request["followups"]]
        for followup in followups:
            followup.verify_binding(record)
        normalized["followups"] = [value.to_dict() for _, value in sorted(
            {value.content_hash: value for value in followups}.items())]
    return normalized, record, blobs, root


class EvidenceStore:
    def __init__(self, root):
        self.root = Path(root).resolve()

    def path(self, relative):
        return inside(self.root, relative)

    def publish(self, request, *, source_root, qualification_registry=None):
        with integrity_errors():
            request, record, blobs, source = validate_request(
                request, lambda m: inside(source_root, m.durable_locator).read_bytes(), qualification_registry)
            payload = {"format_version": VERSION, "scientific_record": record,
                       "scientific_record_hash": digest(record), "provenance": request,
                       "scientific_qualification": record["uncertainty"]["qualification"]}
            data = canonical_bytes(payload)
            identity = digest(payload)
            manifest = ArtifactManifest(
                logical_hash=identity, raw_hash=hashlib.sha256(data).hexdigest(), size_bytes=len(data),
                canonicalization_version="canonical-json-v1", format="json", format_version=VERSION,
                durable_locator=f"blobs/{identity}", producer_attempt=source.producer_attempt,
                parent_artifact_hashes=tuple(sorted({m["logical_hash"] for m in request["manifests"]})),
                retrieval_verification={"status": "VERIFIED_LOCAL", "verifier": VERSION})
            # All inputs are verified before publishing anything. The manifest is
            # the last, exclusive commit marker; orphan blobs are never evidence.
            for raw_hash, blob in sorted(blobs.items()):
                append_file(self.path(f"blobs/{raw_hash}"), blob)
            append_file(self.path(manifest.durable_locator), data)
            append_file(self.path(f"evidence/{identity}.json"), canonical_bytes(manifest))
            self.verify(identity, qualification_registry=qualification_registry)
            return manifest

    def verify(self, identity, *, qualification_registry=None):
        with integrity_errors():
            require_hash(identity)
            manifest = ArtifactManifest.from_dict(json.loads(self.path(f"evidence/{identity}.json").read_bytes()))
            require(manifest.logical_hash == identity and manifest.format_version == VERSION,
                    "evidence manifest identity/version mismatch")
            require(manifest.durable_locator == f"blobs/{identity}" and manifest.raw_hash == identity,
                    "noncanonical evidence locator/hash")
            data = self.path(manifest.durable_locator).read_bytes()
            payload = verified_bytes(manifest, data)
            require(canonical_bytes(payload) == data, "noncanonical evidence serialization")
            require(payload["format_version"] == VERSION, "unsupported evidence version")
            request, record, _, source = validate_request(
                payload["provenance"], lambda m: self.path(f"blobs/{m.raw_hash}").read_bytes(), qualification_registry)
            require(payload["scientific_record"] == record and payload["scientific_record_hash"] == digest(record),
                    "archived record differs from producer output")
            require(payload["scientific_qualification"] == record["uncertainty"]["qualification"],
                    "archival success cannot upgrade scientific qualification")
            require(manifest.producer_attempt == source.producer_attempt and set(manifest.parent_artifact_hashes)
                    == {m["logical_hash"] for m in request["manifests"]}, "evidence lineage mismatch")
            return payload

    def _git_receipt(self, identity, *, git_root, revision, qualification_registry=None):
        """Rebuild a proof without writing files or trusting receipt metadata."""
        with integrity_errors():
            payload = self.verify(identity, qualification_registry=qualification_registry)
            git_root = Path(git_root).resolve()
            require(self.root.is_relative_to(git_root), "store must be inside Git repository")
            def git(*args):
                return subprocess.run(["git", "-C", str(git_root), *args], check=True,
                                      capture_output=True).stdout
            require(Path(git("rev-parse", "--show-toplevel").decode().strip()).resolve() == git_root,
                    "git_root must be the repository root")
            commit = git("rev-parse", "--verify", "--end-of-options", f"{revision}^{{commit}}").decode().strip()
            paths, visited = set(), set()
            def collect(evidence_hash, archive):
                require(evidence_hash not in visited, "cyclic originating evidence")
                visited.add(evidence_hash)
                paths.update((f"evidence/{evidence_hash}.json", f"blobs/{evidence_hash}"))
                paths.update(f"blobs/{m['raw_hash']}" for m in archive["provenance"]["manifests"])
                task = TaskSpec.from_dict(archive["provenance"]["task"])
                if task.provenance is not None:
                    from rudeus.science.followups import generate_followups
                    origin = task.provenance["evidence_hash"]
                    generated = generate_followups(self, origin, qualification_registry=qualification_registry)
                    require(any(item["task"] == task.to_dict() for item in generated["tasks"]),
                            "task is not bound to originating evidence")
                    collect(origin, self.verify(origin, qualification_registry=qualification_registry))
            collect(identity, payload)
            proof = {}
            for relative in sorted(paths):
                path = self.path(relative)
                require(path == self.root / relative, "Git archive paths must not redirect through symlinks")
                tracked = path.relative_to(git_root).as_posix()
                data = git("cat-file", "blob", f"{commit}:{tracked}")
                require(data == path.read_bytes(), "archive differs from committed bytes")
                proof[relative] = hashlib.sha256(data).hexdigest()
            provenance = payload["provenance"]
            task = TaskSpec.from_dict(provenance["task"])
            output = next(m for m in provenance["manifests"]
                          if digest(m) == provenance["record_manifest"])
            return {"format_version": VERSION, "evidence_hash": identity, "git_commit": commit,
                       "git_tree": git("rev-parse", f"{commit}^{{tree}}").decode().strip(),
                       "store_path": self.root.relative_to(git_root).as_posix(),
                       "record_manifest": provenance["record_manifest"],
                       "artifact_hash": output["logical_hash"],
                       "producer_attempt": output["producer_attempt"], "task_id": task.task_id,
                       "parent_artifact_hashes": sorted(output["parent_artifact_hashes"]),
                       "task_provenance": task.to_dict().get("provenance"),
                       "files": proof, "artifact_status": "DURABLY_INGESTED",
                       "remote_replication": "NOT_ATTESTED",
                       "scientific_verdict": payload["scientific_record"]["assessment"]["verdict"]}

    def acknowledge_git(self, identity, *, git_root, revision, qualification_registry=None):
        """Append a deterministic receipt for archive bytes in an existing commit.

        No commit/push occurs. The receipt itself requires a later Git commit.
        Local Git durability does not attest remote replication or qualification.
        """
        with integrity_errors():
            receipt = self._git_receipt(identity, git_root=git_root, revision=revision,
                                        qualification_registry=qualification_registry)
            append_file(self.path(f"receipts/{digest(receipt)}.json"), canonical_bytes(receipt))
            return receipt

    def verify_git_receipt(self, receipt_hash, *, git_root, qualification_registry=None):
        """Read-only verification of receipt identity, lineage and committed bytes.

        Checks the recorded commit, independent of current HEAD/branch. Required
        working archive files must also match; unrelated working edits are allowed.
        """
        with integrity_errors():
            require_hash(receipt_hash)
            data = self.path(f"receipts/{receipt_hash}.json").read_bytes()
            receipt = json.loads(data)
            require(digest(receipt) == receipt_hash and canonical_bytes(receipt) == data,
                    "receipt content identity mismatch")
            expected = self._git_receipt(receipt["evidence_hash"], git_root=git_root,
                revision=receipt["git_commit"], qualification_registry=qualification_registry)
            require(receipt == expected, "receipt differs from verified Git state")
            return receipt


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("publish", "verify", "acknowledge-git", "verify-git-receipt"))
    parser.add_argument("input", help="request JSON for publish; receipt SHA256 for verify-git-receipt; evidence SHA256 otherwise")
    parser.add_argument("--store-root", required=True)
    parser.add_argument("--source-root")
    parser.add_argument("--git-root")
    parser.add_argument("--revision")
    args = parser.parse_args(argv)
    store = EvidenceStore(args.store_root)
    try:
        with integrity_errors():
            if args.operation == "publish":
                require(args.source_root is not None, "publish requires --source-root")
                request = json.loads(Path(args.input).read_text(encoding="utf-8-sig"))
                manifest = store.publish(request, source_root=args.source_root)
                result = {"artifact_status": "VERIFIED_LOCAL", "evidence_hash": manifest.logical_hash,
                          "git_ingestion": "NOT_ATTESTED"}
            elif args.operation == "verify":
                payload = store.verify(args.input)
                result = {"artifact_status": "VERIFIED_LOCAL", "evidence_hash": args.input,
                          "scientific_verdict": payload["scientific_record"]["assessment"]["verdict"]}
            elif args.operation == "verify-git-receipt":
                require(args.git_root is not None, "verify-git-receipt requires --git-root")
                result = store.verify_git_receipt(args.input, git_root=args.git_root)
            else:
                require(args.git_root is not None and args.revision is not None,
                        "acknowledge-git requires --git-root and --revision")
                result = store.acknowledge_git(args.input, git_root=args.git_root, revision=args.revision)
    except ExecutionError as exc:
        print(json.dumps({"artifact_status": "FAILED", "failure_class": exc.failure_class.value,
                          "scientific_verdict": "UNKNOWN", "reason": str(exc)}))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
