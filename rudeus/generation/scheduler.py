"""Candidate-supply-v2 scheduling and lossless pre-P1 audit records.

These records belong to the G stage only.  They are deliberately separate from
CandidateMaterial and from the core existence/dynamic/transport state machines.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional


class ScheduleState(str, Enum):
    """Outcome of one parent x operator-version scheduling decision."""

    SCHEDULED = "SCHEDULED"
    INAPPLICABLE = "INAPPLICABLE"
    DISABLED_BY_POLICY = "DISABLED_BY_POLICY"
    DEFERRED_PENDING_DESIGN = "DEFERRED_PENDING_DESIGN"
    BLOCKED_BY_PARENT_P0 = "BLOCKED_BY_PARENT_P0"


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


def _p1_eligible_for_candidate_supply_v2(candidate) -> bool:
    """Mirror the existing make_batches P1 eligibility rule locally."""

    if candidate.metadata.get("novelty_tag") != "novel":
        return False
    if candidate.existence_state.value == "PLAUSIBLE":
        return True
    rejection = candidate.metadata.get("p0_rejection") or {}
    return (
        candidate.existence_state.value == "FAIL"
        and rejection.get("neutrality_ok") is True
    )


def execute_candidate_supply_v2_for_parent(
    parent,
    *,
    seed: int,
    generation_config_hash: str,
    matcher=None,
    allowed_swaps=None,
    displacement_sigma_A_provisional: float = 0.05,
    strain_max_fraction_provisional: float = 0.02,
    mobile_ion: str = "Li",
    defect_modes=("vacancy", "interstitial"),
    matcher_ltol_provisional: float = 0.2,
    matcher_stol_provisional: float = 0.3,
    matcher_angle_tol_provisional: float = 5.0,
):
    """Execute the currently scheduled candidate-supply-v2 work for one parent."""

    from rudeus.generation.generator import generate_children

    schedule_records = schedule_candidate_supply_v2(
        parent_id=parent.parent_id,
        parent_chemical_family=parent.chemical_family,
        seed=seed,
        generation_config_hash=generation_config_hash,
    )

    from rudeus.filters.p0 import evaluate_p0

    if parent.structure is not None:
        parent_p0 = evaluate_p0(
            str(parent.structure.composition.reduced_formula),
            structure=parent.structure,
        )
        if parent_p0.neutrality_ok is False:
            displace_index = next(
                index
                for index, record in enumerate(schedule_records)
                if record.operator_name == "displace"
            )
            schedule_records[displace_index] = replace(
                schedule_records[displace_index],
                schedule_state=ScheduleState.BLOCKED_BY_PARENT_P0,
                reason="parent P0 neutrality blocks execution",
            )
            return schedule_records, [], []

    children = generate_children(
        parent,
        operators=["displace"],
        children_per_parent=1,
        seed=seed,
        matcher=matcher,
        allowed_swaps=allowed_swaps,
        displacement_sigma_A_provisional=displacement_sigma_A_provisional,
        strain_max_fraction_provisional=strain_max_fraction_provisional,
        mobile_ion=mobile_ion,
        defect_modes=defect_modes,
        matcher_ltol_provisional=matcher_ltol_provisional,
        matcher_stol_provisional=matcher_stol_provisional,
        matcher_angle_tol_provisional=matcher_angle_tol_provisional,
        generation_config_hash=generation_config_hash,
    )

    audit_rows = []
    if children:
        child = children[0]
        scheduled_index = next(
            index
            for index, record in enumerate(schedule_records)
            if record.schedule_state is ScheduleState.SCHEDULED
        )
        schedule_records[scheduled_index] = replace(
            schedule_records[scheduled_index],
            child_material_id=child.material_id,
        )
        audit_rows.append(
            audit_row_from_candidate(
                candidate=child,
                parent_chemical_family=parent.chemical_family,
                operator_version=schedule_records[scheduled_index].operator_version,
                schedule_state=ScheduleState.SCHEDULED,
                p1_eligible=_p1_eligible_for_candidate_supply_v2(child),
            )
        )

    return schedule_records, audit_rows, children


def execute_candidate_supply_v2_cohort(
    parents,
    *,
    base_seed: int,
    generation_config_hash: str,
    matcher=None,
    allowed_swaps=None,
    displacement_sigma_A_provisional: float = 0.05,
    strain_max_fraction_provisional: float = 0.02,
    mobile_ion: str = "Li",
    defect_modes=("vacancy", "interstitial"),
    matcher_ltol_provisional: float = 0.2,
    matcher_stol_provisional: float = 0.3,
    matcher_angle_tol_provisional: float = 5.0,
):
    """Execute candidate-supply-v2 for parents in caller-supplied order."""

    schedule_records = []
    audit_rows = []
    children = []

    for parent_index, parent in enumerate(parents):
        seed = base_seed + parent_index
        if getattr(parent, "perturbable", False) and parent.structure is not None:
            parent_records, parent_rows, parent_children = (
                execute_candidate_supply_v2_for_parent(
                    parent,
                    seed=seed,
                    generation_config_hash=generation_config_hash,
                    matcher=matcher,
                    allowed_swaps=allowed_swaps,
                    displacement_sigma_A_provisional=(
                        displacement_sigma_A_provisional
                    ),
                    strain_max_fraction_provisional=(
                        strain_max_fraction_provisional
                    ),
                    mobile_ion=mobile_ion,
                    defect_modes=defect_modes,
                    matcher_ltol_provisional=matcher_ltol_provisional,
                    matcher_stol_provisional=matcher_stol_provisional,
                    matcher_angle_tol_provisional=matcher_angle_tol_provisional,
                )
            )
        else:
            parent_records = schedule_candidate_supply_v2(
                parent_id=parent.parent_id,
                parent_chemical_family=parent.chemical_family,
                seed=seed,
                generation_config_hash=generation_config_hash,
            )
            displace_index = next(
                index
                for index, record in enumerate(parent_records)
                if record.operator_name == "displace"
            )
            parent_records[displace_index] = replace(
                parent_records[displace_index],
                schedule_state=ScheduleState.INAPPLICABLE,
                reason="parent is not perturbable or has no structure",
            )
            parent_rows = []
            parent_children = []

        schedule_records.extend(parent_records)
        audit_rows.extend(parent_rows)
        children.extend(parent_children)

    payload = build_candidate_supply_v2_audit(
        schedule_records=schedule_records,
        child_rows=audit_rows,
    )
    return schedule_records, audit_rows, children, payload


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


def build_candidate_supply_v2_audit(*, schedule_records, child_rows):
    """Build a JSON-ready, lossless candidate-supply-v2 audit payload."""

    schedule_data = [record.to_dict() for record in schedule_records]
    child_data = [row.to_dict() for row in child_rows]

    return {
        "audit_version": "candidate-supply-v2-audit-v1",
        "schedule_records": schedule_data,
        "child_rows": child_data,
        "summary": {
            "schedule_records": len(schedule_data),
            "children_generated": len(child_data),
            "p1_eligible": sum(
                1 for row in child_data if row["p1_eligible"]
            ),
        },
    }


def write_candidate_supply_v2_audit(path, payload):
    """Atomically write a candidate-supply-v2 audit payload as UTF-8 JSON."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            json.dump(
                payload,
                temporary,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            temporary.write("\n")
            temporary.flush()
            os.fsync(temporary.fileno())

        os.replace(temporary_path, destination)
    except BaseException:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass
        raise
