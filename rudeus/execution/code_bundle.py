"""Committed repository inventory, never an attestation of executed code.

P3 execution-identity contract (I1):
- ``TaskSpec.code_revision`` is the requested Git source revision. It is
  declarative until proven by downstream verification.
- ``CodeBundle.bundle_hash`` is the canonical identity of the committed
  execution-byte inventory under scope ``rudeus-tree-plus-project-files-v1``.
- The controlled execution environment is instructed to materialize that
  inventory and re-verifies it before, during, and after execution.

CodeBundle.bundle_hash identifies the canonical committed execution-byte
inventory (scope ``rudeus-tree-plus-project-files-v1``) that the controlled
execution environment was instructed to materialize, as re-verified before,
during, and after execution. It does not, by itself, attest that the
computation process actually executed those bytes; ``actual_execution_identity``
therefore remains ``NOT_ATTESTED`` on every path.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path, PurePosixPath
import subprocess

from rudeus.execution.contracts import ExecutionError, TaskSpec
from rudeus.science.contracts import Record, canonical_bytes, require_hash

VERSION = "code-bundle-v1"
SCOPE = "rudeus-tree-plus-project-files-v1"
ROOT_FILES = {"pyproject.toml", "requirements.txt", "config.yaml"}
ENTRYPOINT = "rudeus/execution/local.py"


def _require(condition, message):
    if not condition:
        raise ExecutionError(message, "INTEGRITY")


def _oid(value, object_format):
    size = {"sha1": 40, "sha256": 64}.get(object_format)
    if not size or not isinstance(value, str) or len(value) != size or any(c not in "0123456789abcdef" for c in value):
        raise ValueError("invalid Git object identity")


def _scoped(path):
    return path in ROOT_FILES or path.startswith("rudeus/")


@dataclass(frozen=True, kw_only=True)
class CodeBundle(Record):
    code_revision: str
    git_object_format: str
    git_tree: str
    files: tuple
    version: str = VERSION
    scope_policy: str = SCOPE
    entrypoint: str = ENTRYPOINT

    def validate(self):
        super().validate()
        if (self.version, self.scope_policy, self.entrypoint) != (VERSION, SCOPE, ENTRYPOINT):
            raise ValueError("unsupported code bundle version, scope or entrypoint")
        _oid(self.code_revision, self.git_object_format)
        _oid(self.git_tree, self.git_object_format)
        paths = []
        for item in self.files:
            if set(item) != {"relative_path", "git_mode", "git_blob_oid", "raw_sha256"}:
                raise ValueError("invalid code inventory entry")
            path = item["relative_path"]
            if (not isinstance(path, str) or not _scoped(path) or "\\" in path
                    or PurePosixPath(path).is_absolute() or ".." in path.split("/")
                    or PurePosixPath(path).as_posix() != path):
                raise ValueError("external or noncanonical code path")
            if item["git_mode"] not in ("100644", "100755"):
                raise ValueError("only regular Git blobs are supported")
            _oid(item["git_blob_oid"], self.git_object_format)
            require_hash(item["raw_sha256"])
            paths.append(path)
        if paths != sorted(set(paths)) or not ROOT_FILES.union({ENTRYPOINT}) <= set(paths):
            raise ValueError("incomplete, duplicate or unsorted code inventory")

    @property
    def bundle_hash(self):
        """Canonical identity of the committed execution-byte inventory.

        This is the content hash of the inventory record itself: it names
        exactly which committed bytes were requested, not proof that any
        process executed them.
        """
        # Record.content_hash already hashes canonical_bytes(self), exactly once.
        return self.content_hash


def reconstruct_bundle(task: TaskSpec, *, git_root) -> CodeBundle:
    """Reconstruct from the requested commit, independent of checkout and HEAD.

    Git replacement objects and inherited Git repository/config overrides are
    disabled. No checkout filters, archive substitutions or application imports
    are used. External Python dependencies are outside repository-byte scope.
    """
    def git(*args):
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
        env.update(GIT_NO_REPLACE_OBJECTS="1", GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
        return subprocess.run(["git", "--no-replace-objects", "-C", str(Path(git_root)), *args],
                              env=env, check=True, capture_output=True).stdout
    try:
        object_format = git("rev-parse", "--show-object-format=storage").decode().strip()
        _oid(task.code_revision, object_format)
        _require(git("cat-file", "-t", task.code_revision).strip() == b"commit",
                 "requested code revision is not a commit")
        tree = git("rev-parse", "--verify", f"{task.code_revision}^{{tree}}").decode().strip()
        entries = git("ls-tree", "-r", "-z", "--full-tree", tree).split(b"\0")
        files = []
        for entry in entries:
            if not entry:
                continue
            metadata, raw_path = entry.split(b"\t", 1)
            path = raw_path.decode("utf-8")
            if not (_scoped(path) or path == "rudeus"):
                continue
            mode, kind, oid = metadata.decode("ascii").split()
            if mode not in ("100644", "100755") or kind != "blob":
                raise ExecutionError(f"unsupported scoped Git entry: {path} ({mode})", "UNSUPPORTED_INPUT")
            data = git("cat-file", "blob", oid)
            # Verify the object content as well as its external SHA256 identity.
            object_bytes = b"blob " + str(len(data)).encode("ascii") + b"\0" + data
            _require(hashlib.new(object_format, object_bytes).hexdigest() == oid, "Git blob identity mismatch")
            if data.splitlines()[:1] == [b"version https://git-lfs.github.com/spec/v1"]:
                raise ExecutionError(f"external LFS object is not bundled: {path}", "UNSUPPORTED_INPUT")
            files.append({"relative_path": path, "git_mode": mode, "git_blob_oid": oid,
                          "raw_sha256": hashlib.sha256(data).hexdigest()})
        return CodeBundle(code_revision=task.code_revision, git_object_format=object_format,
                          git_tree=tree, files=tuple(sorted(files, key=lambda item: item["relative_path"])))
    except ExecutionError:
        raise
    except (OSError, ValueError, TypeError, subprocess.CalledProcessError) as exc:
        raise ExecutionError(f"code bundle reconstruction failed: {exc}", "INTEGRITY") from exc


def verify_bundle(bundle, bundle_hash: str, task: TaskSpec, *, git_root):
    """Independently compare retained data/hash to the complete committed scope.

    Verification proves the retained bundle matches the complete committed
    inventory requested by ``task.code_revision``, but does not attest that
    the computation process actually executed those bytes.
    """
    try:
        require_hash(bundle_hash)
        retained = bundle if isinstance(bundle, CodeBundle) else CodeBundle.from_dict(bundle)
        _require(retained.bundle_hash == bundle_hash, "code bundle hash mismatch")
        expected = reconstruct_bundle(task, git_root=git_root)
        _require(canonical_bytes(retained) == canonical_bytes(expected),
                 "code bundle differs from requested committed inventory")
        return {"bundle_hash": bundle_hash, "repository_bundle": "VERIFIED",
                "execution_identity": "NOT_ATTESTED"}
    except ExecutionError:
        raise
    except (ValueError, TypeError, KeyError) as exc:
        raise ExecutionError(f"code bundle verification failed: {exc}", "INTEGRITY") from exc
