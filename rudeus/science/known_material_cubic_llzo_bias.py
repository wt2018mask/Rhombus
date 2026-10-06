"""Quantitative representation-bias assessment for the cubic Al-LLZO ensemble."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from rudeus.science.contracts import Record, require_hash
from rudeus.science.known_material_cubic_llzo_ordered import (
    build_cubic_llzo_ordered_structures,
    ordered_structure_hash,
)
from rudeus.science.known_material_occupancy_ensemble import (
    nearest_equal_weight_ensemble_average,
)
from rudeus.science.known_material_occupancy_integrality import OccupancySiteConstraint


CUBIC_LLZO_BIAS_ASSESSMENT_VERSION = "known-material-cubic-llzo-bias-assessment-v1"


@dataclass(frozen=True, kw_only=True)
class CubicLlzoBiasAssessment(Record):
    assessment_version: str
    source_artifact_hash: str
    realization_hashes: tuple[str, ...]
    formula_units_total: int
    ensemble_formula_li: str
    ensemble_formula_al: str
    formula_li_absolute_error: str
    formula_al_absolute_error: str
    max_site_occupancy_absolute_error: str
    member_atom_count_min: int
    member_atom_count_max: int

    def validate(self):
        super().validate()
        if self.assessment_version != CUBIC_LLZO_BIAS_ASSESSMENT_VERSION:
            raise ValueError("unsupported cubic LLZO bias-assessment version")
        require_hash(self.source_artifact_hash)
        if len(self.realization_hashes) != 16:
            raise ValueError("cubic LLZO bias assessment requires 16 realizations")
        if len(set(self.realization_hashes)) != 16:
            raise ValueError("cubic LLZO bias assessment requires unique realizations")
        for digest in self.realization_hashes:
            require_hash(digest)
        if self.formula_units_total != 256:
            raise ValueError("16 two-cell realizations must contain 256 formula units")
        if self.member_atom_count_min <= 0 or self.member_atom_count_max < self.member_atom_count_min:
            raise ValueError("invalid member atom-count range")


def assess_cubic_llzo_ensemble_bias(
    cif_path: Path,
    *,
    source_artifact_hash: str,
) -> CubicLlzoBiasAssessment:
    require_hash(source_artifact_hash)
    structures = build_cubic_llzo_ordered_structures(cif_path)
    realization_hashes = tuple(ordered_structure_hash(item) for item in structures)

    li_total = Decimal("0")
    al_total = Decimal("0")
    atom_counts = []
    for structure in structures:
        amounts = structure.composition.get_el_amt_dict()
        li_total += Decimal(str(amounts["Li"]))
        al_total += Decimal(str(amounts["Al"]))
        atom_counts.append(len(structure))

    formula_units_total = 16 * 2 * 8
    ensemble_li = li_total / Decimal(formula_units_total)
    ensemble_al = al_total / Decimal(formula_units_total)

    constraints = (
        OccupancySiteConstraint(
            site_id="Li1", multiplicity=24, occupancy_decimal="0.54"
        ),
        OccupancySiteConstraint(
            site_id="Al1", multiplicity=24, occupancy_decimal="0.06530"
        ),
        OccupancySiteConstraint(
            site_id="Li2", multiplicity=96, occupancy_decimal="0.37"
        ),
    )
    approximations = tuple(
        nearest_equal_weight_ensemble_average(
            item, replicas_per_realization=2, realization_count=16
        )
        for item in constraints
    )
    max_site_error = max(
        Decimal(item.absolute_error) for item in approximations
    )

    return CubicLlzoBiasAssessment(
        assessment_version=CUBIC_LLZO_BIAS_ASSESSMENT_VERSION,
        source_artifact_hash=source_artifact_hash,
        realization_hashes=realization_hashes,
        formula_units_total=formula_units_total,
        ensemble_formula_li=format(ensemble_li, "f"),
        ensemble_formula_al=format(ensemble_al, "f"),
        formula_li_absolute_error=format(abs(ensemble_li - Decimal("6.060")), "f"),
        formula_al_absolute_error=format(abs(ensemble_al - Decimal("0.196")), "f"),
        max_site_occupancy_absolute_error=format(max_site_error, "f"),
        member_atom_count_min=min(atom_counts),
        member_atom_count_max=max(atom_counts),
    )
