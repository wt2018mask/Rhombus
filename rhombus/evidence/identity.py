"""Typed identities and bindings shared by the Rhombus 2.0 Evidence Ledger."""

from __future__ import annotations

from dataclasses import dataclass
import re


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _require_text(name: str, value: str) -> None:
    if not value.strip():
        raise ValueError(f"{name} must be non-empty")


def _validate_sha256(name: str, value: str | None) -> None:
    if value is not None and not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase 64-character SHA-256")


@dataclass(frozen=True)
class SourceBinding:
    source_type: str
    source_id: str
    uri: str | None = None
    sha256: str | None = None

    def __post_init__(self) -> None:
        _require_text("source_type", self.source_type)
        _require_text("source_id", self.source_id)
        _validate_sha256("source sha256", self.sha256)


@dataclass(frozen=True)
class ArtifactBinding:
    artifact_id: str
    sha256: str | None = None
    media_type: str | None = None
    source_id: str | None = None

    def __post_init__(self) -> None:
        _require_text("artifact_id", self.artifact_id)
        _validate_sha256("artifact sha256", self.sha256)


@dataclass(frozen=True)
class Limitation:
    code: str
    statement: str

    def __post_init__(self) -> None:
        _require_text("limitation code", self.code)
        _require_text("limitation statement", self.statement)


@dataclass(frozen=True)
class ModelIdentity:
    model_id: str
    name: str
    version: str | None = None
    checkpoint_sha256: str | None = None
    dtype: str | None = None
    framework: str | None = None

    def __post_init__(self) -> None:
        _require_text("model_id", self.model_id)
        _require_text("model name", self.name)
        _validate_sha256("checkpoint_sha256", self.checkpoint_sha256)


@dataclass(frozen=True)
class ModelLineage:
    model_id: str
    parent_model_ids: tuple[str, ...] = ()
    training_source_ids: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_text("model_id", self.model_id)
        if self.model_id in self.parent_model_ids:
            raise ValueError("model cannot list itself as a parent")


@dataclass(frozen=True)
class ProtocolIdentity:
    protocol_id: str
    capability: str
    version: str
    config_hash: str | None = None
    immutable: bool = True

    def __post_init__(self) -> None:
        _require_text("protocol_id", self.protocol_id)
        _require_text("protocol capability", self.capability)
        _require_text("protocol version", self.version)
        if not self.immutable:
            raise ValueError("qualified protocol identities must be immutable")
