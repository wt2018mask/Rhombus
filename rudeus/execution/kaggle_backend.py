"""Capability-gated Kaggle adapter. No unverified remote execution is enabled.

Run `python -m rudeus.execution.kaggle_backend` for a secret-free prerequisite
probe. Finding credentials is not authentication, quota or execution evidence.
"""
import importlib.util
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import subprocess
import tempfile
from dataclasses import dataclass
from collections.abc import Mapping

from rudeus.science.contracts import Record, canonical_bytes, digest, require_hash

from rudeus.execution.backend import (BackendCapabilities, TaskBundle, prepare_attempt,
                                      advance, validate_prepared_attempt)


_LEGACY_KERNEL_IDENTITY = "wt2018mask/rhombus-mobile-ion-e2e"


def _valid_kernel_identity(value):
    return value == _LEGACY_KERNEL_IDENTITY or (
        isinstance(value, str)
        and re.fullmatch(r"wt2018mask/rhombus-m6b-[0-9a-f]{16}", value) is not None
    )
from rudeus.execution.contracts import ExecutionError, classify_failure


def _hardened_e2e_driver():
    """Load the repository's existing local identity/manifest validators."""
    path = Path(__file__).resolve().parents[2] / "scripts" / "kaggle" / "mobile_ion_displace_e2e.py"
    spec = importlib.util.spec_from_file_location("_rhombus_mobile_ion_e2e_contract", path)
    if spec is None or spec.loader is None:
        raise ExecutionError("hardened Kaggle E2E validator is unavailable", "INTEGRITY")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise ExecutionError(f"hardened Kaggle E2E validator could not be loaded: {exc}", "INTEGRITY") from exc
    return module


@dataclass(frozen=True, kw_only=True)
class KaggleLocalPreparation(Record):
    """Immutable local payload/spec binding; contains no provider execution claim."""
    task_id: str
    task_content_hash: str
    task_bundle_hash: str
    code_bundle_hash: str
    backend_identity: str
    attempt_id: str
    prepared_attempt_hash: str
    prepared_from_hash: str
    attempt_state: str
    dataset_root: str
    staged_driver_path: str
    dataset_metadata_path: str
    kernel_metadata_path: str
    workspace_identity: dict
    dataset_spec: dict
    dataset_spec_raw_sha256: str
    dataset_transport_inventory: tuple
    kernel_spec: dict
    kernel_spec_raw_sha256: str
    staged_driver_raw_sha256: str
    submission_gate: str = "CLOSED"
    version: str = "kaggle-local-preparation-v1"

    def validate(self):
        super().validate()
        for name in ("task_id", "task_content_hash", "task_bundle_hash", "code_bundle_hash",
                     "attempt_id", "prepared_attempt_hash", "prepared_from_hash",
                     "dataset_spec_raw_sha256", "kernel_spec_raw_sha256", "staged_driver_raw_sha256"):
            require_hash(getattr(self, name))
        if (self.version != "kaggle-local-preparation-v1" or self.backend_identity != "kaggle"
                or self.attempt_state != "PREPARED" or self.submission_gate != "CLOSED"):
            raise ValueError("invalid or remotely enabled Kaggle preparation record")
        if not self.dataset_transport_inventory:
            raise ValueError("Kaggle preparation requires a verified transport inventory")
        if any(not isinstance(path, str) or not Path(path).is_absolute() for path in (
                self.dataset_root, self.staged_driver_path, self.dataset_metadata_path,
                self.kernel_metadata_path)):
            raise ValueError("Kaggle local preparation paths must be absolute")


@dataclass(frozen=True, kw_only=True)
class KaggleSubmissionReceipt(Record):
    """Provider-accepted submission facts; operational evidence only."""
    backend_identity: str
    dataset_ref: str
    dataset_action: str
    workspace_run_id: str
    kernel_identity: str
    kernel_spec_sha256: str
    provider_run_id: str
    provider_status: str
    dataset_version_id: str | None = None
    kernel_version: int | None = None
    version: str = "kaggle-submission-receipt-v1"

    def validate(self):
        super().validate()
        if (self.version != "kaggle-submission-receipt-v1"
                or self.backend_identity != "kaggle"
                or self.dataset_ref != "wt2018mask/rhombus-mobile-ion-runtime"
                or self.dataset_action not in ("CREATE", "VERSION")
                or not self.workspace_run_id
                or not _valid_kernel_identity(self.kernel_identity)
                or self.provider_status != "ACCEPTED"
                or self.provider_run_id != self.kernel_identity):
            raise ValueError("Kaggle provider submission is not positively identified as accepted")
        require_hash(self.kernel_spec_sha256)
        if self.kernel_version is not None and (type(self.kernel_version) is not int or self.kernel_version < 1):
            raise ValueError("invalid Kaggle kernel version")


@dataclass(frozen=True, kw_only=True)
class KaggleSubmissionHandoff(Record):
    """Attempt-bound evidence emitted only after Python authorizes submission."""
    attempt_id: str
    prepared_content_hash: str
    task_id: str
    task_content_hash: str
    task_bundle_hash: str
    code_bundle_hash: str
    backend_identity: str
    preparation_hash: str
    workspace_run_id: str
    dataset_ref: str
    dataset_root: str
    dataset_metadata_sha256: str
    dataset_transport_files: tuple
    dataset_transport_inventory: tuple
    protected_artifacts: tuple
    dataset_transport_manifest_sha256: str
    workspace_identity: dict
    kernel_identity: str
    kernel_stage_root: str
    kernel_metadata_sha256: str
    staged_driver_sha256: str
    version: str = "kaggle-submission-handoff-v1"

    def validate(self):
        super().validate()
        for name in ("attempt_id", "prepared_content_hash", "task_id", "task_content_hash",
                     "task_bundle_hash", "code_bundle_hash", "preparation_hash",
                     "dataset_metadata_sha256", "dataset_transport_manifest_sha256",
                     "kernel_metadata_sha256", "staged_driver_sha256"):
            require_hash(getattr(self, name))
        if (self.version != "kaggle-submission-handoff-v1" or self.backend_identity != "kaggle"
                or not self.workspace_run_id
                or self.dataset_ref != "wt2018mask/rhombus-mobile-ion-runtime"
                or not _valid_kernel_identity(self.kernel_identity)
                or self.workspace_identity.get("provider_kernel_identity", _LEGACY_KERNEL_IDENTITY)
                != self.kernel_identity
                or not Path(self.dataset_root).is_absolute()
                or not Path(self.kernel_stage_root).is_absolute()
                or not self.dataset_transport_files
                or {item["relative_path"] for item in self.dataset_transport_inventory}
                != set(self.dataset_transport_files)):
            raise ValueError("invalid or incomplete Kaggle submission handoff")


class KaggleSubmissionFailure(ExecutionError):
    """Operational submission error with an append-only FAILED attempt snapshot."""
    def __init__(self, message, failure_class, *, failed_attempt, provider_facts=None):
        super().__init__(message, failure_class)
        self.failed_attempt = failed_attempt
        self.provider_facts = provider_facts


class KaggleSubmissionNotStarted(ExecutionError):
    """Local command setup failed before any Kaggle provider call could occur."""


class _HardenedKaggleSubmissionAdapter:
    """Invoke the submit-only entry point backed by scripts/run.ps1's hardened flow."""
    def __init__(self, *, powershell_executable=None, runner=subprocess.run, timeout_s=1800):
        self.powershell_executable = powershell_executable
        self.runner = runner
        self.timeout_s = timeout_s
        self._resolved_executable = None

    def preflight(self):
        executable = self.powershell_executable or shutil.which("pwsh.exe") or shutil.which("pwsh") or shutil.which("powershell.exe")
        if not executable:
            raise KaggleSubmissionNotStarted(
                "PowerShell is required for the hardened Kaggle submit path", "UNSUPPORTED_INPUT",
            )
        script = Path(__file__).resolve().parents[2] / "scripts" / "run.ps1"
        if not script.is_file():
            raise KaggleSubmissionNotStarted("hardened Kaggle submission script is missing", "INTEGRITY")
        self._resolved_executable = executable

    def __call__(self, preparation, handoff):
        if self._resolved_executable is None:
            self.preflight()
        executable = self._resolved_executable
        repo_root = Path(__file__).resolve().parents[2]
        script = repo_root / "scripts" / "run.ps1"
        handoff.validate()
        if handoff.preparation_hash != preparation.content_hash:
            raise KaggleSubmissionNotStarted("submission handoff does not match local preparation", "INTEGRITY")
        payload = canonical_bytes(handoff)
        envelope = json.dumps({
            "payload_base64": base64.b64encode(payload).decode("ascii"),
            "payload_sha256": hashlib.sha256(payload).hexdigest(),
        }, sort_keys=True, separators=(",", ":")).encode("utf-8")
        with tempfile.TemporaryDirectory(prefix="rhombus-kaggle-handoff-") as handoff_dir:
            handoff_path = Path(handoff_dir) / "submission-handoff.json"
            handoff_path.write_bytes(envelope)
            command = [
                executable, "-NoProfile", "-File", str(script),
                "kaggle-mobile-ion-submit-prepared", preparation.dataset_root,
                str(Path(preparation.kernel_metadata_path).parent), str(handoff_path),
            ]
            return self._run(command, preparation)

    def _run(self, command, preparation):
        executable = command[0]
        try:
            completed = self.runner(
                command, capture_output=True, timeout=self.timeout_s, check=False,
            )
        except Exception as exc:
            if isinstance(exc, subprocess.TimeoutExpired):
                partial_output = "\n".join(
                    value.decode(errors="replace") if isinstance(value, bytes) else str(value or "")
                    for value in (exc.stdout, exc.stderr)
                )
                action = next((line.split("=", 1)[1] for line in partial_output.splitlines()
                               if line.startswith("DATASET_ACTION=") and
                               line.split("=", 1)[1] in ("CREATE", "VERSION")), None)
                facts = {"backend_identity": "kaggle", "phase": "submission_command_timeout",
                         "output_tail": partial_output[-8000:]}
                if action:
                    facts.update(dataset_action=action,
                                 dataset_ref="wt2018mask/rhombus-mobile-ion-runtime")
                raise KaggleSubmissionFailure(
                    "hardened Kaggle submission command timed out", "TIMEOUT",
                    failed_attempt=None, provider_facts=facts,
                ) from exc
            if isinstance(exc, OSError):
                raise KaggleSubmissionNotStarted(
                    f"hardened Kaggle submission process could not start: {exc}", "INTEGRITY",
                ) from exc
            raise ExecutionError(f"hardened Kaggle submission command failed to start: {exc}",
                                 classify_failure(exc)) from exc
        output = "\n".join(
            part.decode("utf-8", errors="replace") if isinstance(part, bytes) else part
            for part in (completed.stdout, completed.stderr) if part
        )
        lines = [line.split("=", 1)[1] for line in output.splitlines()
                 if line.startswith("RHOMBUS_SUBMISSION_RECEIPT=")]
        if completed.returncode != 0 or len(lines) != 1:
            failure_classes = [line.split("=", 1)[1] for line in output.splitlines()
                               if line.startswith("RHOMBUS_SUBMISSION_FAILURE_CLASS=")]
            fact_lines = [line.split("=", 1)[1] for line in output.splitlines()
                          if line.startswith("RHOMBUS_PROVIDER_FACTS=")]
            facts = None
            if len(fact_lines) == 1:
                try:
                    facts = json.loads(fact_lines[0])
                except json.JSONDecodeError:
                    facts = {"phase": "provider_response_parse_failed"}
            if isinstance(facts, Mapping) and facts.get("phase") == "local_precondition":
                failure_class = failure_classes[0] if len(failure_classes) == 1 else "INTEGRITY"
                raise KaggleSubmissionNotStarted(
                    "hardened Kaggle command rejected local staging before provider calls", failure_class,
                )
            if facts is None and output:
                facts = {"phase": "submission_command_failed"}
            if isinstance(facts, Mapping):
                facts = {**facts, "output_tail": output[-8000:]}
            failure_class = failure_classes[0] if len(failure_classes) == 1 else "SOFTWARE"
            raise KaggleSubmissionFailure(
                "hardened Kaggle submission was not positively confirmed",
                failure_class, failed_attempt=None, provider_facts=facts,
            )
        try:
            response = json.loads(lines[0])
        except json.JSONDecodeError as exc:
            raise KaggleSubmissionFailure(
                "hardened Kaggle submission receipt is malformed", "INTEGRITY",
                failed_attempt=None,
                provider_facts={"backend_identity": "kaggle", "phase": "receipt_parse_failed",
                                "output_tail": output[-8000:]},
            ) from exc
        kernel_ref = response.get("provider_run_id")
        try:
            return KaggleSubmissionReceipt(
                backend_identity="kaggle",
                dataset_ref="wt2018mask/rhombus-mobile-ion-runtime",
                dataset_action=response.get("dataset_action"),
                workspace_run_id=preparation.workspace_identity["run_id"],
                kernel_identity=preparation.kernel_spec["id"],
                kernel_spec_sha256=preparation.kernel_spec_raw_sha256,
                provider_run_id=kernel_ref,
                provider_status=response.get("provider_status"),
                dataset_version_id=response.get("dataset_version_id"),
                kernel_version=response.get("kernel_version"),
            )
        except Exception as exc:
            raise KaggleSubmissionFailure(
                f"hardened Kaggle submission response was not valid: {exc}", "INTEGRITY",
                failed_attempt=None,
                provider_facts={"backend_identity": "kaggle", "phase": "receipt_validation_failed",
                                "dataset_action": response.get("dataset_action"),
                                "provider_run_id": kernel_ref, "output_tail": output[-8000:]},
            ) from exc


def probe():
    """Read-only local probe; no secret contents, provider writes or paid fallback."""
    config = Path(os.environ.get("KAGGLE_CONFIG_DIR", str(Path.home()/".kaggle")))
    try:
        sdk = importlib.util.find_spec("kaggle") is not None
    except (ImportError, ValueError):
        sdk = False
    checks = {
        "cli_present": shutil.which("kaggle") is not None or
                       (Path(sys.executable).parent/"kaggle.exe").is_file(),
        "sdk_present": sdk,
        "credential_file_present": (config/"kaggle.json").is_file(),
        "access_token_file_present": (Path.home()/".kaggle/access_token").is_file(),
        "token_environment_present": bool(os.environ.get("KAGGLE_API_TOKEN")),
        "legacy_environment_present": bool(os.environ.get("KAGGLE_USERNAME") and os.environ.get("KAGGLE_KEY")),
    }
    reasons = ["no authenticated, account-specific free execution/capacity probe has succeeded",
               "remote packaging, run binding and retrieval are not enabled without execution evidence"]
    if not checks["cli_present"] and not checks["sdk_present"]:
        reasons.append("Kaggle CLI/SDK unavailable")
    if not any(checks[name] for name in checks if name not in ("cli_present", "sdk_present")):
        reasons.append("Kaggle credentials unavailable")
    return {
        "version": "kaggle-capability-probe-v1", "backend": "kaggle",
        "probe_scope": "LOCAL_PREREQUISITES_ONLY", "local_checks": checks,
        "availability": "UNKNOWN", "free_execution": "UNKNOWN",
        "capabilities": {name: {"state": "UNKNOWN", "value": None} for name in (
            "cpu", "gpu", "memory_bytes", "runtime_limit_s", "network",
            "persistent_storage", "artifact_upload", "artifact_retrieval")},
        "capability_model": BackendCapabilities(backend_identity="kaggle").to_dict(),
        "execution_mode": {"requested": "unattended-controlled-python", "state": "UNSUPPORTED"},
        "unavailable_reasons": reasons,
        "actual_execution_identity": "NOT_ATTESTED",
        "repository_evidence": {
            "local_preparation": {
                "state": "IMPLEMENTED",
                "source": "rudeus/execution/kaggle_backend.py::KaggleBackend.prepare_local_payload",
                "provider_io": False,
            },
            "hardened_e2e_contract": {
                "state": "IMPLEMENTED",
                "sources": [
                    "scripts/run.ps1::New-MobileIonRuntimeDatasetStage",
                    "scripts/run.ps1::Invoke-MobileIonDatasetUpload",
                    "scripts/run.ps1::Wait-MobileIonDatasetReady",
                    "scripts/run.ps1::Invoke-MobileIonE2E",
                    "scripts/kaggle/mobile_ion_displace_e2e.py::verify_workspace_integrity",
                    "scripts/kaggle/mobile_ion_displace_e2e.py::validate_runtime_dataset",
                ],
            },
            "historical_remote_execution": {
                "state": "HISTORICAL_SUCCESS_REPORTED_NOT_REVALIDATED",
                "source": "user-provided repository checkpoint; not current capability/quota evidence",
            },
        },
    }


class KaggleBackend:
    """Only the prerequisite probe is supported in this environment.

    Submission never invents a provider run or an accepted attempt. Installing
    an SDK or adding credentials alone cannot unlock the execution gate.
    """
    def capabilities(self):
        return probe()

    def prepare(self, task_bundle, resource_requirements):
        """Validate a transfer bundle and create a local PREPARED attempt only."""
        if not isinstance(task_bundle, TaskBundle):
            task_bundle = TaskBundle.from_dict(task_bundle)
        task_bundle.validate()
        if canonical_bytes(resource_requirements) != canonical_bytes(task_bundle.task["resource_requirements"]):
            raise ExecutionError("resource requirements differ from immutable TaskSpec", "INTEGRITY")
        return prepare_attempt(task_bundle, "kaggle")

    def prepare_local_payload(self, task_spec, task_bundle, attempt, *, dataset_root,
                              staged_driver_path, dataset_metadata_path, kernel_metadata_path):
        """Validate existing E2E staging and bind its specs to a PREPARED attempt.

        This is deliberately local-only. It does not authenticate, upload, poll,
        submit, or mutate any generic lifecycle record.
        """
        try:
            from rudeus.execution.contracts import TaskSpec

            if not isinstance(task_bundle, TaskBundle):
                task_bundle = TaskBundle.from_dict(task_bundle)
            task_bundle.validate()
            if not isinstance(task_spec, TaskSpec):
                task_spec = TaskSpec.from_dict(task_spec)
            task_spec.validate()
            if canonical_bytes(task_spec) != canonical_bytes(TaskSpec.from_dict(task_bundle.task)):
                raise ExecutionError("TaskSpec differs from immutable TaskBundle", "INTEGRITY")
            validate_prepared_attempt(attempt, task_bundle, "kaggle")

            driver = _hardened_e2e_driver()
            dataset_root = Path(dataset_root)
            staged_driver_path = Path(staged_driver_path)
            dataset_metadata_path = Path(dataset_metadata_path)
            kernel_metadata_path = Path(kernel_metadata_path)
            for path in (dataset_root, staged_driver_path, dataset_metadata_path, kernel_metadata_path):
                if not path.exists():
                    raise ExecutionError(f"required Kaggle preparation input is missing: {path.name}", "INTEGRITY")
            if not dataset_root.is_dir() or any(not path.is_file() for path in (
                    staged_driver_path, dataset_metadata_path, kernel_metadata_path)):
                raise ExecutionError("Kaggle preparation input has an invalid filesystem type", "INTEGRITY")
            dataset_root_resolved = dataset_root.resolve(strict=True)
            expected_dataset_metadata = dataset_root_resolved / "dataset-metadata.json"
            if not expected_dataset_metadata.is_file() or expected_dataset_metadata.is_symlink():
                raise ExecutionError("top-level staged dataset-metadata.json is required", "INTEGRITY")
            if dataset_metadata_path.resolve(strict=True) != expected_dataset_metadata.resolve(strict=True):
                raise ExecutionError(
                    "dataset metadata path must be the exact top-level file in dataset_root", "INTEGRITY",
                )

            workspace = driver.load_embedded_workspace_identity(staged_driver_path)
            configured_kernel = task_spec.config.get("kernel_identity", _LEGACY_KERNEL_IDENTITY)
            workspace_kernel = workspace.get("provider_kernel_identity", _LEGACY_KERNEL_IDENTITY)
            execution_mode = task_spec.config.get("execution_mode", "CANDIDATE_DIAGNOSTIC_E2E")
            if (not _valid_kernel_identity(configured_kernel)
                    or workspace_kernel != configured_kernel
                    or (execution_mode != "M6B_PAIRED_DIAGNOSTIC"
                        and configured_kernel != _LEGACY_KERNEL_IDENTITY)
                    or (execution_mode == "M6B_PAIRED_DIAGNOSTIC"
                        and task_spec.config.get("config_identity") != "candidate-supply-v2-m6b-li-sigma-035-seeds-44-45-46-family-balanced-15p-d8-v1")):
                raise ExecutionError("provider kernel identity is not authorized/bound to this task", "INTEGRITY")
            kernel_title = configured_kernel.split("/", 1)[1]
            for metadata_path, expected, label in (
                (dataset_metadata_path, {
                    "id": "wt2018mask/rhombus-mobile-ion-runtime",
                    "title": "rhombus-mobile-ion-runtime", "isPrivate": True,
                    "licenses": [{"name": "other"}],
                }, "dataset"),
                (kernel_metadata_path, {
                    "id": configured_kernel,
                    "title": kernel_title,
                    "code_file": "mobile_ion_displace_e2e.py", "language": "python",
                    "kernel_type": "script", "is_private": True, "enable_gpu": False,
                    "enable_internet": True,
                    "dataset_sources": ["wt2018mask/rhombus-mobile-ion-runtime"],
                    "competition_sources": [], "kernel_sources": [], "model_sources": [],
                }, "kernel"),
            ):
                raw = metadata_path.read_bytes()
                if raw.startswith(b"\xef\xbb\xbf"):
                    raise ExecutionError(f"Kaggle {label} metadata must be UTF-8 without BOM", "INTEGRITY")
                try:
                    parsed = json.loads(raw.decode("utf-8"))
                except (UnicodeError, json.JSONDecodeError) as exc:
                    raise ExecutionError(f"Kaggle {label} metadata is malformed", "INTEGRITY") from exc
                if not isinstance(parsed, dict) or canonical_bytes(parsed) != canonical_bytes(expected):
                    raise ExecutionError(f"Kaggle {label} metadata identity/spec mismatch", "INTEGRITY")
                if label == "dataset":
                    dataset_spec, dataset_spec_hash = parsed, hashlib.sha256(raw).hexdigest()
                else:
                    kernel_spec, kernel_spec_hash = parsed, hashlib.sha256(raw).hexdigest()

            driver_resolved = staged_driver_path.resolve(strict=True)
            kernel_stage_resolved = kernel_metadata_path.resolve(strict=True).parent
            if (staged_driver_path.name != kernel_spec["code_file"]
                    or driver_resolved.name != kernel_spec["code_file"]
                    or driver_resolved.parent != kernel_stage_resolved
                    or workspace.get("driver_path") != kernel_spec["code_file"]):
                raise ExecutionError(
                    "staged driver name/location does not match kernel metadata and workspace identity",
                    "INTEGRITY",
                )

            diagnostic = driver.inspect_runtime_dataset(
                dataset_root, workspace, allow_dataset_metadata=True,
            )
            if diagnostic["status"] != "DATASET_MOUNT_MATCH_OK":
                raise ExecutionError(
                    f"Kaggle runtime dataset failed exact E2E manifest validation: {diagnostic['reason']}",
                    "INTEGRITY",
                )
            embedded = driver.load_embedded_workspace_identity(staged_driver_path)
            if canonical_bytes(embedded) != canonical_bytes(workspace):
                raise ExecutionError("staged driver workspace identity changed during preparation", "INTEGRITY")

            runtime_files = driver.require_workspace_runtime_files(workspace)
            obelix_files = driver.runtime_obelix_files(dataset_root)
            explicit_hash = driver.sha256_bytes(
                driver.canonical_manifest(dataset_root, obelix_files).encode("utf-8"))
            if explicit_hash != workspace.get("explicitly_staged_input_manifest_sha256"):
                raise ExecutionError("explicit OBELiX input manifest hash mismatch", "INTEGRITY")
            driver_name = workspace["driver_path"]
            runtime_manifest = driver.canonical_manifest(
                dataset_root, runtime_files, driver_name, driver_source_path=staged_driver_path,
            )
            runtime_hash = driver.sha256_bytes(runtime_manifest.encode("utf-8"))
            if runtime_hash != workspace.get("runtime_manifest_sha256"):
                raise ExecutionError("runtime manifest including staged driver hash mismatch", "INTEGRITY")
            for protected in workspace["protected_artifacts"]:
                protected_path = dataset_root / protected["path"]
                if (not protected_path.is_file()
                        or driver.sha256_file(protected_path) != protected.get("sha256")):
                    raise ExecutionError("protected artifact hash mismatch in Kaggle preparation", "INTEGRITY")

            inventory = tuple({
                "relative_path": relative,
                "raw_sha256": driver.sha256_file(dataset_root / relative),
                "size_bytes": (dataset_root / relative).stat().st_size,
            } for relative in sorted(driver.dataset_transport_files(workspace)))
            return KaggleLocalPreparation(
                task_id=task_spec.task_id,
                task_content_hash=task_bundle.task_content_hash,
                task_bundle_hash=task_bundle.content_hash,
                code_bundle_hash=task_bundle.bundle_hash,
                backend_identity=attempt.backend,
                attempt_id=attempt.attempt_id,
                prepared_attempt_hash=attempt.content_hash,
                prepared_from_hash=attempt.previous_hash,
                attempt_state=attempt.state,
                dataset_root=str(dataset_root_resolved),
                staged_driver_path=str(driver_resolved),
                dataset_metadata_path=str(expected_dataset_metadata),
                kernel_metadata_path=str(kernel_metadata_path.resolve(strict=True)),
                workspace_identity=workspace,
                dataset_spec=dataset_spec,
                dataset_spec_raw_sha256=dataset_spec_hash,
                dataset_transport_inventory=inventory,
                kernel_spec=kernel_spec,
                kernel_spec_raw_sha256=kernel_spec_hash,
                staged_driver_raw_sha256=driver.sha256_file(staged_driver_path),
            )
        except ExecutionError:
            raise
        except OSError as exc:
            raise ExecutionError(f"Kaggle local preparation I/O failed: {exc}", "INTEGRITY") from exc
        except (KeyError, TypeError, ValueError) as exc:
            raise ExecutionError(f"Kaggle local preparation input is invalid: {exc}", "INTEGRITY") from exc
        except Exception as exc:
            raise ExecutionError(f"Kaggle E2E preparation validation failed: {exc}", "INTEGRITY") from exc

    @staticmethod
    def _provider_failure(attempt, exc, provider_facts=None):
        """Append a FAILED operational snapshot, retaining explicitly known side effects."""
        facts = None
        if provider_facts is not None:
            if not isinstance(provider_facts, Mapping):
                exc = ExecutionError("provider failure facts are malformed", "INTEGRITY")
            else:
                facts = {"backend_identity": "kaggle", **dict(provider_facts)}
                facts["backend_identity"] = "kaggle"
        remote_run_id = facts.get("provider_run_id") if facts else None
        if not isinstance(remote_run_id, str) or not remote_run_id:
            remote_run_id = None
        failed = advance(
            attempt, "FAILED", failure_class=classify_failure(exc).value,
            remote_run_id=remote_run_id, provider_provenance=facts,
        )
        return KaggleSubmissionFailure(
            f"Kaggle provider submission failed operationally: {exc}",
            classify_failure(exc), failed_attempt=failed, provider_facts=facts,
        )

    def submit_prepared_payload(
        self, task_spec, task_bundle, attempt, preparation, *,
        submission_authorized=False, provider_submitter=None,
    ):
        """Submit a locally validated Kaggle payload only under explicit authorization.

        ``provider_submitter`` is the narrow bridge to the established hardened
        dataset-upload/readiness/kernel-push path. It must return a receipt with
        positive provider acceptance and identity; this method never polls or
        retrieves results. No callback or authorization is enabled by default.
        """
        from rudeus.execution.contracts import TaskSpec

        if not isinstance(preparation, KaggleLocalPreparation):
            raise ExecutionError("validated Kaggle local preparation is required", "INTEGRITY")
        try:
            preparation.validate()
            if not isinstance(task_bundle, TaskBundle):
                task_bundle = TaskBundle.from_dict(task_bundle)
            task_bundle.validate()
            if not isinstance(task_spec, TaskSpec):
                task_spec = TaskSpec.from_dict(task_spec)
            task_spec.validate()
            validate_prepared_attempt(attempt, task_bundle, "kaggle")
        except ExecutionError:
            raise
        except Exception as exc:
            raise ExecutionError(f"Kaggle submission binding validation failed: {exc}", "INTEGRITY") from exc
        if canonical_bytes(task_spec) != canonical_bytes(TaskSpec.from_dict(task_bundle.task)):
            raise ExecutionError("TaskSpec differs from immutable TaskBundle", "INTEGRITY")
        expected_binding = (
            preparation.task_id == task_spec.task_id
            and preparation.task_content_hash == task_bundle.task_content_hash
            and preparation.task_bundle_hash == task_bundle.content_hash
            and preparation.code_bundle_hash == task_bundle.bundle_hash
            and preparation.backend_identity == attempt.backend == "kaggle"
            and preparation.attempt_id == attempt.attempt_id
            and preparation.prepared_attempt_hash == attempt.content_hash
            and preparation.prepared_from_hash == attempt.previous_hash
            and preparation.attempt_state == attempt.state == "PREPARED"
            and preparation.submission_gate == "CLOSED"
        )
        if not expected_binding:
            raise ExecutionError("Kaggle preparation does not match this PREPARED task/bundle attempt", "INTEGRITY")
        refreshed = self.prepare_local_payload(
            task_spec, task_bundle, attempt,
            dataset_root=preparation.dataset_root,
            staged_driver_path=preparation.staged_driver_path,
            dataset_metadata_path=preparation.dataset_metadata_path,
            kernel_metadata_path=preparation.kernel_metadata_path,
        )
        if canonical_bytes(refreshed) != canonical_bytes(preparation):
            raise ExecutionError("Kaggle staged payload changed after local preparation", "INTEGRITY")
        if submission_authorized is not True:
            raise ExecutionError("Kaggle provider submission requires explicit caller authorization",
                                 "UNSUPPORTED_INPUT")
        if provider_submitter is None:
            provider_submitter = _HardenedKaggleSubmissionAdapter()
        if not callable(provider_submitter):
            raise ExecutionError("hardened Kaggle provider submission adapter is invalid", "INTEGRITY")
        preflight = getattr(provider_submitter, "preflight", None)
        if callable(preflight):
            preflight()

        try:
            handoff = KaggleSubmissionHandoff(
                attempt_id=attempt.attempt_id,
                prepared_content_hash=attempt.content_hash,
                task_id=task_spec.task_id,
                task_content_hash=task_bundle.task_content_hash,
                task_bundle_hash=task_bundle.content_hash,
                code_bundle_hash=task_bundle.bundle_hash,
                backend_identity="kaggle",
                preparation_hash=refreshed.content_hash,
                workspace_run_id=refreshed.workspace_identity["run_id"],
                dataset_ref=refreshed.dataset_spec["id"],
                dataset_root=refreshed.dataset_root,
                dataset_metadata_sha256=refreshed.dataset_spec_raw_sha256,
                dataset_transport_files=tuple(refreshed.workspace_identity["dataset_transport_files"]),
                dataset_transport_inventory=refreshed.dataset_transport_inventory,
                protected_artifacts=tuple(refreshed.workspace_identity["protected_artifacts"]),
                dataset_transport_manifest_sha256=refreshed.workspace_identity["dataset_transport_manifest_sha256"],
                workspace_identity=refreshed.workspace_identity,
                kernel_identity=refreshed.kernel_spec["id"],
                kernel_stage_root=str(Path(refreshed.kernel_metadata_path).parent),
                kernel_metadata_sha256=refreshed.kernel_spec_raw_sha256,
                staged_driver_sha256=refreshed.staged_driver_raw_sha256,
            )
            result = provider_submitter(refreshed, handoff)
        except KaggleSubmissionNotStarted:
            raise
        except Exception as exc:
            failure = self._provider_failure(attempt, exc, getattr(exc, "provider_facts", None))
            raise failure from exc

        partial_facts = result if isinstance(result, Mapping) else None
        try:
            receipt = result if isinstance(result, KaggleSubmissionReceipt) else KaggleSubmissionReceipt.from_dict(result)
            receipt.validate()
            if (receipt.workspace_run_id != preparation.workspace_identity["run_id"]
                    or receipt.kernel_spec_sha256 != preparation.kernel_spec_raw_sha256):
                raise ValueError("provider receipt workspace/kernel binding mismatch")
        except Exception as exc:
            if isinstance(result, KaggleSubmissionReceipt):
                partial_facts = result.to_dict()
            failure = self._provider_failure(
                attempt, ExecutionError(f"invalid provider submission receipt: {exc}", "INTEGRITY"),
                partial_facts,
            )
            raise failure from exc

        return advance(
            attempt, "SUBMITTED", remote_run_id=receipt.provider_run_id,
            provider_provenance=receipt.to_dict(),
        )

    def submit(self, attempt, task_bundle, resource_requirements):
        if not isinstance(task_bundle, TaskBundle):
            task_bundle = TaskBundle.from_dict(task_bundle)
        validate_prepared_attempt(attempt, task_bundle, "kaggle")
        if canonical_bytes(resource_requirements) != canonical_bytes(task_bundle.task["resource_requirements"]):
            raise ExecutionError("resource requirements differ from immutable TaskSpec", "INTEGRITY")
        self.capabilities()  # Explicit fresh check before any submission decision.
        raise ExecutionError("Kaggle unattended free execution is not verified; submission disabled",
                             "UNSUPPORTED_INPUT")

    def status(self, attempt):
        if attempt.backend != "kaggle":
            raise ExecutionError("attempt belongs to another backend", "INTEGRITY")
        raise ExecutionError("Kaggle run observation is not verified or enabled", "UNSUPPORTED_INPUT")

    def retrieve(self, attempt):
        if attempt.backend != "kaggle":
            raise ExecutionError("attempt belongs to another backend", "INTEGRITY")
        raise ExecutionError("Kaggle run-bound retrieval is not verified or enabled", "UNSUPPORTED_INPUT")


def main():
    print(json.dumps(probe(), sort_keys=True))
    return 2  # Machine-readable distinction from a successful execution probe.


if __name__ == "__main__":
    raise SystemExit(main())
