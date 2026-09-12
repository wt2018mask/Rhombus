"""Worker-side git safety: commit ONLY generated P1 outputs, never user changes.

Rules (spec section 15):
  - The intended set is exactly done_dir/*.json (relative repo paths).
  - If anything else is already staged, ABORT without touching the index —
    pre-existing staged user changes are never swept into a worker commit
    (this exact accident happened in Stage 1).
  - After `git add`, re-verify the staged set equals the intended set;
    on mismatch, unstage exactly what was added and abort.
  - Push failures propagate; local outputs are never deleted.
  - No locks, no daemon; restartable (re-running recommits nothing new).
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Dict, List, Union


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


def select_commit_files(repo_root: Union[str, Path],
                        done_dir: Union[str, Path]) -> List[str]:
    """Intended commit set: done_dir/*.json as repo-relative paths, sorted."""
    repo_root, done_path = Path(repo_root), Path(done_dir)
    if not done_path.is_absolute():
        done_path = repo_root / done_path
    files = sorted(p for p in done_path.glob("*.json") if p.is_file())
    return sorted(str(p.relative_to(repo_root)).replace("\\", "/")
                  for p in files)


def commit_done_files(repo_root: Union[str, Path],
                      done_dir: Union[str, Path],
                      message: str) -> Dict[str, object]:
    """Commit exactly the done files. Aborts (no index change) on any surprise."""
    intended = select_commit_files(repo_root, done_dir)
    if not intended:
        raise GitSafetyError("no done files to commit")
    foreign = [f for f in _staged_files(repo_root) if f not in set(intended)]
    if foreign:
        raise GitSafetyError(
            "refusing to commit: unrelated files already staged: "
            + ", ".join(foreign))
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


def push_branch(repo_root: Union[str, Path], branch: str,
                remote: str = "origin") -> Dict[str, object]:
    """Push HEAD to a dedicated worker branch. Never main. No credentials stored.

    Authentication comes from the environment (prompt/agent). On failure the
    exception propagates and local outputs remain untouched.
    """
    if branch in ("main", "master"):
        raise GitSafetyError("refusing to push directly to main/master")
    r = _git(repo_root, "push", remote, f"HEAD:refs/heads/{branch}")
    if r.returncode != 0:
        raise GitSafetyError(f"git push failed: {(r.stdout + r.stderr)[:500]}")
    return {"branch": branch, "remote": remote,
            "output": (r.stdout + r.stderr)[-500:]}
