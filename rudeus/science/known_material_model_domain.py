"""Generic model-domain snapshot contracts for known-material benchmark B2.

A model's supported element set is extracted from the exact pinned checkpoint. The
snapshot is evidence about model applicability, not a claim about material physics.
Unsupported species must be classified before MLIP execution, never inferred from a
runtime crash or converted into a material FAIL.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from pathlib import Path
import tempfile
from typing import Any, Callable, Mapping
import urllib.request

from pymatgen.core import Element

from rudeus.science.contracts import Record, require_hash


MODEL_DOMAIN_REGISTRY_VERSION = "known-material-model-domain-registry-v1"
MODEL_DOMAIN_INDEX_VERSION = "known-material-model-domain-index-v1"
MODEL_DOMAIN_SNAPSHOT_VERSION = "known-material-model-domain-snapshot-v1"
MACE_DOMAIN_ADAPTER = "mace-checkpoint-domain-v1"

MODEL_DOMAIN_ROOT = Path("data/benchmarks/known_material/model_domains")


class ModelDomainScope(str, Enum):
    UNRESOLVED = "unresolved"
    ALL = "all"
    DOMAIN = "domain"


@dataclass(frozen=True, kw_only=True)
class ModelDomainRegistryEntry(Record):
    domain_key: str
    model_id: str
    source_adapter: str
    checkpoint_url: str
    checkpoint_sha256: str
    expected_element_count: int | None
    package_constraint: str
    snapshot_path: str
    evidence_refs: tuple[str, ...] = ()

    def validate(self):
        super().validate()
        if not self.domain_key or not self.model_id:
            raise ValueError("model-domain registry entry identity is incomplete")
        if self.source_adapter != MACE_DOMAIN_ADAPTER:
            raise ValueError("unsupported model-domain source adapter")
        if not self.checkpoint_url.startswith("https://"):
            raise ValueError("model-domain checkpoint URL must be HTTPS")
        require_hash(self.checkpoint_sha256)
        if self.expected_element_count is not None and self.expected_element_count <= 0:
            raise ValueError("expected element count must be positive")
        if not self.package_constraint:
            raise ValueError("model-domain package constraint is required")
        path = Path(self.snapshot_path)
        if (
            path.is_absolute()
            or ".." in path.parts
            or not path.is_relative_to(MODEL_DOMAIN_ROOT)
        ):
            raise ValueError("model-domain snapshot path escapes benchmark root")


@dataclass(frozen=True, kw_only=True)
class ModelDomainRegistry(Record):
    registry_version: str
    entries: tuple[ModelDomainRegistryEntry, ...]

    @classmethod
    def from_dict(cls, value):
        value = dict(value)
        value["entries"] = tuple(
            ModelDomainRegistryEntry.from_dict(item)
            for item in value["entries"]
        )
        return cls(**value)

    def validate(self):
        super().validate()
        if self.registry_version != MODEL_DOMAIN_REGISTRY_VERSION:
            raise ValueError("unsupported model-domain registry version")
        keys = [item.domain_key for item in self.entries]
        paths = [item.snapshot_path for item in self.entries]
        if len(keys) != len(set(keys)):
            raise ValueError("model-domain registry requires unique domain keys")
        if len(paths) != len(set(paths)):
            raise ValueError("model-domain registry requires unique snapshot paths")


@dataclass(frozen=True, kw_only=True)
class ModelDomainSnapshot(Record):
    snapshot_version: str
    domain_key: str
    model_id: str
    source_adapter: str
    checkpoint_sha256: str
    extractor_package: str
    extractor_package_version: str
    model_atomic_number_order: tuple[int, ...]
    supported_atomic_numbers: tuple[int, ...]
    supported_symbols: tuple[str, ...]
    element_count: int
    unsupported_atomic_numbers_1_to_118: tuple[int, ...]
    evidence_refs: tuple[str, ...]

    def validate(self):
        super().validate()
        if self.snapshot_version != MODEL_DOMAIN_SNAPSHOT_VERSION:
            raise ValueError("unsupported model-domain snapshot version")
        if self.source_adapter != MACE_DOMAIN_ADAPTER:
            raise ValueError("unsupported model-domain snapshot adapter")
        require_hash(self.checkpoint_sha256)
        if not self.domain_key or not self.model_id:
            raise ValueError("model-domain snapshot identity is incomplete")
        if not self.extractor_package or not self.extractor_package_version:
            raise ValueError("model-domain extractor identity is required")
        ordered = tuple(self.model_atomic_number_order)
        canonical = tuple(self.supported_atomic_numbers)
        if not ordered or len(ordered) != len(set(ordered)):
            raise ValueError("model atomic-number order must be non-empty and unique")
        if canonical != tuple(sorted(set(ordered))):
            raise ValueError(
                "supported atomic numbers must be the sorted unique model domain"
            )
        if self.element_count != len(canonical):
            raise ValueError("model-domain element count is inconsistent")
        if any(z < 1 or z > 118 for z in canonical):
            raise ValueError("model-domain atomic numbers must lie within 1..118")
        expected_symbols = tuple(str(Element.from_Z(z)) for z in canonical)
        if tuple(self.supported_symbols) != expected_symbols:
            raise ValueError("model-domain symbols do not match atomic numbers")
        unsupported = tuple(z for z in range(1, 119) if z not in set(canonical))
        if tuple(self.unsupported_atomic_numbers_1_to_118) != unsupported:
            raise ValueError("unsupported atomic-number complement is inconsistent")
        if not self.evidence_refs:
            raise ValueError("model-domain snapshot requires evidence refs")


@dataclass(frozen=True, kw_only=True)
class ModelDomainIndexEntry(Record):
    domain_key: str
    snapshot_path: str
    snapshot_content_hash: str
    checkpoint_sha256: str
    element_count: int

    def validate(self):
        super().validate()
        if not self.domain_key:
            raise ValueError("model-domain index entry requires domain key")
        require_hash(self.snapshot_content_hash)
        require_hash(self.checkpoint_sha256)
        if self.element_count <= 0:
            raise ValueError("model-domain index entry requires positive element count")


@dataclass(frozen=True, kw_only=True)
class ModelDomainIndex(Record):
    index_version: str
    entries: tuple[ModelDomainIndexEntry, ...]

    @classmethod
    def from_dict(cls, value):
        value = dict(value)
        value["entries"] = tuple(
            ModelDomainIndexEntry.from_dict(item) for item in value["entries"]
        )
        return cls(**value)

    def validate(self):
        super().validate()
        if self.index_version != MODEL_DOMAIN_INDEX_VERSION:
            raise ValueError("unsupported model-domain index version")
        keys = [item.domain_key for item in self.entries]
        paths = [item.snapshot_path for item in self.entries]
        if len(keys) != len(set(keys)):
            raise ValueError("model-domain index requires unique domain keys")
        if len(paths) != len(set(paths)):
            raise ValueError("model-domain index requires unique snapshot paths")


@dataclass(frozen=True, kw_only=True)
class ModelDomainCheck(Record):
    domain_key: str
    input_atomic_numbers: tuple[int, ...]
    unsupported_atomic_numbers: tuple[int, ...]
    supported: bool
    disposition: str
    reason_codes: tuple[str, ...]

    def validate(self):
        super().validate()
        if self.disposition not in {
            "SUPPORTED_BY_MODEL_DOMAIN",
            "UNKNOWN_MODEL_DOMAIN_UNSUPPORTED",
        }:
            raise ValueError("unsupported model-domain check disposition")
        if self.supported != (not self.unsupported_atomic_numbers):
            raise ValueError("model-domain check support flag is inconsistent")
        if self.supported and self.disposition != "SUPPORTED_BY_MODEL_DOMAIN":
            raise ValueError("supported model-domain input has wrong disposition")
        if not self.supported and self.disposition != "UNKNOWN_MODEL_DOMAIN_UNSUPPORTED":
            raise ValueError("unsupported model-domain input must remain UNKNOWN")
        if not self.reason_codes:
            raise ValueError("model-domain check requires reason codes")


def load_model_domain_registry(path: Path) -> ModelDomainRegistry:
    return ModelDomainRegistry.from_dict(
        json.loads(path.read_text(encoding="utf-8"))
    )


def load_model_domain_index(path: Path) -> ModelDomainIndex:
    return ModelDomainIndex.from_dict(
        json.loads(path.read_text(encoding="utf-8"))
    )


def load_model_domain_snapshot(path: Path) -> ModelDomainSnapshot:
    return ModelDomainSnapshot.from_dict(
        json.loads(path.read_text(encoding="utf-8"))
    )


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _default_mace_loader(checkpoint_path: Path):
    from importlib.metadata import version
    from rudeus.mlip.relax import load_calculator

    calculator = load_calculator(
        checkpoint_path,
        device="cpu",
        dtype="float64",
    )
    atomic_numbers = tuple(int(z) for z in calculator.z_table.zs)
    return atomic_numbers, "mace-torch", version("mace-torch")


def extract_model_domain_snapshot(
    entry: ModelDomainRegistryEntry,
    *,
    checkpoint_path: Path,
    loader: Callable[[Path], tuple[tuple[int, ...], str, str]] | None = None,
) -> ModelDomainSnapshot:
    actual_sha = sha256_file(checkpoint_path)
    if actual_sha != entry.checkpoint_sha256:
        raise ValueError(
            f"checkpoint hash mismatch for {entry.domain_key}: "
            f"expected {entry.checkpoint_sha256}, got {actual_sha}"
        )

    atomic_numbers, package_name, package_version = (
        loader or _default_mace_loader
    )(checkpoint_path)
    ordered = tuple(int(z) for z in atomic_numbers)
    canonical = tuple(sorted(set(ordered)))

    if entry.expected_element_count is not None:
        if len(canonical) != entry.expected_element_count:
            raise ValueError(
                f"model-domain element count mismatch for {entry.domain_key}: "
                f"expected {entry.expected_element_count}, got {len(canonical)}"
            )

    return ModelDomainSnapshot(
        snapshot_version=MODEL_DOMAIN_SNAPSHOT_VERSION,
        domain_key=entry.domain_key,
        model_id=entry.model_id,
        source_adapter=entry.source_adapter,
        checkpoint_sha256=actual_sha,
        extractor_package=package_name,
        extractor_package_version=package_version,
        model_atomic_number_order=ordered,
        supported_atomic_numbers=canonical,
        supported_symbols=tuple(str(Element.from_Z(z)) for z in canonical),
        element_count=len(canonical),
        unsupported_atomic_numbers_1_to_118=tuple(
            z for z in range(1, 119) if z not in set(canonical)
        ),
        evidence_refs=(
            *entry.evidence_refs,
            f"checkpoint-sha256:{actual_sha}",
        ),
    )


def check_model_domain(
    snapshot: ModelDomainSnapshot,
    atomic_numbers: tuple[int, ...],
) -> ModelDomainCheck:
    inputs = tuple(sorted(set(int(z) for z in atomic_numbers)))
    if not inputs:
        raise ValueError("model-domain check requires at least one atomic number")
    if any(z < 1 or z > 118 for z in inputs):
        raise ValueError("input atomic numbers must lie within 1..118")

    supported = set(snapshot.supported_atomic_numbers)
    missing = tuple(z for z in inputs if z not in supported)
    if missing:
        return ModelDomainCheck(
            domain_key=snapshot.domain_key,
            input_atomic_numbers=inputs,
            unsupported_atomic_numbers=missing,
            supported=False,
            disposition="UNKNOWN_MODEL_DOMAIN_UNSUPPORTED",
            reason_codes=("MODEL_DOMAIN_UNSUPPORTED_SPECIES",),
        )
    return ModelDomainCheck(
        domain_key=snapshot.domain_key,
        input_atomic_numbers=inputs,
        unsupported_atomic_numbers=(),
        supported=True,
        disposition="SUPPORTED_BY_MODEL_DOMAIN",
        reason_codes=("MODEL_DOMAIN_SPECIES_SUPPORTED",),
    )


def deterministic_unsupported_atomic_number(
    snapshot: ModelDomainSnapshot,
) -> int:
    if not snapshot.unsupported_atomic_numbers_1_to_118:
        raise ValueError("model snapshot covers all atomic numbers 1..118")
    return snapshot.unsupported_atomic_numbers_1_to_118[0]


def plan_model_domain_entries(
    registry: ModelDomainRegistry,
    index: ModelDomainIndex,
    *,
    scope: str,
    selector: str | None = None,
) -> tuple[ModelDomainRegistryEntry, ...]:
    parsed_scope = ModelDomainScope(scope)
    indexed = {item.domain_key for item in index.entries}

    if parsed_scope == ModelDomainScope.DOMAIN:
        if not selector:
            raise ValueError("domain scope requires selector")
        selected = tuple(
            item for item in registry.entries if item.domain_key == selector
        )
        if not selected:
            raise ValueError(f"unknown model-domain selector: {selector}")
        return selected

    if selector:
        raise ValueError(f"{parsed_scope.value} scope does not accept selector")
    if parsed_scope == ModelDomainScope.ALL:
        return registry.entries
    return tuple(
        item for item in registry.entries if item.domain_key not in indexed
    )


def retain_model_domain_snapshot(
    *,
    entry: ModelDomainRegistryEntry,
    snapshot: ModelDomainSnapshot,
    index: ModelDomainIndex,
    repo_root: Path,
) -> ModelDomainIndex:
    if snapshot.domain_key != entry.domain_key:
        raise ValueError("model-domain snapshot/registry key mismatch")
    if snapshot.checkpoint_sha256 != entry.checkpoint_sha256:
        raise ValueError("model-domain snapshot checkpoint mismatch")

    path = repo_root / entry.snapshot_path
    payload = (
        json.dumps(snapshot.to_dict(), sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")

    if path.exists() and path.read_bytes() != payload:
        raise ValueError(
            f"conflicting model-domain snapshot already exists: {entry.snapshot_path}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)

    by_key = {item.domain_key: item for item in index.entries}
    new_entry = ModelDomainIndexEntry(
        domain_key=entry.domain_key,
        snapshot_path=entry.snapshot_path,
        snapshot_content_hash=snapshot.content_hash,
        checkpoint_sha256=snapshot.checkpoint_sha256,
        element_count=snapshot.element_count,
    )
    existing = by_key.get(entry.domain_key)
    if existing is not None and existing != new_entry:
        raise ValueError("conflicting model-domain index entry")
    by_key[entry.domain_key] = new_entry
    return ModelDomainIndex(
        index_version=MODEL_DOMAIN_INDEX_VERSION,
        entries=tuple(by_key[key] for key in sorted(by_key)),
    )


def persist_model_domain_index(index: ModelDomainIndex, path: Path) -> None:
    payload = json.dumps(index.to_dict(), sort_keys=True, indent=2) + "\n"
    path.write_text(payload, encoding="utf-8")


def verify_model_domain_repository_state(
    registry: ModelDomainRegistry,
    index: ModelDomainIndex,
    *,
    repo_root: Path,
) -> tuple[str, ...]:
    registry_by_key = {item.domain_key: item for item in registry.entries}
    checked: list[str] = []
    for item in index.entries:
        entry = registry_by_key.get(item.domain_key)
        if entry is None:
            raise ValueError(
                f"model-domain index references unknown registry key: {item.domain_key}"
            )
        if item.snapshot_path != entry.snapshot_path:
            raise ValueError("model-domain index snapshot path differs from registry")
        path = repo_root / item.snapshot_path
        if not path.is_file():
            raise ValueError(f"model-domain snapshot is missing: {item.snapshot_path}")
        snapshot = load_model_domain_snapshot(path)
        if snapshot.domain_key != item.domain_key:
            raise ValueError("model-domain snapshot identity mismatch")
        if snapshot.content_hash != item.snapshot_content_hash:
            raise ValueError("model-domain snapshot content hash mismatch")
        if snapshot.checkpoint_sha256 != item.checkpoint_sha256:
            raise ValueError("model-domain snapshot checkpoint hash mismatch")
        if snapshot.element_count != item.element_count:
            raise ValueError("model-domain snapshot element count mismatch")
        if entry.expected_element_count is not None:
            if snapshot.element_count != entry.expected_element_count:
                raise ValueError("model-domain snapshot violates expected element count")
        checked.append(item.domain_key)
    return tuple(checked)


def download_checkpoint(entry: ModelDomainRegistryEntry, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=target.parent,
        prefix=target.name + ".",
        suffix=".tmp",
        delete=False,
    ) as tmp:
        temp_path = Path(tmp.name)
    try:
        urllib.request.urlretrieve(entry.checkpoint_url, temp_path)
        actual = sha256_file(temp_path)
        if actual != entry.checkpoint_sha256:
            raise ValueError(
                f"downloaded checkpoint hash mismatch for {entry.domain_key}"
            )
        temp_path.replace(target)
    finally:
        if temp_path.exists():
            temp_path.unlink()
    return target
