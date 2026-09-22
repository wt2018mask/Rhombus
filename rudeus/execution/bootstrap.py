"""Standalone -I -S bootstrap. Only standard library imports precede checks."""
import hashlib
import importlib.abc
import importlib.machinery
import json
from pathlib import Path
import sys


def check_snapshot(root, bundle):
    root = Path(root).resolve()
    expected = {item["relative_path"]: item for item in bundle["files"]}
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() or p.is_symlink()}
    if actual != set(expected):
        raise ValueError("prepared code inventory differs from verified bundle")
    for name, item in expected.items():
        path = root/name
        if (path.resolve() != path or not path.resolve().is_relative_to(root)
                or path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != item["raw_sha256"]):
            raise ValueError(f"prepared code mismatch: {name}")


class OriginGuard(importlib.abc.MetaPathFinder):
    def __init__(self, root, bundle, dependency_roots, standard_roots):
        self.root = Path(root).resolve()
        self.files = {item["relative_path"]: item for item in bundle["files"]}
        self.dependencies = [Path(p).resolve() for p in dependency_roots]
        self.standard = [Path(p).resolve() for p in standard_roots]

    def location(self, path, dependency_only=False):
        path = Path(path).resolve()
        roots = [(f"dependency:{i}", p) for i, p in enumerate(self.dependencies)]
        if not dependency_only:
            roots = [("bundle", self.root)] + roots + [(f"stdlib:{i}", p) for i, p in enumerate(self.standard)]
        for label, root in roots:
            if path.is_relative_to(root):
                return f"{label}/{path.relative_to(root).as_posix()}"
        raise ValueError(f"module origin outside controlled import roots: {path}")

    def check(self, fullname, origin):
        path = Path(origin).resolve()
        label = self.location(path)
        if fullname == "rudeus" or fullname.startswith("rudeus."):
            if not path.is_relative_to(self.root):
                raise ValueError(f"alternate repository import root: {fullname}")
            relative = path.relative_to(self.root).as_posix()
            item = self.files.get(relative)
            if item is None or hashlib.sha256(path.read_bytes()).hexdigest() != item["raw_sha256"]:
                raise ValueError(f"repository module differs from bundle: {fullname}")
        return label

    def find_spec(self, fullname, path=None, target=None):
        spec = importlib.machinery.PathFinder.find_spec(fullname, path, target)
        if spec:
            if spec.origin not in (None, "built-in", "frozen"):
                self.check(fullname, spec.origin)
            for location in spec.submodule_search_locations or ():
                self.location(location)
        return spec

    def find_distributions(self, context=None):
        # Keep normal installed-package metadata discovery without restoring
        # ambient import finders or executing .pth/site customization files.
        return importlib.machinery.PathFinder.find_distributions(context)


def run(context):
    if not (sys.flags.isolated and sys.flags.no_site and sys.flags.dont_write_bytecode):
        raise ValueError("bootstrap requires -I -S -B")
    root = Path(__file__).resolve().parents[2]
    check_snapshot(root, context["bundle"])
    standard = tuple(sys.path)
    dependencies = context["dependency_roots"]
    if any(not Path(p).is_absolute() or not Path(p).is_dir() for p in dependencies):
        raise ValueError("dependency roots must be explicit existing absolute directories")
    if any((Path(p)/"rudeus").exists() for p in dependencies):
        raise ValueError("dependency root contains alternate repository package")
    guard = OriginGuard(root, context["bundle"], dependencies, standard)
    sys.path[:] = [str(root), *standard, *dependencies]
    sys.meta_path[:] = [importlib.machinery.BuiltinImporter, importlib.machinery.FrozenImporter, guard]
    # Snapshot checks have completed before any repository/application import.
    from rudeus.execution.code_bundle import CodeBundle
    from rudeus.execution.contracts import TaskSpec
    from rudeus.execution.runtime import ExecutionManifest, capture_runtime, verify_execution_records
    from rudeus.science.contracts import canonical_bytes
    from rudeus.science.evidence import EvidenceStore, append_file
    task = TaskSpec.from_dict(context["task"])
    bundle = CodeBundle.from_dict(context["bundle"])
    if bundle.bundle_hash != context["bundle_hash"] or bundle.code_revision != task.code_revision:
        raise ValueError("bootstrap task/bundle identity mismatch")
    from rudeus.execution.local import execute_local
    runtime = capture_runtime(guard)
    manifest = ExecutionManifest(attempt_id=context["attempt_id"], task_content_hash=task.content_hash,
        bundle_hash=bundle.bundle_hash, runtime_record_hash=runtime.content_hash)
    statuses = verify_execution_records(manifest, manifest.content_hash, runtime, runtime.content_hash, bundle, task)
    store = EvidenceStore(context["store_root"])
    for directory, record in (("code_bundles", bundle), ("runtime_records", runtime), ("execution_manifests", manifest)):
        append_file(store.path(f"{directory}/{record.content_hash}.json"), canonical_bytes(record))
    result = execute_local(task, store, launch_context=(manifest, runtime, bundle))
    check_snapshot(root, context["bundle"])
    return {**result, **statuses, "repository_bundle": "VERIFIED",
            "execution_manifest_hash": manifest.content_hash, "runtime_record_hash": runtime.content_hash,
            "bundle_hash": bundle.bundle_hash}


def _failure_class_name(exc):
    """Canonical failure class name for standalone failure reporting.

    Preserves an ExecutionError's own classification first, then uses the
    canonical classifier. The import stays lazy because only standard library
    imports may precede checks under -I -S -B; if the canonical import is
    unavailable, the previous stdlib-only mapping is kept so reporting never
    breaks.
    """
    failure = getattr(getattr(exc, "failure_class", None), "value", None)
    if failure is not None:
        return failure
    try:
        from rudeus.execution.contracts import classify_failure
    except ImportError:
        return ("INTEGRITY" if isinstance(exc, ValueError)
                else "RESOURCE" if isinstance(exc, MemoryError) else "SOFTWARE")
    return classify_failure(exc).value


if __name__ == "__main__":
    try:
        result = run(json.loads(Path(sys.argv[1]).read_bytes()))
    except Exception as exc:
        result = {"artifact_status": "FAILED", "failure_class": _failure_class_name(exc),
                  "reason": str(exc), "actual_execution_identity": "NOT_ATTESTED"}
    Path(sys.argv[2]).write_text(json.dumps(result, sort_keys=True), encoding="utf-8")
    raise SystemExit(0 if result.get("artifact_status") == "VERIFIED_LOCAL" else 1)
