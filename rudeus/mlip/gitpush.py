"""Worker-side git safety: commit ONLY generated worker outputs, never user changes.

Rules (spec section 15, extended to P2 Git-as-DB persistence):
  - The intended set is an EXPLICIT list of repo-relative paths (P2: exactly
    the result files written by this worker invocation; P1 legacy entry point
    passes done_dir/*.json as that explicit list).
  - Staging uses `git add -- <explicit paths>` ONLY. Never `git add .`,
    never `git add -A`, never a bare directory pathspec.
  - If anything else is already staged, ABORT without touching the index —
    pre-existing staged user changes are never swept into a worker commit
    (this exact accident happened in Stage 1).
  - After `git add`, re-verify the staged set equals the intended set;
    on mismatch, unstage exactly what was added and abort.
  - Push failures propagate; local outputs are never deleted, reset, or
    overwritten. A failed push keeps the local commit for later retry.
  - No locks, no daemon, no database; restartable (re-running with no new
    results commits nothing new).
  - Authentication comes from the environment (Kaggle `GITHUB_PAT` secret);
    no tokens are hardcoded, stored, or printed here.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Union


class GitSafetyError(Exception):
    """Raised when committing would sweep in unintended files."""


def _git(repo_root: Union[str, Path], *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args],
        cwd=str(repo_root), capture_output=True, text=True)


def _staged_files(repo_root: Union[str, Path]) -> List[str]:
    r = _git(repo_root, "diff", "--cached", "--name-only")
    if r.returncode != 0:
        raise GitSafetyError(f"git diff --cached failed: {r.stderr[:300]}")
    return sorted(l for l in r.stdout.splitlines() if l.strip())


def _repo_relative_path(repo_root: Path, path: Union[str, Path]) -> str:
    """Normalize `path` against `repo_root` to a repo-relative POSIX path.

    Both sides are resolved to absolute normalized form first, so an
    absolute output dir combined with a relative repo_root (e.g. "." as used
    by run_p2/run_p1 on Kaggle workers) no longer trips `relative_to`.
    Paths resolving outside the repository are rejected (never staged).
    """
    repo_root = Path(repo_root).resolve()
    try:
        rel = Path(path).resolve().relative_to(repo_root)
    except ValueError:
        raise GitSafetyError(
            f"refusing to use file outside repository: {path}")
    return rel.as_posix()


def select_commit_files(repo_root: Union[str, Path],
                        done_dir: Union[str, Path]) -> List[str]:
    """Intended commit set: done_dir/*.json as repo-relative paths, sorted."""
    repo_root, done_path = Path(repo_root).resolve(), Path(done_dir)
    if not done_path.is_absolute():
        done_path = repo_root / done_path
    files = sorted(p for p in done_path.glob("*.json") if p.is_file())
    return sorted(_repo_relative_path(repo_root, p) for p in files)


def commit_only_files(repo_root: Union[str, Path],
                      files: Sequence[str],
                      message: str) -> Dict[str, object]:
    """Commit EXACTLY the listed repo-relative files. Nothing else.

    `files` must be a non-empty list of repo-relative posix paths (no `..`,
    no absolute paths, no directories). Staging is `git add -- <files>` only;
    this function never runs `git add .` / `git add -A`. Any unrelated
    already-staged file aborts with no index change; any post-add divergence
    unstages exactly our adds and aborts. Unstaged/unrelated working-tree
    modifications are left untouched.
    """
    intended = sorted(set(files))
    if not intended:
        raise GitSafetyError("no files to commit")
    repo_root = Path(repo_root)
    for f in intended:
        if not isinstance(f, str) or not f or f.startswith("/") \
                or f.startswith("\\") or ".." in Path(f).parts:
            raise GitSafetyError(f"refusing to commit unsafe path: {f!r}")
        if not (repo_root / Path(*Path(f).parts)).is_file():
            raise GitSafetyError(f"refusing to commit missing file: {f!r}")
    foreign = [f for f in _staged_files(repo_root) if f not in set(intended)]
    if foreign:
        raise GitSafetyError(
            "refusing to commit: unrelated files already staged: "
            + ", ".join(foreign))
    # Exact staging: explicit pathspec only. NEVER `git add .` / `git add -A`.
    r = _git(repo_root, "add", "--", *intended)
    if r.returncode != 0:
        raise GitSafetyError(f"git add failed: {r.stderr[:300]}")
    staged = _staged_files(repo_root)
    if staged != intended:
        _git(repo_root, "reset", "--", *intended)  # unstage exactly our adds
        raise GitSafetyError(
            f"staged set diverged from intended set after add: {staged}")
    r = _git(repo_root, "commit", "-m", message)
    if r.returncode != 0:
        raise GitSafetyError(f"git commit failed: {(r.stdout + r.stderr)[:500]}")
    sha = _git(repo_root, "rev-parse", "HEAD").stdout.strip()
    return {"commit": sha, "files": intended}


def commit_done_files(repo_root: Union[str, Path],
                      done_dir: Union[str, Path],
                      message: str) -> Dict[str, object]:
    """Commit exactly the done files. Aborts (no index change) on any surprise.

    Legacy P1 entry point: the intended set is done_dir/*.json, passed as an
    explicit file list to :func:`commit_only_files` (same safety contract).
    """
    intended = select_commit_files(repo_root, done_dir)
    if not intended:
        raise GitSafetyError("no done files to commit")
    return commit_only_files(repo_root, intended, message)


def p2_worker_branch(worker: str, shard: int, of: int) -> str:
    """Deterministic P2 worker branch: worker/p2/<worker>-s<shard>-of<of>.

    Identifies the worker/run without coordination. Never main/master, never
    force-pushed (see :func:`push_branch`). `worker` is sanitized to
    `[A-Za-z0-9_-]` so the result is always a valid ref name.
    """
    clean = re.sub(r"[^A-Za-z0-9_-]", "-", str(worker or "").strip()) or "worker"
    return f"worker/p2/{clean}-s{int(shard)}-of{int(of)}"


def p25_worker_branch(worker: str, shard: int, of: int) -> str:
    """Deterministic P2.5 worker branch: worker/p25/<worker>-s<shard>-of<of>.

    Same contract as :func:`p2_worker_branch`: never main/master, never
    force-pushed, sanitized worker name.
    """
    clean = re.sub(r"[^A-Za-z0-9_-]", "-", str(worker or "").strip()) or "worker"
    return f"worker/p25/{clean}-s{int(shard)}-of{int(of)}"


def validate_p2_result_file(path: Union[str, Path],
                            batch_id: str) -> Dict[str, object]:
    """Structural integrity gate for one P2 result file (opaque to science).

    Checks: file exists, parses as JSON, top-level batch_id matches, and a
    `result` mapping carrying a `p2_verdict` is present. No scientific
    reinterpretation: PASS/FAIL/INDETERMINATE/ERROR are accepted as-is.
    Raises GitSafetyError on any defect; the file itself is never modified.
    """
    path = Path(path)
    if not path.is_file():
        raise GitSafetyError(f"p2 result file missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise GitSafetyError(f"p2 result file malformed ({path.name}): {e}")
    if not isinstance(payload, dict) or payload.get("batch_id") != batch_id:
        raise GitSafetyError(
            f"p2 result file {path.name} does not belong to batch {batch_id}")
    result = payload.get("result")
    if not isinstance(result, dict) or "p2_verdict" not in result:
        raise GitSafetyError(
            f"p2 result file {path.name} has no valid result/p2_verdict")
    return {"batch_id": batch_id, "p2_verdict": result["p2_verdict"]}


def validate_traj_artifact_file(path: Union[str, Path],
                                expected_sha256: str) -> Dict[str, object]:
    """Integrity gate for one P2 trajectory artifact (opaque to science).

    Checks: file exists, loads as a trajectory artifact, and its canonical
    SHA256 (same definition as the P2 JSON binding) equals
    `expected_sha256`. Raises GitSafetyError on any defect (missing,
    malformed, or hash mismatch); the file itself is never modified.
    """
    from rudeus.mlip.p2_traj import verify_traj_artifact
    try:
        payload = verify_traj_artifact(path, expected_sha256)
    except Exception as e:
        raise GitSafetyError(
            f"p2 trajectory artifact invalid ({Path(path).name}): {e}")
    return {"n_production_frames": payload["n_production_frames"],
            "sha256": expected_sha256}


def persist_p2_results(repo_root: Union[str, Path],
                       p2_dir: Union[str, Path],
                       batch_ids: Sequence[str],
                       message: str,
                       traj_dir: Optional[Union[str, Path]] = None,
                       ) -> Dict[str, object]:
    """Validate + commit EXACTLY this worker's P2 result files.

    `batch_ids` are the results written by this invocation (or an explicit
    restore list, e.g. the backed-up campaign results copied into a fresh
    checkout). Each `p2_dir/<batch_id>.json` is integrity-checked, then the
    exact set is committed via :func:`commit_only_files`. Unrelated files are
    never staged; local results are never deleted. Push is separate
    (:func:`push_branch`) so a push failure keeps the local commit for retry.

    When `traj_dir` is given, each result that carries a
    `trajectory_artifact` binding additionally requires its recorded
    artifact (resolved repo-relative against `repo_root`) to exist and
    rehash to the recorded SHA256; verified artifact files join the same
    single commit. Results without a binding (legacy results, ERROR
    records) commit JSON-only. A missing or mismatched artifact for a
    bound result aborts with no index change (fail closed).
    """
    batch_ids = sorted(set(batch_ids))
    if not batch_ids:
        raise GitSafetyError("no p2 results to persist")
    repo_root = Path(repo_root).resolve()
    p2_path = Path(p2_dir)
    if not p2_path.is_absolute():
        p2_path = repo_root / p2_path
    intended: List[str] = []
    for bid in batch_ids:
        if not isinstance(bid, str) or not bid or "/" in bid or "\\" in bid \
                or ".." in bid:
            raise GitSafetyError(f"refusing to persist unsafe batch id: {bid!r}")
        target = p2_path / f"{bid}.json"
        validate_p2_result_file(target, bid)
        intended.append(_repo_relative_path(repo_root, target))
        if traj_dir is None:
            continue
        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
            binding = (payload.get("result") or {}).get("trajectory_artifact")
        except Exception as e:
            raise GitSafetyError(
                f"p2 result file {target.name} unreadable for artifact "
                f"binding check: {e}")
        if not isinstance(binding, dict):
            continue  # legacy/ERROR result: JSON-only, nothing to bind
        for key in ("path", "sha256"):
            if not isinstance(binding.get(key), str) or not binding[key]:
                raise GitSafetyError(
                    f"p2 result file {target.name} has a malformed "
                    f"trajectory_artifact binding")
        traj_target = Path(binding["path"])
        if not traj_target.is_absolute():
            traj_target = repo_root / traj_target
        validate_traj_artifact_file(traj_target, binding["sha256"])
        traj_rel = _repo_relative_path(repo_root, traj_target)
        # The trajectory is part of the provenance contract, but it may
        # already be tracked and byte-identical to HEAD. In that case there
        # is nothing to stage or commit for the artifact; it was still
        # integrity-verified above. Only add it to the commit set when Git
        # reports a working-tree/index change (including a new untracked file).
        status = _git(repo_root, "status", "--porcelain", "--", traj_rel)
        if status.returncode != 0:
            raise GitSafetyError(
                f"git status failed for trajectory artifact: {traj_rel}")
        if status.stdout.strip():
            intended.append(traj_rel)
    return commit_only_files(repo_root, intended, message)


def push_branch(repo_root: Union[str, Path], branch: str,
                remote: str = "origin") -> Dict[str, object]:
    """Push HEAD to a dedicated worker branch. Never main. No credentials stored.

    Authentication comes from the environment (Kaggle `GITHUB_PAT` secret or
    agent credential helper; never hardcoded or printed). On failure the
    exception propagates and local outputs/commits remain untouched for
    later retry. Never force-pushes; a divergent remote branch fails safe
    instead of overwriting.
    """
    if not branch or branch in ("main", "master"):
        raise GitSafetyError("refusing to push directly to main/master")
    r = _git(repo_root, "push", remote, f"HEAD:refs/heads/{branch}")
    if r.returncode != 0:
        raise GitSafetyError(f"git push failed: {(r.stdout + r.stderr)[:500]}")
    return {"branch": branch, "remote": remote,
            "output": (r.stdout + r.stderr)[-500:]}


def validate_p25_result_file(path: Union[str, Path],
                             batch_id: str) -> Dict[str, object]:
    """Structural integrity gate for one P2.5 result file (opaque to science).

    Checks: file exists, parses as JSON, top-level batch_id matches, and a
    `result` mapping carrying a `p25_verdict`/`transport_state` is present.
    No scientific reinterpretation: DIFFUSIVE/NONDIFFUSIVE/INDETERMINATE/
    ERROR are accepted as-is. Raises GitSafetyError on any defect; the
    file itself is never modified.
    """
    path = Path(path)
    if not path.is_file():
        raise GitSafetyError(f"p25 result file missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise GitSafetyError(f"p25 result file malformed ({path.name}): {e}")
    if not isinstance(payload, dict) or payload.get("batch_id") != batch_id:
        raise GitSafetyError(
            f"p25 result file {path.name} does not belong to batch {batch_id}")
    result = payload.get("result")
    if not isinstance(result, dict) or "transport_state" not in result:
        raise GitSafetyError(
            f"p25 result file {path.name} has no valid result/transport_state")
    return {"batch_id": batch_id,
            "transport_state": result["transport_state"]}


def persist_p25_results(repo_root: Union[str, Path],
                        p25_dir: Union[str, Path],
                        batch_ids: Sequence[str],
                        message: str) -> Dict[str, object]:
    """Validate + commit EXACTLY this worker's P2.5 result files.

    Same safety contract as :func:`persist_p2_results`: explicit file list
    only, foreign staged files abort with no index change, push is separate
    so failures keep the local commit for retry. P2.5 outputs are JSON
    only (trajectory artifacts were already committed by the P2 worker).
    """
    batch_ids = sorted(set(batch_ids))
    if not batch_ids:
        raise GitSafetyError("no p25 results to persist")
    repo_root = Path(repo_root).resolve()
    p25_path = Path(p25_dir)
    if not p25_path.is_absolute():
        p25_path = repo_root / p25_path
    intended: List[str] = []
    for bid in batch_ids:
        if not isinstance(bid, str) or not bid or "/" in bid or "\\" in bid \
                or ".." in bid:
            raise GitSafetyError(f"refusing to persist unsafe batch id: {bid!r}")
        target = p25_path / f"{bid}.json"
        validate_p25_result_file(target, bid)
        intended.append(_repo_relative_path(repo_root, target))
    return commit_only_files(repo_root, intended, message)
