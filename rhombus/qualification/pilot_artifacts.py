"""Offline verification of a real pilot's file and logical trajectory bindings."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from rudeus.mlip.p2_traj import verify_traj_artifact
from rudeus.mlip.sharding import structure_dict_sha256
from rhombus.tools.evidence_query import _verify_evidence_row


def verify_pilot_artifacts(directory: Path, *, expected_report_sha256: str) -> dict:
    """Require a host-pinned report, then verify its complete retained file set.

    Byte digests and canonical trajectory digests are different identities; both
    are checked. No inference, source reacquisition or scientific promotion.
    """
    directory = Path(directory).resolve(strict=True)
    raw = (directory / "report.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_report_sha256:
        raise ValueError("pilot report digest mismatch")
    report = json.loads(raw)
    if report.get("schema_version") != "rhombus-digital-pilot-result-v1":
        raise ValueError("unsupported pilot report schema")
    if (report.get("qualified_survivors") != [] or report.get("scientific_GO") is not False
            or report.get("production_enabled") is not False or report.get("TEST121_accessed") is not False):
        raise ValueError("pilot receipt cannot confer material qualification")
    for name, expected in report["artifact_files_sha256"].items():
        path = directory / name
        if path.is_symlink() or directory not in path.resolve().parents or not path.is_file():
            raise ValueError("pilot artifact absent or outside bound root")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("pilot artifact byte digest mismatch")
    for i, row in enumerate(report["evidence_records"], 1):
        _verify_evidence_row(row, lineno=i)
        if row["scientific_verdict"] != "INDETERMINATE" or row["applicability"]["domain_status"] != "UNQUALIFIED":
            raise ValueError("unqualified pilot evidence was promoted")
        if row["model_identity"]["checkpoint_sha256"] != report["model_sha256"]:
            raise ValueError("pilot model identity mismatch")
        if any(b["sha256"] not in report["artifact_files_sha256"].values() for b in row["artifact_bindings"]):
            raise ValueError("evidence refers to an unbound pilot artifact")
    delivered = [json.loads(line) for line in (directory / "evidence.jsonl").read_text().splitlines()]
    if delivered != report["evidence_records"]:
        raise ValueError("MCP snapshot and bound report evidence disagree")
    count = 0
    for candidate in report["candidates"]:
        saved_candidate = json.loads((directory / candidate["candidate_id"] / "candidate.json").read_text())
        if saved_candidate != candidate:
            raise ValueError("report and retained candidate disagree")
        qualification = candidate["digital_qualification"]
        if qualification["qualified_survivor"] is not False or qualification["qualification"] != "ABSTAIN":
            raise ValueError("unqualified pilot candidate was promoted")
        for run in candidate["runs"]:
            payload_path = directory / candidate["candidate_id"] / (run["label"] + ".json")
            saved = json.loads(payload_path.read_text())
            p2 = run["P2"]
            if saved["result"] != p2:
                raise ValueError("report and retained P2 result disagree")
            expected_structure = structure_dict_sha256(candidate["P1"]["relaxed_structure_dict"])
            if p2["p1_relaxed_structure_sha256"] != expected_structure:
                raise ValueError("P1/P2 structure ancestry mismatch")
            artifact = directory / candidate["candidate_id"] / (p2["batch_id"] + ".npz")
            verified = verify_traj_artifact(artifact, p2["trajectory_artifact"]["sha256"])
            if verified["seed"] != run["seed"] or verified["timestep_fs"] != run["timestep_fs"]:
                raise ValueError("trajectory seed/timestep identity mismatch")
            if p2["p2_verdict"] != "PASS" and run["P25"].get("status") != "BLOCKED":
                raise ValueError("P2 rejection did not block transport admission")
            p3 = run["P3"]
            if p3["conductivity_S_cm"] is not None or p3["qualified_diffusion_m2_s"] is not None:
                raise ValueError("short pilot manufactured a transport property")
            count += 1
    return {"file_count": len(report["artifact_files_sha256"]), "trajectory_count": count,
            "evidence_count": len(report["evidence_records"]), "qualified_survivors": []}
