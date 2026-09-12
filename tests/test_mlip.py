"""Tests for rudeus.mlip.sharding (dead-session resume, CPU-only stubs)."""

import json

import pytest

from rudeus.mlip.relax import (
    energies_match,
    ensure_checkpoint,
)
from rudeus.mlip.sharding import (
    assign_shard,
    make_batch_file,
    make_batch_id,
    run_batches,
    shard_batches,
)


def _make_pending(tmp_path, n=6):
    pending = tmp_path / "pending"
    for i in range(n):
        make_batch_file(
            pending, parent_id=f"obelix:p{i % 2}", child_index=i,
            generation_config_hash="cfghash", checkpoint_id="ckpt",
            structure_dict={"fake": i},
        )
    return pending


def test_batch_id_deterministic_and_shard_partition():
    """Same inputs -> same ID; shards are disjoint and cover everything."""
    a = make_batch_id("obelix:x", 0, "cfg", "ckpt")
    assert make_batch_id("obelix:x", 0, "cfg", "ckpt") == a
    assert make_batch_id("obelix:x", 1, "cfg", "ckpt") != a
    ids = [make_batch_id("p", i, "cfg", "ckpt") for i in range(6)]
    s0, s1 = shard_batches(ids, 0, 2), shard_batches(ids, 1, 2)
    assert not set(s0) & set(s1)  # disjoint: no duplicated shards
    assert sorted(s0 + s1) == sorted(ids)  # complete: no lost shards
    with pytest.raises(ValueError):
        assign_shard(ids[0], 2, 2)


def test_dead_session_resume_no_loss_no_duplication(tmp_path):
    """Simulated death mid-batch: resume completes exactly the missing set.

    True process death is a BaseException (never caught, no file written),
    unlike a relax_fn Exception (caught per candidate as an ERROR record).
    """
    pending = _make_pending(tmp_path)
    done = tmp_path / "done"
    calls = {"n": 0}

    def dying_stub(struct):
        calls["n"] += 1
        if calls["n"] > 2:
            raise KeyboardInterrupt("simulated session kill")
        return {"relaxed_energy_ev": -1.0, "converged": True}

    with pytest.raises(KeyboardInterrupt, match="simulated session kill"):
        run_batches(pending, done, 0, 1, dying_stub, {"worker": "dead"})
    assert len(list(done.glob("*.json"))) == 2  # partial progress kept

    def good_stub(struct):
        return {"relaxed_energy_ev": -2.0, "converged": True}

    summary = run_batches(pending, done, 0, 1, good_stub, {"worker": "retry"})
    assert summary == {"processed": 4, "errored": 0,
                       "skipped_done": 2, "skipped_shard": 0}

    done_ids = sorted(p.stem for p in done.glob("*.json"))
    pending_ids = sorted(p.stem for p in pending.glob("*.json"))
    assert done_ids == pending_ids  # same total result set, nothing lost
    assert len(done_ids) == len(set(done_ids))  # nothing duplicated
    for p in done.glob("*.json"):
        payload = json.loads(p.read_text(encoding="utf-8"))
        assert {"batch_id", "result", "worker"} <= set(payload)  # schema holds

    # Fully-done re-run is a no-op (idempotent, no file locks anywhere).
    again = run_batches(pending, done, 0, 1, good_stub, {"worker": "retry"})
    assert again == {"processed": 0, "errored": 0,
                     "skipped_done": 6, "skipped_shard": 0}


def test_failing_candidate_gets_error_record_without_aborting(tmp_path):
    """One raising candidate -> ERROR record; the good one completes; no raise."""
    pending = _make_pending(tmp_path, n=2)
    done = tmp_path / "done"
    ids = sorted(p.stem for p in pending.glob("*.json"))

    def flaky_stub(struct):
        if struct.get("fake") == 0:
            raise ValueError("deliberate relax failure")
        return {"relaxed_energy_ev": -2.0, "converged": True}

    summary = run_batches(pending, done, 0, 1, flaky_stub, {"worker": "w"})
    assert summary == {"processed": 1, "errored": 1,
                       "skipped_done": 0, "skipped_shard": 0}
    assert sorted(p.stem for p in done.glob("*.json")) == ids
    by_id = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in done.glob("*.json")}
    err = by_id[[k for k, v in by_id.items()
                 if v["result"].get("p1_verdict") == "ERROR"][0]]["result"]
    assert err["error_type"] == "ValueError"
    assert "deliberate relax failure" in err["error_message"]
    ok = by_id[[k for k, v in by_id.items()
                if v["result"].get("converged") is True][0]]["result"]
    assert ok["relaxed_energy_ev"] == pytest.approx(-2.0)


def test_energies_match_provisional_tolerance():
    """Dedup helper: 5 meV/atom boundary behaves (Q4 PROVISIONAL)."""
    assert energies_match(-100.0, -100.004, 10) is True   # 0.4 meV/atom
    assert energies_match(-100.0, -100.06, 10) is False   # 6 meV/atom
    assert energies_match(-100.0, -100.06, 100) is True   # 0.6 meV/atom


def test_ensure_checkpoint_refuses_unpinned_and_mismatched(tmp_path):
    """No silent fallback: missing pin or wrong hash raises loudly."""
    model = tmp_path / "model.pt"
    model.write_bytes(b"fake-checkpoint")
    with pytest.raises(ValueError, match="not pinned"):
        ensure_checkpoint("http://example.com/m.model", model, "")
    with pytest.raises(ValueError, match="hash mismatch"):
        ensure_checkpoint("http://example.com/m.model", model, "0" * 64)


def test_relax_structure_tiny_end_to_end():
    """Real mace_mp path on a 2-atom cell (CPU, float32): manifest schema holds."""
    from pathlib import Path
    import yaml
    from pymatgen.core import Lattice, Structure
    from rudeus.mlip.relax import default_model_path, load_calculator, relax_structure

    if not default_model_path().exists():
        pytest.skip("pinned checkpoint not downloaded locally")
    mcfg = yaml.safe_load(open("config.yaml", encoding="utf-8"))["mlip"]
    calc = load_calculator(default_model_path(), device="cpu", dtype="float32")
    struct = Structure(Lattice.cubic(4.0), ["Li", "Cl"],
                       [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]])
    res = relax_structure(struct.as_dict(), calc, force_tol_ev_A=0.05,
                          max_steps=30, mace_precision="float32",
                          worker_info={"session": "pytest"})
    assert {"relaxed_energy_ev", "energy_per_atom_ev", "converged",
            "p1_verdict", "mace_precision", "worker"} <= set(res)
    assert res["e_hull_ev_per_atom"] is None and res["hull_source"] == "deferred"
    assert res["mace_precision"] == "float32"
    assert res["p1_verdict"] in ("KEEP_FOR_P2", "FAIL_CONVERGENCE", "FAIL_UNPHYSICAL")
    assert res["relaxed_energy_ev"] == pytest.approx(
        res["energy_per_atom_ev"] * len(struct))


def test_make_batches_writes_eligible_only(tmp_path):
    """Batch prep: 1e9 yields files only for novel+PLAUSIBLE/geometry-FAIL kids."""
    from pathlib import Path
    from rudeus.mlip.make_batches import prepare_batches

    if not Path("data/obelix").exists():
        pytest.skip("data/obelix repository not found locally")
    out = tmp_path / "pending"
    written = prepare_batches("config.yaml", ["obelix:1e9"], str(out))
    assert len(written) >= 1  # smoke shortlist had 2 eligible 1e9 children
    for w in written:
        payload = json.loads(Path(w).read_text(encoding="utf-8"))
        assert Path(w).stem == payload["batch_id"]
        assert payload["novelty_tag"] == "novel"
        assert payload["p0_state"] in ("PLAUSIBLE", "FAIL")


def test_disordered_structure_skipped_not_crashed():
    """Disordered input -> SKIPPED_DISORDERED placeholder result, never a raise."""
    from pymatgen.core import Lattice, Structure
    from rudeus.mlip.relax import relax_structure

    disordered = Structure(
        Lattice.cubic(5.0),
        [{"Li": 0.5, "Na": 0.5}, "Cl"],
        [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]],
    )
    assert not disordered.is_ordered
    res = relax_structure(disordered.as_dict(), calc=None)
    assert res["p1_verdict"] == "SKIPPED_DISORDERED"
    assert "reason" in res and "Q5" in res["reason"]
    assert res["relaxed_energy_ev"] is None
    assert res["e_hull_ev_per_atom"] is None
