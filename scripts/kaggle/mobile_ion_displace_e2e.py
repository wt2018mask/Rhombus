#!/usr/bin/env python3
"""Fail-closed CPU scientific E2E driver for mobile-ion-displace-v2.

This file is intentionally an operational harness.  It calls the repository
generator and validates its persisted observational artifact; it does not
implement or authorize scientific production behavior.
"""

from __future__ import annotations

import hashlib
import base64
import importlib
import importlib.metadata
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path


TEST_IDENTITY = "mobile-ion-displace-v2"
CONFIG_IDENTITY = (
    "candidate-supply-v2-mobile-ion-displace-li-sigma-030-035-040-seeds-42-45"
)
M6A_CONFIG_IDENTITY = "candidate-supply-v2-m6a-li-sigma-035-seeds-42-43-12p-d8-v1"
M6B_CONFIG_IDENTITY = "candidate-supply-v2-m6b-li-sigma-035-seeds-44-45-46-family-balanced-15p-d8-v1"
M6A_PARENT_FAILURE_BANDS = {
    "GE_10": (("obelix:5z0", 12), ("obelix:9zk", 12),
              ("obelix:bq9", 12), ("obelix:br1", 12)),
    "5_TO_9": (("obelix:47i", 7), ("obelix:5bz", 7),
               ("obelix:5zv", 7), ("obelix:an2", 6)),
    "2_TO_4": (("obelix:1xt", 3), ("obelix:2uv", 3),
               ("obelix:3rx", 2), ("obelix:4ba", 3)),
}
M6A_PARENT_IDS = tuple(
    parent_id for band in M6A_PARENT_FAILURE_BANDS.values()
    for parent_id, _count in band
)
M6A_SIGMA = 0.35
M6A_SEEDS = (42, 43)
M6A_TARGET_SPECIES = "Li"
M6A_OPERATOR_NAME = "mobile-ion-local-clearance-gaussian-radius"
M6A_OPERATOR_VERSION = "mobile-ion-local-clearance-gaussian-radius-v1"
M6A_DIRECTION_BUDGET = 8
M6A_VERSION_9_FREEZE_SHA256 = "0cf58202ee92bb9f604554ad45e97b2cdf0a0b097be0292b43db64ddc3a7f303"
M6A_VERSION_9_PANEL_SHA256 = "0dffa1bc6585d2bf20d042f52856ce71ee9f7b46c2aff4e2b22e0bb923fd37b4"
M6B_PARENT_IDS = (
    "obelix:4kt", "obelix:be9", "obelix:l9v",
    "obelix:11b", "obelix:883", "obelix:95j",
    "obelix:00x", "obelix:7cr", "obelix:9lo",
    "obelix:4p7", "obelix:dc8", "obelix:goi",
    "obelix:0iv", "obelix:1e9", "obelix:b4c",
)
M6B_PARENT_FAMILIES = (
    "halide", "halide", "halide", "other", "other", "other",
    "oxide", "oxide", "oxide", "oxyhalide", "oxyhalide", "oxyhalide",
    "sulfide", "sulfide", "sulfide",
)
M6B_SIGMA = 0.35
M6B_SEEDS = (44, 45, 46)
M6B_DIRECTION_BUDGET = 8
M6B_SELECTION_RULE = (
    "From the verified pre-M6-A version-9 diagnostic panel, exclude every M6-A parent; "
    "within each of its five available chemical-family strata, sort eligible parent IDs "
    "lexically and select the first three. Preserve family order halide, other, oxide, "
    "oxyhalide, sulfide, then lexical order within family."
)
M6B_ADVANCEMENT_RULE = (
    "Advance only to bounded M7 policy-integration investigation if the complete paired "
    "panel shows D8 geometry-failure reduction across multiple families and all three "
    "seed blocks without lower generated coverage, while useful diagnostic outcomes "
    "are not materially lower and no repeated failure/tradeoff invalidates the result; "
    "this is not activation or P1 authorization."
)
TARGET_SPECIES = "Li"  # Explicit current experimental validation profile only.
INPUT_RELATIVE = "data/batches/audit/g_ordered_expansion_v1.json"
ARTIFACT_RELATIVE = (
    "data/batches/audit/"
    "g_candidate_supply_v2_mobile_ion_displace_diagnostic_panel.json"
)
REMOTE_RUNTIME_TEMP_ROOT = Path("/kaggle/temp/rhombus_mobile_ion_runtime")
REMOTE_REPORT_OUTPUT_ROOT = Path("/kaggle/working/rhombus_mobile_ion_e2e_output")
SIGMAS = [0.30, 0.35, 0.40]
SEEDS = [42, 43, 44, 45]
PERSISTENT_THRESHOLD = 0.75
REFERENCE_VERSIONS = {
    "Python": "3.11.15",
    "numpy": "2.4.6",
    "scipy": "1.17.1",
    "pymatgen": "2026.5.4",
    "smact": "4.0.0",
    "PyYAML": "6.0.3",
}
ENVIRONMENT_PROBE_PACKAGES = (
    ("numpy", "numpy"),
    ("scipy", "scipy"),
    ("pymatgen", "pymatgen"),
    ("smact", "smact"),
    ("yaml", "PyYAML"),
)
EMBEDDED_WORKSPACE_IDENTITY_B64 = "__RHOMBUS_WORKSPACE_IDENTITY_B64__"
EMBEDDED_IDENTITY_REQUIRED_FIELDS = (
    "schema_version", "run_id", "git_head", "branch", "tracked_dirty",
    "status_porcelain", "repository_tracked_files", "repository_workspace_manifest_sha256",
    "tracked_delta_sha256", "driver_template_sha256", "driver_path",
    "explicitly_staged_untracked_inputs", "explicitly_staged_input_manifest_sha256",
    "runtime_files", "runtime_manifest_sha256", "runtime_dataset_files",
    "runtime_dataset_manifest_sha256", "dataset_transport_files",
    "dataset_transport_manifest_sha256", "protected_artifacts",
)
RUNTIME_DRIVER_RELATIVE = "mobile_ion_displace_e2e.py"
EXPECTED_KAGGLE_DATASET_OWNER = "wt2018mask"
EXPECTED_KAGGLE_DATASET_SLUG = "rhombus-mobile-ion-runtime"
RUNTIME_SOURCE_FILES = (
    "config.yaml",
    INPUT_RELATIVE,
    "rudeus/__init__.py",
    "rudeus/schema.py",
    "rudeus/empirical/__init__.py",
    "rudeus/empirical/liion.py",
    "rudeus/empirical/obelix.py",
    "rudeus/filters/__init__.py",
    "rudeus/filters/bvse.py",
    "rudeus/filters/f3_diffusive.py",
    "rudeus/filters/p0.py",
    "rudeus/generation/__init__.py",
    "rudeus/generation/audit.py",
    "rudeus/generation/generator.py",
    "rudeus/generation/mobile_ion_diagnostic.py",
    "rudeus/generation/scheduler.py",
)
OBELIX_RUNTIME_FILES = (
    "data/obelix/data/processed.csv",
    "data/obelix/data/train_idx.csv",
    "data/obelix/data/test_idx.csv",
    "data/obelix/data/misc/LiIonDatabase.csv",
)


class InfrastructureFailure(RuntimeError):
    pass


class ScientificValidationFailure(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


PASS_IDENTITY_SCHEMA_VERSION = "mobile-ion-generation-pass-identity-v1"
PASS_IDENTITY_CANARY_CONFIG_IDENTITY = "mobile-ion-pass-identity-canary-v1"
PASS_IDENTITY_CANARY_PASS_BYTES = b'{"canary":"pass-identity-v1","synthetic":true}\n'
PROTECTED_PROVENANCE_CANARY_BEFORE_BYTES = b'{"synthetic_protected_state":"before"}\n'
PROTECTED_PROVENANCE_CANARY_AFTER_BYTES = b'{"synthetic_protected_state":"after","operation":"deterministic-transform"}\n'


def generation_pass_identity_status(report: dict) -> str:
    """Read pass identity conservatively; historical reports remain UNKNOWN."""
    evidence = report.get("generation_pass_identity") if isinstance(report, dict) else None
    if not isinstance(evidence, dict) or evidence.get("schema_version") != PASS_IDENTITY_SCHEMA_VERSION:
        return "UNKNOWN"
    pass1, pass2 = evidence.get("pass_1"), evidence.get("pass_2")
    identical = evidence.get("byte_identical")
    if (not isinstance(pass1, dict) or not isinstance(pass2, dict)
            or not isinstance(pass1.get("sha256"), str)
            or not isinstance(pass2.get("sha256"), str)
            or type(pass1.get("byte_length")) is not int
            or type(pass2.get("byte_length")) is not int
            or type(identical) is not bool):
        return "UNKNOWN"
    if (any(not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]) for item in (pass1, pass2))
            or pass1["byte_length"] < 0 or pass2["byte_length"] < 0
            or (identical and (pass1["sha256"] != pass2["sha256"]
                               or pass1["byte_length"] != pass2["byte_length"]))):
        return "UNKNOWN"
    return "IDENTICAL" if identical else "MISMATCH"


def pass2_temp_cleanup_allowed(pass2: bytes | None, pass_identity: dict | None) -> bool:
    """Remove the temporary pass-2 copy only after its durable evidence is valid."""
    if pass2 is None or not isinstance(pass_identity, dict):
        return False
    status = generation_pass_identity_status(
        {"generation_pass_identity": pass_identity},
    )
    if status == "IDENTICAL":
        return True
    return (
        status == "MISMATCH"
        and isinstance(pass_identity.get("pass_2_diagnostic_artifact"), dict)
    )


def _write_json_exclusive_atomic(path: Path, payload: dict) -> bytes:
    """Durably publish a new run-specific JSON evidence record without overwrite."""
    encoded = (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    temporary = None
    try:
        fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        temporary = Path(name)
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        # link() publishes atomically and refuses to replace an existing run record.
        os.link(temporary, path)
        _fsync_directory(path.parent)
        return encoded
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _fsync_directory(path: Path) -> None:
    try:
        directory_fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(directory_fd)
    except OSError:
        pass
    finally:
        os.close(directory_fd)


def require_prepared_execution_identity(workspace: dict) -> dict:
    execution_identity = workspace.get("execution_identity") if isinstance(workspace, dict) else None
    required = (
        "task_id", "task_content_hash", "task_bundle_hash", "code_bundle_hash",
        "attempt_id", "prepared_attempt_hash", "task_config_hash",
    )
    if (not isinstance(execution_identity, dict)
            or any(not isinstance(execution_identity.get(name), str)
                   or not re.fullmatch(r"[0-9a-f]{64}", execution_identity[name])
                   for name in required)):
        raise InfrastructureFailure("generic Kaggle execution requires complete prepared task/attempt identity")
    if (execution_identity.get("execution_mode") not in
            ("CANDIDATE_DIAGNOSTIC_E2E", "PASS_IDENTITY_CANARY", "M6A_PAIRED_DIAGNOSTIC", "M6B_PAIRED_DIAGNOSTIC")
            or not isinstance(execution_identity.get("configuration_identity"), str)
            or not execution_identity["configuration_identity"]):
        raise InfrastructureFailure("generic Kaggle execution mode/configuration identity is incomplete")
    if (execution_identity["execution_mode"] == "CANDIDATE_DIAGNOSTIC_E2E"
            and execution_identity["configuration_identity"] != CONFIG_IDENTITY):
        raise InfrastructureFailure("candidate diagnostic configuration identity mismatch")
    if (execution_identity["execution_mode"] == "PASS_IDENTITY_CANARY"
            and execution_identity["configuration_identity"] != PASS_IDENTITY_CANARY_CONFIG_IDENTITY):
        raise InfrastructureFailure("pass identity canary configuration identity mismatch")
    if (execution_identity["execution_mode"] == "M6A_PAIRED_DIAGNOSTIC"
            and execution_identity["configuration_identity"] != M6A_CONFIG_IDENTITY):
        raise InfrastructureFailure("M6-A paired diagnostic configuration identity mismatch")
    if (execution_identity["execution_mode"] == "M6B_PAIRED_DIAGNOSTIC"
            and (execution_identity["configuration_identity"] != M6B_CONFIG_IDENTITY
                 or not re.fullmatch(r"wt2018mask/rhombus-m6b-[0-9a-f]{16}",
                                     str(workspace.get("provider_kernel_identity", ""))))):
        raise InfrastructureFailure("M6-B paired diagnostic configuration/kernel identity mismatch")
    return execution_identity


def persist_generation_pass_identity(report: dict, output_root: Path, pass1: bytes, pass2: bytes,
                                     workspace: dict, *, report_path: Path | None = None) -> dict:
    """Persist exact pass identities before validation and retain mismatching pass 2."""
    output_root = Path(output_root)
    run_id = workspace.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise InfrastructureFailure("pass identity evidence requires the embedded workspace run_id")
    execution_identity = require_prepared_execution_identity(workspace)
    byte_identical = pass1 == pass2
    pass1_sha, pass2_sha = sha256_bytes(pass1), sha256_bytes(pass2)
    diagnostic = None
    if not byte_identical:
        diagnostic_path = output_root / f"generation-pass-2-mismatch-{run_id}-{pass2_sha}.bin"
        with diagnostic_path.open("xb") as handle:
            handle.write(pass2)
            handle.flush()
            os.fsync(handle.fileno())
        _fsync_directory(output_root)
        diagnostic_sha = sha256_file(diagnostic_path)
        diagnostic_length = diagnostic_path.stat().st_size
        if diagnostic_sha != pass2_sha or diagnostic_length != len(pass2):
            raise InfrastructureFailure("retained pass-2 diagnostic bytes failed exact verification")
        diagnostic = {
            "relative_path": diagnostic_path.name,
            "sha256": diagnostic_sha,
            "byte_length": diagnostic_length,
        }
    identity = {
        "run_id": run_id,
        "task_attempt": execution_identity,
        "workspace_identity_sha256": sha256_bytes(
            json.dumps(workspace, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")),
        "runtime_manifest_sha256": workspace.get("runtime_manifest_sha256"),
        "configuration_identity": execution_identity["configuration_identity"],
        "configuration_identity_sha256": sha256_bytes(
            execution_identity["configuration_identity"].encode("utf-8")),
        "test_identity": TEST_IDENTITY,
    }
    evidence = {
        "schema_version": PASS_IDENTITY_SCHEMA_VERSION,
        "identity": identity,
        "pass_1": {"sha256": pass1_sha, "byte_length": len(pass1)},
        "pass_2": {"sha256": pass2_sha, "byte_length": len(pass2)},
        "byte_identical": byte_identical,
        "pass_2_diagnostic_artifact": diagnostic,
    }
    evidence_path = output_root / f"generation-pass-identity-{run_id}.json"
    evidence_bytes = _write_json_exclusive_atomic(evidence_path, evidence)
    report_evidence = {
        **evidence,
        "evidence_artifact": {
            "relative_path": evidence_path.name,
            "sha256": sha256_bytes(evidence_bytes),
            "byte_length": len(evidence_bytes),
        },
    }
    report["generation_pass_identity"] = report_evidence
    if report_path is not None:
        write_json(Path(report_path), report)
    return report_evidence


def canonical_driver_template_bytes(source: bytes) -> bytes:
    """Normalize only driver-template line endings for stable cross-platform identity."""
    return source.replace(b"\r\n", b"\n")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def versions() -> dict[str, str | None]:
    result = {"Python": platform_python(), "numpy": None, "scipy": None, "pymatgen": None}
    for name in ("numpy", "scipy", "pymatgen"):
        try:
            result[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            result[name] = None
    return result


def platform_python() -> str:
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


BOOTSTRAP_MARKER = "RHOMBUS_EXACT_ENV_BOOTSTRAPPED"
BOOTSTRAP_RUNTIME_ROOT = "RHOMBUS_VERIFIED_RUNTIME_ROOT"
BOOTSTRAP_OUTPUT_ROOT = "RHOMBUS_VERIFIED_OUTPUT_ROOT"
BOOTSTRAP_INITIAL_ENV = "RHOMBUS_INITIAL_ENVIRONMENT_B64"
BOOTSTRAP_RUN_ID = "RHOMBUS_EXPECTED_RUN_ID"
BOOTSTRAP_PERFORMED = "RHOMBUS_DEPENDENCY_INSTALL_PERFORMED"
UV_VERSION = "0.12.19"
UV_COMMAND_TIMEOUTS = (900, 180, 1800)
UV_PYPI_INSTALL_TIMEOUT_SECONDS = 900
UV_VERSION_PROBE_TIMEOUT_SECONDS = 60
FINAL_ENVIRONMENT_PROBE_TIMEOUT_SECONDS = 120
REEXEC_TIMEOUT_SECONDS = 21600
SCIENTIFIC_HEARTBEAT_INTERVAL_SECONDS = 60
SCIENTIFIC_STAGE_TIMEOUT_SECONDS = 1800
SCIENTIFIC_TIMEOUT_POLICY = "NOT_ENFORCED_IN_PROCESS"


class StageObservability:
    def __init__(self, writer=print, clock=time.monotonic):
        self.writer = writer
        self.clock = clock
        self.current_stage = "startup"
        self.last_stage = "startup"
        self.last_progress = ""
        self.stage_started = None
        self.stage_elapsed_seconds = None
        self.stage_active = False
        self.heartbeat_enabled = True
        self.failed_stage = None
        self.failed_progress = None
        self.failed_elapsed_seconds = None

    def _write(self, line: str) -> None:
        self.writer(line, flush=True)
        self.last_progress = line

    def stage(self, name: str) -> None:
        self.current_stage = name.removesuffix("_start").removesuffix("_done")
        self.last_stage = name
        self.stage_started = self.clock()
        self.stage_active = True
        self._write(f"STAGE={name}")

    def stage_done(self, name: str, started: float | None = None, *, emit: bool = True) -> None:
        elapsed = max(0.0, self.clock() - (self.stage_started if started is None else started))
        self.current_stage = name
        self.last_stage = f"{name}_done"
        self.stage_elapsed_seconds = round(elapsed, 3)
        self.stage_active = False
        line = f"STAGE={name}_done ELAPSED_SECONDS={self.stage_elapsed_seconds:.3f}"
        if emit:
            self._write(line)
        else:
            self.last_progress = line

    def bootstrap(self, name: str, state: str) -> None:
        self.current_stage = name
        self.last_stage = f"{name}_{state.lower()}"
        self.stage_active = state == "START"
        self.stage_started = self.clock()
        self._write(f"BOOTSTRAP_STAGE={name} {state}")

    def failed(self) -> None:
        if self.stage_active and self.stage_started is not None:
            self.stage_elapsed_seconds = round(max(0.0, self.clock() - self.stage_started), 3)
        self.last_stage = self.current_stage
        self.stage_active = False
        self.failed_stage = self.current_stage
        self.failed_elapsed_seconds = self.stage_elapsed_seconds
        self.failed_progress = f"STAGE_FAILED={self.current_stage}"
        self._write(self.failed_progress)

    def snapshot(self) -> dict:
        elapsed = self.stage_elapsed_seconds
        if self.stage_started is not None and self.stage_active:
            elapsed = round(max(0.0, self.clock() - self.stage_started), 3)
        return {
            "last_stage": self.failed_stage or self.last_stage,
            "last_progress": self.failed_progress or self.last_progress,
            "stage_elapsed_seconds": self.failed_elapsed_seconds if self.failed_stage else elapsed,
            "failed_stage": self.failed_stage,
            "heartbeat_enabled": self.heartbeat_enabled,
            "scientific_timeout_policy": {
                "state": SCIENTIFIC_TIMEOUT_POLICY,
                "configured_timeout_seconds": SCIENTIFIC_STAGE_TIMEOUT_SECONDS,
            },
        }


def _periodic_heartbeat(stage: str, stop: threading.Event, interval: float, writer) -> None:
    started = time.monotonic()
    while not stop.wait(interval):
        elapsed = int(time.monotonic() - started)
        writer(format_heartbeat_line(stage, elapsed), flush=True)


def format_heartbeat_line(stage: str, elapsed_seconds: int) -> str:
    return f"HEARTBEAT_STAGE={stage} ELAPSED_SECONDS={max(0, int(elapsed_seconds))}"


def run_with_periodic_heartbeat(
    observer: StageObservability, stage: str, operation, *, interval: float = SCIENTIFIC_HEARTBEAT_INTERVAL_SECONDS,
):
    observer.stage(f"{stage}_start")
    started = observer.clock()
    stop = threading.Event()
    heartbeat = threading.Thread(
        target=_periodic_heartbeat,
        args=(stage, stop, interval, observer.writer),
        daemon=True,
        name=f"rhombus-heartbeat-{stage}",
    )
    heartbeat.start()
    completed = False
    try:
        result = operation()
        completed = True
        return result
    finally:
        stop.set()
        heartbeat.join()
        if completed:
            observer.stage_done(stage, started)


def observability_self_test() -> None:
    captured = []
    observer = StageObservability(writer=lambda line, *, flush: captured.append((line, flush)), clock=lambda: 11.25)
    sequence = (
        ("runtime_integrity_verified", False),
        ("environment_bootstrap_start", False),
        ("environment_bootstrap_done", False),
        ("environment_verified", False),
        ("source_cohort_load_start", False),
        ("source_cohort_load_done", True),
        ("generation_pass_1_start", False),
        ("generation_pass_1_done", True),
        ("generation_pass_2_start", False),
        ("generation_pass_2_done", True),
        ("validation_start", False),
        ("validation_done", True),
        ("report_write_start", False),
        ("report_write_done", True),
    )
    for stage, done in sequence:
        if done:
            observer.stage_done(stage.removesuffix("_done"), started=10.0)
        else:
            observer.stage(stage)
    assert [line.split(" ELAPSED_SECONDS=")[0] for line, _ in captured] == [
        f"STAGE={name}" for name, _ in sequence
    ]
    assert all(flush is True for _, flush in captured)
    assert captured[5][0] == "STAGE=source_cohort_load_done ELAPSED_SECONDS=1.250"

    failed_output = []
    failed = StageObservability(writer=lambda line, *, flush: failed_output.append((line, flush)))
    failed.stage("source_cohort_load_start")
    failed.failed()
    assert failed_output[-1] == ("STAGE_FAILED=source_cohort_load", True)
    assert failed.snapshot()["last_stage"] == "source_cohort_load"
    failed.stage("report_write_start")
    assert failed.snapshot()["last_stage"] == "source_cohort_load"
    assert failed.snapshot()["last_progress"] == "STAGE_FAILED=source_cohort_load"

    bootstrap_output = []
    bootstrap = StageObservability(writer=lambda line, *, flush: bootstrap_output.append((line, flush)))
    bootstrap.bootstrap("uv_pypi_install", "START")
    bootstrap.bootstrap("uv_pypi_install", "DONE")
    assert [line for line, _ in bootstrap_output] == [
        "BOOTSTRAP_STAGE=uv_pypi_install START", "BOOTSTRAP_STAGE=uv_pypi_install DONE",
    ]
    assert format_heartbeat_line("generation_pass_1", 60) == "HEARTBEAT_STAGE=generation_pass_1 ELAPSED_SECONDS=60"
    assert format_heartbeat_line("generation_pass_1", 60) == format_heartbeat_line("generation_pass_1", 60)

    scientific_payload = {"rows": [{"parent_id": "fixture", "value": 7}]}
    artifact_bytes = json.dumps(scientific_payload, sort_keys=True).encode("utf-8")
    report = {"observability": failed.snapshot()}
    assert json.dumps(scientific_payload, sort_keys=True).encode("utf-8") == artifact_bytes
    assert "observability" not in scientific_payload

    before = len(bootstrap_output)
    untouched = {"scientific": [1, 2, 3]}
    result = run_with_periodic_heartbeat(
        bootstrap, "self_test", lambda: untouched, interval=0.005,
    )
    assert result is untouched and untouched == {"scientific": [1, 2, 3]}
    assert len(bootstrap_output) > before
    assert bootstrap_output[-1][0].startswith("STAGE=self_test_done ELAPSED_SECONDS=")
    assert all(flush is True for _, flush in bootstrap_output)

    assert all(timeout > 0 for timeout in (
        UV_PYPI_INSTALL_TIMEOUT_SECONDS, UV_VERSION_PROBE_TIMEOUT_SECONDS,
        *UV_COMMAND_TIMEOUTS, FINAL_ENVIRONMENT_PROBE_TIMEOUT_SECONDS,
        REEXEC_TIMEOUT_SECONDS,
    ))
    assert exact_environment(dict(REFERENCE_VERSIONS))
    assert dict(REFERENCE_VERSIONS)["Python"] == "3.11.15"
    assert dict(REFERENCE_VERSIONS)["PyYAML"] == "6.0.3"
    assert SCIENTIFIC_TIMEOUT_POLICY == "NOT_ENFORCED_IN_PROCESS"
    assert report["observability"]["scientific_timeout_policy"]["configured_timeout_seconds"] == SCIENTIFIC_STAGE_TIMEOUT_SECONDS
    print("OBSERVABILITY_SELF_TEST=PASS")


def exact_environment(environment: dict) -> bool:
    return all(environment.get(name) == value for name, value in REFERENCE_VERSIONS.items())


def environment_action(environment: dict, *, reexecuted: bool) -> str:
    if exact_environment(environment):
        return "CONTINUE"
    return "ERROR" if reexecuted else "BOOTSTRAP"


def scientific_execution_allowed(environment: dict, import_errors: dict, *, reexecuted: bool) -> bool:
    return environment_action(environment, reexecuted=reexecuted) == "CONTINUE" and not import_errors


def _environment_probe_code() -> str:
    return (
        "import importlib,importlib.metadata,json,sys; "
        f"packages={ENVIRONMENT_PROBE_PACKAGES!r}; "
        "versions={'Python':'.'.join(map(str,sys.version_info[:3]))}; errors={}; "
        "\nfor module,distribution in packages:\n"
        " try:\n  importlib.import_module(module)\n  versions[distribution]=importlib.metadata.version(distribution)\n"
        " except Exception as exc:\n  errors[module]=type(exc).__name__+': '+str(exc)\n"
        "  try: versions[distribution]=importlib.metadata.version(distribution)\n  except Exception: versions[distribution]=None\n"
        "print(json.dumps({'versions':versions,'import_errors':errors},sort_keys=True))"
    )


def probe_environment(executable: str | Path, *, timeout: int = 120) -> tuple[dict, dict]:
    try:
        completed = subprocess.run(
            [str(executable), "-c", _environment_probe_code()],
            check=False, text=True, capture_output=True, timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise InfrastructureFailure(f"environment probe failed: {type(exc).__name__}: {exc}") from exc
    if completed.returncode != 0:
        raise InfrastructureFailure(
            f"environment probe exited {completed.returncode}: {(completed.stdout + completed.stderr)[-3000:]}"
        )
    try:
        result = json.loads(completed.stdout.strip().splitlines()[-1])
        environment, import_errors = result["versions"], result["import_errors"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise InfrastructureFailure(
            f"environment probe returned unparseable output: {(completed.stdout + completed.stderr)[-3000:]}"
        ) from exc
    if not isinstance(environment, dict) or not isinstance(import_errors, dict):
        raise InfrastructureFailure("environment probe returned an invalid payload")
    return environment, import_errors


def build_uv_pypi_install_command(system_python: str | Path, transient_uv_dir: Path) -> list[str]:
    return [
        str(system_python), "-m", "pip", "install", "--disable-pip-version-check",
        "--no-input", f"uv=={UV_VERSION}", "--target", str(transient_uv_dir),
    ]


def build_uv_commands(uv_executable: Path, bootstrap_root: Path) -> tuple[list[str], ...]:
    venv = bootstrap_root / "venv"
    python = venv / "bin" / "python"
    pins = [f"{name}=={version}" for name, version in REFERENCE_VERSIONS.items() if name != "Python"]
    return (
        [str(uv_executable), "python", "install", REFERENCE_VERSIONS["Python"]],
        [str(uv_executable), "venv", "--python", REFERENCE_VERSIONS["Python"],
         "--python-preference", "only-managed", str(venv)],
        [str(uv_executable), "pip", "install", "--python", str(python), *pins],
    )


def validate_uv_version(exit_code: int, output: str) -> str:
    match = re.search(r"(?m)^\s*uv\s+(\S+)", output)
    if exit_code == 0 and match and match.group(1) == UV_VERSION:
        return "UV_OK"
    detail = f"exit_code={exit_code}; output={output[-3000:]}"
    raise InfrastructureFailure(f"uv_version_probe: expected uv {UV_VERSION}; {detail}")


def _bounded_output(stdout, stderr) -> str:
    def as_text(value):
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return str(value or "")
    return (as_text(stdout) + as_text(stderr))[-3000:]


def bootstrap_stage_failure(stage: str, detail: str) -> InfrastructureFailure:
    return InfrastructureFailure(f"{stage}: {detail}")


def run_bootstrap_stage(stage: str, command: list[str], *, timeout: int, env: dict, observer=None):
    if observer is not None:
        observer.bootstrap(stage, "START")
    try:
        completed = subprocess.run(
            command, check=False, text=True, capture_output=True, timeout=timeout, env=env,
        )
    except subprocess.TimeoutExpired as exc:
        raise bootstrap_stage_failure(
            stage, f"timed out after {timeout}s; output={_bounded_output(exc.stdout, exc.stderr)}",
        ) from exc
    except OSError as exc:
        raise bootstrap_stage_failure(stage, f"{type(exc).__name__}: {exc}") from exc
    if completed.returncode != 0:
        raise bootstrap_stage_failure(
            stage, f"exited {completed.returncode}; output={_bounded_output(completed.stdout, completed.stderr)}",
        )
    if observer is not None:
        observer.bootstrap(stage, "DONE")
    return completed


def bootstrap_exact_environment(
    runtime_root: Path, *, integrity_verified: bool, status: dict | None = None, observer=None,
) -> Path:
    if not integrity_verified:
        raise InfrastructureFailure("refusing environment bootstrap before runtime integrity verification")
    verified_root = Path(runtime_root).resolve()
    bootstrap_root = verified_root.parent / f"{verified_root.name}-bootstrap"
    uv_target = bootstrap_root / "uv-pypi"
    uv_cache = bootstrap_root / "uv-cache"
    uv_python = bootstrap_root / "uv-python"
    try:
        uv_target.mkdir(parents=True, exist_ok=True)
        uv_cache.mkdir(parents=True, exist_ok=True)
        uv_python.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise bootstrap_stage_failure("uv_pypi_install", f"cannot prepare transient install paths: {exc}") from exc
    pip_env = os.environ.copy()
    pip_env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    if status is not None:
        status["dependency_install_performed"] = True
    run_bootstrap_stage(
        "uv_pypi_install", build_uv_pypi_install_command(sys.executable, uv_target),
        timeout=UV_PYPI_INSTALL_TIMEOUT_SECONDS, env=pip_env, observer=observer,
    )
    uv_executable = uv_target / "bin" / "uv"
    if not uv_executable.is_file():
        raise InfrastructureFailure(f"uv_version_probe: installed uv entrypoint is missing: {uv_executable}")
    version_result = run_bootstrap_stage(
        "uv_version_probe", [str(uv_executable), "--version"],
        timeout=UV_VERSION_PROBE_TIMEOUT_SECONDS, env=os.environ.copy(), observer=observer,
    )
    validate_uv_version(version_result.returncode, _bounded_output(version_result.stdout, version_result.stderr))
    env = os.environ.copy()
    env.update({"UV_CACHE_DIR": str(uv_cache), "UV_PYTHON_INSTALL_DIR": str(uv_python)})
    commands = build_uv_commands(uv_executable, bootstrap_root)
    run_bootstrap_stage(
        "python_3_11_15_install", commands[0], timeout=UV_COMMAND_TIMEOUTS[0], env=env, observer=observer,
    )
    run_bootstrap_stage(
        "python_3_11_15_install", commands[1], timeout=UV_COMMAND_TIMEOUTS[1], env=env, observer=observer,
    )
    run_bootstrap_stage(
        "package_install", commands[2], timeout=UV_COMMAND_TIMEOUTS[2], env=env, observer=observer,
    )
    python = bootstrap_root / "venv" / "bin" / "python"
    if not python.is_file():
        raise InfrastructureFailure(f"uv bootstrap did not create the expected interpreter: {python}")
    return python


def bootstrap_reexec_environment(
    original: dict, workspace: dict, runtime_root: Path, output_root: Path,
) -> dict[str, str]:
    child_env = os.environ.copy()
    child_env.update({
        BOOTSTRAP_MARKER: "1",
        BOOTSTRAP_RUNTIME_ROOT: str(Path(runtime_root).resolve()),
        BOOTSTRAP_OUTPUT_ROOT: str(Path(output_root).resolve()),
        "RHOMBUS_E2E_OUTPUT": str(Path(output_root).resolve()),
        BOOTSTRAP_INITIAL_ENV: base64.b64encode(
            json.dumps(original, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).decode("ascii"),
        BOOTSTRAP_RUN_ID: str(workspace["run_id"]),
        BOOTSTRAP_PERFORMED: "1",
    })
    for key in ("PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV"):
        child_env.pop(key, None)
    return child_env


def _initial_environment_from_handoff(workspace: dict, runtime_root: Path, output_root: Path) -> dict:
    try:
        initial = json.loads(base64.b64decode(os.environ[BOOTSTRAP_INITIAL_ENV], validate=True))
    except Exception as exc:
        raise InfrastructureFailure(f"bootstrap handoff environment provenance is invalid: {exc}") from exc
    root_value = os.environ.get(BOOTSTRAP_RUNTIME_ROOT)
    output_value = os.environ.get(BOOTSTRAP_OUTPUT_ROOT)
    if not root_value or not output_value:
        raise InfrastructureFailure("bootstrap handoff omitted its verified runtime/output paths")
    expected_root = Path(root_value).resolve()
    if expected_root != Path(runtime_root).resolve():
        raise InfrastructureFailure("bootstrap handoff runtime root changed across re-execution")
    if Path(output_value).resolve() != Path(output_root).resolve():
        raise InfrastructureFailure("bootstrap handoff report output root changed across re-execution")
    if os.environ.get(BOOTSTRAP_RUN_ID) != str(workspace.get("run_id")):
        raise InfrastructureFailure("bootstrap handoff run identity changed across re-execution")
    expected_driver = (expected_root / str(workspace.get("driver_path"))).resolve()
    if Path(__file__).resolve() != expected_driver:
        raise InfrastructureFailure("bootstrap re-execution is not using the verified staged driver")
    if not isinstance(initial, dict) or not all(key in initial for key in REFERENCE_VERSIONS):
        raise InfrastructureFailure("bootstrap handoff omitted the original environment snapshot")
    return initial


def environment_report(initial: dict, final: dict, installed: bool, import_errors: dict | None = None) -> dict:
    return {
        "initial": initial,
        "final": final,
        "initial_python": initial.get("Python"),
        "final_python": final.get("Python"),
        "exact_reference_match": exact_environment(final) and not import_errors,
        "dependency_install_performed": installed,
        "reference_versions": REFERENCE_VERSIONS,
        "final_import_errors": import_errors or {},
    }


def environment_bootstrap_self_test() -> None:
    compile(_environment_probe_code(), "<environment-probe-self-test>", "exec")
    exact = dict(REFERENCE_VERSIONS)
    assert {name: exact[name] for name in ("Python", "numpy", "scipy", "pymatgen")} == {
        "Python": "3.11.15", "numpy": "2.4.6", "scipy": "1.17.1", "pymatgen": "2026.5.4",
    }
    assert ("yaml", "PyYAML") in ENVIRONMENT_PROBE_PACKAGES
    assert exact["PyYAML"] == "6.0.3"
    mismatched = {**exact, "Python": "3.12.13", "numpy": "2.0.2", "scipy": "1.16.3", "pymatgen": None}
    assert environment_action(exact, reexecuted=False) == "CONTINUE"
    assert environment_action(mismatched, reexecuted=False) == "BOOTSTRAP"
    assert environment_action(exact, reexecuted=True) == "CONTINUE"
    assert environment_action(mismatched, reexecuted=True) == "ERROR"
    with tempfile.TemporaryDirectory(prefix="rhombus-env-self-test-") as temporary:
        base = Path(temporary)
        bootstrap_root = base / "bootstrap"
        uv_target = bootstrap_root / "uv-pypi"
        pip_command = build_uv_pypi_install_command("/kaggle/python", uv_target)
        assert pip_command[0:2] == ["/kaggle/python", "-m"]
        assert pip_command[2:6] == ["pip", "install", "--disable-pip-version-check", "--no-input"]
        assert pip_command[6] == "uv==0.12.19"
        assert Path(pip_command[-1]).is_relative_to(bootstrap_root)
        assert Path(pip_command[-1]) == uv_target
        source = Path(__file__).read_text(encoding="utf-8")
        assert "astral" + ".sh" not in source
        assert validate_uv_version(0, "uv 0.12.19 (x86_64-unknown-linux-gnu)") == "UV_OK"
        try:
            validate_uv_version(0, "uv 0.12.18")
        except InfrastructureFailure as exc:
            assert "uv_version_probe:" in str(exc)
        else:
            raise AssertionError("wrong uv version was accepted")
        commands = build_uv_commands(uv_target / "bin" / "uv", bootstrap_root)
        assert commands[0][2:] == ["install", "3.11.15"]
        assert "3.11.15" in commands[1]
        assert commands[2][-5:] == [
            "numpy==2.4.6", "scipy==1.17.1", "pymatgen==2026.5.4", "smact==4.0.0",
            "PyYAML==6.0.3",
        ]
        failure_stages = (
            "uv_pypi_install", "uv_version_probe", "python_3_11_15_install",
            "package_install", "final_environment_probe", "reexec",
        )
        assert len({str(bootstrap_stage_failure(stage, "fixture")).split(":", 1)[0] for stage in failure_stages}) == 6
        workspace = {"run_id": "stable-run"}
        handoff = bootstrap_reexec_environment(exact, workspace, base / "runtime", base / "output")
        assert handoff[BOOTSTRAP_RUN_ID] == "stable-run"
        assert handoff[BOOTSTRAP_RUNTIME_ROOT] == str((base / "runtime").resolve())
        assert handoff[BOOTSTRAP_OUTPUT_ROOT] == str((base / "output").resolve())
        assert handoff["RHOMBUS_E2E_OUTPUT"] == str((base / "output").resolve())
        assert json.loads(base64.b64decode(handoff[BOOTSTRAP_INITIAL_ENV])) == exact
        try:
            bootstrap_exact_environment(base / "runtime", integrity_verified=False)
        except InfrastructureFailure:
            pass
        else:
            raise AssertionError("bootstrap was allowed before integrity verification")
        assert not exact_environment(mismatched)
        assert exact_environment(exact)
        missing_smact = {name: value for name, value in exact.items() if name != "smact"}
        wrong_smact = {**exact, "smact": "3.0.0"}
        assert not exact_environment(missing_smact)
        assert not exact_environment(wrong_smact)
        assert not scientific_execution_allowed(missing_smact, {}, reexecuted=False)
        assert not scientific_execution_allowed(exact, {"smact": "ModuleNotFoundError"}, reexecuted=True)
        assert not scientific_execution_allowed(wrong_smact, {}, reexecuted=True)
        missing_pyyaml = {name: value for name, value in exact.items() if name != "PyYAML"}
        wrong_pyyaml = {**exact, "PyYAML": "6.0.2"}
        assert not exact_environment(missing_pyyaml)
        assert not exact_environment(wrong_pyyaml)
        assert not scientific_execution_allowed(missing_pyyaml, {}, reexecuted=False)
        assert not scientific_execution_allowed(exact, {"yaml": "ModuleNotFoundError"}, reexecuted=True)
        assert not scientific_execution_allowed(wrong_pyyaml, {}, reexecuted=True)
        assert not scientific_execution_allowed(mismatched, {}, reexecuted=False)
        assert not scientific_execution_allowed(exact, {"numpy": "import failed"}, reexecuted=True)
        assert scientific_execution_allowed(exact, {}, reexecuted=True)
        preserved = environment_report(mismatched, exact, True)
        assert preserved["initial"] == mismatched and preserved["final"] == exact
        assert preserved["dependency_install_performed"] is True
        not_attempted = environment_report(mismatched, {}, False)
        assert not_attempted["dependency_install_performed"] is False
        assert environment_report(exact, exact, True)["exact_reference_match"] is True
        assert environment_report(wrong_smact, wrong_smact, True)["exact_reference_match"] is False
        assert environment_action(exact, reexecuted=True) == "CONTINUE"
    print("ENVIRONMENT_BOOTSTRAP_SELF_TEST=PASS")


def protected_paths(root: Path) -> tuple[list[str], str]:
    paths = [INPUT_RELATIVE]
    basis = "required immutable source input plus conservative protection; no authoritative exact frozen set was found"
    audit = root / "data" / "batches" / "audit"
    if audit.exists():
        for path in sorted(audit.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            name = path.name.lower()
            if rel == ARTIFACT_RELATIVE or rel == INPUT_RELATIVE:
                continue
            # Conservative read-only safety guard only.  Filename prefixes are
            # not treated as proof of historical/frozen status.
            if name.startswith(("p2", "p25", "p3")):
                paths.append(rel)
    return sorted(set(paths)), basis


def hash_protected(root: Path, paths: list[str]) -> list[dict]:
    records = []
    for relative in paths:
        path = root / relative
        if not path.is_file():
            raise InfrastructureFailure(f"required protected artifact is missing: {relative}")
        records.append({"path": relative, "sha256": sha256_file(path)})
    return records


def capture_protected_artifact_evidence(
    report: dict, root: Path, paths: list[str], before: list[dict], workspace: dict,
    *, evidence_output_root: Path | None = None,
) -> list[dict]:
    """Bind exact before/after protected hashes to this prepared execution."""
    after = hash_protected(root, paths)
    before_by_path = {item["path"]: item["sha256"] for item in before}
    after_by_path = {item["path"]: item["sha256"] for item in after}
    all_paths = sorted(set(before_by_path) | set(after_by_path))
    paired = [
        {
            "path": path,
            "before_sha256": before_by_path.get(path),
            "after_sha256": after_by_path.get(path),
        }
        for path in all_paths
    ]
    execution_identity = require_prepared_execution_identity(workspace)
    workspace_bytes = json.dumps(
        workspace, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    report["protected_artifacts"] = paired
    state = {
        "schema_version": "protected-artifact-state-v1",
        "identity": {
            "run_id": workspace["run_id"],
            "task_attempt": execution_identity,
            "workspace_identity_sha256": sha256_bytes(workspace_bytes),
            "runtime_manifest_sha256": workspace.get("runtime_manifest_sha256"),
            "configuration_identity": execution_identity["configuration_identity"],
        },
        "before": before,
        "after": after,
        "unchanged": before_by_path == after_by_path,
    }
    report["protected_artifact_state"] = state
    if evidence_output_root is not None:
        output_root = Path(evidence_output_root)
        output_root.mkdir(parents=True, exist_ok=True)
        encoded = (json.dumps(state, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
        state_sha256 = sha256_bytes(encoded)
        state_path = output_root / f"protected-artifact-state-{workspace['run_id']}-{state_sha256}.json"
        if state_path.exists():
            if state_path.read_bytes() != encoded:
                raise InfrastructureFailure("existing protected-artifact state sidecar differs from current evidence")
        else:
            _write_json_exclusive_atomic(state_path, state)
        report["protected_artifact_state_artifact"] = {
            "relative_path": state_path.name,
            "sha256": state_sha256,
            "byte_length": len(encoded),
        }
    return after


def prepare_protected_artifact_provenance_canary(
    root: Path, workspace: dict, *, integrity_checks: dict,
) -> str:
    """Create one run-specific synthetic protected file in the ephemeral runtime snapshot."""
    if not isinstance(integrity_checks, dict) or integrity_checks.get("all_required") is not True:
        raise InfrastructureFailure(
            "synthetic protected canary requires successful workspace integrity verification"
        )
    relative = f"data/batches/audit/p2-protected-provenance-canary-{workspace['run_id']}.json"
    path = Path(root) / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != PROTECTED_PROVENANCE_CANARY_BEFORE_BYTES:
            raise InfrastructureFailure("synthetic protected canary path already contains unexpected bytes")
    else:
        with path.open("xb") as handle:
            handle.write(PROTECTED_PROVENANCE_CANARY_BEFORE_BYTES)
            handle.flush()
            os.fsync(handle.fileno())
        _fsync_directory(path.parent)
    return relative


def execute_protected_artifact_provenance_canary_operation(
    runtime_root: Path, output_root: Path, workspace: dict,
    protected_relative_path: str,
) -> dict:
    """Transform only the synthetic runtime file and retain exact operation evidence."""
    protected_path = Path(runtime_root) / protected_relative_path
    before_bytes = protected_path.read_bytes()
    if before_bytes != PROTECTED_PROVENANCE_CANARY_BEFORE_BYTES:
        raise InfrastructureFailure("synthetic protected canary did not have its expected before bytes")
    before_sha256 = sha256_bytes(before_bytes)
    with protected_path.open("wb") as handle:
        handle.write(PROTECTED_PROVENANCE_CANARY_AFTER_BYTES)
        handle.flush()
        os.fsync(handle.fileno())
    _fsync_directory(protected_path.parent)
    after_bytes = protected_path.read_bytes()
    after_sha256 = sha256_bytes(after_bytes)
    if after_bytes != PROTECTED_PROVENANCE_CANARY_AFTER_BYTES or before_sha256 == after_sha256:
        raise InfrastructureFailure("synthetic protected canary operation result failed exact verification")
    operation = {
        "schema_version": "protected-artifact-provenance-canary-operation-v1",
        "run_id": workspace["run_id"],
        "identity": {
            "task_attempt": require_prepared_execution_identity(workspace),
            "workspace_identity_sha256": sha256_bytes(
                json.dumps(workspace, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")),
            "runtime_manifest_sha256": workspace.get("runtime_manifest_sha256"),
            "configuration_identity": workspace["execution_identity"]["configuration_identity"],
        },
        "input_sha256": before_sha256,
        "input_byte_length": len(before_bytes),
        "operation": "deterministic-protected-file-transform",
        "result_sha256": after_sha256,
        "protected_artifact": {
            "path": protected_relative_path,
            "before_sha256": before_sha256,
            "before_byte_length": len(before_bytes),
            "after_sha256": after_sha256,
            "after_byte_length": len(after_bytes),
        },
    }
    encoded = (json.dumps(operation, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    retained_path = output_root / (
        f"protected-provenance-canary-transformed-{workspace['run_id']}-{after_sha256}.bin")
    if retained_path.exists():
        if retained_path.read_bytes() != after_bytes:
            raise InfrastructureFailure("existing retained synthetic protected bytes differ")
    else:
        with retained_path.open("xb") as handle:
            handle.write(after_bytes)
            handle.flush()
            os.fsync(handle.fileno())
        _fsync_directory(output_root)
    operation["retained_after_artifact"] = {
        "relative_path": retained_path.name,
        "sha256": after_sha256,
        "byte_length": len(after_bytes),
    }
    encoded = (json.dumps(operation, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    output_sha256 = sha256_bytes(encoded)
    output_path = output_root / f"protected-provenance-canary-operation-{workspace['run_id']}-{output_sha256}.json"
    if output_path.exists():
        if output_path.read_bytes() != encoded:
            raise InfrastructureFailure("existing synthetic canary operation output differs")
    else:
        _write_json_exclusive_atomic(output_path, operation)
    return {
        "relative_path": output_path.name,
        "sha256": output_sha256,
        "byte_length": len(encoded),
        "operation": operation["operation"],
        "protected_artifact": operation["protected_artifact"],
        "retained_after_artifact": operation["retained_after_artifact"],
    }


def write_json(path: Path, payload: dict) -> bytes:
    encoded = (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    path.write_bytes(encoded)
    return encoded


def resolve_runtime_temp_root(temp_root: Path | None = None) -> Path:
    return Path(temp_root) if temp_root is not None else REMOTE_RUNTIME_TEMP_ROOT


def resolve_report_output_root(output_root: Path | None = None) -> Path:
    if output_root is not None:
        return Path(output_root)
    return Path(os.environ.get("RHOMBUS_E2E_OUTPUT", str(REMOTE_REPORT_OUTPUT_ROOT)))


def diagnostic_panel_output_path(output_root: Path) -> Path:
    return Path(output_root) / Path(ARTIFACT_RELATIVE).name


def activate_runtime_root(runtime_root: Path) -> None:
    resolved = str(Path(runtime_root).resolve())
    os.chdir(resolved)
    if not sys.path or sys.path[0] != resolved:
        sys.path.insert(0, resolved)


def canonical_manifest(
    root: Path, relative_paths: list[str], driver_path: str | None = None,
    *, driver_source_path: Path | None = None,
) -> str:
    lines = []
    normalized_paths = [str(relative).replace("\\", "/") for relative in relative_paths]
    if len(normalized_paths) != len(set(normalized_paths)):
        raise InfrastructureFailure("runtime manifest contains duplicate paths")
    for relative in sorted(normalized_paths):
        if relative.startswith("/") or ".." in Path(relative).parts:
            raise InfrastructureFailure(f"runtime manifest path is not repository-relative: {relative}")
        path = driver_source_path if relative == driver_path and driver_source_path is not None else root / relative
        if not path.is_file():
            raise InfrastructureFailure(f"staged manifest file is missing: {relative}")
        if relative == driver_path:
            source = path.read_bytes()
            pattern = re.compile(rb'(?m)^(EMBEDDED_WORKSPACE_IDENTITY_B64 = ")([^"]*)(")\r?$')
            matches = list(pattern.finditer(source))
            if len(matches) != 1:
                raise InfrastructureFailure("runtime driver identity marker structure is missing or duplicated")
            source = source[:matches[0].start(2)] + (b"__RHOMBUS_" + b"WORKSPACE_IDENTITY_B64__") + source[matches[0].end(2):]
            digest = sha256_bytes(canonical_driver_template_bytes(source))
        else:
            digest = sha256_file(path)
        lines.append(f"{relative}\t{digest}")
    return "\n".join(lines) + "\n"


def runtime_obelix_files(root: Path) -> list[str]:
    """Return the positive OBELiX data boundary read by this execution."""
    paths = list(OBELIX_RUNTIME_FILES)
    cif_root = root / "data" / "obelix" / "data" / "randomized_cifs"
    if cif_root.is_dir():
        paths.extend(
            path.relative_to(root).as_posix()
            for path in sorted(cif_root.glob("*.cif"))
            if path.is_file()
        )
    return sorted(paths)


def runtime_dataset_files(workspace: dict) -> list[str]:
    files = workspace.get("runtime_dataset_files")
    if not isinstance(files, list) or not files or any(not isinstance(item, str) for item in files):
        raise InfrastructureFailure("workspace_identity.runtime_dataset_files is missing or invalid")
    normalized = [item.replace("\\", "/") for item in files]
    if len(normalized) != len(set(normalized)) or RUNTIME_DRIVER_RELATIVE in normalized:
        raise InfrastructureFailure("runtime dataset manifest paths are duplicated or include the executable driver")
    return normalized


def require_workspace_runtime_files(workspace: dict) -> list[str]:
    """Require the declared runtime set to be exactly dataset files plus driver.

    Shared by the full E2E integrity validator and local backend preparation so
    both enforce the same path-set contract without normalization of declarations.
    """
    runtime_files = workspace.get("runtime_files")
    if not isinstance(runtime_files, list) or not runtime_files:
        raise InfrastructureFailure("workspace_identity.runtime_files is missing or invalid")
    dataset_files = runtime_dataset_files(workspace)
    if set(runtime_files) != set(dataset_files) | {workspace.get("driver_path")}:
        raise InfrastructureFailure("workspace runtime and dataset file sets disagree")
    return runtime_files


def dataset_transport_files(workspace: dict) -> list[str]:
    files = workspace.get("dataset_transport_files")
    runtime_files = runtime_dataset_files(workspace)
    protected = workspace.get("protected_artifacts")
    if not isinstance(files, list) or not files or any(not isinstance(item, str) for item in files):
        raise InfrastructureFailure("workspace_identity.dataset_transport_files is missing or invalid")
    normalized = [item.replace("\\", "/") for item in files]
    if len(normalized) != len(set(normalized)) or not set(runtime_files).issubset(normalized):
        raise InfrastructureFailure("dataset transport paths are duplicated or omit runtime dataset files")
    if not isinstance(protected, list) or any(not isinstance(item, dict) or not isinstance(item.get("path"), str) for item in protected):
        raise InfrastructureFailure("workspace_identity.protected_artifacts is missing or invalid")
    protected_paths = {item["path"].replace("\\", "/") for item in protected}
    if not protected_paths.issubset(normalized):
        raise InfrastructureFailure("dataset transport manifest omits protected artifacts")
    return normalized


def inspect_runtime_dataset(
    root: Path, workspace: dict, *, allow_materialized_driver: bool = False,
    allow_dataset_metadata: bool = False,
) -> dict:
    """Return exact-match status and diagnostic details without relaxing either manifest."""
    runtime_files = runtime_dataset_files(workspace)
    expected = dataset_transport_files(workspace)
    expected_sorted = sorted(expected)
    missing = sorted(relative for relative in expected_sorted if not (root / relative).is_file())
    details = {
        "status": "EXPECTED_FILES_MISSING" if missing else "MANIFEST_MISMATCH",
        "reason": "",
        "missing_expected_files": missing,
        "unexpected_files": [],
        "transport_manifest_sha256": None,
        "expected_transport_manifest_sha256": workspace.get("dataset_transport_manifest_sha256"),
        "runtime_manifest_sha256": None,
        "expected_runtime_manifest_sha256": workspace.get("runtime_dataset_manifest_sha256"),
    }
    if missing:
        details["reason"] = "expected_files_missing"
        return details
    actual = sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    )
    if allow_dataset_metadata:
        actual = [path for path in actual if path != "dataset-metadata.json"]
    if allow_materialized_driver:
        actual = [path for path in actual if path != workspace.get("driver_path")]
    unexpected = sorted(set(actual) - set(expected_sorted))
    if "config.yaml" not in expected or INPUT_RELATIVE not in expected:
        details["reason"] = "embedded_transport_manifest_omits_required_config_or_cohort_input"
        return details
    expected_obelix = sorted(path for path in runtime_files if path.startswith("data/obelix/"))
    if expected_obelix != runtime_obelix_files(root):
        details["reason"] = "obelix_runtime_file_set_mismatch"
        return details
    try:
        transport_manifest = canonical_manifest(root, expected)
        runtime_manifest = canonical_manifest(root, runtime_files)
    except InfrastructureFailure as exc:
        details["reason"] = f"manifest_construction_failed:{exc}"
        return details
    transport_hash = sha256_bytes(transport_manifest.encode("utf-8"))
    runtime_hash = sha256_bytes(runtime_manifest.encode("utf-8"))
    details["transport_manifest_sha256"] = transport_hash
    details["runtime_manifest_sha256"] = runtime_hash
    if transport_hash != details["expected_transport_manifest_sha256"]:
        details["reason"] = "transport_manifest_hash_mismatch"
        return details
    if runtime_hash != details["expected_runtime_manifest_sha256"]:
        details["reason"] = "runtime_manifest_hash_mismatch"
        return details
    if unexpected:
        details["reason"] = "unexpected_files_present"
        return details
    details.update({"status": "DATASET_MOUNT_MATCH_OK", "reason": "exact_file_set_and_manifests_match"})
    return details


def validate_runtime_dataset(root: Path, workspace: dict, *, allow_materialized_driver: bool = False) -> bool:
    """Require exact dataset transport membership and independent manifests."""
    return inspect_runtime_dataset(
        root, workspace, allow_materialized_driver=allow_materialized_driver,
    )["status"] == "DATASET_MOUNT_MATCH_OK"


def dataset_mount_candidates(input_root: Path, *, max_depth: int = 3) -> list[Path]:
    """Find mount roots through max_depth, without following symlinks."""
    input_root = Path(input_root)
    frontier = [input_root]
    candidates = []
    if any(path.is_file() and not path.is_symlink() for path in input_root.iterdir()):
        candidates.append(input_root)
    for _depth in range(1, max_depth + 1):
        next_frontier = []
        for parent in sorted(frontier, key=lambda path: path.as_posix()):
            try:
                children = sorted(parent.iterdir(), key=lambda path: path.name)
            except OSError:
                continue
            for child in children:
                if child.is_dir() and not child.is_symlink():
                    candidates.append(child)
                    next_frontier.append(child)
        frontier = next_frontier
    preferred = input_root / "datasets" / EXPECTED_KAGGLE_DATASET_OWNER / EXPECTED_KAGGLE_DATASET_SLUG
    return sorted(
        candidates,
        key=lambda path: (
            path != preferred,
            len(path.relative_to(input_root).parts) if path != input_root else 0,
            path.as_posix(),
        ),
    )


def dataset_mount_diagnostic(root: Path, workspace: dict, *, input_root: Path | None = None) -> dict:
    try:
        details = inspect_runtime_dataset(root, workspace)
    except Exception as exc:
        details = {
            "status": "MANIFEST_MISMATCH",
            "reason": f"inspection_failed:{type(exc).__name__}:{exc}",
            "missing_expected_files": [],
            "unexpected_files": [],
            "transport_manifest_sha256": None,
            "expected_transport_manifest_sha256": workspace.get("dataset_transport_manifest_sha256"),
        }
    try:
        top_level_filenames = sorted(
            path.name for path in root.iterdir() if path.is_file() and not path.is_symlink()
        )
    except OSError:
        top_level_filenames = []
    details.update({
        "mount_path": str(root),
        "mount_name": root.name,
        "mount_depth": len(root.relative_to(input_root).parts) if input_root is not None else None,
        "top_level_filenames": top_level_filenames,
        "config_yaml_exists": (root / "config.yaml").is_file(),
        "data_zip_exists": (root / "data.zip").is_file(),
        "rudeus_zip_exists": (root / "rudeus.zip").is_file(),
    })
    return details


def locate_runtime_dataset(input_root: Path, workspace: dict, *, diagnostic_writer=print) -> Path:
    """Find exactly one exact dataset root, preferring the expected depth-three Kaggle hierarchy."""
    if not input_root.is_dir():
        diagnostic_writer(f"DATASET_MOUNT_DISCOVERY=NO_DATASET_MOUNTS input_root={input_root}", flush=True)
        raise InfrastructureFailure(f"NO_DATASET_MOUNTS: Kaggle input root is unavailable: {input_root}")
    candidates = dataset_mount_candidates(input_root, max_depth=3)
    if not candidates:
        diagnostic_writer(f"DATASET_MOUNT_DISCOVERY=NO_DATASET_MOUNTS input_root={input_root}", flush=True)
        raise InfrastructureFailure("NO_DATASET_MOUNTS: no directories found under Kaggle input root")
    diagnostics = []
    for candidate in candidates:
        diagnostic = dataset_mount_diagnostic(candidate, workspace, input_root=input_root)
        diagnostics.append(diagnostic)
    matches = [Path(item["mount_path"]) for item in diagnostics if item["status"] == "DATASET_MOUNT_MATCH_OK"]
    if len(matches) != 1:
        for diagnostic in diagnostics:
            diagnostic_writer(
                "DATASET_MOUNT_DIAGNOSTIC " + json.dumps(diagnostic, sort_keys=True, separators=(",", ":")),
                flush=True,
            )
        if len(matches) > 1:
            classification = "AMBIGUOUS_MATCH"
            reason = f"{len(matches)} exact dataset mount roots matched"
        elif any(item["status"] == "MANIFEST_MISMATCH" for item in diagnostics):
            classification = "MANIFEST_MISMATCH"
            reason = "candidate directories contain files but fail exact manifest validation"
        else:
            classification = "EXPECTED_FILES_MISSING"
            reason = "no candidate directory contains the complete expected file set"
        diagnostic_writer(f"DATASET_MOUNT_DISCOVERY={classification} reason={reason}", flush=True)
        raise InfrastructureFailure(f"{classification}: {reason}")
    matched_diagnostic = next(item for item in diagnostics if Path(item["mount_path"]) == matches[0])
    diagnostic_writer(
        "DATASET_MOUNT_DIAGNOSTIC " + json.dumps(matched_diagnostic, sort_keys=True, separators=(",", ":")),
        flush=True,
    )
    diagnostic_writer(f"DATASET_MOUNT_DISCOVERY=DATASET_MOUNT_MATCH_OK mount={matches[0]}", flush=True)
    return matches[0]


def mount_discovery_self_test() -> None:
    runtime_files = sorted(["config.yaml", INPUT_RELATIVE, *OBELIX_RUNTIME_FILES])
    workspace = {
        "runtime_dataset_files": runtime_files,
        "runtime_dataset_manifest_sha256": "",
        "dataset_transport_files": runtime_files,
        "dataset_transport_manifest_sha256": "",
        "protected_artifacts": [],
    }

    def populate(path: Path, omit: str | None = None) -> None:
        for relative in runtime_files:
            if relative == omit:
                continue
            file_path = path / relative
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_bytes(f"fixture:{relative}\n".encode("utf-8"))

    with tempfile.TemporaryDirectory(prefix="rhombus-mount-discovery-self-test-") as temporary:
        base = Path(temporary)
        canonical_root = base / "canonical"
        canonical_root.mkdir()
        populate(canonical_root)
        workspace["runtime_dataset_manifest_sha256"] = sha256_bytes(
            canonical_manifest(canonical_root, runtime_files).encode("utf-8")
        )
        workspace["dataset_transport_manifest_sha256"] = workspace["runtime_dataset_manifest_sha256"]

        def locate_expect(root: Path, expected_class: str, expected_path: Path | None = None, identity=None):
            output = []
            try:
                actual_path = locate_runtime_dataset(
                    root, workspace if identity is None else identity,
                    diagnostic_writer=lambda line, *, flush: output.append(line),
                )
            except InfrastructureFailure as exc:
                assert str(exc).startswith(expected_class + ":"), str(exc)
                actual_path = None
            else:
                assert expected_class == "DATASET_MOUNT_MATCH_OK"
            if expected_path is not None:
                assert actual_path == expected_path
            return output

        exact_input = base / "exact-input"
        exact_mount = exact_input / "dataset-name"
        exact_mount.parent.mkdir(parents=True)
        shutil.copytree(canonical_root, exact_mount)
        exact_lines = locate_expect(exact_input, "DATASET_MOUNT_MATCH_OK", exact_mount)
        assert exact_lines[-1].startswith("DATASET_MOUNT_DISCOVERY=DATASET_MOUNT_MATCH_OK")
        exact_diagnostic = dataset_mount_diagnostic(exact_mount, workspace)
        assert exact_diagnostic["transport_manifest_sha256"] == workspace["dataset_transport_manifest_sha256"]
        assert exact_diagnostic["config_yaml_exists"] is True
        assert exact_diagnostic["data_zip_exists"] is False
        assert exact_diagnostic["rudeus_zip_exists"] is False

        direct_root = base / "direct-root-input"
        direct_root.mkdir()
        populate(direct_root)
        locate_expect(direct_root, "DATASET_MOUNT_MATCH_OK", direct_root)

        nested_input = base / "nested-input"
        nested_mount = nested_input / "dataset-name" / "payload"
        nested_mount.mkdir(parents=True)
        shutil.copytree(canonical_root, nested_mount, dirs_exist_ok=True)
        locate_expect(nested_input, "DATASET_MOUNT_MATCH_OK", nested_mount)

        kaggle_input = base / "kaggle-input"
        kaggle_mount = kaggle_input / "datasets" / EXPECTED_KAGGLE_DATASET_OWNER / EXPECTED_KAGGLE_DATASET_SLUG
        kaggle_mount.mkdir(parents=True)
        shutil.copytree(canonical_root, kaggle_mount, dirs_exist_ok=True)
        ordered_candidates = dataset_mount_candidates(kaggle_input, max_depth=3)
        assert ordered_candidates[0] == kaggle_mount
        kaggle_lines = locate_expect(kaggle_input, "DATASET_MOUNT_MATCH_OK", kaggle_mount)
        kaggle_diagnostic = json.loads(next(
            line.split(" ", 1)[1] for line in kaggle_lines
            if line.startswith("DATASET_MOUNT_DIAGNOSTIC ")
        ))
        assert kaggle_diagnostic["mount_path"] == str(kaggle_mount)
        assert kaggle_diagnostic["mount_depth"] == 3
        assert kaggle_diagnostic["status"] == "DATASET_MOUNT_MATCH_OK"
        assert kaggle_lines[-1].startswith("DATASET_MOUNT_DISCOVERY=DATASET_MOUNT_MATCH_OK")

        missing_input = base / "missing-input"
        missing_mount = missing_input / "dataset-name"
        missing_mount.mkdir(parents=True)
        populate(missing_mount, omit="config.yaml")
        missing_lines = locate_expect(missing_input, "EXPECTED_FILES_MISSING")
        missing_diagnostic = json.loads(next(line.split(" ", 1)[1] for line in missing_lines if line.startswith("DATASET_MOUNT_DIAGNOSTIC ")))
        assert missing_diagnostic["reason"] == "expected_files_missing"
        assert "config.yaml" in missing_diagnostic["missing_expected_files"]
        assert missing_diagnostic["config_yaml_exists"] is False

        stale_identity = dict(workspace, dataset_transport_manifest_sha256="0" * 64)
        stale_input = base / "stale-input"
        stale_mount = stale_input / "dataset-name"
        stale_mount.mkdir(parents=True)
        shutil.copytree(canonical_root, stale_mount, dirs_exist_ok=True)
        stale_lines = locate_expect(stale_input, "MANIFEST_MISMATCH", identity=stale_identity)
        stale_diagnostic = json.loads(next(line.split(" ", 1)[1] for line in stale_lines if line.startswith("DATASET_MOUNT_DIAGNOSTIC ")))
        assert stale_diagnostic["reason"] == "transport_manifest_hash_mismatch"
        assert stale_diagnostic["transport_manifest_sha256"] != stale_identity["dataset_transport_manifest_sha256"]

        ambiguous_input = base / "ambiguous-input"
        ambiguous_input.mkdir()
        shutil.copytree(canonical_root, ambiguous_input / "first")
        ambiguous_expected = ambiguous_input / "datasets" / EXPECTED_KAGGLE_DATASET_OWNER / EXPECTED_KAGGLE_DATASET_SLUG
        ambiguous_expected.mkdir(parents=True)
        shutil.copytree(canonical_root, ambiguous_expected, dirs_exist_ok=True)
        locate_expect(ambiguous_input, "AMBIGUOUS_MATCH")

        empty_input = base / "empty-input"
        empty_input.mkdir()
        locate_expect(empty_input, "NO_DATASET_MOUNTS")
    print("MOUNT_DISCOVERY_SELF_TEST=PASS")


def materialize_runtime_snapshot(
    workspace: dict,
    *,
    input_root: Path,
    temp_root: Path,
    output_root: Path | None = None,
    executing_driver: Path,
) -> Path:
    """Validate the immutable input mount, then copy it and the driver to writable storage."""
    source = locate_runtime_dataset(input_root, workspace)
    runtime_base = resolve_runtime_temp_root(temp_root).resolve()
    report_root = resolve_report_output_root(output_root).resolve()
    if runtime_base == report_root or report_root in runtime_base.parents:
        raise InfrastructureFailure("transient runtime root must not be beneath the preserved report output root")
    runtime_base.mkdir(parents=True, exist_ok=True)
    run_id = re.sub(r"[^A-Za-z0-9._-]", "_", str(workspace.get("run_id") or "run"))
    runtime_root = Path(tempfile.mkdtemp(prefix=f"{run_id}-", dir=runtime_base))
    try:
        for relative in dataset_transport_files(workspace):
            destination = runtime_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / relative, destination)
        driver_relative = str(workspace.get("driver_path", ""))
        if not driver_relative or driver_relative in runtime_dataset_files(workspace):
            raise InfrastructureFailure("embedded driver path is invalid for dataset materialization")
        driver_destination = runtime_root / driver_relative
        driver_destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(executing_driver, driver_destination)
        if not validate_runtime_dataset(runtime_root, workspace, allow_materialized_driver=True):
            raise InfrastructureFailure("materialized runtime dataset differs from its embedded manifest")
        checks = verify_runtime_integrity(runtime_root, workspace)
        if not all(checks.values()):
            raise InfrastructureFailure(f"materialized runtime integrity verification failed: {checks}")
        return runtime_root
    except Exception:
        shutil.rmtree(runtime_root, ignore_errors=True)
        raise


def load_embedded_workspace_identity(source_path: Path | None = None) -> dict:
    """Decode identity from this executable and verify its template hash."""
    source = (source_path or Path(__file__)).read_bytes()
    marker = "__RHOMBUS_" + "WORKSPACE_IDENTITY_B64__"
    pattern = re.compile(rb'(?m)^EMBEDDED_WORKSPACE_IDENTITY_B64 = "([^"]*)"\r?$')
    matches = list(pattern.finditer(source))
    if len(matches) != 1:
        raise InfrastructureFailure("embedded identity marker structure is missing or duplicated")
    encoded = matches[0].group(1).decode("ascii", errors="strict")
    if encoded == marker:
        raise InfrastructureFailure("embedded workspace identity payload is missing")
    try:
        payload = base64.b64decode(encoded, validate=True)
        workspace = json.loads(payload.decode("utf-8"))
    except (ValueError, UnicodeError, json.JSONDecodeError) as exc:
        raise InfrastructureFailure(f"embedded workspace identity is malformed: {exc}") from exc
    if not isinstance(workspace, dict) or any(field not in workspace for field in EMBEDDED_IDENTITY_REQUIRED_FIELDS):
        raise InfrastructureFailure("embedded workspace identity is missing required fields")
    reconstructed = source[:matches[0].start(1)] + marker.encode("ascii") + source[matches[0].end(1):]
    if sha256_bytes(canonical_driver_template_bytes(reconstructed)) != workspace["driver_template_sha256"]:
        raise InfrastructureFailure("embedded driver template hash mismatch")
    return workspace


def verify_workspace_integrity(root: Path, workspace: dict) -> dict:
    repository_files = workspace.get("repository_tracked_files")
    if not isinstance(repository_files, list):
        raise InfrastructureFailure("workspace_identity.repository_tracked_files is missing or invalid")
    checks = {"repository_identity_embedded": isinstance(workspace.get("repository_workspace_manifest_sha256"), str)}
    checks.update(verify_runtime_integrity(root, workspace))
    checks["explicitly_staged_input_manifest"] = checks["explicit_obelix_manifest"]
    checks["ordered_expansion_input"] = checks["runtime_ordered_expansion"]
    protected_records = workspace.get("protected_artifacts")
    protected_ok = isinstance(protected_records, list) and bool(protected_records)
    if protected_ok:
        for record in protected_records:
            path = root / str(record.get("path", ""))
            if not path.is_file() or sha256_file(path) != record.get("sha256"):
                protected_ok = False
                break
    checks["protected_artifacts"] = protected_ok
    checks["all_required"] = all(checks.values())
    return checks


def verify_runtime_integrity(root: Path, workspace: dict) -> dict:
    runtime_files = require_workspace_runtime_files(workspace)
    dataset_files = runtime_dataset_files(workspace)
    runtime_manifest = canonical_manifest(root, runtime_files, workspace.get("driver_path"))
    checks = {
        "runtime_manifest": sha256_bytes(runtime_manifest.encode("utf-8")) == workspace.get("runtime_manifest_sha256"),
        "runtime_dataset": validate_runtime_dataset(root, workspace, allow_materialized_driver=True),
        "runtime_ordered_expansion": INPUT_RELATIVE in runtime_files,
        "runtime_explicit_obelix": any(path.startswith("data/obelix/") for path in runtime_files),
    }
    obelix_files = runtime_obelix_files(root)
    checks["explicit_obelix_manifest"] = bool(obelix_files) and sha256_bytes(canonical_manifest(root, obelix_files).encode("utf-8")) == workspace.get("explicitly_staged_input_manifest_sha256")
    if not checks["runtime_ordered_expansion"] or not checks["runtime_explicit_obelix"]:
        return checks
    driver = root / str(workspace.get("driver_path", ""))
    checks["driver_template"] = driver.is_file()
    if checks["driver_template"]:
        source = driver.read_bytes()
        pattern = re.compile(rb'(?m)^(EMBEDDED_WORKSPACE_IDENTITY_B64 = ")([^"]*)(")\r?$')
        matches = list(pattern.finditer(source))
        reconstructed = source[:matches[0].start(2)] + (b"__RHOMBUS_" + b"WORKSPACE_IDENTITY_B64__") + source[matches[0].end(2):] if len(matches) == 1 else b""
        checks["driver_template"] = len(matches) == 1 and sha256_bytes(canonical_driver_template_bytes(reconstructed)) == workspace.get("driver_template_sha256")
    return checks


def load_parents(root: Path):
    try:
        from rudeus.generation.generator import retrieve_obelix_parents
        source = json.loads((root / INPUT_RELATIVE).read_text(encoding="utf-8"))
        ordered_ids = list(source["per_parent"].keys())
        if len(ordered_ids) != 72:
            raise InfrastructureFailure(f"source cohort has {len(ordered_ids)} parents, expected 72")
        config = json.loads("{}")
        import yaml
        config = yaml.safe_load((root / "config.yaml").read_text(encoding="utf-8"))
        available = retrieve_obelix_parents(config["datasets"]["obelix_repo"])
        by_id = {parent.parent_id: parent for parent in available}
        missing = [parent_id for parent_id in ordered_ids if parent_id not in by_id]
        if missing:
            raise InfrastructureFailure(f"source cohort parents missing from staged OBELiX data: {missing}")
        return [by_id[parent_id] for parent_id in ordered_ids]
    except InfrastructureFailure:
        raise
    except Exception as exc:
        raise InfrastructureFailure(f"unable to load source cohort / repository implementation: {exc}") from exc


def run_integrity_self_test() -> None:
    """Exercise runtime dataset, materialization, and identity integrity locally."""
    with tempfile.TemporaryDirectory(prefix="rhombus-integrity-self-test-") as temporary:
        base = Path(temporary)
        root = base / "runtime"
        root.mkdir()
        driver_source = Path(__file__).read_bytes()
        canonical_source = canonical_driver_template_bytes(driver_source)
        crlf_source = canonical_source.replace(b"\n", b"\r\n")
        assert sha256_bytes(canonical_driver_template_bytes(canonical_source)) == sha256_bytes(canonical_driver_template_bytes(crlf_source))
        print("DRIVER_TEMPLATE_LF_CRLF_HASH_EQUIVALENCE=PASS")
        mutated_source = bytes([canonical_source[0] ^ 1]) + canonical_source[1:]
        assert sha256_bytes(canonical_driver_template_bytes(mutated_source)) != sha256_bytes(canonical_driver_template_bytes(canonical_source))
        print("DRIVER_TEMPLATE_SEMANTIC_MUTATION_HASH=PASS")
        dataset_files = sorted([
            *RUNTIME_SOURCE_FILES,
            *OBELIX_RUNTIME_FILES,
            "data/obelix/data/randomized_cifs/synthetic.cif",
        ])
        for relative in dataset_files:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(("fixture:" + relative + "\n").encode("utf-8"))
        (root / RUNTIME_DRIVER_RELATIVE).write_bytes(driver_source)
        identity_pattern = re.compile(rb'(?m)^(EMBEDDED_WORKSPACE_IDENTITY_B64 = ")([^"]*)(")\r?$')
        matches = list(identity_pattern.finditer(driver_source))
        assert len(matches) == 1
        marker = ("__RHOMBUS_" + "WORKSPACE_IDENTITY_B64__").encode("ascii")
        template_bytes = driver_source[:matches[0].start(2)] + marker + driver_source[matches[0].end(2):]
        template_hash = sha256_bytes(canonical_driver_template_bytes(template_bytes))
        runtime_files = [RUNTIME_DRIVER_RELATIVE, *dataset_files]
        runtime_manifest_without_protected = sha256_bytes(
            canonical_manifest(root, runtime_files, RUNTIME_DRIVER_RELATIVE).encode("utf-8")
        )
        protected_relative = "data/batches/audit/synthetic-protected-self-test.json"
        protected_path = root / protected_relative
        protected_path.parent.mkdir(parents=True, exist_ok=True)
        protected_path.write_bytes(b"synthetic protected fixture\n")
        transport_files = sorted([*dataset_files, protected_relative])
        runtime_dataset_hash_without_protected = sha256_bytes(
            canonical_manifest(root, dataset_files).encode("utf-8")
        )
        workspace = {
            "schema_version": "rhombus-workspace-identity-v1",
            "run_id": "self-test-run", "git_head": "self-test-head",
            "branch": "self-test", "tracked_dirty": False,
            "status_porcelain": [],
            "repository_tracked_files": [".github/workflows/cron.yml", *dataset_files],
            "repository_workspace_manifest_sha256": "provenance-only",
            "tracked_delta_sha256": "self-test-delta", "driver_template_sha256": template_hash,
            "driver_path": RUNTIME_DRIVER_RELATIVE, "runtime_files": runtime_files,
            "runtime_dataset_files": dataset_files,
            "runtime_dataset_manifest_sha256": runtime_dataset_hash_without_protected,
            "dataset_transport_files": transport_files,
            "dataset_transport_manifest_sha256": sha256_bytes(
                canonical_manifest(root, transport_files).encode("utf-8")
            ),
            "runtime_manifest_sha256": "",
            "explicitly_staged_untracked_inputs": ["data/obelix"],
            "explicitly_staged_input_manifest_sha256": sha256_bytes(
                canonical_manifest(root, runtime_obelix_files(root)).encode("utf-8")
            ),
            "protected_artifacts": [{
                "path": protected_relative, "sha256": sha256_file(protected_path)
            }],
        }
        workspace["runtime_manifest_sha256"] = sha256_bytes(
            canonical_manifest(root, runtime_files, RUNTIME_DRIVER_RELATIVE).encode("utf-8")
        )
        assert workspace["runtime_manifest_sha256"] == runtime_manifest_without_protected
        identity_json = json.dumps(workspace, sort_keys=True, separators=(",", ":"))
        identity_b64 = base64.b64encode(identity_json.encode("utf-8")).decode("ascii")
        driver = (
            driver_source[:matches[0].start(2)] + identity_b64.encode("ascii")
            + driver_source[matches[0].end(2):]
        )
        driver_path = root / RUNTIME_DRIVER_RELATIVE
        driver_path.write_bytes(driver)

        expected = set(transport_files)
        actual = {
            path.relative_to(root).as_posix() for path in root.rglob("*")
            if path.is_file() and path != driver_path
        }
        assert "config.yaml" in actual and INPUT_RELATIVE in actual
        assert set(runtime_obelix_files(root)) == {
            path for path in dataset_files if path.startswith("data/obelix/")
        }
        assert actual == expected
        assert ".github/workflows/cron.yml" in workspace["repository_tracked_files"]
        assert ".github/workflows/cron.yml" not in expected
        assert protected_relative in workspace["dataset_transport_files"]
        assert protected_relative not in workspace["runtime_dataset_files"]
        assert protected_relative not in workspace["runtime_files"]
        assert sha256_bytes(canonical_manifest(root, dataset_files).encode("utf-8")) == runtime_dataset_hash_without_protected
        assert protected_relative in set(dataset_transport_files(workspace))
        assert not any(
            part in {".git", ".venv", ".opencode"}
            for relative in actual for part in Path(relative).parts
        )
        assert load_embedded_workspace_identity(driver_path) == workspace
        assert all(verify_runtime_integrity(root, workspace).values())
        assert all(verify_workspace_integrity(root, workspace).values())
        marker_line = re.search(rb'(?m)^EMBEDDED_WORKSPACE_IDENTITY_B64 = "[^"]*"\r?$', driver)
        assert marker_line is not None
        malformed_cases = {
            "duplicate": driver + b"\n" + marker_line.group(0),
            "missing": driver[:marker_line.start()] + driver[marker_line.end():],
        }
        for label, malformed_driver in malformed_cases.items():
            malformed_path = base / f"driver-{label}.py"
            malformed_path.write_bytes(malformed_driver)
            try:
                load_embedded_workspace_identity(malformed_path)
            except InfrastructureFailure:
                pass
            else:
                raise AssertionError(f"{label} embedded identity marker was accepted")
        print("DRIVER_TEMPLATE_MARKER_REJECTION=PASS")
        assert str(REMOTE_RUNTIME_TEMP_ROOT).replace("\\", "/").startswith("/kaggle/temp/")
        assert REMOTE_REPORT_OUTPUT_ROOT == Path("/kaggle/working/rhombus_mobile_ion_e2e_output")
        assert resolve_runtime_temp_root() == REMOTE_RUNTIME_TEMP_ROOT
        assert resolve_report_output_root(REMOTE_REPORT_OUTPUT_ROOT) == REMOTE_REPORT_OUTPUT_ROOT
        assert not REMOTE_REPORT_OUTPUT_ROOT.is_relative_to(REMOTE_RUNTIME_TEMP_ROOT)
        assert not REMOTE_RUNTIME_TEMP_ROOT.is_relative_to(REMOTE_REPORT_OUTPUT_ROOT)
        assert not (REMOTE_RUNTIME_TEMP_ROOT / transport_files[0]).is_relative_to(REMOTE_REPORT_OUTPUT_ROOT)

        mount_root = base / "input"
        mount = mount_root / "disambiguated-mount-name"
        for relative in transport_files:
            destination = mount / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / relative, destination)
        assert locate_runtime_dataset(mount_root, workspace) == mount
        report_root = base / "working" / "rhombus_mobile_ion_e2e_output"
        report_root.mkdir(parents=True, exist_ok=True)
        materialized = materialize_runtime_snapshot(
            workspace, input_root=mount_root,
            temp_root=base / "transient" / "rhombus_mobile_ion_runtime",
            output_root=report_root,
            executing_driver=driver_path,
        )
        assert all(verify_runtime_integrity(materialized, workspace).values())
        assert all(verify_workspace_integrity(materialized, workspace).values())
        assert materialized.is_relative_to(base / "transient")
        assert not materialized.is_relative_to(base / "working")
        for record in workspace["protected_artifacts"]:
            protected_materialized = materialized / record["path"]
            assert protected_materialized.is_file()
            assert not protected_materialized.is_relative_to(report_root)
        assert load_embedded_workspace_identity(materialized / RUNTIME_DRIVER_RELATIVE)["run_id"] == "self-test-run"
        try:
            materialize_runtime_snapshot(
                workspace, input_root=mount_root,
                temp_root=report_root / "runtime-tree", output_root=report_root,
                executing_driver=driver_path,
            )
        except InfrastructureFailure:
            pass
        else:
            raise AssertionError("runtime materialization beneath report output root was accepted")

        previous_cwd = Path.cwd()
        previous_sys_path = list(sys.path)
        probe_module = "rhombus_transient_runtime_import_self_test"
        try:
            (materialized / f"{probe_module}.py").write_text("VALUE = 'transient-root'\n", encoding="utf-8")
            activate_runtime_root(materialized)
            imported = importlib.import_module(probe_module)
            assert imported.VALUE == "transient-root"
            assert Path.cwd().resolve() == materialized.resolve()
            assert sys.path[0] == str(materialized.resolve())
        finally:
            sys.modules.pop(probe_module, None)
            sys.path[:] = previous_sys_path
            os.chdir(previous_cwd)
            (materialized / f"{probe_module}.py").unlink(missing_ok=True)

        report_path = report_root / "mobile_ion_displace_e2e_report.json"
        panel_output_path = diagnostic_panel_output_path(report_root)
        report_bytes = write_json(report_path, {"run_id": "self-test-run", "ok": True})
        assert json.loads(report_bytes.decode("utf-8")) == {"run_id": "self-test-run", "ok": True}
        assert report_path.is_file() and report_path.is_relative_to(report_root)
        assert panel_output_path == report_root / Path(ARTIFACT_RELATIVE).name
        assert not report_path.is_relative_to(materialized)
        assert not panel_output_path.is_relative_to(materialized)
        assert {path.name for path in report_root.iterdir()} == {report_path.name}

        wrong_root = base / "wrong-input"
        wrong_mount = wrong_root / "candidate"
        shutil.copytree(mount, wrong_mount)
        wrong_file = wrong_mount / "config.yaml"
        wrong_file.write_bytes(wrong_file.read_bytes() + b"tampered\n")
        try:
            locate_runtime_dataset(wrong_root, workspace, diagnostic_writer=lambda *_args, **_kwargs: None)
        except InfrastructureFailure:
            pass
        else:
            raise AssertionError("wrong candidate mount was accepted")

        ambiguous_root = base / "ambiguous-input"
        shutil.copytree(mount, ambiguous_root / "first")
        shutil.copytree(mount, ambiguous_root / "second")
        try:
            locate_runtime_dataset(ambiguous_root, workspace, diagnostic_writer=lambda *_args, **_kwargs: None)
        except InfrastructureFailure:
            pass
        else:
            raise AssertionError("ambiguous matching mounts were accepted")

        for relative in ("config.yaml", INPUT_RELATIVE,
                         "data/obelix/data/randomized_cifs/synthetic.cif"):
            path = root / relative
            original = path.read_bytes()
            path.write_bytes(original + b"changed\n")
            try:
                valid = all(verify_runtime_integrity(root, workspace).values())
            except InfrastructureFailure:
                valid = False
            assert not valid
            path.write_bytes(original)
        for relative in ("config.yaml", OBELIX_RUNTIME_FILES[0]):
            path = root / relative
            original = path.read_bytes()
            path.unlink()
            try:
                valid = all(verify_runtime_integrity(root, workspace).values())
            except InfrastructureFailure:
                valid = False
            assert not valid
            path.write_bytes(original)
        original = protected_path.read_bytes()
        protected_path.write_bytes(original + b"mutated\n")
        assert not validate_runtime_dataset(root, workspace)
        assert not verify_workspace_integrity(root, workspace)["protected_artifacts"]
        protected_path.write_bytes(original)
        protected_path.unlink()
        assert not validate_runtime_dataset(root, workspace)
        assert not verify_workspace_integrity(root, workspace)["protected_artifacts"]
        protected_path.write_bytes(original)
        assert load_embedded_workspace_identity(driver_path)["run_id"] == "self-test-run"
        print("RUNTIME_OUTPUT_BOUNDARY_SELF_TEST=PASS")
    print("INTEGRITY_SELF_TEST=PASS")


def canonical_manifest_self_test(root: Path) -> None:
    paths = sorted(
        path.relative_to(root).as_posix() for path in root.rglob("*")
        if path.is_file() and path.relative_to(root).as_posix() != "dataset-metadata.json"
    )
    manifest = canonical_manifest(root, paths)
    encoded = base64.b64encode(manifest.encode("utf-8")).decode("ascii")
    print(f"CANONICAL_MANIFEST_B64={encoded}")
    print(f"CANONICAL_MANIFEST_SHA256={sha256_bytes(manifest.encode('utf-8'))}")


def count_rows(rows):
    generated = [row for row in rows if row.get("diagnostic_state") == "GENERATED"]
    return {
        "requested_parents": len(rows),
        "blocked_parents": sum(row.get("diagnostic_state") == "BLOCKED_BY_PARENT_P0" for row in rows),
        "inapplicable_parents": sum(row.get("diagnostic_state") == "INAPPLICABLE" for row in rows),
        "generated_children": len(generated),
        "novel": sum(row.get("novelty_tag") == "novel" for row in generated),
        "rediscovery": sum(row.get("novelty_tag") == "rediscovery" for row in generated),
        "p0_plausible": sum(row.get("p0_state") == "PLAUSIBLE" for row in generated),
        "geometry_failures": sum(row.get("p0_geometry_ok") is False for row in generated),
        "useful_diagnostic_yield": sum(row.get("novelty_tag") == "novel" and row.get("p0_state") == "PLAUSIBLE" for row in generated),
    }


def close_enough(left, right):
    return abs(float(left) - float(right)) <= 1e-15


def require(condition: bool, message: str):
    if not condition:
        raise ScientificValidationFailure(message)


def validate_panel(panel: dict, protected_before: list[dict], protected_after: list[dict],
                  pass1: bytes, pass2: bytes, final_versions: dict) -> dict:
    checks = {}
    failures = []
    def check(name, condition, message):
        checks[name] = bool(condition)
        if not condition:
            failures.append(message)

    rows = panel.get("rows")
    runs = panel.get("runs")
    summary = panel.get("summary")
    check("panel_schema", isinstance(rows, list) and isinstance(runs, list) and isinstance(summary, dict), "panel schema missing rows/runs/summary")
    if not checks["panel_schema"]:
        result = {**checks, "regression_reference": {"status": "NOT_COMPARABLE", "match": False, "reason": "panel schema missing"}, "failure": failures[0]}
        raise ScientificValidationFailure(json.dumps(result, sort_keys=True))
    row_accounting = len(rows) == 864
    check("row_accounting", row_accounting, f"expected 864 rows, found {len(rows)}")
    expected_pairs = {(sigma, seed) for sigma in SIGMAS for seed in SEEDS}
    actual_pairs = [(run.get("sigma_A_provisional"), run.get("base_seed")) for run in runs]
    run_accounting = len(runs) == 12 and set(actual_pairs) == expected_pairs and len(set(actual_pairs)) == 12
    check("run_accounting", run_accounting, "sigma/seed run accounting is not exactly 12 unique pairs")
    run_summaries_ok = True
    for run in runs:
        pair_rows = [r for r in rows if (r.get("sigma_A_provisional"), r.get("base_seed")) == (run.get("sigma_A_provisional"), run.get("base_seed"))]
        run_summaries_ok = run_summaries_ok and run.get("summary") == count_rows(pair_rows) and len(pair_rows) == 72
    check("run_summary_reconciliation", run_summaries_ok, "run summary or row accounting mismatch")

    global_freq = summary.get("per_parent_useful_frequency", {})
    global_geom = summary.get("per_parent_geometry_failure_frequency", {})
    global_reconciliation = True
    for parent_id in set(global_freq) | set(global_geom):
        parent_rows = [r for r in rows if r.get("parent_id") == parent_id]
        generated = [r for r in parent_rows if r.get("diagnostic_state") == "GENERATED"]
        observations = len(generated)
        useful = sum(r.get("novelty_tag") == "novel" and r.get("p0_state") == "PLAUSIBLE" for r in generated)
        geometry = sum(r.get("p0_geometry_ok") is False for r in generated)
        useful_item, geom_item = global_freq.get(parent_id), global_geom.get(parent_id)
        ok = useful_item is not None and geom_item is not None
        if ok:
            ok = (useful_item.get("observations_count") == observations and useful_item.get("useful_count") == useful and
                  close_enough(useful_item.get("useful_frequency"), useful / observations if observations else 0.0) and
                  geom_item.get("observations_count") == observations and geom_item.get("geometry_fail_count") == geometry and
                  close_enough(geom_item.get("geometry_fail_frequency"), geometry / observations if observations else 0.0) and
                  0.0 <= useful_item.get("useful_frequency") <= 1.0 and 0.0 <= geom_item.get("geometry_fail_frequency") <= 1.0)
        global_reconciliation = global_reconciliation and ok
    check("global_frequency_reconciliation", global_reconciliation, "global frequency reconciliation failed")

    per_sigma = summary.get("parent_persistence_by_sigma", {})
    per_sigma_reconciliation = True
    for sigma in SIGMAS:
        sigma_key = str(sigma)
        sigma_rows = [r for r in rows if r.get("sigma_A_provisional") == sigma]
        stored = per_sigma.get(sigma_key, {})
        for parent_id in {r.get("parent_id") for r in sigma_rows}:
            generated = [r for r in sigma_rows if r.get("parent_id") == parent_id and r.get("diagnostic_state") == "GENERATED"]
            useful = sum(r.get("novelty_tag") == "novel" and r.get("p0_state") == "PLAUSIBLE" for r in generated)
            item = stored.get(parent_id)
            ok = item is not None and item.get("generated_count") == len(generated) and item.get("observations_count") == len(generated) and item.get("useful_count") == useful and close_enough(item.get("useful_frequency"), useful / len(generated) if generated else 0.0) and item.get("persistent_useful") == ((useful / len(generated) if generated else 0.0) >= PERSISTENT_THRESHOLD)
            per_sigma_reconciliation = per_sigma_reconciliation and ok
    check("per_sigma_reconciliation", per_sigma_reconciliation, "per-sigma persistence reconciliation failed")

    auth = panel.get("authorization", {})
    authorization = (panel.get("artifact_type") == "OBSERVATIONAL_DIAGNOSTIC" and
                     auth.get("scheduler_activation") is False and auth.get("p1_eligibility") is False and
                     auth.get("downstream_scientific_superiority_claim") is False and
                     panel.get("activation_authorized") is False and panel.get("p1_eligibility_authorized") is False and
                     panel.get("downstream_scientific_claims_authorized") is False)
    check("authorization", authorization, "observational diagnostic authorization contract violated")
    determinism = pass1 == pass2
    check("determinism", determinism, "generation pass bytes are not identical")
    historical = protected_before == protected_after
    check("historical_isolation", historical, "protected historical artifact changed during execution")

    regression = {"status": "NOT_COMPARABLE", "match": False, "reason": ""}
    regression["reason"] = "no authoritative historical workspace identity is available for the reference summaries"

    checks["regression_reference"] = regression["status"] == "NOT_COMPARABLE"
    result = {**checks, "determinism_byte_identical": determinism, "regression_reference": regression}
    if failures:
        result["failure"] = failures[0]
        raise ScientificValidationFailure(json.dumps(result, sort_keys=True))
    return result


def select_m6a_parents(parents):
    by_id = {parent.parent_id: parent for parent in parents}
    missing = [parent_id for parent_id in M6A_PARENT_IDS if parent_id not in by_id]
    if missing:
        raise InfrastructureFailure(f"M6-A selected parents missing from staged cohort: {missing}")
    if len(by_id) != len(parents):
        raise InfrastructureFailure("M6-A source cohort contains duplicate parent identities")
    return [by_id[parent_id] for parent_id in M6A_PARENT_IDS]


def validate_m6a_panel(panel: dict, pass1: bytes, pass2: bytes) -> dict:
    """Validate the fixed 12-parent paired diagnostic without v1 864-row assumptions."""
    checks = {}
    failures = []

    def check(name, condition, message):
        checks[name] = bool(condition)
        if not condition:
            failures.append(message)

    if not isinstance(panel, dict):
        raise ScientificValidationFailure(json.dumps({
            "m6a_schema": False, "failure": "M6-A observational panel must be an object",
        }, sort_keys=True))
    metadata = panel.get("metadata")
    rows = panel.get("rows") if isinstance(panel, dict) else None
    arms_expected = {"BASELINE_GAUSSIAN", "GAUSSIAN_LOCAL_D8"}
    operator_contract = {
        "BASELINE_GAUSSIAN": ("mobile-ion-displace", "mobile-ion-displace-v2"),
        "GAUSSIAN_LOCAL_D8": (M6A_OPERATOR_NAME, M6A_OPERATOR_VERSION),
    }
    check("m6a_schema", panel.get("schema_version") == "candidate-supply-v2-operator-tournament-v1"
          and panel.get("artifact_type") == "OBSERVATIONAL_DIAGNOSTIC"
          and isinstance(metadata, dict) and isinstance(rows, list)
          and all(isinstance(row, dict) for row in rows)
          and isinstance(panel.get("summary"), dict)
          and isinstance(panel.get("authorization"), dict),
          "M6-A observational panel schema mismatch")
    if not checks["m6a_schema"]:
        raise ScientificValidationFailure(json.dumps({**checks, "failure": failures[0]}, sort_keys=True))
    check("m6a_selection", metadata.get("ordered_parent_ids") == list(M6A_PARENT_IDS)
          and metadata.get("failure_count_bands") == {
              band: [{"parent_id": parent_id, "historical_geometry_failures": count}
                     for parent_id, count in members]
              for band, members in M6A_PARENT_FAILURE_BANDS.items()
          }
          and metadata.get("selection_rule") == (
              "first four parent IDs in lexical order within each immutable "
              "version-9 repeated-geometry-failure count band: >=10, 5-9, 2-4"
          )
          and metadata.get("version_9_freeze_sha256") == M6A_VERSION_9_FREEZE_SHA256
          and metadata.get("version_9_panel_sha256") == M6A_VERSION_9_PANEL_SHA256,
          "M6-A parent selection or historical strata mismatch")
    check("m6a_configuration", metadata.get("mobile_ion") == M6A_TARGET_SPECIES
          and metadata.get("sigma_values_A_provisional") == [M6A_SIGMA]
          and metadata.get("base_seeds") == list(M6A_SEEDS)
          and metadata.get("diagnostic_config_hash") == M6A_CONFIG_IDENTITY
          and metadata.get("configurations") == ["BASELINE_GAUSSIAN", "GAUSSIAN_LOCAL_D8"]
          and metadata.get("include_bounded_clearance") is False
          and metadata.get("gaussian_local_direction_budgets") == [M6A_DIRECTION_BUDGET]
          and metadata.get("configuration_details") == [
              {"id": "BASELINE_GAUSSIAN", "operator_name": "mobile-ion-displace",
               "operator_version": "mobile-ion-displace-v2", "budget": None},
              {"id": "GAUSSIAN_LOCAL_D8", "operator_name": M6A_OPERATOR_NAME,
               "operator_version": M6A_OPERATOR_VERSION,
               "budget": M6A_DIRECTION_BUDGET},
          ],
          "M6-A paired arm/configuration identity mismatch")
    authorization = panel.get("authorization", {})
    check("authorization", all(value is False for value in (
        authorization.get("scheduler_activation"), authorization.get("p1_eligibility"),
        authorization.get("operator_superiority"), authorization.get("automatic_promotion"),
        authorization.get("downstream_diffusion_claim"), authorization.get("threshold_modification"),
    )), "M6-A authorization boundary violated")
    expected_pairs = {(parent_id, seed) for parent_id in M6A_PARENT_IDS for seed in M6A_SEEDS}
    actual_pairs = [(row.get("parent_id"), row.get("base_seed")) for row in rows]
    expected_pair_order = [(parent_id, seed) for parent_id in M6A_PARENT_IDS for seed in M6A_SEEDS]
    check("pair_accounting", len(rows) == 24 and len(set(actual_pairs)) == 24
          and set(actual_pairs) == expected_pairs and actual_pairs == expected_pair_order,
          "M6-A pair accounting is not exactly 12 parents x 2 seeds")
    source_hashes = metadata.get("source_structure_hashes")
    source_hashes_valid = (
        isinstance(source_hashes, list) and len(source_hashes) == len(M6A_PARENT_IDS)
        and all(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)
                for value in source_hashes)
    )
    check("source_identity", source_hashes_valid,
          "M6-A source structure identities are missing or malformed")
    per_arm = {arm: {"requested": 0, "blocked": 0, "inapplicable": 0,
                     "attempted": 0, "generated": 0, "accepted": 0, "exhausted": 0,
                     "geometry_fail": 0, "novel": 0, "rediscovery": 0,
                     "p0_plausible": 0, "useful": 0} for arm in arms_expected}
    rows_valid = True
    for row in rows:
        arms = row.get("arms")
        expected_pair_id = hashlib.sha256(json.dumps({
            "parent_id": row.get("parent_id"),
            "sigma_A_provisional": M6A_SIGMA,
            "base_seed": row.get("base_seed"),
        }, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()
        if (row.get("target_species") != M6A_TARGET_SPECIES
                or row.get("sigma_A_provisional") != M6A_SIGMA
                or row.get("diagnostic_config_hash") != M6A_CONFIG_IDENTITY
                or row.get("pair_id") != expected_pair_id
                or (row.get("parent_id") in M6A_PARENT_IDS and source_hashes_valid
                    and row.get("parent_source_structure_sha256")
                    != source_hashes[M6A_PARENT_IDS.index(row["parent_id"])])
                or not isinstance(row.get("pair_rng_identity"), str)
                or not row.get("pair_rng_identity")
                or type(row.get("pair_rng_seed")) is not int
                or not isinstance(row.get("gaussian_local_rng_identity"), str)
                or not row.get("gaussian_local_rng_identity")
                or type(row.get("gaussian_local_rng_seed")) is not int
                or not isinstance(arms, dict) or set(arms) != arms_expected):
            rows_valid = False
            continue
        for arm_id, arm in arms.items():
            metrics = per_arm[arm_id]
            metrics["requested"] += 1
            if ((arm.get("operator_name"), arm.get("operator_version"))
                    != operator_contract[arm_id]):
                rows_valid = False
                continue
            if (not isinstance(arm.get("operator_rng_identity"), str)
                    or not arm["operator_rng_identity"]
                    or type(arm.get("operator_rng_seed")) is not int):
                rows_valid = False
                continue
            identity_key = ("pair_rng_identity", "pair_rng_seed") if arm_id == "BASELINE_GAUSSIAN" else (
                "gaussian_local_rng_identity", "gaussian_local_rng_seed"
            )
            if (arm.get("operator_rng_identity") != row.get(identity_key[0])
                    or arm.get("operator_rng_seed") != row.get(identity_key[1])):
                rows_valid = False
                continue
            if arm.get("status") in ("BLOCKED_BY_PARENT_P0", "INAPPLICABLE"):
                if (arm.get("generated") is not False or arm.get("child_material_id") is not None
                        or any(arm.get(field) is not None for field in (
                            "child_structure_dict", "novelty_tag", "novelty_matched",
                            "novelty_matcher_version", "p0_state", "p0_plausible",
                            "p0_neutrality_ok", "p0_pauling_ok", "p0_geometry_ok",
                            "geometry_ok", "p0_details", "useful",
                        ))):
                    rows_valid = False
                else:
                    metrics["blocked" if arm["status"] == "BLOCKED_BY_PARENT_P0"
                            else "inapplicable"] += 1
                continue
            metrics["attempted"] += 1
            if arm_id == "BASELINE_GAUSSIAN":
                if arm.get("status") != "GENERATED" or arm.get("generated") is not True:
                    rows_valid = False
                    continue
            elif arm.get("status") == "EXHAUSTED":
                if (arm.get("generated") is not False or arm.get("novelty_tag") is not None
                        or any(arm.get(field) is not None for field in (
                            "child_structure_dict", "novelty_matched", "novelty_matcher_version",
                            "p0_state", "p0_plausible", "p0_neutrality_ok", "p0_pauling_ok",
                            "p0_geometry_ok", "geometry_ok", "p0_details", "useful",
                        ))
                        or arm.get("child_material_id") is not None):
                    rows_valid = False
                    continue
                metrics["exhausted"] += 1
                continue
            elif arm.get("status") != "ACCEPTED" or arm.get("generated") is not True:
                rows_valid = False
                continue
            if (not isinstance(arm.get("child_material_id"), str)
                    or not isinstance(arm.get("child_structure_dict"), dict)
                    or arm.get("novelty_tag") not in ("novel", "rediscovery")
                    or arm.get("novelty_matcher_version") != "novelty-matcher-v2-same-cell"
                    or not isinstance(arm.get("p0_state"), str)
                    or type(arm.get("p0_plausible")) is not bool
                    or type(arm.get("p0_neutrality_ok")) is not bool
                    or type(arm.get("p0_pauling_ok")) is not bool
                    or type(arm.get("p0_geometry_ok")) is not bool
                    or not isinstance(arm.get("p0_details"), dict)
                    or type(arm.get("geometry_ok")) is not bool
                    or arm.get("useful") is not (arm.get("novelty_tag") == "novel"
                                                   and arm.get("p0_plausible") is True)):
                rows_valid = False
                continue
            if arm_id == "GAUSSIAN_LOCAL_D8" and arm.get("geometry_ok") is not True:
                rows_valid = False
            metrics["generated"] += 1
            metrics["accepted"] += arm_id != "BASELINE_GAUSSIAN"
            metrics["geometry_fail"] += arm["geometry_ok"] is False
            metrics["novel"] += arm["novelty_tag"] == "novel"
            metrics["rediscovery"] += arm["novelty_tag"] == "rediscovery"
            metrics["p0_plausible"] += arm["p0_plausible"] is True
            metrics["useful"] += arm["useful"] is True
    check("raw_rows", rows_valid, "M6-A raw pair/arm evidence is incomplete or inconsistent")
    summaries_match = True
    summary_arms = panel["summary"].get("arms")
    if not isinstance(summary_arms, dict):
        summaries_match = False
    for arm_id, values in per_arm.items():
        attempted, generated = values["attempted"], values["generated"]
        novel, useful = values["novel"], values["useful"]
        values.update({
            "generated_over_attempted": generated / attempted if attempted else 0.0,
            "novel_over_attempted": novel / attempted if attempted else 0.0,
            "novel_over_generated": novel / generated if generated else 0.0,
            "useful_over_attempted": useful / attempted if attempted else 0.0,
            "useful_over_generated": useful / generated if generated else 0.0,
        })
        summary_arm = summary_arms.get(arm_id) if isinstance(summary_arms, dict) else None
        if not isinstance(summary_arm, dict) or any(
                summary_arm.get(key) != value for key, value in values.items()):
            summaries_match = False
    check("summary_reconciliation", summaries_match,
          "M6-A arm summaries do not reconcile with raw rows")
    check("pass_identity", isinstance(pass1, bytes) and isinstance(pass2, bytes)
          and pass1 == pass2,
          "M6-A generation pass bytes are not identical")
    if failures:
        result = {**checks, "failure": failures[0]}
        raise ScientificValidationFailure(json.dumps(result, sort_keys=True))
    return checks


def select_m6b_parents(parents):
    """Select the preregistered, family-stratified M6-B cohort by exact identity."""
    by_id = {parent.parent_id: parent for parent in parents}
    if len(by_id) != len(parents):
        raise InfrastructureFailure("M6-B source cohort contains duplicate parent identities")
    selected = []
    for parent_id, family in zip(M6B_PARENT_IDS, M6B_PARENT_FAMILIES):
        parent = by_id.get(parent_id)
        if parent is None:
            raise InfrastructureFailure(f"M6-B selected parent missing from staged cohort: {parent_id}")
        if parent.chemical_family != family:
            raise InfrastructureFailure(f"M6-B frozen family mismatch for {parent_id}")
        selected.append(parent)
    return selected


def _m6b_panel_provenance(panel, parents):
    from rudeus.generation.mobile_ion_diagnostic import structure_sha256

    panel["metadata"].update({
        "selection_rule": M6B_SELECTION_RULE,
        "ordered_parent_ids": list(M6B_PARENT_IDS),
        "ordered_cohort_identity": hashlib.sha256(json.dumps(
            list(M6B_PARENT_IDS), ensure_ascii=False, separators=(",", ":"),
        ).encode("utf-8")).hexdigest(),
        "parent_chemical_families": list(M6B_PARENT_FAMILIES),
        "version_9_freeze_sha256": M6A_VERSION_9_FREEZE_SHA256,
        "version_9_panel_sha256": M6A_VERSION_9_PANEL_SHA256,
        "excluded_m6a_parent_ids": list(M6A_PARENT_IDS),
        "source_structure_hashes": [structure_sha256(parent.structure) for parent in parents],
        "advancement_interpretation_rule": M6B_ADVANCEMENT_RULE,
    })
    return panel


def validate_m6b_panel(panel: dict, pass1: bytes, pass2: bytes) -> dict:
    """Fail-closed validation of the preregistered M6-B observational pairs."""
    from rudeus.generation.mobile_ion_diagnostic import _tournament_summaries

    failures = []
    checks = {}

    def check(name, condition):
        checks[name] = bool(condition)
        if not condition:
            failures.append(name)

    metadata = panel.get("metadata") if isinstance(panel, dict) else None
    rows = panel.get("rows") if isinstance(panel, dict) else None
    details = [
        {"id": "BASELINE_GAUSSIAN", "operator_name": "mobile-ion-displace",
         "operator_version": "mobile-ion-displace-v2", "budget": None},
        {"id": "GAUSSIAN_LOCAL_D8", "operator_name": M6A_OPERATOR_NAME,
         "operator_version": M6A_OPERATOR_VERSION, "budget": M6B_DIRECTION_BUDGET},
    ]
    check("schema", isinstance(panel, dict)
          and panel.get("schema_version") == "candidate-supply-v2-operator-tournament-v1"
          and panel.get("artifact_type") == "OBSERVATIONAL_DIAGNOSTIC"
          and isinstance(metadata, dict) and isinstance(rows, list)
          and isinstance(panel.get("summary"), dict))
    if not checks["schema"]:
        raise ScientificValidationFailure(json.dumps({**checks, "failure": "M6-B panel schema"}, sort_keys=True))

    check("selection", metadata.get("ordered_parent_ids") == list(M6B_PARENT_IDS)
          and metadata.get("parent_chemical_families") == list(M6B_PARENT_FAMILIES)
          and metadata.get("selection_rule") == M6B_SELECTION_RULE
          and metadata.get("ordered_cohort_identity") == hashlib.sha256(json.dumps(
              list(M6B_PARENT_IDS), ensure_ascii=False, separators=(",", ":"),
          ).encode("utf-8")).hexdigest()
          and metadata.get("excluded_m6a_parent_ids") == list(M6A_PARENT_IDS)
          and metadata.get("version_9_freeze_sha256") == M6A_VERSION_9_FREEZE_SHA256
          and metadata.get("version_9_panel_sha256") == M6A_VERSION_9_PANEL_SHA256)
    check("configuration", metadata.get("mobile_ion") == "Li"
          and metadata.get("sigma_values_A_provisional") == [M6B_SIGMA]
          and metadata.get("base_seeds") == list(M6B_SEEDS)
          and metadata.get("diagnostic_config_hash") == M6B_CONFIG_IDENTITY
          and metadata.get("configurations") == ["BASELINE_GAUSSIAN", "GAUSSIAN_LOCAL_D8"]
          and metadata.get("include_bounded_clearance") is False
          and metadata.get("gaussian_local_direction_budgets") == [M6B_DIRECTION_BUDGET]
          and metadata.get("configuration_details") == details
          and metadata.get("novelty_matcher_version") == "novelty-matcher-v2-same-cell")
    authorization = panel.get("authorization", {})
    check("authorization", all(value is False for value in (
        authorization.get("scheduler_activation"), authorization.get("p1_eligibility"),
        authorization.get("operator_superiority"), authorization.get("automatic_promotion"),
        authorization.get("downstream_diffusion_claim"), authorization.get("threshold_modification"),
    )) and panel.get("activation_authorized") is False
        and panel.get("p1_eligibility_authorized") is False
        and panel.get("downstream_scientific_claims_authorized") is False)

    expected_order = [(parent, seed) for parent in M6B_PARENT_IDS for seed in M6B_SEEDS]
    actual_order = [(row.get("parent_id"), row.get("base_seed")) for row in rows]
    check("paired_identity_accounting", len(rows) == 45 and actual_order == expected_order
          and len(set(actual_order)) == 45)
    source_hashes = metadata.get("source_structure_hashes")
    check("source_identity", isinstance(source_hashes, list) and len(source_hashes) == 15
          and all(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)
                  for value in source_hashes))

    arms_expected = {"BASELINE_GAUSSIAN", "GAUSSIAN_LOCAL_D8"}
    op_contract = {
        "BASELINE_GAUSSIAN": ("mobile-ion-displace", "mobile-ion-displace-v2"),
        "GAUSSIAN_LOCAL_D8": (M6A_OPERATOR_NAME, M6A_OPERATOR_VERSION),
    }
    row_valid = checks["paired_identity_accounting"] and checks["source_identity"]
    for index, row in enumerate(rows):
        parent_index = index // len(M6B_SEEDS)
        expected_parent = M6B_PARENT_IDS[parent_index]
        expected_family = M6B_PARENT_FAMILIES[parent_index]
        expected_seed = M6B_SEEDS[index % len(M6B_SEEDS)]
        expected_pair_id = hashlib.sha256(json.dumps({
            "parent_id": expected_parent, "sigma_A_provisional": M6B_SIGMA,
            "base_seed": expected_seed,
        }, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()
        arms = row.get("arms")
        if (row.get("parent_id") != expected_parent or row.get("base_seed") != expected_seed
                or row.get("chemical_family") != expected_family
                or row.get("parent_source_structure_sha256") != source_hashes[parent_index]
                or row.get("target_species") != "Li"
                or row.get("sigma_A_provisional") != M6B_SIGMA
                or row.get("diagnostic_config_hash") != M6B_CONFIG_IDENTITY
                or row.get("pair_id") != expected_pair_id
                or not isinstance(row.get("pair_rng_identity"), str)
                or type(row.get("pair_rng_seed")) is not int
                or not isinstance(row.get("gaussian_local_rng_identity"), str)
                or type(row.get("gaussian_local_rng_seed")) is not int
                or not isinstance(arms, dict) or set(arms) != arms_expected):
            row_valid = False
            continue
        for arm_id in arms_expected:
            arm = arms[arm_id]
            expected_rng = ((row["pair_rng_identity"], row["pair_rng_seed"])
                            if arm_id == "BASELINE_GAUSSIAN" else
                            (row["gaussian_local_rng_identity"], row["gaussian_local_rng_seed"]))
            status = arm.get("status")
            if ((arm.get("operator_name"), arm.get("operator_version")) != op_contract[arm_id]
                    or arm.get("operator_rng_identity") != expected_rng[0]
                    or arm.get("operator_rng_seed") != expected_rng[1]):
                row_valid = False
                continue
            if status in ("BLOCKED_BY_PARENT_P0", "INAPPLICABLE"):
                if arm.get("generated") is not False or arm.get("child_material_id") is not None:
                    row_valid = False
            elif status == "EXHAUSTED" and arm_id == "GAUSSIAN_LOCAL_D8":
                if (arm.get("generated") is not False or arm.get("child_material_id") is not None
                        or arm.get("novelty_tag") is not None or arm.get("p0_state") is not None
                        or arm.get("geometry_ok") is not None or arm.get("useful") is not None):
                    row_valid = False
            elif status == ("GENERATED" if arm_id == "BASELINE_GAUSSIAN" else "ACCEPTED"):
                if (arm.get("generated") is not True or not isinstance(arm.get("child_material_id"), str)
                        or not isinstance(arm.get("child_structure_dict"), dict)
                        or arm.get("novelty_tag") not in ("novel", "rediscovery")
                        or arm.get("novelty_matcher_version") != "novelty-matcher-v2-same-cell"
                        or type(arm.get("geometry_ok")) is not bool
                        or type(arm.get("p0_plausible")) is not bool
                        or arm.get("useful") is not (arm.get("novelty_tag") == "novel"
                                                       and arm.get("p0_plausible") is True)):
                    row_valid = False
            else:
                row_valid = False
    check("raw_rows", row_valid)
    try:
        recomputed = _tournament_summaries(rows, details, [M6B_SIGMA], list(M6B_PARENT_IDS))
        check("summary_reconciliation", json.dumps(
            recomputed, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        ) == json.dumps(
            panel.get("summary"), sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        ))
    except Exception:
        check("summary_reconciliation", False)
    check("pass_identity", isinstance(pass1, bytes) and isinstance(pass2, bytes) and pass1 == pass2)
    if failures:
        raise ScientificValidationFailure(json.dumps({
            **checks, "failure": "M6-B validation failed: " + ", ".join(failures),
        }, sort_keys=True))
    return checks


def main() -> int:
    observer = StageObservability()
    output = resolve_report_output_root().resolve()
    output.mkdir(parents=True, exist_ok=True)
    report_path = output / "mobile_ion_displace_e2e_report.json"
    panel_path = diagnostic_panel_output_path(output)
    root = None
    protected = []
    protected_before = None
    protected_after = None
    protected_state_persisted = False
    protection_basis = "historical protection not yet evaluated"
    workspace = {}
    try:
        workspace = load_embedded_workspace_identity()
    except Exception as exc:
        embedded_error = exc
    report = {"schema_version": "mobile-ion-displace-e2e-report-v1", "test_identity": TEST_IDENTITY, "config_identity": CONFIG_IDENTITY, "run_id": workspace.get("run_id"), "workspace": workspace, "repository_identity": workspace, "runtime_integrity": {}, "environment": {}, "kaggle": {"kernel_ref": os.environ.get("KAGGLE_KERNEL_REF", "wt2018mask/rhombus-mobile-ion-e2e"), "accelerator": "CPU"}, "execution": {"generation_pass_1_success": False, "generation_pass_2_success": False}, "artifact": {"relative_path": ARTIFACT_RELATIVE}, "validations": {}, "integrity_checks": {}, "protected_protection_basis": protection_basis, "protected_artifacts": [], "observability": observer.snapshot(), "final_classification": "INFRA_FAILURE"}
    initial_environment = None
    try:
        if "embedded_error" in locals():
            raise embedded_error
        execution_identity = require_prepared_execution_identity(workspace)
        execution_mode = execution_identity["execution_mode"]
        expected_kernel_identity = workspace.get("provider_kernel_identity", "wt2018mask/rhombus-mobile-ion-e2e")
        runtime_kernel_identity = os.environ.get("KAGGLE_KERNEL_REF")
        if runtime_kernel_identity and runtime_kernel_identity != expected_kernel_identity:
            raise InfrastructureFailure("runtime Kaggle kernel identity differs from PREPARED workspace")
        report["kaggle"]["kernel_ref"] = expected_kernel_identity
        report["test_identity"] = (
            "mobile-ion-pass-identity-canary-v1" if execution_mode == "PASS_IDENTITY_CANARY"
            else "candidate-supply-v2-m6a-paired-diagnostic-v1"
            if execution_mode == "M6A_PAIRED_DIAGNOSTIC"
            else "candidate-supply-v2-m6b-independent-paired-diagnostic-v1"
            if execution_mode == "M6B_PAIRED_DIAGNOSTIC" else TEST_IDENTITY
        )
        report["config_identity"] = execution_identity["configuration_identity"]
        reexecuted = os.environ.get(BOOTSTRAP_MARKER) == "1"
        if reexecuted:
            root = Path(os.environ.get(BOOTSTRAP_RUNTIME_ROOT, "")).resolve()
            if not os.environ.get(BOOTSTRAP_RUNTIME_ROOT) or not root.is_dir():
                raise InfrastructureFailure("bootstrap handoff runtime root is unavailable")
            initial_environment = _initial_environment_from_handoff(workspace, root, output)
        else:
            root = materialize_runtime_snapshot(
                workspace,
                input_root=Path("/kaggle/input"),
                temp_root=resolve_runtime_temp_root(),
                output_root=output,
                executing_driver=Path(__file__).resolve(),
            )
        activate_runtime_root(root)
        protected, protection_basis = protected_paths(root)
        report["protected_protection_basis"] = protection_basis
        report["runtime_integrity"] = verify_runtime_integrity(root, workspace)
        report["integrity_checks"] = verify_workspace_integrity(root, workspace)
        if not report["integrity_checks"]["all_required"]:
            raise InfrastructureFailure(f"workspace integrity verification failed: {report['integrity_checks']}")
        observer.stage("runtime_integrity_verified")
        observer.stage("environment_bootstrap_start")
        if initial_environment is None:
            observer.bootstrap("final_environment_probe", "START")
            initial_environment, initial_import_errors = probe_environment(
                sys.executable, timeout=FINAL_ENVIRONMENT_PROBE_TIMEOUT_SECONDS,
            )
            observer.bootstrap("final_environment_probe", "DONE")
            current_environment, current_import_errors = initial_environment, initial_import_errors
        else:
            observer.bootstrap("final_environment_probe", "START")
            current_environment, current_import_errors = probe_environment(
                sys.executable, timeout=FINAL_ENVIRONMENT_PROBE_TIMEOUT_SECONDS,
            )
            observer.bootstrap("final_environment_probe", "DONE")
        action = environment_action(current_environment, reexecuted=reexecuted)
        if action == "ERROR":
            report["environment"] = environment_report(
                initial_environment, current_environment, True, current_import_errors,
            )
            raise InfrastructureFailure(
                f"re-executed environment does not exactly match reference: {current_environment}; "
                f"import errors: {current_import_errors}"
            )
        if action == "BOOTSTRAP":
            report["environment"] = environment_report(
                initial_environment, current_environment, False, current_import_errors,
            )
            bootstrap_status = {"dependency_install_performed": False}
            try:
                exact_python = bootstrap_exact_environment(
                    root, integrity_verified=True, status=bootstrap_status, observer=observer,
                )
            except Exception:
                report["environment"] = environment_report(
                    initial_environment, current_environment,
                    bootstrap_status["dependency_install_performed"], current_import_errors,
                )
                raise
            try:
                observer.bootstrap("final_environment_probe", "START")
                final_environment, final_import_errors = probe_environment(
                    exact_python, timeout=FINAL_ENVIRONMENT_PROBE_TIMEOUT_SECONDS,
                )
                observer.bootstrap("final_environment_probe", "DONE")
            except Exception as exc:
                raise bootstrap_stage_failure(
                    "final_environment_probe", f"{type(exc).__name__}: {exc}",
                ) from exc
            report["environment"] = environment_report(
                initial_environment, final_environment, True, final_import_errors,
            )
            if not exact_environment(final_environment) or final_import_errors:
                raise InfrastructureFailure(
                    f"bootstrapped environment does not exactly match reference: {final_environment}; "
                    f"import errors: {final_import_errors}"
                )
            observer.stage("environment_bootstrap_done")
            observer.stage("environment_verified")
            observer.bootstrap("reexec", "START")
            child_env = bootstrap_reexec_environment(initial_environment, workspace, root, output)
            staged_driver = root / str(workspace["driver_path"])
            try:
                child = subprocess.run(
                    [str(exact_python), str(staged_driver)], cwd=str(root), env=child_env,
                    check=False, timeout=REEXEC_TIMEOUT_SECONDS,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                detail = f"{type(exc).__name__}: {exc}"
                if isinstance(exc, subprocess.TimeoutExpired):
                    detail += f"; output={_bounded_output(exc.stdout, exc.stderr)}"
                raise bootstrap_stage_failure("reexec", detail) from exc
            finally:
                shutil.rmtree(Path(exact_python).parents[2], ignore_errors=True)
            return child.returncode
        if current_import_errors or not exact_environment(current_environment):
            raise InfrastructureFailure(
                f"environment does not exactly match reference: {current_environment}; "
                f"import errors: {current_import_errors}"
            )
        observer.stage("environment_bootstrap_done")
        observer.stage("environment_verified")
        report["environment"] = environment_report(
            initial_environment, current_environment,
            os.environ.get(BOOTSTRAP_PERFORMED) == "1", current_import_errors,
        )
        canary_protected_path = None
        if execution_mode == "PASS_IDENTITY_CANARY":
            # This synthetic file is intentionally outside the immutable dataset
            # manifest. Create it only after the final re-executed process has
            # passed exact workspace integrity, otherwise the bootstrap re-exec
            # would correctly reject the added path as unexpected input.
            canary_protected_path = prepare_protected_artifact_provenance_canary(
                root, workspace, integrity_checks=report["integrity_checks"],
            )
            protected = sorted(set(protected) | {canary_protected_path})
            report["protected_artifact_canary_target"] = canary_protected_path
        protected_before = hash_protected(root, protected)
        report["protected_artifacts"] = [
            {"path": x["path"], "before_sha256": x["sha256"]} for x in protected_before
        ]
        final = current_environment
        if execution_mode == "PASS_IDENTITY_CANARY":
            # This branch validates persistence/provenance only. It deliberately
            # avoids loading parents, generating candidates, and scientific checks.
            report["artifact"] = {"relative_path": None, "byte_size": None, "sha256": None}
            report["execution"]["generation_pass_1_success"] = True
            report["execution"]["generation_pass_2_success"] = True
            pass_identity = persist_generation_pass_identity(
                report, output, PASS_IDENTITY_CANARY_PASS_BYTES,
                bytes(PASS_IDENTITY_CANARY_PASS_BYTES), workspace, report_path=report_path,
            )
            report["protected_artifact_canary_operation"] = (
                execute_protected_artifact_provenance_canary_operation(
                    root, output, workspace, canary_protected_path,
                )
            )
            protected_after = capture_protected_artifact_evidence(
                report, root, protected, protected_before, workspace,
                evidence_output_root=output,
            )
            write_json(report_path, report)
            protected_state_persisted = True
            observer.stage("protected_artifact_provenance_persisted")
            report["validations"] = {
                "pass_identity_canary": True,
                "controlled_failure_code": "PASS_IDENTITY_CANARY_CONTROLLED_DOWNSTREAM_FAILURE",
                "candidate_generation_performed": False,
                "protected_artifact_state_persisted": True,
            }
            raise ScientificValidationFailure(json.dumps({
                "pass_identity_canary": True,
                "controlled_failure_code": "PASS_IDENTITY_CANARY_CONTROLLED_DOWNSTREAM_FAILURE",
                "pass_identity_status": generation_pass_identity_status(
                    {"generation_pass_identity": pass_identity}),
                "candidate_generation_performed": False,
                "protected_artifact_state_persisted": True,
            }, sort_keys=True))
        parents = run_with_periodic_heartbeat(
            observer, "source_cohort_load", lambda: load_parents(root),
        )
        if execution_mode == "M6A_PAIRED_DIAGNOSTIC":
            parents = select_m6a_parents(parents)
            from rudeus.generation.mobile_ion_diagnostic import build_candidate_supply_v2_operator_tournament_panel
            kwargs = {
                "mobile_ion": M6A_TARGET_SPECIES,
                "sigma_values_A_provisional": [M6A_SIGMA],
                "base_seeds": list(M6A_SEEDS),
                "diagnostic_config_hash": M6A_CONFIG_IDENTITY,
                "bounded_max_attempts": 8,
                "gaussian_local_direction_budgets": [M6A_DIRECTION_BUDGET],
                "include_bounded_clearance": False,
            }

            def generate_pass_one():
                panel = build_candidate_supply_v2_operator_tournament_panel(parents, **kwargs)
                panel["metadata"].update({
                    "failure_count_bands": {
                        band: [{"parent_id": parent_id,
                                "historical_geometry_failures": count}
                               for parent_id, count in members]
                        for band, members in M6A_PARENT_FAILURE_BANDS.items()
                    },
                    "selection_rule": (
                        "first four parent IDs in lexical order within each immutable "
                        "version-9 repeated-geometry-failure count band: >=10, 5-9, 2-4"
                    ),
                    "version_9_freeze_sha256": M6A_VERSION_9_FREEZE_SHA256,
                    "version_9_panel_sha256": M6A_VERSION_9_PANEL_SHA256,
                })
                encoded = (json.dumps(panel, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
                panel_path.write_bytes(encoded)
                return encoded

            generate_panel = generate_pass_one
        elif execution_mode == "M6B_PAIRED_DIAGNOSTIC":
            parents = select_m6b_parents(parents)
            from rudeus.generation.mobile_ion_diagnostic import build_candidate_supply_v2_operator_tournament_panel
            kwargs = {
                "mobile_ion": "Li",
                "sigma_values_A_provisional": [M6B_SIGMA],
                "base_seeds": list(M6B_SEEDS),
                "diagnostic_config_hash": M6B_CONFIG_IDENTITY,
                "bounded_max_attempts": 8,
                "gaussian_local_direction_budgets": [M6B_DIRECTION_BUDGET],
                "include_bounded_clearance": False,
            }

            def generate_panel():
                panel = build_candidate_supply_v2_operator_tournament_panel(parents, **kwargs)
                _m6b_panel_provenance(panel, parents)
                panel["authorization"].update({
                    "scheduler_activation": False,
                    "p1_eligibility": False,
                    "operator_superiority": False,
                    "automatic_promotion": False,
                    "downstream_diffusion_claim": False,
                    "threshold_modification": False,
                })
                panel.update({
                    "activation_authorized": False,
                    "p1_eligibility_authorized": False,
                    "downstream_scientific_claims_authorized": False,
                })
                panel_path.write_bytes((json.dumps(
                    panel, indent=2, sort_keys=True, ensure_ascii=False,
                ) + "\n").encode("utf-8"))
                return panel_path.read_bytes()

        else:
            from rudeus.generation.mobile_ion_diagnostic import write_mobile_ion_displacement_diagnostic_panel
            kwargs = {"mobile_ion": TARGET_SPECIES, "sigma_values_A_provisional": SIGMAS, "base_seeds": SEEDS, "diagnostic_config_hash": CONFIG_IDENTITY, "persistent_useful_threshold": PERSISTENT_THRESHOLD}

            def generate_panel():
                write_mobile_ion_displacement_diagnostic_panel(panel_path, parents, **kwargs)
                return panel_path.read_bytes()

        def generate_pass_one():
            return generate_panel()
        pass1 = run_with_periodic_heartbeat(observer, "generation_pass_1", generate_pass_one)
        report["execution"]["generation_pass_1_success"] = True
        pass2_dir = Path(tempfile.mkdtemp(prefix="rhombus-mobile-ion-pass2-"))
        pass2 = None
        pass_identity = None
        try:
            pass2_path = pass2_dir / panel_path.name
            def generate_pass_two():
                if execution_mode == "M6A_PAIRED_DIAGNOSTIC":
                    from rudeus.generation.mobile_ion_diagnostic import build_candidate_supply_v2_operator_tournament_panel
                    panel = build_candidate_supply_v2_operator_tournament_panel(parents, **kwargs)
                    panel["metadata"].update({
                        "failure_count_bands": {
                            band: [{"parent_id": parent_id,
                                    "historical_geometry_failures": count}
                                   for parent_id, count in members]
                            for band, members in M6A_PARENT_FAILURE_BANDS.items()
                        },
                        "selection_rule": (
                            "first four parent IDs in lexical order within each immutable "
                            "version-9 repeated-geometry-failure count band: >=10, 5-9, 2-4"
                        ),
                        "version_9_freeze_sha256": M6A_VERSION_9_FREEZE_SHA256,
                        "version_9_panel_sha256": M6A_VERSION_9_PANEL_SHA256,
                    })
                    pass2_path.write_bytes(
                        (json.dumps(panel, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
                    )
                elif execution_mode == "M6B_PAIRED_DIAGNOSTIC":
                    from rudeus.generation.mobile_ion_diagnostic import build_candidate_supply_v2_operator_tournament_panel
                    panel = build_candidate_supply_v2_operator_tournament_panel(parents, **kwargs)
                    _m6b_panel_provenance(panel, parents)
                    panel["authorization"].update({
                        "scheduler_activation": False,
                        "p1_eligibility": False,
                        "operator_superiority": False,
                        "automatic_promotion": False,
                        "downstream_diffusion_claim": False,
                        "threshold_modification": False,
                    })
                    panel.update({
                        "activation_authorized": False,
                        "p1_eligibility_authorized": False,
                        "downstream_scientific_claims_authorized": False,
                    })
                    pass2_path.write_bytes((json.dumps(
                        panel, indent=2, sort_keys=True, ensure_ascii=False,
                    ) + "\n").encode("utf-8"))
                else:
                    write_mobile_ion_displacement_diagnostic_panel(pass2_path, parents, **kwargs)
                return pass2_path.read_bytes()
            pass2 = run_with_periodic_heartbeat(observer, "generation_pass_2", generate_pass_two)
            report["execution"]["generation_pass_2_success"] = True
            # Persist both the standalone evidence and its report binding before validation can fail.
            pass_identity = persist_generation_pass_identity(
                report, output, pass1, pass2, workspace, report_path=report_path,
            )
        finally:
            if pass2_temp_cleanup_allowed(pass2, pass_identity):
                shutil.rmtree(pass2_dir, ignore_errors=True)
        # Capture and publish post-generation protected hashes before parsing
        # or validating the scientific panel, either of which may fail.
        protected_after = capture_protected_artifact_evidence(
            report, root, protected, protected_before, workspace,
            evidence_output_root=output,
        )
        write_json(report_path, report)
        protected_state_persisted = True
        panel = json.loads(pass1.decode("utf-8"))
        report["artifact"].update({"byte_size": len(pass1), "sha256": sha256_bytes(pass1), "row_count": len(panel.get("rows", []))})
        report["run_summaries"] = panel.get("runs", [])
        report["totals"] = (count_rows(panel.get("rows", []))
                            if execution_mode not in ("M6A_PAIRED_DIAGNOSTIC", "M6B_PAIRED_DIAGNOSTIC")
                            and isinstance(panel.get("rows"), list)
                            else {})
        observer.stage("validation_start")
        if execution_mode in ("M6A_PAIRED_DIAGNOSTIC", "M6B_PAIRED_DIAGNOSTIC"):
            validator = validate_m6b_panel if execution_mode == "M6B_PAIRED_DIAGNOSTIC" else validate_m6a_panel
            report["validations"] = validator(panel, pass1, pass2)
            report["m6a_summary" if execution_mode == "M6A_PAIRED_DIAGNOSTIC" else "m6b_summary"] = panel.get("summary")
            report["totals"] = {
                "requested_pairs": len(panel.get("rows", [])),
                "arms": panel.get("summary", {}).get("arms", {}),
            }
        else:
            report["validations"] = validate_panel(panel, protected_before, protected_after, pass1, pass2, final)
        observer.stage_done("validation", observer.stage_started)
        if execution_mode not in ("M6A_PAIRED_DIAGNOSTIC", "M6B_PAIRED_DIAGNOSTIC"):
            totals = count_rows(panel["rows"])
            report["totals"] = totals
            report["max_global_useful_frequency"] = max((x["useful_frequency"] for x in panel["summary"]["per_parent_useful_frequency"].values()), default=0.0)
            report["max_global_geometry_fail_frequency"] = max((x["geometry_fail_frequency"] for x in panel["summary"]["per_parent_geometry_failure_frequency"].values()), default=0.0)
        report["final_classification"] = "PASS"
    except ScientificValidationFailure as exc:
        observer.failed()
        report["failure_reason"] = str(exc)
        try:
            parsed = json.loads(str(exc))
            if isinstance(parsed, dict):
                report["validations"] = parsed
        except json.JSONDecodeError:
            pass
        report["final_classification"] = "SCIENTIFIC_VALIDATION_FAIL"
    except Exception as exc:
        observer.failed()
        report["failure_reason"] = f"{type(exc).__name__}: {exc}"
        report["final_classification"] = "INFRA_FAILURE"
    if protected_before is not None and not protected_state_persisted and root is not None:
        try:
            protected_after = capture_protected_artifact_evidence(
                report, root, protected, protected_before, workspace,
                evidence_output_root=output,
            )
            protected_state_persisted = True
        except Exception as exc:
            report["protected_artifact_state"] = {
                "schema_version": "protected-artifact-state-v1",
                "capture_state": "CAPTURE_FAILED",
                "error": f"{type(exc).__name__}: {exc}",
            }
    observer.stage("report_write_start")
    report["observability"] = observer.snapshot()
    observer.stage_done("report_write", observer.stage_started, emit=False)
    report["observability"] = observer.snapshot()
    write_json(report_path, report)
    observer._write(observer.last_progress)
    print(f"E2E_CLASS={report['final_classification']}")
    print(f"REPORT_PATH={report_path}")
    print(f"ARTIFACT_PATH={panel_path if panel_path.exists() else ''}")
    print(f"REPORT_SHA256={sha256_file(report_path)}")
    return {"PASS": 0, "SCIENTIFIC_VALIDATION_FAIL": 30, "INFRA_FAILURE": 20}[report["final_classification"]]


if __name__ == "__main__":
    if sys.argv[1:] == ["--integrity-self-test"]:
        run_integrity_self_test()
        raise SystemExit(0)
    if sys.argv[1:] == ["--runtime-output-boundary-self-test"]:
        run_integrity_self_test()
        raise SystemExit(0)
    if sys.argv[1:] == ["--environment-bootstrap-self-test"]:
        environment_bootstrap_self_test()
        raise SystemExit(0)
    if sys.argv[1:] == ["--observability-self-test"]:
        observability_self_test()
        raise SystemExit(0)
    if sys.argv[1:] == ["--mount-discovery-self-test"]:
        mount_discovery_self_test()
        raise SystemExit(0)
    if len(sys.argv) == 3 and sys.argv[1] == "--canonical-manifest-self-test":
        canonical_manifest_self_test(Path(sys.argv[2]).resolve())
        raise SystemExit(0)
    raise SystemExit(main())
