"""Frozen structure-comparison executors for Rhombus Phase 3."""

from __future__ import annotations

from functools import lru_cache
import hashlib
from hashlib import sha256
import importlib.util
import json
import os
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from types import ModuleType

from ase import Atoms
from pymatgen.analysis.structure_matcher import StructureMatcher
from pymatgen.core import Structure
from pymatgen.io.ase import AseAtomsAdaptor


CANDIDATE_FINGERPRINT_PROTOCOL_ID = (
    "rhombus-composition-site-count-candidate-fingerprint-v1"
)
STRICT_STRUCTURE_EQUIVALENCE_PROTOCOL_ID = "pymatgen-structure-equivalence-v1"
NEAR_DUPLICATE_PROTOCOL_ID = "pymatgen-structure-near-duplicate-v1"
PROTOTYPE_GROUP_PROTOCOL_ID = "matbench-protostructure-label-v1"

MATBENCH_DISCOVERY_VERSION = "1.3.1"
MOYOPY_VERSION = "0.3.4"
MATBENCH_DISCOVERY_PROTOCOL_COMMIT = "26d3a19073df8cb303c7e4849a0d65e74746d9eb"
MATBENCH_PROTOCOL_SOURCE_ENV = "RHOMBUS_MATBENCH_PROTOCOL_SOURCE_DIR"
MATBENCH_DISCOVERY_BLOBS = {
    "prototype.py": "27f3279a2917fc56a181d85799e11c5634e94aa0",
    "wyckoff-position-multiplicities.yaml.gz": "4f10a2fd8f000bf0f290943e5f2616eadeae02e6",
    "wyckoff-position-relabelings.yaml.gz": "fac2650b9e29db1c3da6db9c16664ad8acf7687b",
}


def as_pymatgen_structure(structure: Structure | Atoms) -> Structure:
    if isinstance(structure, Structure):
        return structure
    if isinstance(structure, Atoms):
        converted = AseAtomsAdaptor.get_structure(structure)
        if not isinstance(converted, Structure):
            raise TypeError(f"Expected periodic Structure, got {type(converted)}")
        return converted
    raise TypeError(f"Expected pymatgen Structure or ASE Atoms, got {type(structure)}")


def _composition_key(structure: Structure) -> str:
    return structure.composition.element_composition.reduced_formula


def structure_candidate_fingerprint_sha256(structure: Structure | Atoms) -> str:
    """Return a safe coarse candidate bucket, never an exact-match verdict.

    Tolerance-based StructureMatcher equivalence cannot be represented by a
    collision-free canonical hash. This fingerprint intentionally contains only
    invariants that every strict match must share: reduced composition and site
    count. Final exact/near decisions must use the frozen comparator executors.
    """

    pmg = as_pymatgen_structure(structure)
    payload = {
        "protocol_id": CANDIDATE_FINGERPRINT_PROTOCOL_ID,
        "composition_key": _composition_key(pmg),
        "site_count": len(pmg),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return sha256(encoded).hexdigest()


def strict_structure_matcher() -> StructureMatcher:
    return StructureMatcher(
        ltol=1e-5,
        stol=1e-5,
        angle_tol=0.001,
        primitive_cell=True,
        scale=False,
        attempt_supercell=False,
    )


def near_duplicate_matcher() -> StructureMatcher:
    return StructureMatcher(
        ltol=0.2,
        stol=0.3,
        angle_tol=5.0,
        primitive_cell=True,
        scale=True,
        attempt_supercell=False,
    )


def strict_structure_equivalent(
    first: Structure | Atoms,
    second: Structure | Atoms,
) -> bool:
    left = as_pymatgen_structure(first)
    right = as_pymatgen_structure(second)
    if _composition_key(left) != _composition_key(right):
        return False
    if len(left) != len(right):
        return False
    return bool(strict_structure_matcher().fit(left, right))


def near_duplicate_structure(
    first: Structure | Atoms,
    second: Structure | Atoms,
) -> bool:
    left = as_pymatgen_structure(first)
    right = as_pymatgen_structure(second)
    if _composition_key(left) != _composition_key(right):
        return False
    return bool(near_duplicate_matcher().fit(left, right))


def _git_blob_sha1(path: Path) -> str:
    payload = path.read_bytes()
    header = b"blob " + str(len(payload)).encode() + b"\0"
    return hashlib.sha1(header + payload).hexdigest()  # noqa: S324 - Git identity


def _require_frozen_prototype_versions() -> None:
    try:
        observed = version("moyopy")
    except PackageNotFoundError as exc:
        raise RuntimeError(
            "Prototype-group execution requires moyopy==0.3.4 and the pinned "
            "Matbench Discovery source checkout."
        ) from exc
    if observed != MOYOPY_VERSION:
        raise RuntimeError(
            f"moyopy version drift: expected={MOYOPY_VERSION} observed={observed}"
        )


def _verify_frozen_prototype_dir(module_dir: Path) -> list[str]:
    errors: list[str] = []
    for name, expected_sha in MATBENCH_DISCOVERY_BLOBS.items():
        path = module_dir / name
        if not path.is_file():
            errors.append(f"missing {path}")
            continue
        observed_sha = _git_blob_sha1(path)
        if observed_sha != expected_sha:
            errors.append(
                f"blob drift file={name} expected={expected_sha} observed={observed_sha}"
            )
    return errors


def _resolve_frozen_prototype_dir() -> Path:
    explicit = os.environ.get(MATBENCH_PROTOCOL_SOURCE_ENV)
    if explicit:
        module_dir = Path(explicit).expanduser().resolve()
        errors = _verify_frozen_prototype_dir(module_dir)
        if errors:
            raise RuntimeError(
                "invalid frozen Matbench source checkout from "
                f"{MATBENCH_PROTOCOL_SOURCE_ENV}: " + "; ".join(errors)
            )
        return module_dir

    raise RuntimeError(
        "prototype-group execution requires the exact Matbench Discovery source "
        f"checkout at commit {MATBENCH_DISCOVERY_PROTOCOL_COMMIT}; set "
        f"{MATBENCH_PROTOCOL_SOURCE_ENV} to its matbench_discovery/structure "
        "directory. The files are then verified by frozen Git blob SHA."
    )


@lru_cache(maxsize=1)
def _load_frozen_prototype_module() -> ModuleType:
    _require_frozen_prototype_versions()
    module_dir = _resolve_frozen_prototype_dir()

    module_path = module_dir / "prototype.py"
    spec = importlib.util.spec_from_file_location(
        "_rhombus_frozen_matbench_prototype",
        module_path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load frozen Matbench prototype module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def matbench_prototype_group(structure: Structure | Atoms) -> str:
    """Execute the frozen Matbench Discovery prototype-label protocol."""

    module = _load_frozen_prototype_module()
    label = module.get_protostructure_label(
        as_pymatgen_structure(structure),
        symprec=0.1,
        raise_errors=True,
    )
    if not label:
        raise ValueError("prototype-group executor returned an empty label")
    return str(label)
