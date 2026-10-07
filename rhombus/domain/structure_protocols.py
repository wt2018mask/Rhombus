"""Frozen structure-comparison executors for Rhombus Phase 3."""

from __future__ import annotations

from hashlib import sha256
import json
from importlib.metadata import PackageNotFoundError, version

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


def _require_frozen_prototype_runtime() -> None:
    required = {
        "matbench-discovery": MATBENCH_DISCOVERY_VERSION,
        "moyopy": MOYOPY_VERSION,
    }
    for package, expected in required.items():
        try:
            observed = version(package)
        except PackageNotFoundError as exc:
            raise RuntimeError(
                "Prototype-group execution requires the Phase 3 audit extra: "
                "pip install 'rhombus[phase3-audit]'"
            ) from exc
        if observed != expected:
            raise RuntimeError(
                f"{package} version drift: expected={expected} observed={observed}"
            )


def matbench_prototype_group(structure: Structure | Atoms) -> str:
    """Execute the frozen Matbench Discovery prototype-label protocol."""

    _require_frozen_prototype_runtime()
    from matbench_discovery.structure.prototype import get_protostructure_label

    label = get_protostructure_label(
        as_pymatgen_structure(structure),
        symprec=0.1,
        raise_errors=True,
    )
    if not label:
        raise ValueError("prototype-group executor returned an empty label")
    return str(label)
