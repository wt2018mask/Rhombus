"""Diagnostic semantics for P0 neutrality on weighted ensemble representations.

The exact-stoichiometry SMACT check is useful for candidate formulas, but an
individual ordered realization of a fractional-occupancy ensemble is not
automatically an authoritative chemical formula. This module classifies check
applicability without changing P0 verdicts.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from rudeus.science.contracts import Record


ENSEMBLE_NEUTRALITY_SEMANTICS_VERSION = "known-material-b5-ensemble-neutrality-semantics-v1"


class NeutralityApplicability(str, Enum):
    APPLICABLE = "APPLICABLE"
    MODEL_DOMAIN_UNSUPPORTED = "MODEL_DOMAIN_UNSUPPORTED"


@dataclass(frozen=True, kw_only=True)
class EnsembleNeutralitySemanticsDiagnostic(Record):
    diagnostic_version: str
    material_key: str
    representation_mode: str
    weighted_ensemble: bool
    source_marginals_only: bool
    member_count: int
    member_neutrality_false_count: int
    member_geometry_true_count: int
    member_pauling_true_count: int
    exact_member_neutrality_applicability: str
    material_verdict_authorized: bool
    rationale: tuple[str, ...]

    def validate(self):
        super().validate()
        if self.diagnostic_version != ENSEMBLE_NEUTRALITY_SEMANTICS_VERSION:
            raise ValueError("unsupported ensemble-neutrality semantics version")
        NeutralityApplicability(self.exact_member_neutrality_applicability)
        if self.member_count <= 0:
            raise ValueError("diagnostic requires members")
        for value in (
            self.member_neutrality_false_count,
            self.member_geometry_true_count,
            self.member_pauling_true_count,
        ):
            if value < 0 or value > self.member_count:
                raise ValueError("invalid member count")
        if self.material_verdict_authorized is not False:
            raise ValueError("diagnostic cannot authorize a material verdict")


def classify_exact_member_neutrality(
    *,
    material_key: str,
    representation_mode: str,
    member_neutrality: tuple[bool | None, ...],
    member_geometry: tuple[bool | None, ...],
    member_pauling: tuple[bool | None, ...],
    weighted_ensemble: bool,
    source_marginals_only: bool,
) -> EnsembleNeutralitySemanticsDiagnostic:
    """Classify whether exact member formulas are authoritative neutrality inputs."""
    if not material_key:
        raise ValueError("material_key is required")
    n = len(member_neutrality)
    if not n or len(member_geometry) != n or len(member_pauling) != n:
        raise ValueError("member result vectors must have equal nonzero length")

    unsupported = (
        representation_mode == "ENSEMBLE"
        and weighted_ensemble
        and source_marginals_only
    )
    disposition = (
        NeutralityApplicability.MODEL_DOMAIN_UNSUPPORTED
        if unsupported
        else NeutralityApplicability.APPLICABLE
    )
    rationale = (
        (
            "ordered members realize source-bound fractional occupancies under exact rational weights",
            "the source constrains marginal occupancies but does not define one exact integer-stoichiometry member formula",
            "therefore per-member exact-stoichiometry SMACT neutrality cannot by itself establish a material FAIL",
        )
        if unsupported
        else (
            "representation does not establish a weighted marginal-only ensemble exception",
            "ordinary exact-member neutrality semantics remain applicable",
        )
    )
    result = EnsembleNeutralitySemanticsDiagnostic(
        diagnostic_version=ENSEMBLE_NEUTRALITY_SEMANTICS_VERSION,
        material_key=material_key,
        representation_mode=representation_mode,
        weighted_ensemble=weighted_ensemble,
        source_marginals_only=source_marginals_only,
        member_count=n,
        member_neutrality_false_count=sum(value is False for value in member_neutrality),
        member_geometry_true_count=sum(value is True for value in member_geometry),
        member_pauling_true_count=sum(value is True for value in member_pauling),
        exact_member_neutrality_applicability=disposition.value,
        material_verdict_authorized=False,
        rationale=rationale,
    )
    result.validate()
    return result
