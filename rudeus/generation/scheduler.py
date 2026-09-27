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


def _p0_rejection_class(candidate) -> Optional[str]:
    """Return a stable compact P0 rejection label for audit rows."""

    rej = candidate.metadata.get("p0_rejection") or {}

    neutrality_ok = rej.get("neutrality_ok")
    pauling_ok = rej.get("pauling_ok")
    geometry_ok = rej.get("geometry_ok")

    failed = []

    if neutrality_ok is False:
        failed.append("neutrality")
    if pauling_ok is False:
        failed.append("pauling")
    if geometry_ok is False:
        failed.append("geometry")

    if not failed:
        return None

    return "+".join(failed)


def audit_row_from_candidate(
    candidate,
    parent_chemical_family: str,
    operator_version: str,
    schedule_state: ScheduleState,
    p1_eligible: bool,
) -> GenerationAuditRow:
    """Build a lossless pre-P1 audit row from a generated candidate."""

    meta = candidate.metadata

    operators = meta.get("operators") or [{}]
    op = operators[0]

    p0_details = meta.get("p0_details") or {}

    return GenerationAuditRow(
        parent_id=str(meta.get("parent_id", "unknown")),
        parent_chemical_family=parent_chemical_family,
        operator_name=str(op.get("operator", "unknown")),
        operator_version=operator_version,
        schedule_state=schedule_state,
        child_material_id=candidate.material_id,
        child_index=int(meta.get("child_index", -1)),
        seed=int(meta.get("seed", 0)),
        generation_config_hash=str(
            meta.get("generation_config_hash") or ""
        ),
        operator_error=meta.get("operator_error"),
        p0_state=candidate.existence_state.value,
        p0_neutrality_ok=p0_details.get("neutrality_ok"),
        p0_pauling_ok=p0_details.get("pauling_ok"),
        p0_geometry_ok=p0_details.get("geometry_ok"),
        p0_rejection_class=_p0_rejection_class(candidate),
        novelty_tag=str(meta.get("novelty_tag", "unknown")),
        novelty_matched=meta.get("novelty_matched"),
        p1_eligible=bool(p1_eligible),
    )
