"""Capability-gated Kaggle adapter. No unverified remote execution is enabled.

Run `python -m rudeus.execution.kaggle_backend` for a secret-free prerequisite
probe. Finding credentials is not authentication, quota or execution evidence.
"""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys

from rudeus.execution.backend import TaskBundle
from rudeus.execution.contracts import ExecutionError
from rudeus.science.contracts import canonical_bytes


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
        "execution_mode": {"requested": "unattended-controlled-python", "state": "UNSUPPORTED"},
        "unavailable_reasons": reasons,
        "actual_execution_identity": "NOT_ATTESTED",
    }


class KaggleBackend:
    """Only the prerequisite probe is supported in this environment.

    Submission never invents a provider run or an accepted attempt. Installing
    an SDK or adding credentials alone cannot unlock the execution gate.
    """
    def capabilities(self):
        return probe()

    def submit(self, task_bundle, resource_requirements):
        if not isinstance(task_bundle, TaskBundle):
            raise ExecutionError("validated TaskBundle required", "UNSUPPORTED_INPUT")
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
