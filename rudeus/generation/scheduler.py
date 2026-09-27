"""Candidate-supply-v2 scheduling and lossless pre-P1 audit records.

These records belong to the G stage only.  They are deliberately separate from
CandidateMaterial and from the core existence/dynamic/transport state machines.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, Optional


class ScheduleState(str, Enum):
    """Outcome of one parent x operator-version scheduling decision."""

    SCHEDULED = "SCHEDULED"
    INAPPLICABLE = "INAPPLICABLE"
    DISABLED_BY_POLICY = "DISABLED_BY_POLICY"
    DEFERRED_PENDING_DESIGN = "DEFERRED_PENDING_DESIGN"


@dataclass(frozen=True)
class GenerationScheduleRecord:
    """Lossless record of one parent x operator-version scheduling decision."""

    parent_id: str
    parent_chemical_family: str
    operator_name: str
    operator_version: str
    schedule_state: ScheduleState
    reason: str
    seed: int
    generation_config_hash: str
    child_material_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["schedule_state"] = self.schedule_state.value
        return data


@dataclass(frozen=True)
class GenerationAuditRow:
    """Per-generated-child diagnostic row retained before P1 filtering."""

    parent_id: str
    parent_chemical_family: str
    operator_name: str
    operator_version: str
    schedule_state: ScheduleState
    child_material_id: str
    child_index: int
    seed: int
    generation_config_hash: str
    operator_error: Optional[str]
    p0_state: str
    p0_neutrality_ok: Optional[bool]
    p0_pauling_ok: Optional[bool]
    p0_geometry_ok: Optional[bool]
    p0_rejection_class: Optional[str]
    novelty_tag: str
    novelty_matched: Optional[str]
    p1_eligible: bool

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["schedule_state"] = self.schedule_state.value
        return data


def schedule_candidate_supply_v2(
    parent_id: str,
    parent_chemical_family: str,
    seed: int,
    generation_config_hash: str,
):
    """Return the explicit candidate-supply-v2 scheduling decisions.

    This function schedules policy only. It does not generate structures,
    invoke operators, run P0, or authorize P1 work.
    """

    policy = (
        (
            "displace",
            "legacy-v1",
            ScheduleState.SCHEDULED,
            "bounded composition-preserving baseline",
        ),
        (
            "strain",
            "legacy-v1",
            ScheduleState.DEFERRED_PENDING_DESIGN,
            "novelty regime not yet justified for v2 activation",
        ),
        (
            "vacancy",
            "legacy-v1",
            ScheduleState.DISABLED_BY_POLICY,
            "legacy uncompensated Li vacancy is not active v2 supply",
        ),
        (
            "interstitial",
            "legacy-v1",
            ScheduleState.DISABLED_BY_POLICY,
            "legacy uncompensated Li interstitial is not active v2 supply",
        ),
        (
            "substitute",
            "legacy-v1",
            ScheduleState.DEFERRED_PENDING_DESIGN,
            "neutrality-aware substitution semantics not yet implemented",
        ),
    )

    return [
        GenerationScheduleRecord(
            parent_id=parent_id,
            parent_chemical_family=parent_chemical_family,
            operator_name=operator_name,
            operator_version=operator_version,
            schedule_state=schedule_state,
            reason=reason,
            seed=seed,
            generation_config_hash=generation_config_hash,
            child_material_id=None,
        )
        for (
            operator_name,
            operator_version,
            schedule_state,
            reason,
        ) in policy
    ]
