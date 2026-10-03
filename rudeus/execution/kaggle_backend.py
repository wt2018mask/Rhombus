"""Capability-gated Kaggle adapter. No unverified remote execution is enabled.

Run `python -m rudeus.execution.kaggle_backend` for a secret-free prerequisite
probe. Finding credentials is not authentication, quota or execution evidence.
"""
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
from dataclasses import dataclass

from rudeus.science.contracts import Record, canonical_bytes, digest, require_hash

from rudeus.execution.backend import (BackendCapabilities, TaskBundle, prepare_attempt,
                                      validate_prepared_attempt)
from rudeus.execution.contracts import ExecutionError


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
            for metadata_path, expected, label in (
                (dataset_metadata_path, {
                    "id": "wt2018mask/rhombus-mobile-ion-runtime",
                    "title": "rhombus-mobile-ion-runtime", "isPrivate": True,
                    "licenses": [{"name": "other"}],
                }, "dataset"),
                (kernel_metadata_path, {
                    "id": "wt2018mask/rhombus-mobile-ion-e2e",
                    "title": "rhombus-mobile-ion-e2e",
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
