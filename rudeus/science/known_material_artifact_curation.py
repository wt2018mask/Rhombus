"""Registry-driven artifact curation for the known-material benchmark.

Material identity lives in data. Source-specific transport/validation lives behind
adapters. The planner never contains a material allowlist, so expanding the benchmark
normally requires registry data, not production-code edits.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping, Protocol
import urllib.request

from rudeus.science.contracts import Record, require_hash
from rudeus.science.known_material_structure_binding import (
    LicenseDisposition,
    StructureArtifactState,
    StructureBindingLedger,
)
from rudeus.science.known_material_structure_import import (
    COD_LICENSE,
    CodArtifactSpec,
    verify_cod_cif_payload,
)


ARTIFACT_REGISTRY_VERSION = "known-material-artifact-registry-v1"
ARTIFACT_RECEIPT_VERSION = "known-material-artifact-receipt-v1"
MAX_ARTIFACT_BYTES = 10 * 1024 * 1024


class ArtifactKind(str, Enum):
    REFERENCE_STRUCTURE = "REFERENCE_STRUCTURE"


class CurationScope(str, Enum):
    UNRESOLVED = "unresolved"
    ALL = "all"
    MATERIAL = "material"
    FAMILY = "family"
    SOURCE = "source"


@dataclass(frozen=True, kw_only=True)
class ArtifactRegistryEntry(Record):
    artifact_key: str
    material_key: str
    chemistry_family: str
    artifact_kind: str
    source_adapter: str
    source_config: Mapping[str, Any]
    validation: Mapping[str, Any]
    retained_path: str
    receipt_path: str

    def validate(self):
        super().validate()
        ArtifactKind(self.artifact_kind)
        if not all((
            self.artifact_key,
            self.material_key,
            self.chemistry_family,
            self.source_adapter,
            self.source_config,
            self.validation,
            self.retained_path,
            self.receipt_path,
        )):
            raise ValueError("artifact registry entry is incomplete")
        for value in (self.retained_path, self.receipt_path):
            path = Path(value)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("artifact registry paths must be repository-relative")
        if self.retained_path == self.receipt_path:
            raise ValueError("artifact and receipt paths must differ")


@dataclass(frozen=True, kw_only=True)
class ArtifactRegistry(Record):
    registry_version: str
    entries: tuple[ArtifactRegistryEntry, ...]

    @classmethod
    def from_dict(cls, value):
        value = dict(value)
        value["entries"] = tuple(
            ArtifactRegistryEntry.from_dict(item) for item in value["entries"]
        )
        return cls(**value)

    def validate(self):
        super().validate()
        if self.registry_version != ARTIFACT_REGISTRY_VERSION:
            raise ValueError("unsupported artifact registry version")
        keys = [entry.artifact_key for entry in self.entries]
        if not keys or len(keys) != len(set(keys)):
            raise ValueError("artifact registry requires unique artifact keys")


@dataclass(frozen=True, kw_only=True)
class ArtifactRetentionReceipt(Record):
    receipt_version: str
    artifact_key: str
    material_key: str
    artifact_kind: str
    source_adapter: str
    source_id: str
    pinned_locator: str
    license_id: str
    artifact_sha256: str
    byte_count: int
    retained_path: str
    validation_summary: Mapping[str, Any]

    def validate(self):
        super().validate()
        if self.receipt_version != ARTIFACT_RECEIPT_VERSION:
            raise ValueError("unsupported artifact receipt version")
        ArtifactKind(self.artifact_kind)
        if not all((
            self.artifact_key,
            self.material_key,
            self.source_adapter,
            self.source_id,
            self.pinned_locator,
            self.license_id,
            self.retained_path,
            self.validation_summary,
        )):
            raise ValueError("artifact retention receipt is incomplete")
        require_hash(self.artifact_sha256)
        if self.byte_count <= 0:
            raise ValueError("retention receipt requires nonempty artifact")


@dataclass(frozen=True, kw_only=True)
class CurationPlan(Record):
    scope: str
    selector: str | None
    artifact_keys: tuple[str, ...]

    def validate(self):
        super().validate()
        scope = CurationScope(self.scope)
        if scope in {CurationScope.MATERIAL, CurationScope.FAMILY, CurationScope.SOURCE}:
            if not self.selector:
                raise ValueError("selected curation scope requires a selector")
        elif self.selector:
            raise ValueError("all/unresolved curation scope does not accept a selector")
        if len(self.artifact_keys) != len(set(self.artifact_keys)):
            raise ValueError("curation plan contains duplicate artifacts")


class ArtifactSourceAdapter(Protocol):
    adapter_id: str

    def retain(
        self,
        entry: ArtifactRegistryEntry,
        *,
        repo_root: Path,
    ) -> ArtifactRetentionReceipt: ...


def _download(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Rhombus-known-material-curation/2",
            "Accept": "chemical/x-cif,text/plain;q=0.9,*/*;q=0.1",
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        status = getattr(response, "status", 200)
        if status != 200:
            raise RuntimeError(f"artifact download returned HTTP {status}")
        payload = response.read(MAX_ARTIFACT_BYTES + 1)
    if len(payload) > MAX_ARTIFACT_BYTES:
        raise RuntimeError("artifact exceeds bounded download size")
    if not payload:
        raise RuntimeError("artifact download is empty")
    return payload


def _atomic_write_bytes(path: Path, payload: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


class CodCifAdapter:
    adapter_id = "cod-cif-v1"

    def retain(
        self,
        entry: ArtifactRegistryEntry,
        *,
        repo_root: Path,
    ) -> ArtifactRetentionReceipt:
        if entry.artifact_kind != ArtifactKind.REFERENCE_STRUCTURE.value:
            raise ValueError("COD CIF adapter only supports reference structures")

        spec = CodArtifactSpec(
            material_key=entry.material_key,
            cod_id=str(entry.source_config["cod_id"]),
            revision=int(entry.source_config["revision"]),
            expected_formula=str(entry.validation["expected_formula"]),
            expected_space_group_number=int(
                entry.validation["expected_space_group_number"]
            ),
        )
        payload = _download(spec.pinned_locator)
        digest = verify_cod_cif_payload(payload, spec)

        destination = repo_root / entry.retained_path
        _atomic_write_bytes(destination, payload)
        retained = destination.read_bytes()
        if retained != payload:
            raise ValueError("retained artifact differs from verified input bytes")

        return ArtifactRetentionReceipt(
            receipt_version=ARTIFACT_RECEIPT_VERSION,
            artifact_key=entry.artifact_key,
            material_key=entry.material_key,
            artifact_kind=entry.artifact_kind,
            source_adapter=self.adapter_id,
            source_id=spec.source_id,
            pinned_locator=spec.pinned_locator,
            license_id=COD_LICENSE,
            artifact_sha256=digest,
            byte_count=len(payload),
            retained_path=entry.retained_path,
            validation_summary={
                "cod_id": spec.cod_id,
                "revision": spec.revision,
                "expected_formula": spec.expected_formula,
                "expected_space_group_number": spec.expected_space_group_number,
            },
        )


_ADAPTERS: dict[str, ArtifactSourceAdapter] = {
    CodCifAdapter.adapter_id: CodCifAdapter(),
}


def adapter_for(adapter_id: str) -> ArtifactSourceAdapter:
    try:
        return _ADAPTERS[adapter_id]
    except KeyError as exc:
        raise ValueError(f"unsupported artifact source adapter: {adapter_id}") from exc


def build_curation_plan(
    registry: ArtifactRegistry,
    ledger: StructureBindingLedger,
    *,
    scope: str,
    selector: str | None = None,
) -> CurationPlan:
    mode = CurationScope(scope)
    selected: list[ArtifactRegistryEntry] = []

    ledger_by_material = {entry.material_key: entry for entry in ledger.entries}

    for entry in registry.entries:
        if mode == CurationScope.MATERIAL and entry.material_key != selector:
            continue
        if mode == CurationScope.FAMILY and entry.chemistry_family != selector:
            continue
        if mode == CurationScope.SOURCE and entry.source_adapter != selector:
            continue
        if mode == CurationScope.UNRESOLVED:
            binding = ledger_by_material.get(entry.material_key)
            if binding is None:
                continue
            if binding.artifact_state != StructureArtifactState.SOURCE_IDENTIFIED.value:
                continue
        selected.append(entry)

    return CurationPlan(
        scope=mode.value,
        selector=selector,
        artifact_keys=tuple(entry.artifact_key for entry in selected),
    )


def apply_structure_retention_receipt(
    ledger: StructureBindingLedger,
    receipt: ArtifactRetentionReceipt,
) -> StructureBindingLedger:
    if receipt.artifact_kind != ArtifactKind.REFERENCE_STRUCTURE.value:
        raise ValueError("receipt is not a reference-structure artifact")

    matches = [
        (index, entry)
        for index, entry in enumerate(ledger.entries)
        if entry.material_key == receipt.material_key
    ]
    if len(matches) != 1:
        raise ValueError("receipt must match exactly one structure binding")
    index, binding = matches[0]

    if binding.source_id != receipt.source_id:
        raise ValueError("receipt source identity differs from structure ledger")
    if binding.artifact_locator != receipt.pinned_locator:
        raise ValueError("receipt locator differs from structure ledger")
    if binding.license_disposition != LicenseDisposition.VERIFIED_REDISTRIBUTABLE.value:
        raise ValueError("retention requires verified redistribution rights")
    if binding.artifact_state == StructureArtifactState.HASHED_AND_VALIDATED.value:
        raise ValueError("validated structure cannot be overwritten by curation")
    if binding.artifact_state == StructureArtifactState.REJECTED.value:
        raise ValueError("rejected structure requires new scientific curation")
    if binding.artifact_sha256 not in (None, receipt.artifact_sha256):
        raise ValueError("existing structure hash conflicts with retention receipt")
    if binding.retained_path not in (None, receipt.retained_path):
        raise ValueError("existing retained path conflicts with retention receipt")

    blockers = tuple(
        blocker
        for blocker in binding.blockers
        if blocker != "artifact_not_yet_retained_and_hashed"
    )
    retained = replace(
        binding,
        artifact_state=StructureArtifactState.ARTIFACT_RETAINED.value,
        artifact_sha256=receipt.artifact_sha256,
        retained_path=receipt.retained_path,
        blockers=blockers,
    )
    entries = list(ledger.entries)
    entries[index] = retained
    return replace(ledger, entries=tuple(entries))


def load_registry(path: Path) -> ArtifactRegistry:
    return ArtifactRegistry.from_dict(json.loads(path.read_text(encoding="utf-8")))
