"""Preparation-only Kaggle thermal study adapter using existing TaskSpec.

No provider write operation exists here. Submission/retry stay closed until a
trusted host supplies atomic consumption, authenticated free allocation and
run-bound retrieval. Historical sAlex operations are never invoked.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import uuid

from rudeus.execution.backend import BackendAttempt, advance
from rudeus.execution.contracts import ExecutionError, TaskSpec
from rudeus.execution.kaggle_backend import probe
from rudeus.science.contracts import digest
from rhombus.atomistics.thermal_trace import canonical_bytes, sha256

PROTOCOL_PATH = "data/development/digital0201/protocol_v1.json"


def load_protocol(root):
    return json.loads((Path(root) / PROTOCOL_PATH).read_bytes())


def source_inventory(root, revision):
    """Extend legacy rudeus-only inventory to include executed rhombus code.

    This is a separate explicit inventory, not a forged legacy CodeBundle.
    Resolve committed blobs; never include credentials, TEST data or caches.
    """
    if len(revision) != 40 or any(c not in "0123456789abcdef" for c in revision):
        raise ValueError("exact source commit required")
    def git(*args):
        return subprocess.check_output(["git", "--no-replace-objects", "-C", str(root), *args])
    paths = git("ls-tree", "-r", "--name-only", revision).decode().splitlines()
    selected = [p for p in paths if p.startswith(("rudeus/", "rhombus/")) or p in (
        PROTOCOL_PATH, "scripts/science/thermal_study_0201.py", "pyproject.toml", "config.yaml", "scripts/ci/constraints.txt")]
    return {p: sha256(git("show", f"{revision}:{p}")) for p in selected}


def build_study_task(p, revision, inventory):
    return TaskSpec(candidate_id="thermal-0201-known-reference-cohort",
        stage="assess_finite_temperature_stability", protocol_hash=inventory[PROTOCOL_PATH],
        config={"study": p["study"], "device": "cpu", "dtype": "float64", "probe": p["probe"]},
        input_artifact_hashes=(p["parent_report_sha256"], p["model_sha256"]), dependencies=(),
        code_revision=revision, code_bundle_hash=digest(inventory),
        resource_requirements=p["resource_budget"], expected_outputs=("thermal-traces", "trajectories", "result-manifest", "runtime-probe"),
        retry_policy={"max_attempts": 1, "automatic_retry": False}, temperature=550.0)


def prepare_thermal_study(root, revision):
    root = Path(root)
    p = load_protocol(root)
    inventory = source_inventory(root, revision)
    if inventory.get(PROTOCOL_PATH) != sha256((root / PROTOCOL_PATH).read_bytes()):
        raise ValueError("protocol is not bound to committed source")
    if "scripts/science/thermal_study_0201.py" not in inventory:
        raise ValueError("runner must be committed before preparation")
    task = build_study_task(p, revision, inventory)
    created = BackendAttempt(attempt_id=digest({"task": task.content_hash, "nonce": uuid.uuid4().hex}),
        task_id=task.task_id, task_content_hash=task.content_hash,
        task_bundle_hash=digest({"task": task.to_dict(), "inventory": inventory}), backend="kaggle")
    prepared = advance(created, "PREPARED")
    return {"schema_version": "rhombus-kaggle-thermal-preparation-v1", "task": task.to_dict(),
            "task_id": task.task_id, "source_inventory": inventory, "protocol": p,
            "attempts": [created.to_dict(), prepared.to_dict()], "state": "PREPARED_NOT_SUBMITTED",
            "submission_gate": "CLOSED", "provider_job_id": None, "device": "cpu",
            "kernel_configuration": {"is_private": True, "enable_gpu": False, "enable_internet": True},
            "provider_readiness": probe(), "free_cpu": "UNKNOWN", "free_gpu": "UNKNOWN",
            "duplicate_safety": "NO_SUBMISSION_IMPLEMENTED; no retry or legacy dispatch",
            "required_host_controls": ["authenticated current free allocation", "task-specific authorization",
                "durable atomic request consumption", "authenticated run-bound result receipt"],
            "weight_delivery": {"mode": "read-only verified input file", "sha256": p["model_sha256"]},
            "scientific_result": "NOT_EXECUTED", "qualified_survivors": []}


def submit_thermal_study(*args, **kwargs):
    raise ExecutionError("0201 submission CLOSED: trusted-host allocation, atomic consumption and authenticated retrieval unprovisioned", "UNSUPPORTED_INPUT")


def verify_remote_thermal_result(directory, request, *, trusted_observation):
    """Host pins provider observation externally; producer receipts cannot do so.

    The host must obtain this observation via an authenticated provider channel,
    not from files returned by the job. This adapter does NOT implement that
    channel or attest a Kaggle run. A COMPLETE producer manifest alone fails.
    """
    from rhombus.atomistics.thermal_trace import verify_thermal_trace
    if (not trusted_observation or trusted_observation.get("task_id") != request["task_id"]
            or trusted_observation.get("provider") != "kaggle"
            or trusted_observation.get("status") != "COMPLETE"
            or not trusted_observation.get("job_id")):
        raise ValueError("independent trusted-host provider observation required")
    root = Path(directory).resolve(strict=True)
    manifest_path = root / "manifest.json"
    if manifest_path.is_symlink() or manifest_path.stat().st_size > 1024 * 1024:
        raise ValueError("unsafe result manifest")
    raw = manifest_path.read_bytes()
    if sha256(raw) != trusted_observation.get("manifest_sha256"):
        raise ValueError("host-pinned result manifest mismatch")
    manifest = json.loads(raw)
    if (manifest["task_id"] != request["task_id"] or manifest["job_id"] != trusted_observation["job_id"]
            or manifest["request_sha256"] != sha256(canonical_bytes(request))):
        raise ValueError("remote receipt task/job mismatch")
    bound = manifest["files"]
    if not bound or sum(r["size_bytes"] for r in bound.values()) > request["protocol"]["resource_budget"]["output_bytes"]:
        raise ValueError("invalid result inventory budget")
    for name, row in bound.items():
        path = root / name
        if (Path(name).name != name or path.is_symlink() or not path.is_file()
                or path.stat().st_size != row["size_bytes"] or sha256(path.read_bytes()) != row["sha256"]):
            raise ValueError("missing/corrupt/orphaned remote artifact")
    if {p.name for p in root.iterdir()} != set(bound) | {"manifest.json"}:
        raise ValueError("unbound remote output")
    results = []
    if not manifest["runs"]:
        raise ValueError("no measured thermal runs")
    parent_raw = (Path(__file__).resolve().parents[2] / request["protocol"]["parent_report"]).read_bytes()
    parent = json.loads(parent_raw)
    if sha256(parent_raw) != request["protocol"]["parent_report_sha256"]:
        raise ValueError("parent report changed")
    from rudeus.mlip.sharding import structure_dict_sha256
    from rudeus.mlip.p2_traj import verify_traj_artifact
    candidates = {c["candidate_id"]: c for c in parent["candidates"]}
    from rudeus.mlip.p2 import P2_PROTOCOL_DEFAULTS, protocol_config_hash
    p = request["protocol"]
    plan = [(p["probe"]["candidate_id"], "cpu_probe", p["probe"])]
    for candidate in p["candidate_ids"]:
        for cfg in p["study"]["runs"]:
            dt = cfg["timestep_fs"]
            plan.append((candidate, cfg["label"], dict(cfg,
                equil_steps=int(p["study"]["equilibration_time_fs"] / dt),
                production_steps=int(p["study"]["production_time_fs"] / dt),
                sample_interval_steps=int(p["study"]["sampling_time_fs"] / dt))))
    observed = [(r["binding"]["candidate_id"], r["label"]) for r in manifest["runs"]]
    if (manifest["status"] not in ("COMPLETE", "PARTIAL")
            or observed != [(c, label) for c, label, _ in plan[:len(observed)]]
            or (manifest["status"] == "COMPLETE" and len(observed) != len(plan))):
        raise ValueError("missing/duplicated/unplanned scientific runs")
    runtime = manifest["runtime"]
    if runtime.get("packages") != p["runtime_pins"] or runtime.get("device") != "cpu" or runtime.get("dtype") != "float64":
        raise ValueError("runtime identity mismatch")
    for run, (_, _, cfg) in zip(manifest["runs"], plan):
        md = dict(P2_PROTOCOL_DEFAULTS, base_seed=cfg["seed"], timestep_fs=cfg["timestep_fs"],
                  equil_steps=cfg["equil_steps"], production_steps=cfg["production_steps"],
                  sample_interval_steps=cfg["sample_interval_steps"])
        if run["md_protocol"] != md:
            raise ValueError("run protocol differs from frozen plan")
        name = run["trace"]["path"]
        if name not in bound or bound[name]["sha256"] != run["trace"]["sha256"]:
            raise ValueError("orphaned trace")
        b = run["binding"]
        c = candidates[b["candidate_id"]]
        if (b["task_id"] != request["task_id"] or b["model_sha256"] != request["protocol"]["model_sha256"]
                or b["protocol_sha256"] != request["task"]["protocol_hash"]
                or b["source_commit"] != request["task"]["code_revision"]
                or b["runtime"] != runtime or b["source_sha256"] != c["source"]["artifact_sha256"]
                or b["relaxed_structure_sha256"] != structure_dict_sha256(c["P1"]["relaxed_structure_dict"])):
            raise ValueError("run ancestry mismatch")
        diagnostic = verify_thermal_trace(root / name, expected_sha256=run["trace"]["sha256"],
            expected_binding=b, expected_protocol=run["md_protocol"])
        p2 = run["P2"]
        traj = run["trajectory"]
        if traj["path"] not in bound:
            raise ValueError("orphaned trajectory")
        verified = verify_traj_artifact(root / traj["path"], traj["logical_sha256"])
        trace = json.loads((root / name).read_bytes())
        expected_frames = [r["md_step"] - md["equil_steps"] for r in trace["samples"] if r["phase"] == "production"]
        if (verified["seed"] != md["base_seed"] or verified["timestep_fs"] != md["timestep_fs"]
                or verified["frame_steps"].tolist() != expected_frames
                or p2["p2_protocol"] != md or p2["p2_config_hash"] != protocol_config_hash(md)
                or p2["p1_relaxed_structure_sha256"] != b["relaxed_structure_sha256"]):
            raise ValueError("trajectory/structure mismatch")
        for key in ("temp_mean_K", "temp_std_K", "energy_mean_ev_per_atom", "energy_drift_ev_per_ps_per_atom", "pressure_mean_GPa", "pressure_std_GPa"):
            import numpy as np
            measured, saved = diagnostic.get(key), p2["thermal_metrics"][key]
            if measured is None and saved is None:
                continue
            if measured is None or saved is None or not np.isclose(measured, saved, rtol=1e-8, atol=1e-8):
                raise ValueError("thermal summary mismatch")
        results.append(diagnostic)
    return {"operational_status": manifest["status"], "runs": results,
            "scientific_verdict": "INDETERMINATE", "qualification": "ABSTAIN",
            "conductivity_S_cm": None, "qualified_survivors": []}
