"""P2 calibration / reproducibility harness (decision reproducibility).

Runs the SAME P2 input repeatedly (same structure + protocol + seed, and
optionally varied seeds) and collects raw P2 result records. Objective:
measure decision reproducibility (do repeats agree on PASS/FAIL?) and metric
spread (Lindemann, RMSD, ...) under real backend nondeterminism.

Explicitly NOT required: bitwise-identical trajectories. Seeds govern all RNG
streams and are recorded; MACE-backend nondeterminism amplified by MD chaos
means reruns differ. Resume/versioning depend only on input/config hashes.

Conventions reused (not duplicated): p2_job_seed, protocol_config_hash,
structure_dict_sha256, atomic writes, build_p2_result result schema.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

import numpy as np

from rudeus.mlip.p2 import (
    build_p2_result,
    p2_job_seed,
    protocol_config_hash,
    run_nvt,
)
from rudeus.mlip.sharding import structure_dict_sha256, write_json_atomic

#: Metrics summarized as mean/std/min/max across repeats (when numeric).
CALIBRATION_METRIC_PATHS = (
    ("host_framework_metrics", "host_rmsd_final_A"),
    ("host_framework_metrics", "host_rmsd_max_A"),
    ("host_framework_metrics", "lindemann_provisional"),
    ("host_framework_metrics", "min_distance_traj_A"),
    ("host_framework_metrics", "volume_drift_fraction"),
    ("host_framework_metrics", "coord_mean_change"),
    ("thermal_metrics", "temp_mean_K"),
    ("thermal_metrics", "temp_std_K"),
    ("thermal_metrics", "energy_mean_ev_per_atom"),
    ("thermal_metrics", "energy_drift_ev_per_ps_per_atom"),
    ("mobile_ion_metrics", "mobile_max_displacement_A"),
    ("sampling_metrics", "n_production_frames"),
)


def make_calibration_job(batch_id: str,
                         child_material_id: Optional[str],
                         parent_id: Optional[str],
                         structure_dict: Dict[str, Any],
                         p1_checkpoint: Optional[Dict[str, Any]],
                         protocol: Dict[str, Any],
                         run_index: int,
                         seed_override: Optional[int] = None) -> Dict[str, Any]:
    """One calibration job: full P2 input identity for a single repeat.

    seed defaults to the deterministic p2_job_seed(base, batch_id);
    seed_override enables explicit different-seed experiments (recorded).
    """
    cfg_hash = protocol_config_hash(protocol)
    seed = seed_override if seed_override is not None else p2_job_seed(
        int(protocol.get("base_seed", 550)), batch_id)
    return {
        "batch_id": batch_id,
        "calibration_run_index": run_index,
        "child_material_id": child_material_id,
        "parent_id": parent_id,
        "relaxed_structure_dict": structure_dict,
        "relaxed_structure_sha256": structure_dict_sha256(structure_dict),
        "p1_checkpoint": p1_checkpoint,
        "p2_protocol": protocol,
        "p2_config_hash": cfg_hash,
        "seed": seed,
        "seed_override": seed_override is not None,
    }


def make_md_runner(calc, calc_info: Dict[str, Any],
                   worker_info: Optional[Dict[str, Any]] = None):
    """Real MD runner factory: trajectory + full P2 result (shared by run_p2)."""
    def md_runner(job: Dict[str, Any]) -> Dict[str, Any]:
        record = run_nvt(job["relaxed_structure_dict"], calc,
                         job["p2_protocol"], job["seed"])
        return build_p2_result(job, record, calc_info, worker_info or {})
    return md_runner


def _record_filename(batch_id: str, run_index: int) -> str:
    return f"{batch_id}.run{run_index}.json"


def run_calibration(job: Dict[str, Any],
                    md_runner: Callable[[Dict[str, Any]], Dict[str, Any]],
                    out_dir: Union[str, Path],
                    worker_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Execute one calibration repeat (or skip a verified identical record).

    Resume: an existing file is reused only if its embedded job matches on
    batch_id, run_index, seed, input structure hash, and config hash;
    otherwise it is recomputed (stale rewrite). Returns counts + path.
    """
    out_dir = Path(out_dir)
    target = out_dir / _record_filename(job["batch_id"],
                                        job["calibration_run_index"])
    if target.exists():
        try:
            prior = json.loads(target.read_text(encoding="utf-8"))
            pj = prior.get("job") or {}
            if (pj.get("batch_id") == job["batch_id"]
                    and pj.get("calibration_run_index") == job["calibration_run_index"]
                    and pj.get("seed") == job["seed"]
                    and pj.get("relaxed_structure_sha256") == job["relaxed_structure_sha256"]
                    and pj.get("p2_config_hash") == job["p2_config_hash"]
                    and isinstance(prior.get("result"), dict)):
                return {"status": "skipped_done", "path": str(target)}
        except Exception:
            pass  # corrupt/stale record: recompute below
        status = "stale_recomputed"
    else:
        status = "processed"
    result = md_runner(job)
    payload = {"batch_id": job["batch_id"],
               "calibration_run_index": job["calibration_run_index"],
               "job": job,
               "result": result,
               "worker": worker_info or {}}
    write_json_atomic(target, payload)
    return {"status": status, "path": str(target)}


def load_calibration_records(out_dir: Union[str, Path],
                             batch_id: str) -> List[Dict[str, Any]]:
    """Load verified records for one batch (input-identity checked)."""
    out_dir = Path(out_dir)
    records = []
    for path in sorted(out_dir.glob(f"{batch_id}.run*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue  # corrupt file: never consumed
        job, result = payload.get("job") or {}, payload.get("result")
        if not isinstance(result, dict):
            continue  # malformed output: never trusted
        # cross-consumption guard: embedded input hash must match the job input
        try:
            expect = structure_dict_sha256(job["relaxed_structure_dict"])
        except Exception:
            continue
        if job.get("relaxed_structure_sha256") != expect:
            continue
        records.append(payload)
    return records


def summarize_calibration(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Distribution summary over repeats: metric spreads + state histogram.

    Descriptive only: no thresholds, no scores, no verdict changes.
    """
    states: Dict[str, int] = {}
    terms: Dict[str, int] = {}
    series: Dict[str, List[float]] = {}
    for payload in records:
        result = payload.get("result") or {}
        states[str(result.get("dynamic_state", "UNKNOWN"))] = \
            states.get(str(result.get("dynamic_state", "UNKNOWN")), 0) + 1
        term = str(((result.get("termination") or {}).get("note") or "completed"))
        terms[term] = terms.get(term, 0) + 1
        for section, key in CALIBRATION_METRIC_PATHS:
            val = (result.get(section) or {}).get(key)
            if isinstance(val, bool):
                continue
            if isinstance(val, (int, float)) and np.isfinite(val):
                series.setdefault(f"{section}.{key}", []).append(float(val))
    spread = {}
    for name, vals in series.items():
        arr = np.array(vals, dtype=float)
        spread[name] = {"n": len(vals), "mean": float(arr.mean()),
                        "std": float(arr.std()),
                        "min": float(arr.min()), "max": float(arr.max())}
    state_names = sorted(states)
    return {"n_records": len(records),
            "dynamic_states": states,
            "terminations": terms,
            "metric_spread": spread,
            "decision_reproducibility": (
                "unanimous" if len(state_names) == 1 else "split"),
            "states_observed": state_names}
