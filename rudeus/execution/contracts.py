"""Execution identity and failure semantics, separate from scientific verdicts."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from collections.abc import Mapping
import subprocess
from rudeus.science.contracts import Record, require_hash, digest


class FailureClass(str, Enum):
    INFRASTRUCTURE = "INFRASTRUCTURE"
    RESOURCE = "RESOURCE"
    TIMEOUT = "TIMEOUT"
    NETWORK = "NETWORK"
    SOFTWARE = "SOFTWARE"
    NUMERICAL = "NUMERICAL"
    INTEGRITY = "INTEGRITY"
    UNSUPPORTED_INPUT = "UNSUPPORTED_INPUT"
    UNKNOWN = "UNKNOWN"


class ExecutionError(RuntimeError):
    def __init__(self, message, failure_class=FailureClass.UNKNOWN):
        super().__init__(message)
        self.failure_class = FailureClass(failure_class)


def classify_failure(exc: Exception) -> FailureClass:
    if isinstance(exc, ExecutionError):
        return exc.failure_class
    if isinstance(exc, (TimeoutError, subprocess.TimeoutExpired)):
        return FailureClass.TIMEOUT
    if isinstance(exc, MemoryError):
        return FailureClass.RESOURCE
    if isinstance(exc, ConnectionError):
        return FailureClass.NETWORK
    if isinstance(exc, (FloatingPointError, OverflowError)):
        return FailureClass.NUMERICAL
    if isinstance(exc, FileNotFoundError):
        return FailureClass.INTEGRITY
    return FailureClass.SOFTWARE


@dataclass(frozen=True, kw_only=True)
class TaskSpec(Record):
    candidate_id: str
    stage: str
    protocol_hash: str
    config: Mapping
    input_artifact_hashes: tuple[str, ...]
    dependencies: tuple[str, ...]
    code_revision: str
    resource_requirements: Mapping
    expected_outputs: tuple[str, ...]
    retry_policy: Mapping
    temperature: float | None = None
    replica: str | None = None
    seed: int | None = None
    # Archival references may contain execution metadata indirectly. They do not
    # define the computation. Omit the absent field to preserve old bytes/hashes.
    provenance: Mapping | None = field(default=None, metadata={"omit_none": True})

    def validate(self):
        super().validate()
        require_hash(self.protocol_hash)
        for h in self.input_artifact_hashes + self.dependencies:
            require_hash(h)
        if not self.candidate_id or not self.stage or not self.code_revision:
            raise ValueError("task scientific identity is incomplete")
        if "backend" in self.config or "backend" in self.resource_requirements:
            raise ValueError("backend selection belongs to execution")
        if not self.expected_outputs or len(set(self.expected_outputs)) != len(self.expected_outputs):
            raise ValueError("expected outputs must be explicit and unique")
        for name in self.expected_outputs:
            if not name or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-" for c in name) or name in (".", ".."):
                raise ValueError("outputs must use simple logical names")
        if self.temperature is not None and self.temperature <= 0:
            raise ValueError("temperature must be positive")

    @property
    def config_hash(self):
        return digest(self.config)

    @property
    def task_id(self):
        # Execution choices/budgets are intentionally excluded. No implicit seeds.
        return digest({"version": self.schema_version, "candidate": self.candidate_id,
                       "stage": self.stage, "protocol": self.protocol_hash,
                       "config": self.config_hash, "inputs": sorted(self.input_artifact_hashes),
                       "dependencies": sorted(self.dependencies), "code": self.code_revision,
                       "temperature": self.temperature, "replica": self.replica, "seed": self.seed,
                       "outputs": sorted(self.expected_outputs)})


@dataclass(frozen=True, kw_only=True)
class ExecutionAttempt(Record):
    attempt_id: str
    task_id: str
    backend: str
    remote_session_id: str | None
    started_at: str
    ended_at: str
    runtime_s: float
    hardware: Mapping
    environment: Mapping
    precision: str | None
    exit_status: int | None
    status: str
    termination_reason: str
    failure_class: FailureClass | None
    logs: tuple[str, ...]
    output_manifest: Mapping

    def validate(self):
        super().validate()
        require_hash(self.attempt_id)
        require_hash(self.task_id)
        if self.runtime_s < 0 or self.status not in ("COMPLETED", "FAILED", "PREEMPTED"):
            raise ValueError("invalid execution status/runtime")
        if (self.status == "COMPLETED") != (self.failure_class is None):
            raise ValueError("completion and failure classification disagree")
        if self.failure_class is not None:
            FailureClass(self.failure_class)


@dataclass(frozen=True, kw_only=True)
class ArtifactManifest(Record):
    logical_hash: str
    canonicalization_version: str
    raw_hash: str
    format: str
    format_version: str
    size_bytes: int
    durable_locator: str
    producer_attempt: str
    parent_artifact_hashes: tuple[str, ...]
    retrieval_verification: Mapping

    def validate(self):
        super().validate()
        for h in (self.logical_hash, self.raw_hash, self.producer_attempt) + self.parent_artifact_hashes:
            require_hash(h)
        if self.size_bytes < 0:
            raise ValueError("negative artifact size")
