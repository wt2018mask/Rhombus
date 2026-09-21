"""Captured runtime observations and execution references; no attestation."""
from dataclasses import dataclass
import hashlib
import importlib.metadata
import platform
from pathlib import Path
import sys
import sysconfig

from rudeus.execution.contracts import ExecutionError
from rudeus.science.contracts import Record, require_hash

POLICY = "isolated-local-v1"


@dataclass(frozen=True, kw_only=True)
class RuntimeRecord(Record):
    interpreter: dict
    launch_flags: dict
    dependencies: dict
    modules: tuple
    unavailable_reasons: tuple[str, ...]
    version: str = "runtime-observations-v1"
    coverage: str = "PARTIAL_OBSERVATIONS"

    def validate(self):
        super().validate()
        if self.version != "runtime-observations-v1" or self.coverage != "PARTIAL_OBSERVATIONS":
            raise ValueError("unsupported runtime observation contract")


@dataclass(frozen=True, kw_only=True)
class ExecutionManifest(Record):
    attempt_id: str
    task_content_hash: str
    bundle_hash: str
    runtime_record_hash: str
    launch_policy_version: str = POLICY
    version: str = "execution-manifest-v1"

    def validate(self):
        super().validate()
        if self.version != "execution-manifest-v1" or self.launch_policy_version != POLICY:
            raise ValueError("unsupported execution manifest policy")
        for value in (self.attempt_id, self.task_content_hash, self.bundle_hash, self.runtime_record_hash):
            require_hash(value)


def verify_execution_records(manifest, manifest_hash, runtime, runtime_hash, bundle, task):
    """Verify record contents and references, not their historical truth."""
    try:
        manifest = manifest if isinstance(manifest, ExecutionManifest) else ExecutionManifest.from_dict(manifest)
        runtime = runtime if isinstance(runtime, RuntimeRecord) else RuntimeRecord.from_dict(runtime)
        require_hash(manifest_hash)
        require_hash(runtime_hash)
        if not (manifest.content_hash == manifest_hash and runtime.content_hash == runtime_hash
                and manifest.runtime_record_hash == runtime_hash
                and manifest.task_content_hash == task.content_hash
                and manifest.bundle_hash == bundle.bundle_hash
                and bundle.code_revision == task.code_revision):
            raise ValueError("execution record binding mismatch")
        return {"execution_manifest": "VERIFIED", "runtime_record": "VERIFIED",
                "actual_execution_identity": "NOT_ATTESTED"}
    except (ValueError, TypeError, KeyError) as exc:
        raise ExecutionError(str(exc), "INTEGRITY") from exc


def file_identity(path, unavailable, label):
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except (OSError, TypeError) as exc:
        unavailable.append(f"{label}: {type(exc).__name__}")
        return None


def capture_runtime(guard):
    """Capture after application imports, before computation; paths are relative
    to named roots. Absolute host locations remain in separate diagnostics.
    """
    unavailable = ["observed before computation; later imports and dynamic/native execution are not exhaustively captured",
                   "observations are not independent execution proof"]
    modules = []
    for name, module in sorted(list(sys.modules.items())):
        if module is None:
            continue
        spec = getattr(module, "__spec__", None)
        origin = getattr(spec, "origin", None)
        path = getattr(module, "__file__", None)
        if origin in ("built-in", "frozen"):
            modules.append({"name": name, "origin": origin, "raw_sha256": None})
            continue
        if path:
            if origin and Path(origin).resolve() != Path(path).resolve():
                raise ExecutionError(f"module origin mismatch: {name}", "INTEGRITY")
            label = guard.check(name, path)
            modules.append({"name": name, "origin": label,
                            "raw_sha256": file_identity(path, unavailable, name)})
        elif name != "__main__":
            unavailable.append(f"{name}: namespace or unavailable file origin")
    dependencies = {}
    for package in ("numpy", "scipy", "ase"):
        try:
            dist = importlib.metadata.distribution(package)
            # Verify metadata came from the explicitly configured package roots.
            root = guard.location(dist.locate_file(""), dependency_only=True)
            module = sys.modules.get(package)
            module_file = getattr(module, "__file__", None)
            if module_file and not Path(module_file).resolve().is_relative_to(Path(dist.locate_file("")).resolve()):
                raise ExecutionError(f"dependency metadata/module origin mismatch: {package}", "INTEGRITY")
            dependencies[package] = {"version": dist.version, "origin": root}
        except importlib.metadata.PackageNotFoundError:
            dependencies[package] = {"version": None, "origin": None}
            unavailable.append(f"{package}: distribution metadata unavailable")
    library = sysconfig.get_config_var("LDLIBRARY")
    if sys.platform == "win32":
        library_path = Path(sys.base_prefix)/f"python{sys.version_info.major}{sys.version_info.minor}.dll"
    elif library and sysconfig.get_config_var("LIBDIR"):
        library_path = Path(sysconfig.get_config_var("LIBDIR"))/library
    else:
        library_path = None
    interpreter = {"implementation": platform.python_implementation(), "version": platform.python_version(),
                   "executable_sha256": file_identity(sys.executable, unavailable, "interpreter executable"),
                   "library_sha256": file_identity(library_path, unavailable, "interpreter library")}
    return RuntimeRecord(interpreter=interpreter,
        launch_flags={key: getattr(sys.flags, key) for key in
                      ("isolated", "ignore_environment", "no_user_site", "no_site", "dont_write_bytecode")},
        dependencies=dependencies, modules=tuple(modules), unavailable_reasons=tuple(sorted(unavailable)))
