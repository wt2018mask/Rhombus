"""Tests for P2 calibration harness (no MACE/CUDA; stub runners only)."""

import json

import pytest

from rudeus.mlip.calibration import (
    load_calibration_records,
    make_calibration_job,
    run_calibration,
    summarize_calibration,
)
from rudeus.mlip.p2 import P2_PROTOCOL_DEFAULTS, protocol_config_hash
from rudeus.mlip.sharding import structure_dict_sha256


def _protocol(**over):
    p = dict(P2_PROTOCOL_DEFAULTS)
    p.update(over)
    return p


def _struct():
    from pymatgen.core import Lattice, Structure
    return Structure(Lattice.cubic(4.0), ["Li", "Cl"],
                     [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]]).as_dict()


def _stub_result(job, lind=0.10, state="PASS"):
    return {
        "candidate_material_id": job.get("child_material_id"),
        "batch_id": job["batch_id"],
        "p2_input_relaxed_sha256": job["relaxed_structure_sha256"],
        "p2_config_hash": job["p2_config_hash"],
        "seed": job["seed"],
        "dynamic_state": state,
        "host_framework_metrics": {
            "host_rmsd_final_A": 0.20, "host_rmsd_max_A": 0.25,
            "lindemann_provisional": lind, "min_distance_traj_A": 2.5,
            "volume_drift_fraction": 0.001, "coord_mean_change": 0.0},
        "thermal_metrics": {"temp_mean_K": 550.0, "temp_std_K": 20.0,
                            "energy_mean_ev_per_atom": -4.0,
                            "energy_drift_ev_per_ps_per_atom": 0.001},
        "mobile_ion_metrics": {"mobile_max_displacement_A": 0.5},
        "sampling_metrics": {"n_production_frames": 60},
        "termination": {"completed": True, "note": None},
        "reasons": ["stub"],
        "provenance": {},
        "evidence_events": [],
    }


def test_repeated_records_preserve_provenance(tmp_path):
    """Same job rerun -> identical record; seed override recorded."""
    proto = _protocol()
    struct = _struct()
    job = make_calibration_job("ab12cd34", "g1-x", "obelix:x", struct,
                               {"checkpoint": "m"}, proto, run_index=0)
    from rudeus.mlip.p2 import p2_job_seed
    assert job["seed"] == p2_job_seed(550, "ab12cd34")
    assert job["p2_config_hash"] == protocol_config_hash(proto)
    assert job["relaxed_structure_sha256"] == structure_dict_sha256(struct)
    assert job["seed_override"] is False

    other = make_calibration_job("ab12cd34", "g1-x", "obelix:x", struct,
                                 {"checkpoint": "m"}, proto, run_index=1,
                                 seed_override=999)
    assert other["seed"] == 999 and other["seed_override"] is True
    assert other["p2_config_hash"] == job["p2_config_hash"]

    out = tmp_path / "cal"
    r1 = run_calibration(job, lambda j: _stub_result(j), out)
    r2 = run_calibration(job, lambda j: _stub_result(j), out)
    assert r1["status"] == "processed" and r2["status"] == "skipped_done"
    recs = load_calibration_records(out, "ab12cd34")
    assert len(recs) == 1
    res = recs[0]["result"]
    for key in ("candidate_material_id", "batch_id", "p2_input_relaxed_sha256",
                "p2_config_hash", "seed", "dynamic_state",
                "host_framework_metrics", "thermal_metrics",
                "mobile_ion_metrics", "sampling_metrics", "termination"):
        assert key in res, key


def test_summary_reports_split_not_score(tmp_path):
    """Mixed states -> split histogram + metric spreads, no verdict change."""
    proto = _protocol()
    struct = _struct()
    out = tmp_path / "cal"
    linds = [0.10, 0.12, 0.35]
    states = ["PASS", "PASS", "FAIL"]
    for k, (lind, state) in enumerate(zip(linds, states)):
        job = make_calibration_job("ab12cd34", "g1-x", "obelix:x", struct,
                                   None, proto, run_index=k)
        run_calibration(job, lambda j, l=lind, s=state: _stub_result(j, l, s),
                        out)
    summary = summarize_calibration(load_calibration_records(out, "ab12cd34"))
    assert summary["n_records"] == 3
    assert summary["dynamic_states"] == {"PASS": 2, "FAIL": 1}
    assert summary["decision_reproducibility"] == "split"
    spread = summary["metric_spread"][
        "host_framework_metrics.lindemann_provisional"]
    assert spread["min"] == pytest.approx(0.10)
    assert spread["max"] == pytest.approx(0.35)
    assert spread["n"] == 3


def test_loader_rejects_cross_consumption(tmp_path):
    """Record for another structure/config is never loaded as this batch."""
    proto = _protocol()
    struct = _struct()
    out = tmp_path / "cal"
    job = make_calibration_job("ab12cd34", "g1-x", "obelix:x", struct,
                               None, proto, run_index=0)
    run_calibration(job, lambda j: _stub_result(j), out)
    # tamper: rewrite the file with a foreign input hash
    path = out / "ab12cd34.run0.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["job"]["relaxed_structure_sha256"] = "0" * 64
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert load_calibration_records(out, "ab12cd34") == []
    # corrupt file is skipped, never trusted
    path.write_text("{broken", encoding="utf-8")
    assert load_calibration_records(out, "ab12cd34") == []


def test_calibration_records_carry_no_transport_claims(tmp_path):
    """Results flowing through calibration never gain diffusion language."""
    proto = _protocol()
    struct = _struct()
    out = tmp_path / "cal"
    job = make_calibration_job("ab12cd34", "g1-x", "obelix:x", struct,
                               None, proto, run_index=0)
    run_calibration(job, lambda j: _stub_result(j, state="FAIL"), out)
    flat = json.dumps(load_calibration_records(out, "ab12cd34")).lower()
    assert "diffus" not in flat and "transport" not in flat
