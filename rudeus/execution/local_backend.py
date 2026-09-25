from __future__ import annotations

from pathlib import Path

from rudeus.execution.backend import (
    BackendAttempt,
    TaskBundle,
    advance,
    new_attempt,
)
from rudeus.execution.contracts import ExecutionError, TaskSpec
from rudeus.execution.code_bundle import CodeBundle
from rudeus.execution.launcher import launch_local
import sys
import sysconfig
from rudeus.science.evidence import EvidenceStore


class LocalBackend:
    """ComputeBackend adapter for the existing local execution path."""

    def __init__(self, *, git_root, store: EvidenceStore):
        self.git_root = git_root
        self.store = store

    def capabilities(self) -> dict:
        return {
            "availability": "VERIFIED_LOCAL",
            "execution_mode": {
                "state": "SUPPORTED",
                "value": "local",
            },
        }

    def submit(
        self,
        task_bundle: TaskBundle,
        resource_requirements: dict,
    ) -> BackendAttempt:
        if not isinstance(task_bundle, TaskBundle):
            task_bundle = TaskBundle.from_dict(task_bundle)

        task_bundle.validate()

        if resource_requirements != task_bundle.task["resource_requirements"]:
            raise ExecutionError(
                "resource requirements differ from immutable TaskSpec",
                "INTEGRITY",
            )

        task = TaskSpec.from_dict(task_bundle.task)
        attempt = new_attempt(task_bundle, "local")

        result = launch_local(
            task,
            CodeBundle.from_dict(task_bundle.code_bundle),
            task_bundle.bundle_hash,
            git_root=self.git_root,
            store_root=self.store.root,
            interpreter=str(Path(sys.executable).absolute()),
            dependency_roots=[sysconfig.get_path("purelib")],
            attempt_id=attempt.attempt_id,
        )

        if result["artifact_status"] != "VERIFIED_LOCAL":
            raise ExecutionError(
                result.get("reason", "local execution failed"),
                result.get("failure_class", "UNKNOWN"),
            )

        execution_attempt = result["attempt"]
        remote_run_id = execution_attempt["attempt_id"]

        submitted = advance(
            attempt,
            "SUBMITTED",
            remote_run_id=remote_run_id,
        )

        return advance(submitted, "COMPLETED")

    def status(self, attempt: BackendAttempt) -> BackendAttempt:
        if attempt.backend != "local":
            raise ExecutionError(
                "attempt belongs to another backend",
                "INTEGRITY",
            )
        return attempt

    def retrieve(self, attempt: BackendAttempt) -> BackendAttempt:
        if attempt.backend != "local":
            raise ExecutionError(
                "attempt belongs to another backend",
                "INTEGRITY",
            )
        return attempt

