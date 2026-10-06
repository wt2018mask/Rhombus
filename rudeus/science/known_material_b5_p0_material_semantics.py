"""Representation-aware material-level aggregation for B5 raw P0 observations.

Raw unit observations are preserved exactly. Aggregation distinguishes a
scientifically applicable failed check from a check whose model domain is not
authoritative for the representation. Unsupported checks can make a material
INDETERMINATE, but can never be promoted to PLAUSIBLE.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Sequence

from rudeus.science.contracts import Record
from rudeus.science.known_material_b5_p0 import (
    B5P0UnitExecutionStatus,
    B5P0UnitObservation,
)


B5_P0_MATERIAL_SEMANTICS_VERSION = "known-material-b5-p0-material-semantics-v1"


class MaterialP0Disposition(str, Enum):
    PLAUSIBLE = "PLAUSIBLE"
    FAIL = "FAIL"
    INDETERMINATE = "INDETERMINATE"


CHECK_FIELDS = {
    "neutrality": "neutrality_ok",
    "pauling": "pauling_ok",
    "geometry": "geometry_ok",
}


@dataclass(frozen=True, kw_only=True)
class B5P0MaterialAssessment(Record):
    semantics_version: str
    material_key: str
    representation_mode: str
    component_count: int
    disposition: str
    applicable_failed_checks: tuple[str, ...]
    unsupported_checks: tuple[str, ...]
    unresolved_checks: tuple[str, ...]
    execution_error_count: int
    source_observation_hashes: tuple[str, ...]
    qualification_evidence_authorized: bool = False
    production_search_authorized: bool = False

    def validate(self):
        super().validate()
        if self.semantics_version != B5_P0_MATERIAL_SEMANTICS_VERSION:
            raise ValueError("unsupported B5 P0 material semantics version")
        MaterialP0Disposition(self.disposition)
        if self.component_count <= 0:
            raise ValueError("material assessment requires components")
        if self.execution_error_count < 0 or self.execution_error_count > self.component_count:
            raise ValueError("invalid execution error count")
        if len(self.source_observation_hashes) != self.component_count:
            raise ValueError("assessment must bind every source observation")
        known = set(CHECK_FIELDS)
        if (
            set(self.applicable_failed_checks)
            | set(self.unsupported_checks)
            | set(self.unresolved_checks)
        ) - known:
            raise ValueError("assessment contains unknown P0 check")
        if set(self.applicable_failed_checks) & set(self.unsupported_checks):
            raise ValueError("a check cannot be both applicable-failed and unsupported")
        if self.qualification_evidence_authorized or self.production_search_authorized:
            raise ValueError("B5 DEV P0 aggregation authorizes no qualification or production")


def aggregate_material_p0(
    observations: Sequence[B5P0UnitObservation],
    *,
    unsupported_checks: Sequence[str] = (),
) -> B5P0MaterialAssessment:
    """Aggregate one material without converting unsupported evidence into PASS."""
    items = tuple(observations)
    if not items:
        raise ValueError("material aggregation requires observations")
    material_keys = {item.material_key for item in items}
    modes = {item.representation_mode for item in items}
    if len(material_keys) != 1 or len(modes) != 1:
        raise ValueError("material aggregation cannot mix identities or representations")

    unsupported = tuple(sorted(set(unsupported_checks)))
    unknown_unsupported = set(unsupported) - set(CHECK_FIELDS)
    if unknown_unsupported:
        raise ValueError("unsupported_checks contains unknown check")

    errors = sum(
        item.execution_status == B5P0UnitExecutionStatus.ERROR.value
        for item in items
    )
    applicable_failed = set()
    unresolved = set()

    for check, field in CHECK_FIELDS.items():
        values = [
            getattr(item, field)
            for item in items
            if item.execution_status == B5P0UnitExecutionStatus.COMPLETED.value
        ]
        if check in unsupported:
            continue
        if any(value is False for value in values):
            applicable_failed.add(check)
        if errors or not values or any(value is None for value in values):
            unresolved.add(check)

    if errors or unresolved:
        disposition = MaterialP0Disposition.INDETERMINATE
    elif applicable_failed:
        disposition = MaterialP0Disposition.FAIL
    elif unsupported:
        # A required P0 dimension is explicitly non-authoritative for this
        # representation. Absence of an applicable failure is not enough to PASS.
        disposition = MaterialP0Disposition.INDETERMINATE
    else:
        disposition = MaterialP0Disposition.PLAUSIBLE

    result = B5P0MaterialAssessment(
        semantics_version=B5_P0_MATERIAL_SEMANTICS_VERSION,
        material_key=next(iter(material_keys)),
        representation_mode=next(iter(modes)),
        component_count=len(items),
        disposition=disposition.value,
        applicable_failed_checks=tuple(sorted(applicable_failed)),
        unsupported_checks=unsupported,
        unresolved_checks=tuple(sorted(unresolved)),
        execution_error_count=errors,
        source_observation_hashes=tuple(item.content_hash for item in items),
        qualification_evidence_authorized=False,
        production_search_authorized=False,
    )
    result.validate()
    return result


def aggregate_b5_p0_materials(
    observations: Sequence[B5P0UnitObservation],
    *,
    unsupported_checks_by_material: Mapping[str, Sequence[str]] | None = None,
) -> tuple[B5P0MaterialAssessment, ...]:
    grouped = {}
    for item in observations:
        grouped.setdefault(item.material_key, []).append(item)
    unsupported_by_material = unsupported_checks_by_material or {}
    return tuple(
        aggregate_material_p0(
            sorted(grouped[material_key], key=lambda item: item.component_label),
            unsupported_checks=unsupported_by_material.get(material_key, ()),
        )
        for material_key in sorted(grouped)
    )
