from __future__ import annotations

from rudeus.execution.backend import BackendAttempt, BackendCapabilities
from rudeus.execution.contracts import ExecutionError
from rudeus.science.evidence import EvidenceStore


class LocalBackend:
    """Local control-plane adapter; scientific TaskSpecs are remote-only."""

    def __init__(self, *, git_root, store: EvidenceStore):
        self.git_root = git_root
        self.store = store

    def capabilities(self) -> dict:
        report = BackendCapabilities(
            backend_identity="local",
            verification_state="VERIFIED",
            supported_task_modes={"state": "VERIFIED", "value": ["control-plane"]},
        )
        return {"availability": "LOCAL_CONTROL_PLANE_ONLY", "execution_mode": {
            "state": "UNSUPPORTED", "value": "scientific-compute"},
            "capability_model": report.to_dict()}

    def submit(
        self,
        attempt: BackendAttempt,
        task_bundle,
        resource_requirements: dict,
    ) -> BackendAttempt:
        raise ExecutionError(
            "scientific TaskSpec execution is remote-only; local backend dispatch is disabled",
            "UNSUPPORTED_INPUT",
        )

    def prepare(self, task_bundle, resource_requirements):
        raise ExecutionError(
            "scientific TaskSpec execution is remote-only; local preparation is disabled",
            "UNSUPPORTED_INPUT",
        )

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

