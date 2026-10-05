"""Registry-driven artifact curation for the known-material benchmark.

Material identity lives in data. Source-specific transport/validation lives behind
adapters. Mechanical artifact retention is tracked independently from scientific
structure binding, so one material may retain multiple phase/disorder/source artifacts
without forcing a premature one-hash scientific interpretation.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from enum import Enum
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping, Protocol
import urllib.request

from rudeus.science.contracts import Record, require_hash
from rudeus.science.known_material_structure_import import (
    COD_LICENSE,
    CodArtifactSpec,
    verify_cod_cif_payload,
)


ARTIFACT_REGISTRY_VERSION = "known-material-artifact-registry-v1"
ARTIFACT_RECEIPT_VERSION = "known-material-artifact-receipt-v1"
ARTIFACT_INDEX_VERSION = "known-material-artifact-retention-index-v1"
ARTIFACT_VERIFICATION_VERSION = "known-material-artifact-verification-v1"
MAX_ARTIFACT_BYTES = 10 * 1024 * 1024

STRUCTURE_ROOT = Path("data/benchmarks/known_material/structures")
RECEIPT_ROOT = Path("data/benchmarks/known_material/receipts")


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

        retained = Path(self.retained_path)
        receipt = Path(self.receipt_path)
        for path in (retained, receipt):
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("artifact registry paths must be repository-relative")
        if retained == receipt:
            raise ValueError("artifact and receipt paths must differ")
        if not retained.is_relative_to(STRUCTURE_ROOT):
            raise ValueError("retained structure path must stay under benchmark structure root")
        if not receipt.is_relative_to(RECEIPT_ROOT):
            raise ValueError("receipt path must stay under benchmark receipt root")


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
        retained_paths = [entry.retained_path for entry in self.entries]
        receipt_paths = [entry.receipt_path for entry in self.entries]
        if not keys or len(keys) != len(set(keys)):
            raise ValueError("artifact registry requires unique artifact keys")
        if len(retained_paths) != len(set(retained_paths)):
            raise ValueError("artifact registry requires unique retained paths")
        if len(receipt_paths) != len(set(receipt_paths)):
            raise ValueError("artifact registry requires unique receipt paths")


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
        path = Path(self.retained_path)
        if path.is_absolute() or ".." in path.parts or not path.is_relative_to(STRUCTURE_ROOT):
            raise ValueError("retained artifact path escapes benchmark structure root")


@dataclass(frozen=True, kw_only=True)
class ArtifactRetentionIndex(Record):
    index_version: str
    receipts: tuple[ArtifactRetentionReceipt, ...]

    @classmethod
    def from_dict(cls, value):
        value = dict(value)
        value["receipts"] = tuple(
            ArtifactRetentionReceipt.from_dict(item) for item in value["receipts"]
        )
        return cls(**value)

    def validate(self):
        super().validate()
        if self.index_version != ARTIFACT_INDEX_VERSION:
            raise ValueError("unsupported artifact retention index version")
        keys = [receipt.artifact_key for receipt in self.receipts]
        paths = [receipt.retained_path for receipt in self.receipts]
        if len(keys) != len(set(keys)):
            raise ValueError("retention index requires unique artifact keys")
        if len(paths) != len(set(paths)):
            raise ValueError("retention index requires unique retained paths")


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


class CodCifLatestFreezeAdapter:
    """Retain the current COD payload and freeze exact bytes by SHA256.

    This adapter is for records whose COD identifier is known but whose upstream
    SVN revision has not been independently established. It never invents a
    revision number: the retained bytes and their SHA256 become the provenance
    unit reviewed before merge.
    """

    adapter_id = "cod-cif-latest-freeze-v1"

    def retain(
        self,
        entry: ArtifactRegistryEntry,
        *,
        repo_root: Path,
    ) -> ArtifactRetentionReceipt:
        if entry.artifact_kind != ArtifactKind.REFERENCE_STRUCTURE.value:
            raise ValueError("COD CIF adapter only supports reference structures")

        cod_id = str(entry.source_config["cod_id"])
        spec = CodArtifactSpec(
            material_key=entry.material_key,
            cod_id=cod_id,
            revision=1,
            expected_formula=str(entry.validation["expected_formula"]),
            expected_space_group_number=int(
                entry.validation["expected_space_group_number"]
            ),
        )
        latest_locator = f"https://www.crystallography.net/cod/{cod_id}.cif"
        payload = _download(latest_locator)
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
            source_id=f"cod:{cod_id}@sha256:{digest}",
            pinned_locator=latest_locator,
            license_id=COD_LICENSE,
            artifact_sha256=digest,
            byte_count=len(payload),
            retained_path=entry.retained_path,
            validation_summary={
                "cod_id": cod_id,
                "revision": "UNASSERTED",
                "retention_policy": "latest-uri-freeze-by-sha256-v1",
                "expected_formula": spec.expected_formula,
                "expected_space_group_number": spec.expected_space_group_number,
            },
        )


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
    CodCifLatestFreezeAdapter.adapter_id: CodCifLatestFreezeAdapter(),
}


def adapter_for(adapter_id: str) -> ArtifactSourceAdapter:
    try:
        return _ADAPTERS[adapter_id]
    except KeyError as exc:
        raise ValueError(f"unsupported artifact source adapter: {adapter_id}") from exc


def build_curation_plan(
    registry: ArtifactRegistry,
    index: ArtifactRetentionIndex,
    *,
    scope: str,
    selector: str | None = None,
) -> CurationPlan:
    mode = CurationScope(scope)
    retained_keys = {receipt.artifact_key for receipt in index.receipts}
    selected: list[ArtifactRegistryEntry] = []

    for entry in registry.entries:
        if mode == CurationScope.MATERIAL and entry.material_key != selector:
            continue
        if mode == CurationScope.FAMILY and entry.chemistry_family != selector:
            continue
        if mode == CurationScope.SOURCE and entry.source_adapter != selector:
            continue
        if mode == CurationScope.UNRESOLVED and entry.artifact_key in retained_keys:
            continue
        selected.append(entry)

    return CurationPlan(
        scope=mode.value,
        selector=selector,
        artifact_keys=tuple(entry.artifact_key for entry in selected),
    )


def apply_retention_receipt(
    index: ArtifactRetentionIndex,
    receipt: ArtifactRetentionReceipt,
) -> ArtifactRetentionIndex:
    by_key = {item.artifact_key: item for item in index.receipts}
    existing = by_key.get(receipt.artifact_key)
    if existing is not None:
        if existing.content_hash != receipt.content_hash:
            raise ValueError("artifact key conflicts with existing retained receipt")
        return index

    if any(item.retained_path == receipt.retained_path for item in index.receipts):
        raise ValueError("retained path already belongs to another artifact")

    return ArtifactRetentionIndex(
        index_version=ARTIFACT_INDEX_VERSION,
        receipts=tuple(index.receipts) + (receipt,),
    )



@dataclass(frozen=True, kw_only=True)
class RetentionVerificationReport(Record):
    verification_version: str
    registry_version: str
    index_version: str
    checked_artifact_keys: tuple[str, ...]

    def validate(self):
        super().validate()
        if self.verification_version != ARTIFACT_VERIFICATION_VERSION:
            raise ValueError("unsupported artifact verification version")
        if self.registry_version != ARTIFACT_REGISTRY_VERSION:
            raise ValueError("verification report registry version mismatch")
        if self.index_version != ARTIFACT_INDEX_VERSION:
            raise ValueError("verification report index version mismatch")
        if len(self.checked_artifact_keys) != len(set(self.checked_artifact_keys)):
            raise ValueError("verification report contains duplicate artifact keys")


def verify_retention_repository_state(
    registry: ArtifactRegistry,
    index: ArtifactRetentionIndex,
    *,
    repo_root: Path,
) -> RetentionVerificationReport:
    """Verify the persisted artifact/index/receipt state after curation.

    Unit tests should not depend on whether the repository currently contains zero,
    one, or many retained artifacts. This verifier instead checks the mutable
    repository state as a consistency graph after any curation batch.
    """
    registry_by_key = {entry.artifact_key: entry for entry in registry.entries}
    indexed_keys = {receipt.artifact_key for receipt in index.receipts}

    unknown = tuple(
        receipt.artifact_key
        for receipt in index.receipts
        if receipt.artifact_key not in registry_by_key
    )
    if unknown:
        raise ValueError(
            "retention index references artifacts outside registry: "
            + ", ".join(unknown)
        )

    for receipt in index.receipts:
        entry = registry_by_key[receipt.artifact_key]
        if receipt.material_key != entry.material_key:
            raise ValueError("retention receipt material identity differs from registry")
        if receipt.artifact_kind != entry.artifact_kind:
            raise ValueError("retention receipt artifact kind differs from registry")
        if receipt.source_adapter != entry.source_adapter:
            raise ValueError("retention receipt source adapter differs from registry")
        if receipt.retained_path != entry.retained_path:
            raise ValueError("retention receipt path differs from registry")

        artifact_path = repo_root / entry.retained_path
        receipt_path = repo_root / entry.receipt_path
        if not artifact_path.is_file():
            raise ValueError(
                f"indexed artifact bytes are missing: {entry.artifact_key}"
            )
        if not receipt_path.is_file():
            raise ValueError(
                f"indexed receipt file is missing: {entry.artifact_key}"
            )

        payload = artifact_path.read_bytes()
        if not payload:
            raise ValueError(f"indexed artifact is empty: {entry.artifact_key}")
        digest = hashlib.sha256(payload).hexdigest()
        if digest != receipt.artifact_sha256:
            raise ValueError(
                f"indexed artifact SHA256 mismatch: {entry.artifact_key}"
            )
        if len(payload) != receipt.byte_count:
            raise ValueError(
                f"indexed artifact byte count mismatch: {entry.artifact_key}"
            )

        persisted = ArtifactRetentionReceipt.from_dict(
            json.loads(receipt_path.read_text(encoding="utf-8"))
        )
        if persisted.content_hash != receipt.content_hash:
            raise ValueError(
                f"persisted receipt differs from retention index: {entry.artifact_key}"
            )

    for entry in registry.entries:
        artifact_exists = (repo_root / entry.retained_path).is_file()
        receipt_exists = (repo_root / entry.receipt_path).is_file()
        if artifact_exists != receipt_exists:
            raise ValueError(
                f"artifact/receipt persistence is incomplete: {entry.artifact_key}"
            )
        if (artifact_exists or receipt_exists) and entry.artifact_key not in indexed_keys:
            raise ValueError(
                f"retained artifact is not indexed: {entry.artifact_key}"
            )

    return RetentionVerificationReport(
        verification_version=ARTIFACT_VERIFICATION_VERSION,
        registry_version=registry.registry_version,
        index_version=index.index_version,
        checked_artifact_keys=tuple(
            receipt.artifact_key for receipt in index.receipts
        ),
    )

def load_registry(path: Path) -> ArtifactRegistry:
    return ArtifactRegistry.from_dict(json.loads(path.read_text(encoding="utf-8")))


def load_retention_index(path: Path) -> ArtifactRetentionIndex:
    return ArtifactRetentionIndex.from_dict(json.loads(path.read_text(encoding="utf-8")))
