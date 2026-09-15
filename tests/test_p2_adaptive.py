"""Tests for the adaptive P2 screening trajectory (no MACE/CUDA).

Policy under test (PROVISIONAL screening-efficiency choice, not a transport
claim): 2000 equilibration steps, then cumulative production tiers of
1000 / 3000 / 8000 steps on ONE continuous trajectory. Clear existing
PASS/FAIL evidence stops the run; borderline/insufficient evidence extends
it. All scientific gates are the pre-existing evaluate_p2 gates, unchanged.
"""

import json

import numpy as np
import pytest

from rudeus.mlip.calibration import compare_tier_durations, make_md_runner
from rudeus.mlip.p2 import (
    P2_PROTOCOL_DEFAULTS,
    P2_PRODUCTION_TIERS_PROVISIONAL,
    build_p2_result,
    effective_production_tiers,
    evaluate_p2,
    evaluate_p2_tier,
    infer_early_stop_reason,
    protocol_config_hash,
    run_nvt_adaptive,
    run_p2_batches,
    tier_stop_decision,
)
from rudeus.schema import DynamicState

CALC_INFO = {"checkpoint_name": "mace_mp:medium-mpa-0",
             "url": "pinned", "sha256": "pinned-sha",
             "device": "cpu", "dtype": "float32"}


def _protocol(**over):
    p = dict(P2_PROTOCOL_DEFAULTS)
    p.update(over)
    return p


def _base_cell(n_host=16, n_li=4, box=10.0):
    rng = np.random.default_rng(0)
    host = rng.uniform(0, box, size=(n_host, 3))
    li = rng.uniform(0, box, size=(n_li, 3))
    return np.vstack([host, li]), ["O"] * n_host + ["Li"] * n_li, \
        np.eye(3) * box


def _record(pos0, species, cell, n_frames=120, host_sig=0.05, li_sig=0.1,
            contract=None, nan_at=None, completed=True, note=None):
    rng = np.random.default_rng(1)
    frames = []
    n = len(species)
    host_idx = [i for i, s in enumerate(species) if s != "Li"]
    for t in range(n_frames):
        p = pos0.copy()
        p[host_idx] += rng.normal(0, host_sig, size=(len(host_idx), 3))
        li_idx = [i for i, s in enumerate(species) if s == "Li"]
        if li_idx:
            p[li_idx] += rng.normal(0, li_sig, size=(len(li_idx), 3))
        if contract is not None:
            p = pos0.mean(axis=0) + (p - pos0.mean(axis=0)) * (1 - contract * t)
        if nan_at is not None and t == nan_at:
            p[0, 0] = np.nan
        frames.append({"phase": "production", "positions": p,
                       "temperature_K": 550.0 + rng.normal(0, 12.0),
                       "energy_ev": -100.0 + rng.normal(0, 0.01),
                       "volume_A3": 1000.0,
                       "pressure_GPa": 0.1,
                       "max_force_ev_A": 0.05,
                       "finite": bool(np.all(np.isfinite(p)))})
    return {"species": species, "cell": cell, "frames": frames,
            "completed": completed, "termination_note": note,
            "timestep_fs": 1.0, "sample_interval_steps": 10,
            "equil_steps": 2000, "production_steps": n_frames * 10,
            "thermostat": "langevin", "friction_fs_inv": 0.02, "seed": 7}


def _dense_grid(n_per_dim=3, spacing=2.8, n_li=4):
    grid = np.array([[[i, j, k] for k in range(n_per_dim)]
                     for j in range(n_per_dim)
                     for i in range(n_per_dim)],
                    dtype=float).reshape(-1, 3) * spacing
    off = (np.array([[i, j, k] for i in range(n_per_dim)
                     for j in range(n_per_dim)
                     for k in range(n_per_dim)],
                    dtype=float).reshape(-1, 3) + 0.5) * spacing
    box = n_per_dim * spacing
    li = np.mod(off[:n_li], box)
    pos = np.vstack([grid, li])
    return pos, ["O"] * len(grid) + ["Li"] * n_li, np.eye(3) * box


def _job(batch_id="aa00", proto=None):
    from rudeus.mlip.sharding import structure_dict_sha256
    from pymatgen.core import Lattice, Structure
    s = Structure(Lattice.cubic(4.0), ["Li", "Cl"],
                  [[0, 0, 0], [0.5, 0.5, 0.5]]).as_dict()
    proto = proto if proto is not None else _protocol()
    return {"batch_id": batch_id, "child_material_id": "g1-test",
            "parent_id": "obelix:test",
            "relaxed_structure_dict": s,
            "relaxed_structure_sha256": structure_dict_sha256(s),
            "p1_checkpoint": None, "p1_worker": None,
            "p2_protocol": proto,
            "p2_config_hash": protocol_config_hash(proto),
            "seed": 11}


def _zero_calc():
    from ase.calculators.calculator import Calculator

    class ZeroCalc(Calculator):
        implemented_properties = ["energy", "energies", "forces",
                                  "free_energy"]

        def calculate(self, atoms=None, properties=None,
                      system_changes=None):
            super().calculate(atoms, properties, system_changes)
            n = len(atoms)
            self.results = {"energy": 0.0, "free_energy": 0.0,
                            "energies": np.zeros(n),
                            "forces": np.zeros((n, 3))}

    return ZeroCalc()


def _tiny_struct():
    from pymatgen.core import Lattice, Structure
    return Structure(Lattice.cubic(4.0), ["Li", "Cl"],
                     [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]])


def _stub_eval(script):
    """evaluate_fn stub playing a scripted per-tier verdict sequence."""
    calls = []

    def fn(record, protocol):
        n_prod = sum(1 for f in record["frames"]
                     if f.get("phase") == "production")
        calls.append(n_prod)
        state = script[min(len(calls) - 1, len(script) - 1)]
        metrics = {"n_production_frames": n_prod, "n_usable_frames": n_prod}
        return state, metrics, [f"stub-{state.value}"]
    fn.calls = calls
    return fn


# --- Protocol ------------------------------------------------------------

def test_tier_schedule_is_exactly_1000_3000_8000():
    assert list(P2_PRODUCTION_TIERS_PROVISIONAL) == [1000, 3000, 8000]
    assert effective_production_tiers(_protocol()) == [1000, 3000, 8000]
    assert _protocol()["equil_steps"] == 2000
    assert _protocol()["production_steps"] == 8000  # final-tier limit


def test_protocol_hash_changes_with_trajectory_policy():
    new_hash = protocol_config_hash(_protocol())
    legacy = {k: v for k, v in _protocol().items()
              if k not in ("p2_protocol_version", "trajectory_policy",
                           "production_tier_schedule_provisional")}
    assert protocol_config_hash(legacy) != new_hash  # old fixed hash retired
    assert protocol_config_hash(
        _protocol(production_tier_schedule_provisional=[1000, 8000])) != new_hash
    assert protocol_config_hash(_protocol(temperature_K=600.0)) != new_hash
    assert protocol_config_hash(_protocol()) == new_hash  # deterministic


def test_pilot_override_collapses_to_single_final_evaluation():
    assert effective_production_tiers(_protocol(production_steps=600)) == [600]
    assert effective_production_tiers(
        _protocol(production_steps=2000)) == [1000, 2000]


def test_tier_stop_decision_never_forces_borderline():
    assert tier_stop_decision(DynamicState.PASS, False) is True
    assert tier_stop_decision(DynamicState.FAIL, False) is True
    assert tier_stop_decision(DynamicState.INDETERMINATE, False) is False
    assert tier_stop_decision(DynamicState.INDETERMINATE, True) is True


# --- Early failure / early PASS / borderline via the MD loop --------------

def test_early_failure_stops_at_first_tier():
    stub = _stub_eval([DynamicState.FAIL])
    rec = run_nvt_adaptive(_tiny_struct().as_dict(), _zero_calc(),
                           _protocol(equil_steps=200,
                                     production_tier_schedule_provisional=[
                                         100, 300, 800],
                                     production_steps=800),
                           seed=7, batch_id="fail-early",
                           evaluate_fn=stub)
    assert rec["adaptive"]["production_stage_reached"] == 100
    assert rec["adaptive"]["production_steps_completed"] == 100
    assert rec["adaptive"]["early_stop_reason"] == "clear_failure"
    assert len(stub.calls) == 1  # no later tiers executed
    assert len(rec["adaptive"]["tier_evaluations"]) == 1


def test_early_pass_stops_and_records_tier():
    stub = _stub_eval([DynamicState.INDETERMINATE, DynamicState.PASS])
    rec = run_nvt_adaptive(_tiny_struct().as_dict(), _zero_calc(),
                           _protocol(equil_steps=200,
                                     production_tier_schedule_provisional=[
                                         100, 300, 800],
                                     production_steps=800),
                           seed=7, batch_id="pass-tier2",
                           evaluate_fn=stub)
    assert rec["adaptive"]["production_stage_reached"] == 300
    assert rec["adaptive"]["early_stop_reason"] == "clear_pass"
    assert len(stub.calls) == 2
    assert rec["completed"] is True  # valid final result, skippable


def test_borderline_continues_without_premature_pass():
    stub = _stub_eval([DynamicState.INDETERMINATE,
                       DynamicState.INDETERMINATE, DynamicState.PASS])
    rec = run_nvt_adaptive(_tiny_struct().as_dict(), _zero_calc(),
                           _protocol(equil_steps=200,
                                     production_tier_schedule_provisional=[
                                         100, 300, 800],
                                     production_steps=800),
                           seed=7, batch_id="borderline",
                           evaluate_fn=stub)
    assert [t["tier_production_steps"]
            for t in rec["adaptive"]["tier_evaluations"]] == [100, 300, 800]
    assert rec["adaptive"]["production_stage_reached"] == 800
    assert rec["adaptive"]["early_stop_reason"] == "clear_pass"
    assert len(stub.calls) == 3


def test_full_extension_runs_continuously_without_reequilibration():
    """100 -> 300 -> 800 costs equil + 800 MD steps, not 3x equil + 800."""
    seen = []
    stub = _stub_eval([DynamicState.INDETERMINATE,
                       DynamicState.INDETERMINATE,
                       DynamicState.INDETERMINATE])
    proto = _protocol(equil_steps=200,
                      production_tier_schedule_provisional=[100, 300, 800],
                      production_steps=800)
    rec = run_nvt_adaptive(_tiny_struct().as_dict(), _zero_calc(), proto,
                           seed=7, batch_id="continuous",
                           step_hook=lambda n, phase: seen.append(phase),
                           evaluate_fn=stub)
    assert len(stub.calls) == 3
    # ASE fires the step observer once at attach (phase equil) plus once per
    # MD step: 1 + 200 equil + 800 production. A restart-per-tier
    # implementation would re-run equilibration (3 x 201 equil-phase calls).
    assert len(seen) == 1 + 200 + 800
    assert seen.count("equil") == 201  # equilibration ran exactly once
    assert seen.count("production") == 800
    assert rec["adaptive"]["production_stage_limit"] == 800
    assert rec["adaptive"]["early_stop_reason"] == "completed_final_tier"
    # production frames accumulate across tiers on the same trajectory
    counts = stub.calls
    assert counts[0] < counts[1] < counts[2]


def test_default_tiers_stop_marks_valid_completed_result():
    """A stub PASS at the default 1000-step tier is completed, not partial."""
    stub = _stub_eval([DynamicState.PASS])
    rec = run_nvt_adaptive(_tiny_struct().as_dict(), _zero_calc(),
                           _protocol(equil_steps=200), seed=7,
                           batch_id="default-tier1", evaluate_fn=stub)
    assert rec["adaptive"]["production_stage_reached"] == 1000
    assert rec["adaptive"]["production_stage_limit"] == 8000
    assert rec["completed"] is True
    assert rec["termination_note"] is None


# --- Real-gate integration (existing machinery, no stubs) ------------------

def test_real_collapse_fails_at_first_tier_with_existing_gate():
    pos0, species, cell = _base_cell()
    rec = _record(pos0, species, cell, n_frames=100, contract=0.004)
    state, _, reasons = evaluate_p2_tier(rec, _protocol())
    assert state == DynamicState.FAIL, reasons
    assert tier_stop_decision(state, False) is True


def test_real_stable_passes_tier_view():
    pos0, species, cell = _base_cell()
    rec = _record(pos0, species, cell, n_frames=100)
    state, _, reasons = evaluate_p2_tier(rec, _protocol())
    assert state == DynamicState.PASS, reasons


def test_marginal_lindemann_still_held_indeterminate_at_tier():
    """Uncorroborated marginal Lindemann is INDETERMINATE -> extends."""
    pos0, species, cell = _dense_grid()
    rec = _record(pos0, species, cell, n_frames=100,
                  host_sig=0.24, li_sig=0.1)
    state, metrics, reasons = evaluate_p2_tier(rec, _protocol())
    assert 0.20 < metrics["lindemann_provisional"] < 0.30, metrics
    assert state == DynamicState.INDETERMINATE
    assert any("marginal-lindemann-uncorroborated" in r for r in reasons)
    assert tier_stop_decision(state, False) is False


def test_thresholds_unchanged():
    p = _protocol()
    assert p["lindemann_fail_provisional"] == 0.20
    assert p["host_rmsd_fail_A_provisional"] == 1.0
    assert p["min_distance_fail_A_provisional"] == 0.8
    assert p["coord_mean_change_fail_provisional"] == 2.0
    assert p["temp_mean_tol_K_provisional"] == 150.0
    assert p["temp_std_fail_K_provisional"] == 150.0
    assert p["energy_drift_fail_ev_per_ps_per_atom_provisional"] == 0.05
    assert p["explosion_abort_A_provisional"] == 3.0
    assert p["temperature_K"] == 550.0
    assert p["timestep_fs"] == 1.0
    assert p["thermostat"] == "langevin"
    assert p["friction_fs_inv_provisional"] == 0.02
    assert p["fix_center_of_mass"] is True


# --- Result provenance -----------------------------------------------------

def test_result_carries_adaptive_provenance():
    pos0, species, cell = _base_cell()
    job = _job()
    record = _record(pos0, species, cell, n_frames=100)
    record["adaptive"] = {
        "trajectory_policy": "adaptive-1000-3000-8000-v1-provisional",
        "p2_protocol_version": "p2-adaptive-v1-provisional",
        "tiers": [1000, 3000, 8000],
        "tier_evaluations": [{"tier_production_steps": 1000,
                              "dynamic_state": "PASS", "reasons": []}],
        "production_steps_completed": 1000,
        "production_stage_reached": 1000,
        "production_stage_limit": 8000,
        "early_stop_reason": "clear_pass",
    }
    result = build_p2_result(job, record, CALC_INFO, {"session": "test"})
    assert result["dynamic_state"] == "PASS"
    assert result["production_steps_completed"] == 1000
    assert result["production_stage_reached"] == 1000
    assert result["production_stage_limit"] == 8000
    assert result["early_stop_reason"] == "clear_pass"
    assert result["equilibration_steps"] == 2000
    assert result["trajectory_policy"] == \
        "adaptive-1000-3000-8000-v1-provisional"
    assert result["p2_protocol_version"] == "p2-adaptive-v1-provisional"
    cond = result["evidence_events"][0]["conditions"]
    assert cond["production_steps_completed"] == 1000
    assert cond["early_stop_reason"] == "clear_pass"


def test_legacy_fixed_record_stays_backward_readable():
    pos0, species, cell = _base_cell()
    result = build_p2_result(_job(), _record(pos0, species, cell), CALC_INFO,
                             {"session": "test"})
    assert result["dynamic_state"] == "PASS"
    assert result["production_stage_limit"] == 8000
    # legacy fixed path: same additive keys, reason follows the verdict
    assert result["early_stop_reason"] == "clear_pass"
    assert "transport_state" not in result
    blob = json.dumps(result).lower()
    assert "diffus" not in blob and "transport" not in blob


def test_infer_early_stop_reason_vocabulary():
    rec = {"completed": True, "termination_note": None}
    assert infer_early_stop_reason(DynamicState.PASS, ["ok"], rec, None) \
        == "clear_pass"
    assert infer_early_stop_reason(DynamicState.FAIL, ["instability: x"], rec,
                                   None) == "clear_failure"
    assert infer_early_stop_reason(
        DynamicState.FAIL, ["numerical-failure: 2 non-finite frames"], rec,
        None) == "numerical_failure"
    assert infer_early_stop_reason(
        DynamicState.FAIL, ["explosive"], {"completed": False,
                                           "termination_note":
                                               "explosive-step"},
        None) == "explosive_termination"
    assert infer_early_stop_reason(DynamicState.INDETERMINATE, ["marginal"],
                                   rec, None) == "completed_final_tier"
    assert infer_early_stop_reason(DynamicState.INDETERMINATE, ["x"],
                                   {"completed": False,
                                    "termination_note": "sampling-error: X"},
                                   None) == "numerical_failure"


# --- Mid-extension abort accounting -------------------------------------------

def test_mid_extension_abort_reports_truthful_partial_steps():
    """Abort during tier-2 extension: partial step count, last evaluated
    tier retained, record stays incomplete (never a false PASS)."""
    from rudeus.mlip.p2 import DiagnosticStall

    def run_once():
        stub = _stub_eval([DynamicState.INDETERMINATE])

        def hook(n, phase):
            if n > 200 + 150:
                raise DiagnosticStall("synthetic stall")

        return run_nvt_adaptive(
            _tiny_struct().as_dict(), _zero_calc(),
            _protocol(equil_steps=200,
                      production_tier_schedule_provisional=[100, 300, 800],
                      production_steps=800),
            seed=7, batch_id="abort-mid", step_hook=hook,
            evaluate_fn=stub)

    rec = run_once()
    assert len(rec["adaptive"]["tier_evaluations"]) == 1  # only tier 1 judged
    assert rec["adaptive"]["production_stage_reached"] == 100
    assert rec["adaptive"]["production_steps_completed"] == 150
    assert rec["completed"] is False
    assert "diagnostic-stall" in (rec["termination_note"] or "")
    assert rec["adaptive"]["early_stop_reason"] == "insufficient_evidence"
    # deterministic rerun: identical partial accounting
    rec2 = run_once()
    assert rec2["adaptive"]["production_steps_completed"] == \
        rec["adaptive"]["production_steps_completed"]


# --- Explosive termination through the adaptive path -----------------------

def _explosive_record(n_prod_frames=40):
    pos0, species, cell = _base_cell()
    rng = np.random.default_rng(1)
    frames = []
    for _ in range(n_prod_frames):
        p = pos0 + rng.normal(0, 0.05, size=pos0.shape)
        frames.append({"phase": "production", "positions": p,
                       "temperature_K": 550.0, "energy_ev": -100.0,
                       "volume_A3": 1000.0, "pressure_GPa": 0.1,
                       "max_force_ev_A": 0.05, "finite": True,
                       "step_jump_A": 0.01})
    return {"species": species, "cell": cell, "frames": frames,
            "completed": False, "termination_note": "explosive-step",
            "wall_clock_s": 7.2,
            "timestep_fs": 1.0, "sample_interval_steps": 10,
            "equil_steps": 2000, "production_steps": 8000,
            "thermostat": "langevin", "friction_fs_inv": 0.02, "seed": 11,
            "adaptive": {"trajectory_policy":
                         "adaptive-1000-3000-8000-v1-provisional",
                         "tiers": [1000, 3000, 8000],
                         "tier_evaluations": [],
                         "production_steps_completed": 400,
                         "production_stage_reached": 0,
                         "production_stage_limit": 8000,
                         "early_stop_reason": "explosive_termination"}}


def _p1_done_record(p1done_dir, batch_id):
    from rudeus.mlip.sharding import structure_dict_sha256
    from pymatgen.core import Lattice, Structure
    s = Structure(Lattice.cubic(4.0), ["Li", "Cl"],
                  [[0, 0, 0], [0.5, 0.5, 0.5]]).as_dict()
    rec = {"batch_id": batch_id, "child_material_id": "g1-test",
           "parent_id": "obelix:test",
           "result": {"p1_verdict": "KEEP_FOR_P2",
                      "relaxed_structure_dict": s,
                      "relaxed_structure_sha256":
                          structure_dict_sha256(s)}}
    (p1done_dir / f"{batch_id}.json").write_text(json.dumps(rec),
                                                 encoding="utf-8")


def test_explosive_adaptive_result_is_structured_fail(tmp_path):
    """Explosive abort: structured FAIL, atomic write, shard continues."""
    p1done, p2out = tmp_path / "p1done", tmp_path / "p2"
    p1done.mkdir()

    def md_runner(job):
        if job["batch_id"] == "aa00":
            return build_p2_result(job, _explosive_record(), CALC_INFO, {})
        pos0, species, cell = _base_cell()
        return build_p2_result(job, _record(pos0, species, cell), CALC_INFO,
                               {})

    _p1_done_record(p1done, "aa00")
    _p1_done_record(p1done, "bb01")
    summary = run_p2_batches(p1done, p2out, 0, 1, md_runner, _protocol())
    assert summary["processed"] == 2 and summary["errored"] == 0
    first = json.loads((p2out / "aa00.json").read_text(encoding="utf-8"))
    assert first["result"]["dynamic_state"] == "FAIL"
    assert first["result"]["early_stop_reason"] == "explosive_termination"
    assert first["result"]["error_info"] is None
    assert list(p2out.glob("*.tmp")) == []
    second = json.loads((p2out / "bb01.json").read_text(encoding="utf-8"))
    assert second["result"]["dynamic_state"] == "PASS"


# --- Resume -----------------------------------------------------------------

def test_resume_skips_valid_adaptive_result_and_recomputes_stale(tmp_path):
    from rudeus.mlip.sharding import structure_dict_sha256
    from pymatgen.core import Lattice, Structure

    p1done, p2out = tmp_path / "p1done", tmp_path / "p2"
    p1done.mkdir()
    _p1_done_record(p1done, "aa00")
    calls = []

    def md_runner(job):
        calls.append(job["batch_id"])
        pos0, species, cell = _base_cell()
        record = _record(pos0, species, cell, n_frames=100)
        record["adaptive"] = {
            "production_steps_completed": 1000,
            "production_stage_reached": 1000,
            "production_stage_limit": 8000,
            "early_stop_reason": "clear_pass",
            "tier_evaluations": []}
        return build_p2_result(job, record, CALC_INFO, {})

    proto = _protocol()
    assert run_p2_batches(p1done, p2out, 0, 1, md_runner, proto)[
        "processed"] == 1
    again = run_p2_batches(p1done, p2out, 0, 1, md_runner, proto)
    assert again["skipped_done"] == 1 and again["processed"] == 0
    assert calls == ["aa00"]  # valid adaptive result not recomputed

    # legacy fixed-hash output is stale under the adaptive protocol hash
    tampered = json.loads((p2out / "aa00.json").read_text(encoding="utf-8"))
    legacy = {k: v for k, v in proto.items()
              if k not in ("p2_protocol_version", "trajectory_policy",
                           "production_tier_schedule_provisional")}
    tampered["result"]["p2_config_hash"] = protocol_config_hash(legacy)
    (p2out / "aa00.json").write_text(json.dumps(tampered), encoding="utf-8")
    fix = run_p2_batches(p1done, p2out, 0, 1, md_runner, proto)
    assert fix["stale_recomputed"] == 1 and calls == ["aa00", "aa00"]
    # rerun is deterministic: same tier, same verdict, same hash
    before = json.loads((p2out / "aa00.json").read_text(encoding="utf-8"))
    run_p2_batches(p1done, p2out, 0, 1, md_runner, proto)
    after = json.loads((p2out / "aa00.json").read_text(encoding="utf-8"))
    assert before["result"]["production_stage_reached"] == \
        after["result"]["production_stage_reached"] == 1000
    assert before["result"]["p2_config_hash"] == protocol_config_hash(proto)


def test_partial_execution_never_counts_as_completed(tmp_path):
    """No output file -> processed, never skipped as done."""
    p1done, p2out = tmp_path / "p1done", tmp_path / "p2"
    p1done.mkdir()
    _p1_done_record(p1done, "aa00")

    def md_runner(job):
        pos0, species, cell = _base_cell()
        return build_p2_result(job, _record(pos0, species, cell), CALC_INFO,
                               {})

    s = run_p2_batches(p1done, p2out, 0, 1, md_runner, _protocol())
    assert s["processed"] == 1 and s["skipped_done"] == 0


# --- Evidence semantics ------------------------------------------------------

def test_shortened_p2_cannot_claim_transport():
    pos0, species, cell = _base_cell(n_host=16, n_li=8)
    for n_frames in (100, 300, 800):
        result = build_p2_result(
            _job(), _record(pos0, species, cell, n_frames=n_frames,
                            li_sig=2.5),
            CALC_INFO, {})
        assert "transport_state" not in result
        assert result["dynamic_state"] in ("PASS", "FAIL", "INDETERMINATE")
        blob = json.dumps(result).lower()
        assert "diffus" not in blob and "transport" not in blob


def test_p2_sources_still_carry_no_transport_machinery():
    from pathlib import Path
    for name in ("rudeus/mlip/p2.py", "rudeus/mlip/run_p2.py",
                 "rudeus/mlip/calibration.py"):
        src = Path(name).read_text(encoding="utf-8")
        assert "TransportState" not in src, name
        assert "validate_diffusive" not in src, name
        assert "is_diffusive" not in src, name
        # no transport verdict is ever assigned (docstrings may name the
        # states only to disclaim them; results carry no such key)
        assert "transport_state =" not in src, name
        assert '"transport_state"' not in src and \
            "'transport_state'" not in src, name


# --- Heartbeat ---------------------------------------------------------------

def test_adaptive_heartbeat_every_100_steps_with_stage_lines(capsys):
    stub = _stub_eval([DynamicState.INDETERMINATE, DynamicState.PASS])
    run_nvt_adaptive(_tiny_struct().as_dict(), _zero_calc(),
                     _protocol(equil_steps=200,
                               production_tier_schedule_provisional=[
                                   100, 300, 800],
                               production_steps=800),
                     seed=7, batch_id="hb-adaptive", evaluate_fn=stub)
    out = capsys.readouterr().out
    assert "[p2] start batch=hb-adaptive natoms=2 equil=200 prod=800" in out
    assert "[p2] progress batch=hb-adaptive step=100/1000" in out
    assert "[p2] progress batch=hb-adaptive step=500/1000" in out
    assert "[p2] stage=1 batch=hb-adaptive production=100/800 " \
        "result=INDETERMINATE" in out
    assert "[p2] stage=2 batch=hb-adaptive start production=100/300" in out
    assert "result=PASS" in out


# --- Calibration harness -----------------------------------------------------

def test_compare_tier_durations_stable_early_stop():
    pos0, species, cell = _base_cell()
    full = _record(pos0, species, cell, n_frames=800)
    report = compare_tier_durations(full, _protocol())
    assert [t["tier_production_steps"] for t in report["tiers"]] == \
        [1000, 3000, 8000]
    assert report["final_state"] == "PASS"
    assert report["early_stop_tier_steps"] == 1000
    assert report["compute_fraction_spent"] == pytest.approx(1000 / 8000)
    assert report["early_agreement"] == {1000: True, 3000: True}
    assert report["false_early_pass_risk"] is False
    assert report["false_early_fail_risk"] is False


def test_compare_tier_durations_collapse_no_false_pass():
    pos0, species, cell = _base_cell()
    full = _record(pos0, species, cell, n_frames=800, contract=0.004)
    report = compare_tier_durations(full, _protocol())
    assert report["final_state"] == "FAIL"
    assert report["tiers"][0]["dynamic_state"] == "FAIL"
    assert report["false_early_pass_risk"] is False


def test_compare_tier_durations_borderline_extends():
    pos0, species, cell = _dense_grid()
    full = _record(pos0, species, cell, n_frames=800,
                   host_sig=0.24, li_sig=0.1)
    report = compare_tier_durations(full, _protocol())
    assert report["tiers"][0]["dynamic_state"] == "INDETERMINATE"
    assert report["early_stop_tier_steps"] >= 3000
    blob = json.dumps(report).lower()
    assert "diffus" not in blob and "transport" not in blob


def test_make_md_runner_uses_adaptive_path(tmp_path):
    """Production md_runner stops at tier 1 for a stub PASS verdict."""
    from rudeus.mlip.p2 import run_nvt_adaptive as _real

    seen = {}

    class ShortCircuit(Exception):
        pass

    import rudeus.mlip.calibration as cal

    def fake_adaptive(structure_dict, calc, protocol, seed, batch_id=None):
        seen["tiers"] = protocol.get(
            "production_tier_schedule_provisional")
        seen["batch"] = batch_id
        pos0, species, cell = _base_cell()
        return _record(pos0, species, cell, n_frames=100)

    orig = cal.run_nvt_adaptive
    cal.run_nvt_adaptive = fake_adaptive
    try:
        runner = make_md_runner(object(), CALC_INFO, {"session": "t"})
        result = runner(_job())
    finally:
        cal.run_nvt_adaptive = orig
    assert seen["tiers"] == [1000, 3000, 8000]
    assert seen["batch"] == "aa00"
    assert result["dynamic_state"] == "PASS"
    assert result["production_stage_limit"] == 8000
