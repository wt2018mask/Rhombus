"""P2 GPU-validation harness (local preparation phase, Task 3.6A).

Runs EXPLICIT validation cases through the existing P2 machinery (no second
MD implementation) and records environment provenance that distinguishes CPU
from GPU execution. CPU results are never labeled GPU results; when CUDA is
unavailable the report states GPU_UNRESOLVED.

Same command runs locally and on Kaggle/Colab; only the environment differs.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from rudeus.mlip.calibration import (
    load_calibration_records,
    make_calibration_job,
    run_calibration,
    summarize_calibration,
)
from rudeus.mlip.p2 import P2_PROTOCOL_DEFAULTS
from rudeus.mlip.sharding import structure_dict_sha256, write_json_atomic

VALIDATION_VERSION = "3.6A.1"

GPU_UNRESOLVED = "UNRESOLVED"
GPU_RUN = "RUN"

#: case_id -> {regime (descriptive, existing vocabulary), p1_done_stem or None}.
#: Collapse P1 records (4a9735f2, 628136c9) are listed so their absence is
#: recorded as an omission, never silently substituted.
VALIDATION_CASES: Dict[str, Dict[str, Optional[str]]] = {
    "control-1e9": {"regime": "stable-control", "p1_done_stem": None},
    "0d4de6bc": {"regime": "marginal", "p1_done_stem": "0d4de6bc17174a64"},
    "f8857e1e": {"regime": "marginal", "p1_done_stem": "f8857e1e2fda4e96"},
    "4a9735f2": {"regime": "collapse", "p1_done_stem": "4a9735f2d72aebe8"},
    "628136c9": {"regime": "collapse", "p1_done_stem": None},
    "synthetic-overlap": {"regime": "synthetic-numerical", "p1_done_stem": None},
}


class CaseUnavailable(Exception):
    """A requested validation case has no valid input artifact."""


def collect_backend_versions() -> Dict[str, Any]:
    """Best-effort version record; unavailable fields are explicit None."""
    out: Dict[str, Any] = {"python_version": platform.python_version(),
                           "torch_version": None, "mace_version": None,
                           "ase_version": None}
    try:
        import torch
        out["torch_version"] = torch.__version__
    except Exception:
        pass
    try:
        import mace
        out["mace_version"] = mace.__version__
    except Exception:
        pass
    try:
        import ase
        out["ase_version"] = ase.__version__
    except Exception:
        pass
    return out


def detect_environment() -> Dict[str, Any]:
    """Environment identity: CPU vs GPU is detected, never assumed."""
    cuda, gpu_name, gpu_count = False, None, 0
    try:
        import torch
        cuda = bool(torch.cuda.is_available())
        if cuda:
            gpu_count = int(torch.cuda.device_count())
            try:
                gpu_name = str(torch.cuda.get_device_name(0))
            except Exception:
                gpu_name = "UNKNOWN"
    except Exception:
        pass
    thread_env = {k: os.environ.get(k) for k in
                  ("OMP_NUM_THREADS", "MKL_NUM_THREADS",
                   "OPENBLAS_NUM_THREADS")}
    try:
        import torch as _t
        torch_threads = int(_t.get_num_threads())
    except Exception:
        torch_threads = None
    return {"device": "cuda" if cuda else "cpu",
            "cuda_available": cuda,
            "gpu_name": gpu_name,
            "gpu_count": gpu_count,
            "backend": "mace-torch",
            "gpu_validation_status": GPU_RUN if cuda else GPU_UNRESOLVED,
            "thread_env": thread_env,
            "torch_num_threads": torch_threads,
            **collect_backend_versions()}


def _synthetic_overlap_dict() -> Dict[str, Any]:
    """Clearly labeled numerical fixture (NOT scientific evidence)."""
    from pymatgen.core import Lattice, Structure
    return Structure(Lattice.cubic(4.0), ["Li", "Cl", "Cl"],
                     [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5],
                      [0.52, 0.5, 0.5]]).as_dict()


def resolve_case(case_id: str, p1_done_dir: Union[str, Path],
                 control_input: Optional[Union[str, Path]] = None
                 ) -> Dict[str, Any]:
    """Resolve a case to its P2 input structure + provenance (or raise)."""
    if case_id not in VALIDATION_CASES:
        raise CaseUnavailable(f"unknown validation case {case_id!r}")
    spec = VALIDATION_CASES[case_id]
    if case_id == "synthetic-overlap":
        return {"structure_dict": _synthetic_overlap_dict(),
                "child_material_id": "SYNTHETIC-OVERLAP",
                "parent_id": None, "p1_checkpoint": None,
                "source": "synthetic-fixture"}
    if case_id == "control-1e9":
        if control_input is None:
            raise CaseUnavailable(
                "control-1e9 needs an explicit relaxed-structure input file "
                "(--control-input); no committed P1 control record exists")
        payload = json.loads(Path(control_input).read_text(encoding="utf-8"))
        struct = payload.get("structure_dict") or payload
        return {"structure_dict": struct,
                "child_material_id": payload.get("child_material_id",
                                                 "CONTROL-1e9"),
                "parent_id": payload.get("parent_id", "obelix:1e9"),
                "p1_checkpoint": payload.get("p1_checkpoint"),
                "source": f"control-input:{control_input}"}
    stem = spec["p1_done_stem"]
    path = Path(p1_done_dir) / f"{stem}.json"
    if stem is None or not path.exists():
        raise CaseUnavailable(
            f"case {case_id}: no P1 done record at {path}; refusing to "
            "substitute any replacement silently")
    rec = json.loads(path.read_text(encoding="utf-8"))
    res = rec.get("result") or {}
    if (res.get("p1_verdict") != "KEEP_FOR_P2"
            or not res.get("relaxed_structure_dict")):
        raise CaseUnavailable(
            f"case {case_id}: P1 record is not KEEP_FOR_P2 with a relaxed "
            "structure; refusing to substitute silently")
    return {"structure_dict": res["relaxed_structure_dict"],
            "child_material_id": rec.get("child_material_id"),
            "parent_id": rec.get("parent_id"),
            "p1_checkpoint": res.get("mlip_checkpoint"),
            "source": f"p1-done:{stem}"}


def check_cpu8000_eligible(case_ids: List[str]) -> None:
    """The single CPU production-length attempt is control-only by design."""
    if case_ids != ["control-1e9"]:
        raise ValueError(
            "--cpu-8000 allows exactly the control case "
            f"(got {case_ids}); production-length CPU MD is too expensive "
            "to substitute for GPU validation")


def run_validation(cases: List[str],
                   md_runner: Callable[[Dict[str, Any]], Dict[str, Any]],
                   records_dir: Union[str, Path],
                   p1_done_dir: Union[str, Path],
                   protocol: Dict[str, Any],
                   seeds: Dict[str, int],
                   worker_info: Optional[Dict[str, Any]] = None,
                   control_input: Optional[Union[str, Path]] = None,
                   run_index_base: int = 0,
                   ) -> Dict[str, Any]:
    """Execute validation cases; returns per-case statuses (no MD invented).

    run_index_base offsets record indices so repeated invocations with
    different seeds coexist (run0, run1, ...) instead of overwriting.
    """
    statuses: Dict[str, Any] = {}
    for case_id in cases:
        try:
            resolved = resolve_case(case_id, p1_done_dir, control_input)
        except CaseUnavailable as e:
            statuses[case_id] = {"status": "omitted", "reason": str(e)}
            continue
        job = make_calibration_job(
            f"p2val-{case_id}", resolved["child_material_id"],
            resolved["parent_id"], resolved["structure_dict"],
            resolved["p1_checkpoint"], protocol,
            run_index=run_index_base,
            seed_override=seeds[case_id])
        job["validation"] = {"version": VALIDATION_VERSION,
                             "case_id": case_id,
                             "regime": VALIDATION_CASES[case_id]["regime"],
                             "source": resolved["source"]}
        out = run_calibration(job, md_runner, records_dir,
                              worker_info or {},
                              extra_top_level={"validation": job["validation"]})
        out["regime"] = VALIDATION_CASES[case_id]["regime"]
        statuses[case_id] = out
    return statuses


def describe_comparison(cpu_result: Dict[str, Any],
                        gpu_result: Dict[str, Any],
                        protocol: Optional[Dict[str, Any]] = None
                        ) -> Dict[str, Any]:
    """Descriptive CPU/GPU deltas + provisional-gate side flags (no verdicts).

    Never requires numerical equality; never changes either record's verdict.
    """
    gates = protocol or P2_PROTOCOL_DEFAULTS
    paths = [("host_framework_metrics", "lindemann_provisional",
              ("lindemann_fail_provisional", None, "above")),
             ("host_framework_metrics", "host_rmsd_final_A",
              ("host_rmsd_fail_A_provisional", None, "above")),
             ("host_framework_metrics", "host_rmsd_max_A", (None, None, None)),
             ("host_framework_metrics", "min_distance_traj_A",
              ("min_distance_fail_A_provisional", None, "below")),
             ("host_framework_metrics", "coord_mean_change",
              ("coord_mean_change_fail_provisional", "abs-above", None)),
             ("thermal_metrics", "temp_mean_K", (None, None, None)),
             ("thermal_metrics", "temp_std_K", (None, None, None)),
             ("thermal_metrics", "energy_drift_ev_per_ps_per_atom",
              (None, None, None))]
    deltas = {}
    for section, key, gate in paths:
        a = (cpu_result.get(section) or {}).get(key)
        b = (gpu_result.get(section) or {}).get(key)
        entry: Dict[str, Any] = {"cpu": a, "gpu": b, "delta": None,
                                 "cpu_gate_side": None, "gpu_gate_side": None}
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            entry["delta"] = float(b - a)
            gname, mode, direction = gate
            if gname is not None:
                thr = float(gates[gname])
                if mode == "abs-above":
                    entry["cpu_gate_side"] = "above" if abs(a) > thr else "below"
                    entry["gpu_gate_side"] = "above" if abs(b) > thr else "below"
                elif direction == "above":
                    entry["cpu_gate_side"] = "above" if a > thr else "below"
                    entry["gpu_gate_side"] = "above" if b > thr else "below"
                else:
                    entry["cpu_gate_side"] = "below" if a < thr else "above"
                    entry["gpu_gate_side"] = "below" if b < thr else "above"
        deltas[f"{section}.{key}"] = entry
    states = (cpu_result.get("dynamic_state"), gpu_result.get("dynamic_state"))
    return {"metric_deltas": deltas,
            "cpu_state": states[0], "gpu_state": states[1],
            "states_agree": states[0] == states[1]}


def build_validation_report(cases: List[str],
                            records_dir: Union[str, Path],
                            protocol: Dict[str, Any],
                            calc_info: Dict[str, Any],
                            environment: Dict[str, Any],
                            git_commit: Optional[str],
                            timestamp: Optional[str] = None,
                            statuses: Optional[Dict[str, Any]] = None,
                            extra: Optional[Dict[str, Any]] = None
                            ) -> Dict[str, Any]:
    """Machine-readable validation artifact (deterministic given timestamp)."""
    from rudeus.mlip.calibration import summarize_calibration

    records_dir = Path(records_dir)
    runs, missing = [], []
    for case_id in cases:
        found = sorted(records_dir.glob(f"p2val-{case_id}.run*.json"))
        if not found:
            missing.append(case_id)
            continue
        for path in found:
            payload = json.loads(path.read_text(encoding="utf-8"))
            result = payload.get("result") or {}
            runs.append({
                "case_id": case_id,
                "regime": (payload.get("validation") or {}).get("regime"),
                "seed": (payload.get("job") or {}).get("seed"),
                "completion": (result.get("termination") or {}).get("completed"),
                "dynamic_state": result.get("dynamic_state"),
                "lindemann": (result.get("host_framework_metrics") or {}).get(
                    "lindemann_provisional"),
                "host_rmsd_final": (result.get("host_framework_metrics") or {}).get(
                    "host_rmsd_final_A"),
                "min_distance": (result.get("host_framework_metrics") or {}).get(
                    "min_distance_traj_A"),
                "coord_change": (result.get("host_framework_metrics") or {}).get(
                    "coord_mean_change"),
                "temp_mean": (result.get("thermal_metrics") or {}).get("temp_mean_K"),
                "temp_std": (result.get("thermal_metrics") or {}).get("temp_std_K"),
                "energy_drift": (result.get("thermal_metrics") or {}).get(
                    "energy_drift_ev_per_ps_per_atom"),
                "reasons": result.get("reasons"),
                "record_file": path.name})
    states: Dict[str, int] = {}
    for r in runs:
        states[str(r["dynamic_state"])] = states.get(str(r["dynamic_state"]), 0) + 1
    from datetime import timezone
    report = {
        "validation_version": VALIDATION_VERSION,
        "git_commit": git_commit,
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
        "environment": environment,
        "gpu_validation_status": environment.get("gpu_validation_status",
                                                 GPU_UNRESOLVED),
        "checkpoint": {k: calc_info.get(k) for k in
                       ("name", "url", "sha256", "mace_version")},
        "protocol": protocol,
        "protocol_hash": __import__(
            "rudeus.mlip.p2", fromlist=["protocol_config_hash"]
        ).protocol_config_hash(protocol),
        "cases_requested": cases,
        "cases_missing": missing,
        "runs": runs,
        "summary": {"n_runs": len(runs),
                    "completed": sum(1 for r in runs if r["completion"]),
                    "by_state": states,
                    "n_missing_cases": len(missing)},
        "scientific_status": (
            "GPU validation unresolved — requires external GPU execution"
            if environment.get("gpu_validation_status") == GPU_UNRESOLVED
            else "GPU runs present — see per-run table; no blanket claim made"),
    }
    if extra:
        report.update(extra)
    return report


def main() -> None:
    """Minimal CLI, portable across local / Kaggle / Colab (no scheduler)."""
    import argparse
    import yaml

    from rudeus.mlip.calibration import make_md_runner
    from rudeus.mlip.relax import (
        default_model_path,
        ensure_checkpoint,
        load_calculator,
    )
    from rudeus.mlip.sharding import write_json_atomic

    parser = argparse.ArgumentParser(description="P2 validation harness.")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--cases", default=",".join(VALIDATION_CASES),
                        help="comma-separated validation case IDs")
    parser.add_argument("--p1-done", default="data/batches/done")
    parser.add_argument("--control-input", default="",
                        help="JSON file with relaxed control structure_dict")
    parser.add_argument("--records-dir", default="",
                        help="where to write per-run records (default: temp)")
    parser.add_argument("--report", default="data/batches/audit/p2_validation.json")
    parser.add_argument("--out", default="data/batches/p2val")
    parser.add_argument("--device", default="auto",
                        help="auto|cpu|cuda (cuda requested but unavailable aborts)")
    parser.add_argument("--worker", default="validator")
    parser.add_argument("--seed-base", type=int, default=20260913)
    parser.add_argument("--run-index-base", type=int, default=0,
                        help="record index offset so repeated invocations "
                             "with different seeds coexist")
    parser.add_argument("--equil-steps", type=int, default=0)
    parser.add_argument("--prod-steps", type=int, default=0)
    parser.add_argument("--sample-interval", type=int, default=0)
    parser.add_argument("--run", action="store_true",
                        help="execute MD (default is dry-run: plan + environment)")
    parser.add_argument("--cpu-8000", action="store_true",
                        help="single production-length CPU attempt (control only)")
    args = parser.parse_args()

    env = detect_environment()
    case_ids = [c for c in args.cases.split(",") if c]
    if args.device == "cuda" and not env["cuda_available"]:
        raise SystemExit("ERROR: --device cuda requested but CUDA unavailable; "
                         "refusing to silently substitute CPU")
    if args.cpu_8000:
        check_cpu8000_eligible(case_ids)

    with open(args.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    protocol = dict(P2_PROTOCOL_DEFAULTS)
    protocol.update(cfg.get("p2", {}))
    if args.cpu_8000:
        protocol.update({"equil_steps": 2000, "production_steps": 8000,
                         "sample_interval_steps": 10})
    if args.equil_steps:
        protocol["equil_steps"] = args.equil_steps
    if args.prod_steps:
        protocol["production_steps"] = args.prod_steps
    if args.sample_interval:
        protocol["sample_interval_steps"] = args.sample_interval

    print(f"environment: device={env['device']} "
          f"cuda={env['cuda_available']} gpu={env['gpu_name']}")
    print(f"cases: {case_ids}")
    if not args.run:
        print("dry-run: resolving cases (no MD executed)")
        for cid in case_ids:
            try:
                info = resolve_case(cid, args.p1_done,
                                    args.control_input or None)
                print(f"  {cid}: OK ({info['source']})")
            except CaseUnavailable as e:
                print(f"  {cid}: OMITTED ({e})")
        return

    mcfg = cfg["mlip"]
    model_path = ensure_checkpoint(mcfg["checkpoint_url"],
                                   default_model_path(),
                                   mcfg["checkpoint_sha256"])
    device = ("cuda" if env["cuda_available"] else "cpu"
              if args.device == "auto" else args.device)
    calc = load_calculator(model_path, device=device,
                           dtype=cfg.get("p2", {}).get("dtype", "float32"))
    calc_info = {"name": mcfg["primary_checkpoint"],
                 "url": mcfg["checkpoint_url"],
                 "sha256": mcfg["checkpoint_sha256"],
                 **collect_backend_versions(),
                 "device": device}
    md_runner = make_md_runner(calc, calc_info, {"session": args.worker})
    records_dir = args.records_dir or args.out
    seeds = {cid: args.seed_base + i for i, cid in enumerate(case_ids)}
    statuses = run_validation(case_ids, md_runner, records_dir,
                              args.p1_done, protocol, seeds,
                              {"session": args.worker},
                              args.control_input or None,
                              run_index_base=args.run_index_base)
    print(json.dumps(statuses, indent=1, default=str))
    try:
        commit = __import__("subprocess").run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True,
            cwd=".").stdout.strip()
    except Exception:
        commit = None
    report = build_validation_report(case_ids, records_dir, protocol,
                                     calc_info, env, commit or None)
    write_json_atomic(args.report, report)
    print(f"report: {args.report} status={report['gpu_validation_status']}")


if __name__ == "__main__":
    main()
