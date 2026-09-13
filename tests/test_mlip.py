"""Tests for rudeus.mlip.sharding (dead-session resume, CPU-only stubs)."""

import json

import pytest

from rudeus.mlip.relax import (
    energies_match,
    ensure_checkpoint,
)
from rudeus.mlip.sharding import (
    BATCH_ID_SCHEME_V2,
    assign_shard,
    make_batch_file,
    make_batch_id,
    make_batch_id_v1,
    run_batches,
    shard_batches,
    structure_dict_sha256,
    write_json_atomic,
)


def test_write_json_atomic_roundtrip_no_tmp_leftover(tmp_path):
    """Atomic writes land complete and leave no temp files behind."""
    target = tmp_path / "sub" / "record.json"
    write_json_atomic(target, {"a": [1, 2, {"b": None}]})
    assert json.loads(target.read_text(encoding="utf-8")) == {
        "a": [1, 2, {"b": None}]}
    assert list(tmp_path.rglob("*.tmp")) == []


def _make_pending(tmp_path, n=6):
    pending = tmp_path / "pending"
    for i in range(n):
        make_batch_file(
            pending, parent_id=f"obelix:p{i % 2}", child_index=i, seed=100 + i,
            generation_config_hash="cfghash", checkpoint_id="ckpt",
            structure_dict={"fake": i},
        )
    return pending


def _licl_dicts():
    """Two genuinely different 2-atom structure dicts + one duplicate."""
    from pymatgen.core import Lattice, Structure
    base = Structure(Lattice.cubic(4.0), ["Li", "Cl"],
                     [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]])
    shifted = Structure(Lattice.cubic(4.0), ["Li", "Cl"],
                        [[0.0, 0.0, 0.0], [0.55, 0.5, 0.5]])
    return base.as_dict(), shifted.as_dict(), base.as_dict()


def test_batch_id_v2_deterministic_and_shard_partition():
    """Same inputs -> same ID; shards are disjoint and cover everything."""
    d, _, d_dup = _licl_dicts()
    a = make_batch_id("obelix:x", 0, 7, "cfg", "ckpt", d)
    assert make_batch_id("obelix:x", 0, 7, "cfg", "ckpt", d) == a
    assert make_batch_id("obelix:x", 1, 7, "cfg", "ckpt", d) != a
    assert make_batch_id("obelix:x", 0, 8, "cfg", "ckpt", d) != a  # seed binds
    assert make_batch_id("obelix:x", 0, 7, "cfg", "ckpt", d_dup) == a  # regen
    ids = [make_batch_id("p", i, i, "cfg", "ckpt", {"fake": i}) for i in range(6)]
    s0, s1 = shard_batches(ids, 0, 2), shard_batches(ids, 1, 2)
    assert not set(s0) & set(s1)  # disjoint: no duplicated shards
    assert sorted(s0 + s1) == sorted(ids)  # complete: no lost shards
    with pytest.raises(ValueError):
        assign_shard(ids[0], 2, 2)


def test_batch_id_collision_regression():
    """MANDATORY: same parent/index/seed/config/checkpoint but different
    structures MUST yield different batch IDs (the observed Stage 1 failure).
    Same structure -> same ID; deterministic regen -> same ID."""
    base, shifted, base_dup = _licl_dicts()
    kw = dict(parent_id="obelix:00x", child_index=0, seed=42,
              generation_config_hash="cfghash", checkpoint_id="medium-mpa-0")
    id_base = make_batch_id(structure_dict=base, **kw)
    id_shifted = make_batch_id(structure_dict=shifted, **kw)
    id_regen = make_batch_id(structure_dict=base_dup, **kw)
    assert id_base != id_shifted  # the collision that overwrote 62a5168...
    assert id_base == id_regen  # ...while deterministic regen is stable
    # v1 cannot see the difference (why it is legacy):
    assert (make_batch_id_v1("obelix:00x", 0, "cfghash", "medium-mpa-0")
            == make_batch_id_v1("obelix:00x", 0, "cfghash", "medium-mpa-0"))


def test_structure_dict_sha_matches_object_sha():
    """Dict-level hash equals the canonical object-level structure_sha256."""
    from rudeus.generation.generator import structure_sha256
    from pymatgen.core import Lattice, Structure
    struct = Structure(Lattice.cubic(4.0), ["Li", "Cl"],
                       [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]])
    assert structure_dict_sha256(struct.as_dict()) == structure_sha256(struct)


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
    assert summary == {"processed": 4, "errored": 0, "skipped": 0,
                       "skipped_done": 2, "skipped_shard": 0,
                       "skipped_legacy": 0, "stale_recomputed": 0,
                       "retried_errors": 0, "retried_skipped": 0}
    done_ids = sorted(p.stem for p in done.glob("*.json"))
    pending_ids = sorted(p.stem for p in pending.glob("*.json"))
    assert done_ids == pending_ids  # same total result set, nothing lost
    assert len(done_ids) == len(set(done_ids))  # nothing duplicated
    for p in done.glob("*.json"):
        payload = json.loads(p.read_text(encoding="utf-8"))
        assert {"batch_id", "result", "worker"} <= set(payload)  # schema holds

    # Fully-done re-run is a no-op (idempotent, no file locks anywhere).
    again = run_batches(pending, done, 0, 1, good_stub, {"worker": "retry"})
    assert again == {"processed": 0, "errored": 0, "skipped": 0,
                     "skipped_done": 6, "skipped_shard": 0,
                     "skipped_legacy": 0, "stale_recomputed": 0,
                     "retried_errors": 0, "retried_skipped": 0}


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
    assert summary == {"processed": 1, "errored": 1, "skipped": 0,
                       "skipped_done": 0, "skipped_shard": 0,
                       "skipped_legacy": 0, "stale_recomputed": 0,
                       "retried_errors": 0, "retried_skipped": 0}
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
    # Phase B provenance/metrics keys (§9/#11), evidence-semantics (§12)
    for key in ("initial_energy_ev", "energy_change_ev", "initial_volume_A3",
                "relaxed_volume_A3", "abc_change_A", "angles_change_deg",
                "max_atomic_displacement_A", "rms_displacement_A",
                "min_interatomic_distance_A", "input_structure_sha256",
                "relaxed_structure_sha256"):
        assert key in res, f"missing provenance key {key}"
    flat = json.dumps(res).lower()
    assert "dynamic" not in flat and "transport" not in flat
    assert "diffusive" not in flat


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


def test_prepare_batches_deterministic_bytes(tmp_path):
    """Same config+parents twice -> byte-identical pending files, same IDs."""
    from pathlib import Path
    from rudeus.mlip.make_batches import prepare_batches

    if not Path("data/obelix").exists():
        pytest.skip("data/obelix repository not found locally")
    out_a, out_b = tmp_path / "a", tmp_path / "b"
    wa = prepare_batches("config.yaml", ["obelix:1e9"], str(out_a))
    wb = prepare_batches("config.yaml", ["obelix:1e9"], str(out_b))
    assert sorted(Path(w).name for w in wa) == sorted(Path(w).name for w in wb)
    assert wa, "expected at least one eligible batch for obelix:1e9"
    for fa, fb in zip(sorted(wa), sorted(wb)):
        assert Path(fa).read_bytes() == Path(fb).read_bytes()
    # shard assignment from the spec is deterministic and disjoint
    from rudeus.mlip.sharding import shard_batches
    ids = [Path(w).stem for w in wa]
    s0 = shard_batches(ids, 0, 2)
    s1 = shard_batches(ids, 1, 2)
    assert not set(s0) & set(s1) and sorted(s0 + s1) == sorted(ids)


def test_make_batches_audit_out(tmp_path):
    """--audit-out path writes a valid JSON audit over ALL children."""
    from pathlib import Path
    from rudeus.mlip.make_batches import prepare_batches

    if not Path("data/obelix").exists():
        pytest.skip("data/obelix repository not found locally")
    out = tmp_path / "pending"
    audit_path = tmp_path / "audit" / "pilot.json"
    prepare_batches("config.yaml", ["obelix:1e9"], str(out),
                    audit_out=str(audit_path))
    report = json.loads(audit_path.read_text(encoding="utf-8"))
    assert report["total"] == 3  # children_per_parent from config
    assert report["unique_parents"] == 1
    assert sum(report["p0"].values()) == 3
    assert sum(report["novelty"].values()) == 3


def test_disordered_structure_skipped_not_crashed():
    """Disordered input -> explicit unsupported verdict, faithful record."""
    from pymatgen.core import Lattice, Structure
    from rudeus.mlip.relax import relax_structure
    from rudeus.mlip.sharding import structure_dict_sha256

    disordered = Structure(
        Lattice.cubic(5.0),
        [{"Li": 0.5, "Na": 0.5}, "Cl"],
        [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]],
    )
    assert not disordered.is_ordered
    frozen = json.dumps(disordered.as_dict(), sort_keys=True, default=str)
    res = relax_structure(disordered.as_dict(), calc=None)
    assert res["p1_verdict"] == "DISORDERED_UNSUPPORTED_FOR_MLIP"
    assert "not attempted" in res["reason"]
    assert res["converged"] is False  # never claimed as success...
    assert res["relaxed_structure_dict"] is None  # ...nor converted
    assert res["relaxed_energy_ev"] is None
    assert res["e_hull_ev_per_atom"] is None
    # faithful: record hash matches the generated (unconverted) structure
    assert res["input_structure_sha256"] == structure_dict_sha256(
        disordered.as_dict())
    assert json.dumps(disordered.as_dict(), sort_keys=True,
                      default=str) == frozen  # input untouched


def test_legacy_pending_files_are_never_processed(tmp_path):
    """v1-scheme files are counted as skipped_legacy, never executed."""
    from rudeus.mlip.sharding import make_batch_id_v1, run_batches, write_json_atomic

    pending = tmp_path / "pending"
    legacy_id = make_batch_id_v1("obelix:x", 0, "cfg", "ckpt")
    write_json_atomic(pending / f"{legacy_id}.json", {
        "batch_id": legacy_id, "parent_id": "obelix:x", "child_index": 0,
        "structure_dict": {"fake": 0}})  # no batch_id_scheme marker: legacy
    calls = {"n": 0}

    def counting_stub(struct):
        calls["n"] += 1
        return {"ok": True}

    summary = run_batches(pending, tmp_path / "done", 0, 1, counting_stub)
    assert calls["n"] == 0  # relax_fn never invoked on legacy input
    assert summary["skipped_legacy"] == 1
    assert list((tmp_path / "done").glob("*.json")) == []  # nothing written


def test_stale_done_record_is_recomputed_not_trusted(tmp_path):
    """A done record for a DIFFERENT structure must never satisfy resume."""
    from rudeus.mlip.sharding import run_batches, structure_dict_sha256

    pending = _make_pending(tmp_path, n=1)
    done = tmp_path / "done"
    done.mkdir()
    (bid,) = [p.stem for p in pending.glob("*.json")]
    stale = {"batch_id": bid,
             "result": {"p1_verdict": "KEEP_FOR_P2", "converged": True,
                        "input_structure_sha256": "0" * 64},  # wrong structure
             "worker": {"session": "old"}}
    (done / f"{bid}.json").write_text(json.dumps(stale), encoding="utf-8")

    calls = {"n": 0}
    received = []

    def fresh_stub(struct):
        calls["n"] += 1
        received.append(struct)
        return {"p1_verdict": "KEEP_FOR_P2", "converged": True,
                "input_structure_sha256": structure_dict_sha256(struct)}

    summary = run_batches(pending, done, 0, 1, fresh_stub)
    assert calls["n"] == 1  # stale record recomputed
    assert summary["stale_recomputed"] == 1
    assert received == [{"fake": 0}]  # recompute used THIS batch's structure
    fixed = json.loads((done / f"{bid}.json").read_text(encoding="utf-8"))
    assert fixed["result"]["input_structure_sha256"] == structure_dict_sha256(
        {"fake": 0})

    # ...while a hash-matching record is trusted and skipped.
    again = run_batches(pending, done, 0, 1, fresh_stub)
    assert again["skipped_done"] == 1 and again["processed"] == 0


def test_error_record_carries_input_structure_hash(tmp_path):
    """ERROR records bind to their input so resume-verify covers failures too."""
    from rudeus.mlip.sharding import run_batches, structure_dict_sha256

    pending = _make_pending(tmp_path, n=1)
    done = tmp_path / "done"

    def boom(struct):
        raise RuntimeError("calc exploded")

    run_batches(pending, done, 0, 1, boom)
    (bid,) = [p.stem for p in pending.glob("*.json")]
    err = json.loads((done / f"{bid}.json").read_text(encoding="utf-8"))["result"]
    assert err["p1_verdict"] == "ERROR"
    assert err["input_structure_sha256"] == structure_dict_sha256({"fake": 0})


def test_malformed_pending_becomes_error_not_abort(tmp_path):
    """Corrupt JSON pending file -> MalformedPending ERROR record, shard lives."""
    from rudeus.mlip.sharding import run_batches

    pending = tmp_path / "pending"
    pending.mkdir()
    (pending / "deadbeef01234567.json").write_text("{not json", encoding="utf-8")

    def stub(struct):
        return {"ok": True}

    summary = run_batches(pending, tmp_path / "done", 0, 1, stub)
    assert summary["errored"] == 1
    rec = json.loads((tmp_path / "done" / "deadbeef01234567.json").read_text(
        encoding="utf-8"))["result"]
    assert rec["p1_verdict"] == "ERROR" and rec["error_type"] == "MalformedPending"


def test_p1_manifest_never_sets_dynamic_or_transport(tmp_path):
    """P1 evidence must not collapse dynamic/transport dimensions (spec 12)."""
    from rudeus.mlip.relax import relax_structure
    from pymatgen.core import Lattice, Structure

    disordered = Structure(
        Lattice.cubic(5.0),
        [{"Li": 0.5, "Na": 0.5}, "Cl"],
        [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]],
    )
    res = relax_structure(disordered.as_dict(), calc=None)
    flat = json.dumps(res).lower()
    assert "dynamic" not in flat and "transport" not in flat
    assert "diffusive" not in flat and "not_run" not in flat


def _licl_structure():
    from pymatgen.core import Lattice, Structure
    return Structure(Lattice.cubic(4.0), ["Li", "Cl"],
                     [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]])


def test_compare_structures_metrics():
    """Volume/displacement/min-distance on identical vs shifted structures."""
    from rudeus.mlip.analysis import compare_structures

    base = _licl_structure()
    same = compare_structures(base.as_dict(), base.as_dict())
    assert same["volume_change_fraction"] == pytest.approx(0.0)
    assert same["max_atomic_displacement_A"] == pytest.approx(0.0)
    assert same["rms_displacement_A"] == pytest.approx(0.0)
    assert same["min_interatomic_distance_A"] == pytest.approx(3.4641016151377544)  # sqrt(3)*2: Li-Cl in 4A rocksalt
    assert same["abc_change_A"] == pytest.approx([0.0, 0.0, 0.0])

    moved = base.copy()
    moved.translate_sites(1, [0.1, 0.0, 0.0], frac_coords=False)
    diff = compare_structures(base.as_dict(), moved.as_dict())
    assert diff["max_atomic_displacement_A"] == pytest.approx(0.1)
    assert diff["rms_displacement_A"] == pytest.approx(0.1 / 2 ** 0.5)
    assert diff["volume_change_fraction"] == pytest.approx(0.0)

    with pytest.raises(ValueError, match="atom count changed"):
        compare_structures(base.as_dict(),
                           {"@module": "x", "@class": "Structure",
                            "lattice": base.lattice.as_dict(),
                            "sites": base.as_dict()["sites"][:1]})


def test_parent_collapse_detection():
    """Relaxed==parent -> rediscovery_after_relaxation; else novel; none -> not-checked."""
    from pymatgen.analysis.structure_matcher import StructureMatcher
    from rudeus.mlip.analysis import annotate_post_relax_novelty

    base = _licl_structure()
    matcher = StructureMatcher()
    hit = annotate_post_relax_novelty(base.as_dict(), base.as_dict(), [], matcher)
    assert hit["post_relax_novelty"] == "rediscovery_after_relaxation"
    assert hit["matched"] == "parent"

    from pymatgen.core import Lattice, Structure
    other = Structure(Lattice.cubic(5.6), ["Na", "Br"],
                      [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]])
    miss = annotate_post_relax_novelty(other.as_dict(), base.as_dict(), [], matcher)
    assert miss["post_relax_novelty"] == "novel"
    assert miss["matched"] is None

    sib = annotate_post_relax_novelty(other.as_dict(), None,
                                      [("abc123", other.as_dict())], matcher)
    assert sib["post_relax_novelty"] == "rediscovery_after_relaxation"
    assert sib["matched"] == "abc123"

    unchecked = annotate_post_relax_novelty(None, base.as_dict(), [], matcher)
    assert unchecked["post_relax_novelty"] == "not-checked"


def test_git_safety_aborts_on_foreign_staged_files(tmp_path):
    """Worker commit refuses when unrelated user changes are staged."""
    import shutil
    import subprocess
    from rudeus.mlip.gitpush import GitSafetyError, commit_done_files

    if shutil.which("git") is None:
        pytest.skip("git binary not available")
    repo = tmp_path / "repo"
    repo.mkdir()
    env = {"GIT_CONFIG_NOSYSTEM": "1", "HOME": str(tmp_path)}
    subprocess.run(["git", "init"], cwd=repo, check=True, env={**env, **__import__("os").environ})
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=repo, check=True)
    (repo / "KAGGLE.md").write_text("user work in progress", encoding="utf-8")
    done = repo / "done"
    done.mkdir()
    (done / "a.json").write_text("{}", encoding="utf-8")
    subprocess.run(["git", "add", "KAGGLE.md"], cwd=repo, check=True)

    with pytest.raises(GitSafetyError, match="unrelated files already staged"):
        commit_done_files(repo, done, "worker commit")
    # nothing committed, user file still staged and untouched
    log = subprocess.run(["git", "log", "--oneline"], cwd=repo,
                         capture_output=True, text=True)
    assert log.stdout.strip() == ""
    assert (repo / "KAGGLE.md").read_text(encoding="utf-8") == "user work in progress"

    subprocess.run(["git", "reset", "KAGGLE.md"], cwd=repo, check=True)
    (repo / "KAGGLE.md").write_text("user work in progress v2", encoding="utf-8")
    info = commit_done_files(repo, done, "worker commit")
    assert info["files"] == ["done/a.json"]
    show = subprocess.run(["git", "show", "--name-only", "--format=",
                           info["commit"]], cwd=repo, capture_output=True,
                          text=True).stdout.split()
    assert show == ["done/a.json"]  # user file NOT swept in
    assert (repo / "KAGGLE.md").read_text(encoding="utf-8") == "user work in progress v2"

    with pytest.raises(GitSafetyError, match="never main|main/master"):
        from rudeus.mlip.gitpush import push_branch
        push_branch(repo, "main")


def _seed_mixed_done(tmp_path):
    """Pending (3 v2 batches) + done: 1 DONE, 1 ERROR, 1 SKIPPED (hashes valid)."""
    from rudeus.mlip.sharding import structure_dict_sha256

    pending = _make_pending(tmp_path, n=3)
    done = tmp_path / "done"
    done.mkdir()
    bids = sorted(p.stem for p in pending.glob("*.json"))
    structs = {b: json.loads((pending / f"{b}.json").read_text(
        encoding="utf-8"))["structure_dict"] for b in bids}
    records = {
        bids[0]: {"p1_verdict": "KEEP_FOR_P2", "converged": True,
                  "input_structure_sha256": structure_dict_sha256(structs[bids[0]])},
        bids[1]: {"p1_verdict": "ERROR", "error_type": "ValueError",
                  "error_message": "boom", "converged": False,
                  "input_structure_sha256": structure_dict_sha256(structs[bids[1]])},
        bids[2]: {"p1_verdict": "DISORDERED_UNSUPPORTED_FOR_MLIP",
                  "reason": "unsupported", "converged": False,
                  "input_structure_sha256": structure_dict_sha256(structs[bids[2]])},
    }
    for b, r in records.items():
        (done / f"{b}.json").write_text(
            json.dumps({"batch_id": b, "result": r, "worker": {}}),
            encoding="utf-8")
    return pending, done, bids


def test_retry_defaults_skip_errors_and_skipped(tmp_path):
    """Default: DONE/ERROR/SKIPPED all skipped; relax never called."""
    from rudeus.mlip.sharding import run_batches

    pending, done, _ = _seed_mixed_done(tmp_path)
    calls = {"n": 0}

    def stub(struct):
        calls["n"] += 1
        return {"p1_verdict": "KEEP_FOR_P2", "converged": True,
                "input_structure_sha256": "x"}

    summary = run_batches(pending, done, 0, 1, stub)
    assert calls["n"] == 0
    assert summary["skipped_done"] == 3
    assert summary["retried_errors"] == 0 and summary["retried_skipped"] == 0


def test_retry_errors_recomputes_only_errors(tmp_path):
    """retry_errors=True recomputes ERROR; DONE+SKIPPED stay skipped."""
    from rudeus.mlip.sharding import run_batches, structure_dict_sha256

    pending, done, bids = _seed_mixed_done(tmp_path)
    seen = []

    def stub(struct):
        seen.append(struct)
        return {"p1_verdict": "KEEP_FOR_P2", "converged": True,
                "input_structure_sha256": structure_dict_sha256(struct)}

    summary = run_batches(pending, done, 0, 1, stub, retry_errors=True)
    assert summary["retried_errors"] == 1 and summary["processed"] == 1
    assert summary["skipped_done"] == 2 and summary["retried_skipped"] == 0
    err_struct = json.loads((pending / f"{bids[1]}.json").read_text(
        encoding="utf-8"))["structure_dict"]
    assert seen == [err_struct]  # exactly the ERROR batch's own structure
    assert json.loads((done / f"{bids[1]}.json").read_text(
        encoding="utf-8"))["result"]["p1_verdict"] == "KEEP_FOR_P2"
    # retry is one-shot: a second default run skips everything again
    again = run_batches(pending, done, 0, 1, stub)
    assert again["skipped_done"] == 3 and again["processed"] == 0


def test_retry_skipped_recomputes_only_skipped(tmp_path):
    """retry_skipped=True recomputes SKIPPED; DONE+ERROR stay skipped."""
    from rudeus.mlip.sharding import run_batches, structure_dict_sha256

    pending, done, bids = _seed_mixed_done(tmp_path)
    seen = []

    def stub(struct):
        seen.append(struct)
        return {"p1_verdict": "DISORDERED_UNSUPPORTED_FOR_MLIP",
                "reason": "still unsupported", "converged": False,
                "input_structure_sha256": structure_dict_sha256(struct)}

    summary = run_batches(pending, done, 0, 1, stub, retry_skipped=True)
    assert summary["retried_skipped"] == 1 and summary["skipped"] == 1
    assert summary["skipped_done"] == 2 and summary["retried_errors"] == 0
    skip_struct = json.loads((pending / f"{bids[2]}.json").read_text(
        encoding="utf-8"))["structure_dict"]
    assert seen == [skip_struct]  # deterministic unsupported -> same record
    # no infinite loop: default rerun skips the fresh SKIPPED record too
    again = run_batches(pending, done, 0, 1, stub)
    assert again["skipped_done"] == 3
