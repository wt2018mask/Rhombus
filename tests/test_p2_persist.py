"""P2 Git-as-DB persistence layer tests (engineering only, no science).

Covers the task-required behaviors using temporary local Git repositories
and bare remotes only — never the real working tree, never Kaggle, never GPU:

  A. atomic result persistence (valid final JSON, no .tmp masquerade)
  B. exact staging (only this worker's files; no `git add .` / `git add -A`)
  C. commit creation (content + message convention)
  D. push success (worker branch pushed, main untouched)
  E. push failure (local JSON + commit preserved, explicit failure, retryable)
  F. resume/idempotency (no recompute, no duplicate commit)
  G. unrelated working tree (staged foreign aborts; unstaged left alone)
  H. scientific invariance (frozen P2 protocol constants)

Scientific P2 logic is NOT exercised beyond structural validity: persistence
treats result JSON as opaque.
"""

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from rudeus.mlip.gitpush import (
    GitSafetyError,
    p2_worker_branch,
    persist_p2_results,
    push_branch,
    validate_p2_result_file,
)
from rudeus.mlip.p2 import (
    P2_PROTOCOL_DEFAULTS,
    P2_PROTOCOL_VERSION,
    P2_PRODUCTION_TIERS_PROVISIONAL,
    P2_TRAJECTORY_POLICY,
    protocol_config_hash,
    run_p2_batches,
)
from rudeus.mlip.run_p2 import resolve_push_branch

NEEDS_GIT = shutil.which("git") is None
pytestmark = pytest.mark.skipif(NEEDS_GIT, reason="git binary not available")


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _git(repo, *args):
    # NOTE: ambient git config is used deliberately (no GIT_CONFIG_NOSYSTEM):
    # the implementation under test also runs with ambient config, and
    # splitting the two (e.g. system core.autocrlf=true for `git add` but
    # false for `git status`) produces spurious worktree dirt on Windows
    # (CRLF worktree vs LF-normalized blob). Same convention as
    # test_mlip.py::test_git_safety_aborts_on_foreign_staged_files.
    return subprocess.run(["git", "-c", "commit.gpgsign=false", *args],
                          cwd=str(repo), capture_output=True, text=True)


def _init_repo(repo: Path) -> Path:
    repo.mkdir(parents=True, exist_ok=True)
    assert _git(repo, "init").returncode == 0
    assert _git(repo, "config", "user.email", "p2-test@local").returncode == 0
    assert _git(repo, "config", "user.name", "p2-test").returncode == 0
    assert _git(repo, "config", "commit.gpgsign", "false").returncode == 0
    (repo / "README.md").write_text("test repo", encoding="utf-8")
    assert _git(repo, "add", "--", "README.md").returncode == 0
    assert _git(repo, "commit", "-m", "init").returncode == 0
    return repo


def _staged(repo) -> list:
    r = _git(repo, "diff", "--cached", "--name-only")
    assert r.returncode == 0
    return sorted(l for l in r.stdout.splitlines() if l.strip())


def _protocol(**over):
    p = dict(P2_PROTOCOL_DEFAULTS)
    p.update(over)
    return p


def _p1_done_record(p1done: Path, batch_id: str):
    from rudeus.mlip.sharding import structure_dict_sha256
    from pymatgen.core import Lattice, Structure
    s = Structure(Lattice.cubic(4.0), ["Li", "Cl"],
                  [[0, 0, 0], [0.5, 0.5, 0.5]]).as_dict()
    rec = {"batch_id": batch_id, "child_material_id": "g1-test",
           "parent_id": "obelix:test",
           "result": {"p1_verdict": "KEEP_FOR_P2",
                      "relaxed_structure_dict": s,
                      "relaxed_structure_sha256": structure_dict_sha256(s)}}
    (p1done / f"{batch_id}.json").write_text(json.dumps(rec), encoding="utf-8")
    return structure_dict_sha256(s)


def test_p2_skips_explicit_p0_reject_without_running_md(tmp_path):
    p1done = tmp_path / "p1done"
    p1done.mkdir(parents=True, exist_ok=True)
    p2out = tmp_path / "p2"
    proto = _protocol()
    batch_id = "p0fail01"
    relaxed_sha = _p1_done_record(p1done, batch_id)
    rec = json.loads((p1done / f"{batch_id}.json").read_text(encoding="utf-8"))
    rec["p0_state"] = "FAIL"
    rec["p0_rejection_reason"] = "test-p0-reject"
    (p1done / f"{batch_id}.json").write_text(
        json.dumps(rec), encoding="utf-8"
    )

    calls = []

    def runner(job):
        calls.append(job["batch_id"])
        return _stub_runner(proto)(job)

    summary = run_p2_batches(
        p1done, p2out, 0, 1, runner, proto, {"session": "test"}
    )

    assert summary["processed"] == 0
    assert summary["errored"] == 0
    assert summary["skipped_p0_rejected"] == 1
    assert summary["wrote"] == []
    assert calls == []
    assert not (p2out / f"{batch_id}.json").exists()


def _stub_runner(protocol, verdict="PASS"):
    cfg_hash = protocol_config_hash(protocol)

    def md_runner(job):
        return {"p2_verdict": verdict,
                "dynamic_state": verdict,
                "p2_input_relaxed_sha256": job["relaxed_structure_sha256"],
                "p2_config_hash": cfg_hash}
    return md_runner


def _run_stub_p2(tmp_path: Path, bids, verdict="PASS"):
    p1done = tmp_path / "p1done"
    p1done.mkdir(parents=True, exist_ok=True)
    p2out = tmp_path / "p2"
    proto = _protocol()
    for b in bids:
        _p1_done_record(p1done, b)
    summary = run_p2_batches(p1done, p2out, 0, 1, _stub_runner(proto, verdict),
                             proto, {"session": "test"})
    return p1done, p2out, summary


def _move_p2_into_repo(p2out: Path, repo: Path) -> Path:
    dest = repo / "data" / "batches" / "p2"
    dest.mkdir(parents=True, exist_ok=True)
    for f in sorted(p2out.glob("*.json")):
        (dest / f.name).write_text(f.read_text(encoding="utf-8"),
                                   encoding="utf-8")
    return dest


# --------------------------------------------------------------------------
# A. atomic result persistence
# --------------------------------------------------------------------------

def test_a_atomic_write_valid_final_json_and_wrote(tmp_path):
    _, p2out, summary = _run_stub_p2(tmp_path, ["aa00", "bb01"])
    assert summary["processed"] == 2
    assert summary["wrote"] == ["aa00", "bb01"]
    assert list(p2out.glob("*.tmp")) == []
    for b in ("aa00", "bb01"):
        payload = json.loads((p2out / f"{b}.json").read_text(encoding="utf-8"))
        assert payload["batch_id"] == b
        assert payload["result"]["p2_verdict"] == "PASS"


def test_a_tmp_file_never_masquerades_as_done(tmp_path):
    p1done, p2out, _ = _run_stub_p2(tmp_path, ["aa00"])
    # Simulate a crashed worker's leftover partial temp file for a candidate
    # with no finished result: it must not count as done.
    (p2out / "cc11.json.tmp").write_text('{"batch_id": "cc11", "half": ',
                                         encoding="utf-8")
    _p1_done_record(p1done, "cc11")
    proto = _protocol()
    summary = run_p2_batches(p1done, p2out, 0, 1, _stub_runner(proto), proto,
                             {"session": "test"})
    assert summary["processed"] == 1
    assert summary["wrote"] == ["cc11"]
    assert json.loads((p2out / "cc11.json").read_text(
        encoding="utf-8"))["batch_id"] == "cc11"


def test_a_malformed_prior_is_recomputed_not_trusted(tmp_path):
    p1done, p2out, _ = _run_stub_p2(tmp_path, ["aa00"])
    (p2out / "aa00.json").write_text("not json{{{", encoding="utf-8")
    proto = _protocol()
    summary = run_p2_batches(p1done, p2out, 0, 1, _stub_runner(proto), proto,
                             {"session": "test"})
    assert summary["stale_recomputed"] == 1
    assert summary["wrote"] == ["aa00"]
    payload = json.loads((p2out / "aa00.json").read_text(encoding="utf-8"))
    assert payload["result"]["p2_verdict"] == "PASS"


# --------------------------------------------------------------------------
# B. exact staging
# --------------------------------------------------------------------------

def test_b_only_intended_p2_files_staged(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    _, p2out, _ = _run_stub_p2(tmp_path / "work", ["aa00", "bb01"])
    p2dir = _move_p2_into_repo(p2out, repo)
    # Unrelated modifications: tracked-but-modified + brand-new untracked.
    (repo / "notes.txt").write_text("user scratch", encoding="utf-8")
    (repo / "README.md").write_text("user edit", encoding="utf-8")
    info = persist_p2_results(
        repo, p2dir, ["aa00", "bb01"],
        "p2 test-worker shard 0/44: 2 processed, 0 errored")
    assert info["files"] == ["data/batches/p2/aa00.json",
                             "data/batches/p2/bb01.json"]
    # Exact-staging outcome: the commit holds ONLY the intended files
    # (post-add staged set == intended set, verified inside commit_only_files
    # via `git diff --cached --name-only` before committing).
    show = _git(repo, "show", "--name-only", "--format=", info["commit"])
    assert sorted(show.stdout.split()) == info["files"]
    assert _staged(repo) == []  # nothing lingered in the index
    status = _git(repo, "status", "--short").stdout
    assert " M README.md" in status and "?? notes.txt" in status
    # Unrelated files untouched on disk and uncommitted.
    assert (repo / "notes.txt").read_text(encoding="utf-8") == "user scratch"
    assert (repo / "README.md").read_text(encoding="utf-8") == "user edit"


def test_b_no_bulk_add_commands_used():
    src = (Path(__file__).resolve().parent.parent
           / "rudeus" / "mlip" / "gitpush.py").read_text(encoding="utf-8")
    # Staging call sites must use an explicit pathspec (`git add -- <files>`);
    # bulk staging must not appear in any subprocess invocation.
    assert re.search(r'"add",\s*"--"', src), "explicit pathspec add missing"
    assert not re.search(r'"add",\s*"\."', src), "git add . forbidden"
    assert not re.search(r'"add",\s*"-A"', src), "git add -A forbidden"
    assert not re.search(r'"add",\s*"-u"', src), "git add -u forbidden"


def test_b_malformed_result_refuses_to_stage_anything(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    _, p2out, _ = _run_stub_p2(tmp_path / "work", ["aa00"])
    p2dir = _move_p2_into_repo(p2out, repo)
    (p2dir / "bb01.json").write_text("corrupt{{{", encoding="utf-8")
    with pytest.raises(GitSafetyError):
        persist_p2_results(repo, p2dir, ["aa00", "bb01"], "msg")
    assert _staged(repo) == []  # nothing staged, valid file not swept in
    assert json.loads((p2dir / "aa00.json").read_text(
        encoding="utf-8"))["batch_id"] == "aa00"


# --------------------------------------------------------------------------
# C. commit creation
# --------------------------------------------------------------------------

def test_c_commit_contains_only_intended_files_with_message(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    _, p2out, _ = _run_stub_p2(tmp_path / "work", ["aa00", "bb01"])
    p2dir = _move_p2_into_repo(p2out, repo)
    msg = "p2 test-worker shard 0/44: 2 processed, 0 errored"
    info = persist_p2_results(repo, p2dir, ["aa00", "bb01"], msg)
    assert len(info["commit"]) == 40
    show = _git(repo, "show", "--name-only", "--format=", info["commit"])
    assert sorted(show.stdout.split()) == ["data/batches/p2/aa00.json",
                                           "data/batches/p2/bb01.json"]
    log = _git(repo, "log", "-1", "--format=%s")
    assert log.stdout.strip() == msg


# --------------------------------------------------------------------------
# D. push success (worker branch pushed, main untouched)
# --------------------------------------------------------------------------

def test_d_push_worker_branch_main_untouched(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    main_sha = _git(repo, "rev-parse", "HEAD").stdout.strip()
    _git(repo, "branch", "-M", "main")
    bare = tmp_path / "remote.git"
    assert _git(tmp_path, "init", "--bare", str(bare)).returncode == 0
    assert _git(repo, "remote", "add", "origin", str(bare)).returncode == 0

    _, p2out, _ = _run_stub_p2(tmp_path / "work", ["aa00"])
    p2dir = _move_p2_into_repo(p2out, repo)
    branch = "worker/p2/test-worker-s0-of44"
    assert _git(repo, "checkout", "-b", branch).returncode == 0
    persist_p2_results(repo, p2dir, ["aa00"],
                       "p2 test-worker shard 0/44: 1 processed, 0 errored")
    commit_sha = _git(repo, "rev-parse", "HEAD").stdout.strip()
    pushed = push_branch(repo, branch)
    assert pushed["branch"] == branch

    ls = _git(repo, "ls-remote", str(bare))
    refs = dict(l.split("\t")[::-1] for l in ls.stdout.splitlines()
                if l.strip())
    assert refs.get(f"refs/heads/{branch}") == commit_sha
    assert "refs/heads/main" not in refs  # default branch never pushed
    assert _git(repo, "rev-parse", "main").stdout.strip() == main_sha


def test_d_push_refuses_main_and_master(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    with pytest.raises(GitSafetyError, match="main/master"):
        push_branch(repo, "main")
    with pytest.raises(GitSafetyError, match="main/master"):
        push_branch(repo, "master")


# --------------------------------------------------------------------------
# E. push failure preserves local results + commit, retry works
# --------------------------------------------------------------------------

def test_e_push_failure_preserves_local_result_and_commit(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    _, p2out, _ = _run_stub_p2(tmp_path / "work", ["aa00"])
    p2dir = _move_p2_into_repo(p2out, repo)
    persist_p2_results(repo, p2dir, ["aa00"],
                       "p2 test-worker shard 0/44: 1 processed, 0 errored")
    commit_sha = _git(repo, "rev-parse", "HEAD").stdout.strip()
    before = (p2dir / "aa00.json").read_text(encoding="utf-8")

    assert _git(repo, "remote", "add", "origin",
                str(tmp_path / "no-such-remote.git")).returncode == 0
    branch = "worker/p2/test-worker-s0-of44"
    with pytest.raises(GitSafetyError, match="git push failed"):
        push_branch(repo, branch)
    # Failure state is explicit; local result + commit preserved, no reset.
    assert (p2dir / "aa00.json").read_text(encoding="utf-8") == before
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == commit_sha
    assert _git(repo, "status", "--short").stdout.strip() == ""

    # Retry without recomputation: point at a real bare remote and push the
    # SAME commit (case C idempotency — no P2 rerun needed).
    bare = tmp_path / "remote.git"
    assert _git(tmp_path, "init", "--bare", str(bare)).returncode == 0
    assert _git(repo, "remote", "set-url", "origin", str(bare)).returncode == 0
    pushed = push_branch(repo, branch)
    assert pushed["branch"] == branch
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == commit_sha


# --------------------------------------------------------------------------
# F. resume: no recompute, no duplicate commit
# --------------------------------------------------------------------------

def test_f_resume_skips_valid_results_no_duplicate_commit(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    p1done, p2out, first = _run_stub_p2(tmp_path / "work", ["aa00", "bb01"])
    assert first["wrote"] == ["aa00", "bb01"]
    p2dir = _move_p2_into_repo(p2out, repo)
    persist_p2_results(repo, p2dir, first["wrote"],
                       "p2 test-worker shard 0/44: 2 processed, 0 errored")
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    n_commits = _git(repo, "rev-list", "--count", "HEAD").stdout.strip()
    blobs = {b: (p2dir / f"{b}.json").read_text(encoding="utf-8")
             for b in ("aa00", "bb01")}

    calls = []
    proto = _protocol()
    base = _stub_runner(proto)

    def counting(job):
        calls.append(job["batch_id"])
        return base(job)

    # Rerun against the persisted files (as restored in a fresh checkout).
    p2again = tmp_path / "work2"
    p2again.mkdir()
    for b in ("aa00", "bb01"):
        (p2again / f"{b}.json").write_text(blobs[b], encoding="utf-8")
    second = run_p2_batches(p1done, p2again, 0, 1, counting, proto,
                            {"session": "test"})
    assert second["processed"] == 0 and second["errored"] == 0
    assert second["skipped_done"] == 2
    assert second["wrote"] == [] and calls == []  # no recomputation
    for b in ("aa00", "bb01"):
        assert (p2again / f"{b}.json").read_text(encoding="utf-8") == blobs[b]

    # Nothing new -> the worker must not create a duplicate commit.
    with pytest.raises(GitSafetyError, match="no p2 results to persist"):
        persist_p2_results(repo, p2dir, second["wrote"], "duplicate?")
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == head
    assert _git(repo, "rev-list", "--count", "HEAD").stdout.strip() == n_commits


# --------------------------------------------------------------------------
# G. unrelated working tree
# --------------------------------------------------------------------------

def test_g_staged_foreign_file_aborts_without_touching_index(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    _, p2out, _ = _run_stub_p2(tmp_path / "work", ["aa00", "bb01"])
    p2dir = _move_p2_into_repo(p2out, repo)
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    (repo / "user-plan.md").write_text("user work in progress",
                                       encoding="utf-8")
    assert _git(repo, "add", "--", "user-plan.md").returncode == 0
    with pytest.raises(GitSafetyError, match="unrelated files already staged"):
        persist_p2_results(repo, p2dir, ["aa00", "bb01"], "worker commit")
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == head
    assert _staged(repo) == ["user-plan.md"]  # user staging untouched
    assert (repo / "user-plan.md").read_text(
        encoding="utf-8") == "user work in progress"
    assert (p2dir / "aa00.json").is_file()  # local results preserved


def test_g_unstaged_modifications_not_committed(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    _, p2out, _ = _run_stub_p2(tmp_path / "work", ["aa00"])
    p2dir = _move_p2_into_repo(p2out, repo)
    (repo / "README.md").write_text("user edit stays out of commit",
                                    encoding="utf-8")
    info = persist_p2_results(repo, p2dir, ["aa00"],
                              "p2 test-worker shard 0/44: 1 processed, 0 errored")
    show = _git(repo, "show", "--name-only", "--format=", info["commit"])
    assert show.stdout.split() == ["data/batches/p2/aa00.json"]
    assert (repo / "README.md").read_text(
        encoding="utf-8") == "user edit stays out of commit"


# --------------------------------------------------------------------------
# restore path: backed-up campaign results persist by explicit list
# --------------------------------------------------------------------------

def test_restore_backed_up_campaign_results_by_explicit_list(tmp_path):
    """The 8-result Kaggle backup scenario: files restored into a fresh
    checkout persist via an explicit id list (no recompute, exact staging)."""
    repo = _init_repo(tmp_path / "repo")
    campaign = (Path(__file__).resolve().parent.parent
                / "data" / "batches" / "p2")
    restored = sorted(p.stem for p in campaign.glob("*.json"))
    assert restored, "expected committed campaign fixtures under data/batches/p2"
    dest = repo / "data" / "batches" / "p2"
    dest.mkdir(parents=True, exist_ok=True)
    for stem in restored:
        (dest / f"{stem}.json").write_text(
            (campaign / f"{stem}.json").read_text(encoding="utf-8"),
            encoding="utf-8")
        validate_p2_result_file(dest / f"{stem}.json", stem)
    info = persist_p2_results(repo, dest, restored,
                              "p2 restore shard: campaign backup persisted")
    assert info["files"] == [f"data/batches/p2/{s}.json" for s in restored]
    assert _staged(repo) == []
    show = _git(repo, "show", "--name-only", "--format=", info["commit"])
    assert sorted(show.stdout.split()) == info["files"]


# --------------------------------------------------------------------------
# branch naming + run_p2 resolution
# --------------------------------------------------------------------------

def test_worker_branch_deterministic_and_safe():
    assert (p2_worker_branch("kaggle-gpu-1", 3, 44)
            == "worker/p2/kaggle-gpu-1-s3-of44")
    assert resolve_push_branch("auto", "kaggle-gpu-1", 3, 44) == \
        "worker/p2/kaggle-gpu-1-s3-of44"
    assert resolve_push_branch("p2-gpu-validation-s0", "w", 0, 2) == \
        "p2-gpu-validation-s0"  # explicit branch passes through (CLI compat)
    assert p2_worker_branch("bad name!/$", 0, 1) == "worker/p2/bad-name----s0-of1"
    assert p2_worker_branch("", 0, 1).startswith("worker/p2/worker-s0-of1")


# --------------------------------------------------------------------------
# H. scientific invariance: frozen P2 protocol constants
# --------------------------------------------------------------------------

def test_h_p2_protocol_constants_frozen():
    p = P2_PROTOCOL_DEFAULTS
    assert p["temperature_K"] == 550.0
    assert p["timestep_fs"] == 1.0
    assert p["equil_steps"] == 2000
    assert p["production_steps"] == 8000
    assert p["sample_interval_steps"] == 10
    assert p["thermostat"] == "langevin"
    assert p["friction_fs_inv_provisional"] == 0.02
    assert p["fix_center_of_mass"] is True
    assert p["mobile_species"] == "Li"
    assert p["base_seed"] == 550
    assert P2_PRODUCTION_TIERS_PROVISIONAL == (1000, 3000, 8000)
    assert P2_PROTOCOL_VERSION == "p2-adaptive-v1-provisional"
    assert P2_TRAJECTORY_POLICY == "adaptive-1000-3000-8000-v1-provisional"
    # Guards/thresholds referenced by the frozen evaluator (PROVISIONAL).
    assert p["host_rmsd_fail_A_provisional"] == 1.0
    assert p["lindemann_fail_provisional"] == 0.20
    assert p["min_distance_fail_A_provisional"] == 0.8
    assert p["explosion_abort_A_provisional"] == 3.0


# --------------------------------------------------------------------------
# Regression: relative repo_root (".") with absolute output dir (Kaggle).
# run_p2 calls persist_p2_results(".", args.out, ...) where args.out is an
# absolute path (/kaggle/working/...); naive relative_to(".") raised
# ValueError "'.../aa00.json' is not in the subpath of '.'". Both sides
# must be normalized consistently before relativizing.
# --------------------------------------------------------------------------

def test_regression_relative_repo_root_with_absolute_out_dir(
        tmp_path, monkeypatch):
    from rudeus.mlip.gitpush import select_commit_files
    repo = _init_repo(tmp_path / "repo")
    _, p2out, _ = _run_stub_p2(tmp_path / "work", ["aa00", "bb01"])
    p2dir = _move_p2_into_repo(p2out, repo)
    monkeypatch.chdir(repo)  # so repo_root="." resolves to this repo
    assert select_commit_files(".", str(p2dir.resolve())) == [
        "data/batches/p2/aa00.json", "data/batches/p2/bb01.json"]
    info = persist_p2_results(
        ".", str(p2dir.resolve()), ["aa00", "bb01"],
        "p2 test-worker shard 0/44: 2 processed, 0 errored")
    assert info["files"] == ["data/batches/p2/aa00.json",
                             "data/batches/p2/bb01.json"]
    show = _git(repo, "show", "--name-only", "--format=", info["commit"])
    assert sorted(show.stdout.split()) == info["files"]
    assert _staged(repo) == []


def test_regression_absolute_outside_repo_still_rejected(
        tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (outside / "aa00.json").write_text(
        json.dumps({"batch_id": "aa00",
                    "result": {"p2_verdict": "PASS"}}), encoding="utf-8")
    monkeypatch.chdir(repo)
    with pytest.raises(GitSafetyError):
        persist_p2_results(".", str(outside.resolve()), ["aa00"], "msg")
    assert _staged(repo) == []  # nothing staged, worktree untouched
    assert (outside / "aa00.json").is_file()
