"""Kaggle-only computational driver and local preparation CLI for study 0201.

There is deliberately no submit CLI. A future trusted host adapter must call
execute_on_kaggle only AFTER authenticating allocation, consuming authorization
atomically and binding provider run identity. No local inference fallback.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import time

from rhombus.atomistics.thermal_trace import build_thermal_trace, canonical_bytes, sha256, write_thermal_trace
from rhombus.atomistics.thermal_study import build_study_task, load_protocol, prepare_thermal_study, source_inventory
from rudeus.execution.contracts import TaskSpec

ROOT = Path(__file__).resolve().parents[2]


def validate_request(request, root):
    task = TaskSpec.from_dict(request["task"])
    task.validate()
    inventory = source_inventory(root, task.code_revision)
    from rudeus.science.contracts import digest
    if (task.task_id != request["task_id"] or request["source_inventory"] != inventory
            or task.code_bundle_hash != digest(inventory)
            or load_protocol(root) != request["protocol"]
            or task.to_dict() != build_study_task(load_protocol(root), task.code_revision, inventory).to_dict()):
        raise ValueError("task/source/protocol mismatch")
    for name, expected in inventory.items():
        path = Path(root) / name
        if path.is_symlink() or sha256(path.read_bytes()) != expected:
            raise ValueError("executed checkout differs from requested committed bytes")
    if subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"]).decode().strip() != task.code_revision:
        raise ValueError("exact source checkout required")
    return task


def execute_on_kaggle(request, model, output, *, host_context=None):
    """Internal driver, NOT an authorization/receipt issuing service.

    host_context is supplied by the trusted controller, never scientific task
    payloads/MCP/job outputs. That controller is UNPROVISIONED in 0201. These
    checks are necessary, not evidence that such a controller has been verified.
    """
    required = {"allocation_verified_free", "authorization_consumed_atomically", "authenticated_run_identity"}
    if (not host_context or any(host_context.get(k) is not True for k in required)
            or host_context.get("request_sha256") != sha256(canonical_bytes(request))
            or host_context.get("provider") != "kaggle" or not host_context.get("job_id")):
        raise PermissionError("trusted-host allocation/authorization/atomic-consumption context required; no local fallback")
    if not Path("/kaggle/working").is_dir():
        raise PermissionError("Kaggle runtime required; local scientific calculation disabled")
    return execute_thermal_workload(request, model, output,
        execution_origin={"mode": "CONTROLLED_HOST", "provider_job_id": host_context["job_id"]})


def execute_thermal_workload(request, model, output, *, execution_origin):
    """Shared scientific body; callers own launch control, never MCP-facing.

    Manual launch is a distinct owner-operated path, not a host attestation.
    Both entry points use the same frozen dynamics, resources and artifacts.
    """
    import resource
    task = validate_request(request, ROOT)
    p = request["protocol"]
    if p["device"] != "cpu" or request["device"] != "cpu":
        raise ValueError("no GPU allocation or precision qualification for this CPU task")
    output, model = Path(output), Path(model)
    if output.exists():
        raise FileExistsError("preserve previous/partial results; no automatic retry")
    if sha256(model.read_bytes()) != p["model_sha256"]:
        raise ValueError("model digest mismatch before deserialization")
    for package, version in p["runtime_pins"].items():
        if importlib.metadata.version(package) != version:
            raise ValueError("unverified runtime package: " + package)
    from rhombus.qualification.pilot_artifacts import verify_pilot_artifacts
    verify_pilot_artifacts((ROOT / p["parent_report"]).parent, expected_report_sha256=p["parent_report_sha256"])
    parent = json.loads((ROOT / p["parent_report"]).read_bytes())
    candidates = {c["candidate_id"]: c for c in parent["candidates"]}
    output.mkdir(parents=True)
    started, cpu = time.monotonic(), time.process_time()
    budget = p["resource_budget"]
    os.environ.update(OMP_NUM_THREADS=str(p["cpu_threads"]), OPENBLAS_NUM_THREADS=str(p["cpu_threads"]), MKL_NUM_THREADS=str(p["cpu_threads"]))
    import torch
    torch.set_num_threads(p["cpu_threads"])
    from mace.calculators import MACECalculator
    from rudeus.mlip.p2 import P2_PROTOCOL_DEFAULTS, DiagnosticStall, run_nvt, build_p2_result, protocol_config_hash
    from rudeus.mlip.sharding import structure_dict_sha256
    def timed_out(*_):
        raise DiagnosticStall("0201 wall deadline")
    previous = signal.signal(signal.SIGALRM, timed_out)
    signal.alarm(budget["wall_seconds"])
    runtime = {"python": platform.python_version(), "packages": dict(p["runtime_pins"]),
               "device": "cpu", "dtype": "float64", "threads": torch.get_num_threads(),
               "available_cpu_count": os.cpu_count(), "physical_memory_bytes": os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")}
    manifest = {"schema_version": "rhombus-thermal-study-result-v1", "task_id": task.task_id,
                "request_sha256": sha256(canonical_bytes(request)), "job_id": execution_origin["provider_job_id"],
                "execution_origin": execution_origin,
                "runtime": runtime, "status": "PARTIAL", "runs": [], "files": {},
                "scientific_verdict": "INDETERMINATE", "conductivity_S_cm": None,
                "qualification": "ABSTAIN", "error_type": None}
    def save():
        manifest["cost"] = {"wall_seconds": time.monotonic() - started, "process_cpu_seconds": time.process_time() - cpu,
                            "peak_memory_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, "money_usd": 0}
        manifest["files"] = {f.name: {"sha256": sha256(f.read_bytes()), "size_bytes": f.stat().st_size}
                             for f in output.iterdir() if f.is_file() and f.name != "manifest.json"}
        temp = output / ".manifest.tmp"
        temp.write_bytes(canonical_bytes(manifest)); temp.replace(output / "manifest.json")
    def budget_hook(step, phase):
        if (time.monotonic() - started >= budget["wall_seconds"]
                or resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024 > budget["memory_mib"]
                or sum(f.stat().st_size for f in output.iterdir() if f.is_file()) > budget["output_bytes"]):
            raise DiagnosticStall("0201 resource limit")
    try:
        loading = time.monotonic()
        calc = MACECalculator(model_paths=str(model), device="cpu", default_dtype="float64")
        runtime["model_load_seconds"] = time.monotonic() - loading
        def calculate(candidate_id, label, cfg):
            c = candidates[candidate_id]
            dt = cfg["timestep_fs"]
            md = dict(P2_PROTOCOL_DEFAULTS, base_seed=cfg["seed"], timestep_fs=dt,
                      equil_steps=cfg["equil_steps"], production_steps=cfg["production_steps"],
                      sample_interval_steps=cfg["sample_interval_steps"])
            relaxed = c["P1"]["relaxed_structure_dict"]
            binding = {"task_id": task.task_id, "candidate_id": candidate_id,
                       "source_sha256": c["source"]["artifact_sha256"],
                       "relaxed_structure_sha256": structure_dict_sha256(relaxed),
                       "model_sha256": p["model_sha256"], "protocol_sha256": task.protocol_hash,
                       "source_commit": task.code_revision, "runtime": runtime}
            before = time.monotonic()
            record = run_nvt(relaxed, calc, md, cfg["seed"], step_hook=budget_hook, retain_thermal_trace=True)
            trace = build_thermal_trace(record, binding, md)
            trace_artifact = write_thermal_trace(output, trace)
            job_id = sha256((task.task_id + candidate_id + label).encode())[:24]
            job = {"batch_id": job_id, "child_material_id": candidate_id, "parent_id": c["source"]["artifact_key"],
                   "relaxed_structure_sha256": binding["relaxed_structure_sha256"], "p2_protocol": md,
                   "p2_config_hash": protocol_config_hash(md), "seed": cfg["seed"]}
            result = build_p2_result(job, record, {"checkpoint_name": "medium-mpa-0", "checkpoint_sha256": p["model_sha256"]}, traj_artifact_dir=output)
            run = {"label": label, "binding": binding, "md_protocol": md, "trace": trace_artifact, "P2": result,
                   "trajectory": {"path": job_id + ".npz", "logical_sha256": result["trajectory_artifact"]["sha256"]},
                   "wall_seconds": time.monotonic() - before}
            manifest["runs"].append(run); save()
            if not record["completed"]:
                raise RuntimeError("partial MD retained; study stopped")
            return run
        probe_started = time.monotonic()
        signal.alarm(min(budget["probe_wall_seconds"], budget["wall_seconds"]))
        run = calculate(p["probe"]["candidate_id"], "cpu_probe", p["probe"])
        probe_wall = time.monotonic() - probe_started
        steps = p["probe"]["equil_steps"] + p["probe"]["production_steps"]
        total = sum(int((p["study"]["equilibration_time_fs"] + p["study"]["production_time_fs"]) / r["timestep_fs"]) for r in p["study"]["runs"]) * len(p["candidate_ids"])
        projected = 2 * probe_wall / steps * total
        manifest["cpu_probe"] = {"wall_seconds": probe_wall, "seconds_per_step_including_setup": probe_wall / steps,
                                 "projected_study_seconds_factor2": projected, "output_bytes": sum(f.stat().st_size for f in output.iterdir())}
        if projected > budget["max_projection_fraction"] * budget["wall_seconds"]:
            raise RuntimeError("CPU projection exceeds frozen free allocation budget; no GPU/local fallback")
        signal.alarm(max(1, int(budget["wall_seconds"] - (time.monotonic() - started))))
        for candidate_id in p["candidate_ids"]:
            for cfg in p["study"]["runs"]:
                dt = cfg["timestep_fs"]
                calculate(candidate_id, cfg["label"], dict(cfg,
                    equil_steps=int(p["study"]["equilibration_time_fs"] / dt),
                    production_steps=int(p["study"]["production_time_fs"] / dt),
                    sample_interval_steps=int(p["study"]["sampling_time_fs"] / dt)))
        manifest["status"] = "COMPLETE"
    except Exception as exc:
        # Keep partial measurements and operational error type. Raw exception
        # text can contain provider credentials; it is intentionally not stored.
        manifest["error_type"] = type(exc).__name__
    finally:
        signal.alarm(0); signal.signal(signal.SIGALRM, previous); save()
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    args = parser.parse_args()
    request = prepare_thermal_study(ROOT, args.source_commit)
    with args.prepare.open("xb") as out:
        out.write(canonical_bytes(request))
    print(json.dumps({"state": request["state"], "task_id": request["task_id"], "submission_gate": "CLOSED"}))


if __name__ == "__main__":
    main()
