"""Diagnostic amendment candidate for cubic Al-LLZO execution representation.

This records the B5-discovered constraint-aware ordered realizations without
mutating the persisted B4 representation evidence. It is the bridge required
before any canonical evidence/hash amendment.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from pymatgen.core import Structure
from pymatgen.io.cif import CifParser

from rudeus.science.contracts import Record
from rudeus.science.known_material_b4_execution_structure import (
    EXECUTION_STRUCTURE_BINDING_VERSION,
    ExecutionStructureBinding,
    ExecutionStructureComponent,
)
from rudeus.science.known_material_cubic_llzo_coordinates import (
    extract_cubic_llzo_two_cell_coordinate_pools,
)
from rudeus.science.known_material_cubic_llzo_joint_feasibility import (
    DIAGNOSTIC_VERSION as JOINT_DIAGNOSTIC_VERSION,
    build_joint_occupancy_feasibility_diagnostics,
)
from rudeus.science.known_material_cubic_llzo_ordered import ordered_structure_hash
from rudeus.science.known_material_cubic_llzo_weighted_ensemble import (
    build_exact_weighted_cubic_llzo_count_patterns,
)


AMENDMENT_CANDIDATE_VERSION = "known-material-cubic-llzo-representation-amendment-candidate-v1"
WEIGHTING_ASSUMPTION = "independent-marginal-product-no-source-correlation-claim-v1"
CONSTRAINT_SCOPE = (
    "EXECUTION_GEOMETRY_EXCLUSIONS_ONLY_NO_SOURCE_CONFIGURATIONAL_CORRELATION_CLAIM"
)


@dataclass(frozen=True, kw_only=True)
class CubicLlzoRepresentationAmendmentCandidate(Record):
    amendment_version: str
    source_artifact_hash: str
    joint_diagnostic_version: str
    weighting_assumption: str
    constraint_scope: str
    old_binding_hash: str
    candidate_binding: ExecutionStructureBinding
    candidate_component_hashes: tuple[str, ...]
    all_geometry_ok: bool
    canonical_evidence_mutated: bool

    def validate(self):
        super().validate()
        if self.amendment_version != AMENDMENT_CANDIDATE_VERSION:
            raise ValueError("unsupported representation amendment candidate version")
        if self.joint_diagnostic_version != JOINT_DIAGNOSTIC_VERSION:
            raise ValueError("amendment candidate must bind current joint diagnostic")
        if self.constraint_scope != CONSTRAINT_SCOPE:
            raise ValueError("unexpected constraint scope")
        if len(self.candidate_component_hashes) != 8:
            raise ValueError("amendment candidate requires eight components")
        if len(set(self.candidate_component_hashes)) != 8:
            raise ValueError("candidate component hashes must be unique")
        if self.all_geometry_ok is not True:
            raise ValueError("amendment candidate requires geometry-clean members")
        if self.canonical_evidence_mutated is not False:
            raise ValueError("candidate stage must not mutate canonical evidence")


def _host_sites(structure: Structure):
    hosts = []
    for site in structure:
        if site.is_ordered and site.specie.symbol in {"La", "Zr", "O"}:
            hosts.append((site.specie.symbol, tuple(float(v) % 1.0 for v in site.frac_coords)))
    return tuple(sorted(hosts, key=lambda x: (x[0], x[1])))


def _coord(values):
    return tuple(float(v) for v in values)


def _materialize_candidate_structures(cif_path: Path):
    parsed = CifParser(str(cif_path)).parse_structures(primitive=False)
    if len(parsed) != 1:
        raise ValueError("cubic LLZO CIF must contain exactly one structure")
    source = parsed[0]
    source.make_supercell([2, 1, 1])
    hosts = _host_sites(source)
    shared_pool, li2_pool = extract_cubic_llzo_two_cell_coordinate_pools(cif_path)

    rows = build_joint_occupancy_feasibility_diagnostics(cif_path)
    patterns = build_exact_weighted_cubic_llzo_count_patterns()
    if len(rows) != len(patterns):
        raise ValueError("joint diagnostic/member-count mismatch")

    result = []
    for row, pattern in zip(rows, patterns):
        if not row.constructive_assignment_found or row.geometry_ok is not True:
            raise ValueError("joint diagnostic has no geometry-clean constructive assignment")
        species = [symbol for symbol, _ in hosts]
        coords = [coord for _, coord in hosts]
        for index in row.li1_indices:
            species.append("Li")
            coords.append(_coord(shared_pool.fractional_coordinates[index]))
        for index in row.al1_indices:
            species.append("Al")
            coords.append(_coord(shared_pool.fractional_coordinates[index]))
        for index in row.li2_indices:
            species.append("Li")
            coords.append(_coord(li2_pool.fractional_coordinates[index]))
        structure = Structure(
            lattice=source.lattice,
            species=species,
            coords=coords,
            coords_are_cartesian=False,
            to_unit_cell=True,
        )
        result.append((row, pattern, structure))
    return tuple(result)


def build_cubic_llzo_representation_amendment_candidate(
    cif_path: Path,
    *,
    source_artifact_hash: str,
    old_binding_hash: str,
) -> CubicLlzoRepresentationAmendmentCandidate:
    materialized = _materialize_candidate_structures(cif_path)
    components = []
    hashes = []
    for row, pattern, structure in materialized:
        structure_hash = ordered_structure_hash(structure)
        hashes.append(structure_hash)
        components.append(
            ExecutionStructureComponent(
                label=f"member-{row.member_index:02d}",
                structure_hash=structure_hash,
                weight_numerator=pattern.weight_numerator,
                weight_denominator=pattern.weight_denominator,
            )
        )
    binding = ExecutionStructureBinding(
        binding_version=EXECUTION_STRUCTURE_BINDING_VERSION,
        mode="ENSEMBLE",
        components=tuple(components),
        weighting_assumption=WEIGHTING_ASSUMPTION,
    )
    candidate = CubicLlzoRepresentationAmendmentCandidate(
        amendment_version=AMENDMENT_CANDIDATE_VERSION,
        source_artifact_hash=source_artifact_hash,
        joint_diagnostic_version=JOINT_DIAGNOSTIC_VERSION,
        weighting_assumption=WEIGHTING_ASSUMPTION,
        constraint_scope=CONSTRAINT_SCOPE,
        old_binding_hash=old_binding_hash,
        candidate_binding=binding,
        candidate_component_hashes=tuple(hashes),
        all_geometry_ok=all(row.geometry_ok is True for row, _, _ in materialized),
        canonical_evidence_mutated=False,
    )
    candidate.validate()
    if sum(
        Fraction(c.weight_numerator, c.weight_denominator)
        for c in candidate.candidate_binding.components
    ) != 1:
        raise ValueError("candidate weights must sum exactly to one")
    return candidate
