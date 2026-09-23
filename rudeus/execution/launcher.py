"""Explicit local launcher; invoke this absolute file with Python -I -S -B.

The installed launcher/control contracts are trusted local tooling. Application
code is imported only in a fresh, verified snapshot. No independent attestation.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid


def prepare_snapshot(task, bundle, bundle_hash, *, git_root, destination):
    from rudeus.execution.code_bundle import verify_bundle
    from rudeus.execution.contracts import ExecutionError
    verify_bundle(bundle, bundle_hash, task, git_root=git_root)
    destination = Path(destination).resolve()
    if not destination.is_dir() or any(destination.iterdir()):
        raise ExecutionError("execution directory must be fresh and empty", "INTEGRITY")
    env = {key: value for key, value in os.environ.items() if not key.upper().startswith("GIT_")}
    env.update(GIT_NO_REPLACE_OBJECTS="1", GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    for item in bundle.files:
        data = subprocess.run(["git", "--no-replace-objects", "-C", str(git_root), "cat-file", "blob",
            item["git_blob_oid"]], env=env, check=True, capture_output=True).stdout
        if hashlib.sha256(data).hexdigest() != item["raw_sha256"]:
            raise ExecutionError("committed code bytes changed during preparation", "INTEGRITY")
        path = destination/item["relative_path"]
        if not path.resolve().is_relative_to(destination):
            raise ExecutionError("external code path", "INTEGRITY")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as handle:
            handle.write(data)
        if os.name != "nt":
            path.chmod(0o755 if item["git_mode"] == "100755" else 0o644)
    # Verify the materialized files again before starting any subprocess.
    from rudeus.execution.bootstrap import check_snapshot
    check_snapshot(destination, bundle.to_dict())


def launch_local(task, bundle, bundle_hash, *, git_root, store_root, interpreter, dependency_roots, attempt_id=None):
    from rudeus.execution.contracts import ExecutionError
    from rudeus.science.contracts import canonical_bytes, digest
    interpreter = Path(interpreter)
    if not interpreter.is_absolute() or not interpreter.is_file():
        raise ExecutionError("an explicit absolute interpreter is required", "UNSUPPORTED_INPUT")
    if any(not Path(path).is_absolute() for path in dependency_roots):
        raise ExecutionError("dependency roots must be absolute", "UNSUPPORTED_INPUT")
    roots = [str(Path(path).resolve()) for path in dependency_roots]
    if not roots or any(not Path(path).is_dir() for path in roots):
        raise ExecutionError("explicit dependency directories are required", "UNSUPPORTED_INPUT")
    with tempfile.TemporaryDirectory(prefix="rhombus-controlled-") as temporary:
        work = Path(temporary)
        code = work/"code"
        code.mkdir()
        prepare_snapshot(task, bundle, bundle_hash, git_root=git_root, destination=code)
        bootstrap = code/"rudeus/execution/bootstrap.py"
        if not bootstrap.is_file():
            raise ExecutionError("requested revision does not support controlled launch", "UNSUPPORTED_INPUT")
        context = {"task": task.to_dict(), "bundle": bundle.to_dict(), "bundle_hash": bundle_hash,
                   "attempt_id": attempt_id or digest({"task": task.content_hash, "nonce": uuid.uuid4().hex}),
                   "store_root": str(Path(store_root).resolve()), "dependency_roots": roots}
        context_path, response = work/"context.json", work/"response.json"
        context_path.write_bytes(canonical_bytes(context))
        env = {key: value for key, value in os.environ.items()
               if not key.upper().startswith(("PYTHON", "GIT_"))}
        run = subprocess.run([str(interpreter), "-I", "-S", "-B", str(bootstrap),
                              str(context_path), str(response)], cwd=work, env=env, capture_output=True)
        if not response.is_file():
            raise ExecutionError(f"bootstrap failed (exit {run.returncode}): "
                                 + run.stderr.decode(errors="replace")[-2000:], "SOFTWARE")
        result = json.loads(response.read_text(encoding="utf-8"))
        if (run.returncode == 0) != (result.get("artifact_status") == "VERIFIED_LOCAL"):
            raise ExecutionError("inconsistent bootstrap exit/result", "INTEGRITY")
        if "execution_manifest_hash" in result:
            from rudeus.execution.code_bundle import CodeBundle
            from rudeus.execution.runtime import ExecutionManifest, RuntimeRecord, verify_execution_records
            from rudeus.science.evidence import EvidenceStore
            store = EvidenceStore(store_root)
            def read_record(directory, identity, cls):
                from rudeus.science.contracts import require_hash
                require_hash(identity)
                data = store.path(f"{directory}/{identity}.json").read_bytes()
                record = cls.from_dict(json.loads(data))
                if record.content_hash != identity or canonical_bytes(record) != data:
                    raise ExecutionError("retained execution record differs from its hash", "INTEGRITY")
                return record
            retained = read_record("code_bundles", bundle_hash, CodeBundle)
            manifest = read_record("execution_manifests", result["execution_manifest_hash"], ExecutionManifest)
            runtime = read_record("runtime_records", result["runtime_record_hash"], RuntimeRecord)
            statuses = verify_execution_records(manifest, manifest.content_hash, runtime,
                                                 runtime.content_hash, retained, task)
            if not (manifest.attempt_id == context["attempt_id"] == result["attempt"]["attempt_id"]
                    and result["attempt"]["task_content_hash"] == task.content_hash
                    and result["attempt"]["environment"]["execution_manifest_hash"] == manifest.content_hash
                    and retained == bundle):
                raise ExecutionError("bootstrap execution references differ from launch context", "INTEGRITY")
            result.update(statuses)
        elif result.get("artifact_status") == "VERIFIED_LOCAL":
            raise ExecutionError("completed bootstrap has no retained execution manifest", "INTEGRITY")
        result["actual_execution_identity"] = "NOT_ATTESTED"
        return result


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task")
    parser.add_argument("bundle")
    parser.add_argument("--bundle-hash", required=True)
    parser.add_argument("--git-root", required=True)
    parser.add_argument("--store-root", required=True)
    parser.add_argument("--interpreter", required=True)
    parser.add_argument("--dependency-root", action="append", required=True)
    args = parser.parse_args()
    if not (sys.flags.isolated and sys.flags.no_site and sys.flags.dont_write_bytecode):
        parser.error("invoke the explicit launcher file with -I -S -B")
    # This explicit launcher installation is the local tooling trust boundary;
    # neither caller CWD nor PYTHONPATH supplies control modules.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from rudeus.execution.code_bundle import CodeBundle
    from rudeus.execution.contracts import TaskSpec, classify_failure
    try:
        result = launch_local(TaskSpec.from_dict(json.loads(Path(args.task).read_bytes())),
            CodeBundle.from_dict(json.loads(Path(args.bundle).read_bytes())), args.bundle_hash,
            git_root=args.git_root, store_root=args.store_root, interpreter=args.interpreter,
            dependency_roots=args.dependency_root)
    except Exception as exc:
        result = {"artifact_status": "FAILED", "failure_class": classify_failure(exc).value,
                  "reason": str(exc), "actual_execution_identity": "NOT_ATTESTED"}
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("artifact_status") == "VERIFIED_LOCAL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
