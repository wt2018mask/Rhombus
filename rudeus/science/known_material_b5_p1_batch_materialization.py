"""Materialize B5 known-material P1 plans into legacy-compatible stateless batches.

The output records are directly consumable by rudeus.mlip.sharding.run_batches.
No P1 calculation is performed here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from rudeus.mlip.sharding import BATCH_ID_SCHEME_V2, make_batch_id, structure_dict_sha256
from rudeus.science.contracts import Record, require_hash
from rudeus.science.known_material_b5_p1_execution_plan import (
    B5P1ExecutionPlan,
    B5P1ExecutionUnit,
)


B5_P1_BATCH_MATERIALIZATION_VERSION = "known-material-b5-p1-batch-materialization-v1"
B5_P1_BATCH_SEED = 0


@dataclass(frozen=True, kw_only=True)
class B5P1PendingBatch(Record):
    materialization_version: str
    batch_id_scheme: str
    batch_id: str
    child_index: int
    seed: int
    parent_id: str
    child_material_id: str
    generation_config_hash: str
    checkpoint_id: str
    structure_sha256: str
    structure_dict: Mapping[str, Any]
    material_key: str
    component_label: str
    representation_mode: str
    source_execution_plan_hash: str
    source_execution_unit_hash: str
    source_b5_structure_unit_hash: str
    input_structure_hash: str
    source_path: str
    mlip_protocol: Mapping[str, Any]
    p0_state: str
    split: str

    def validate(self):
        super().validate()
        if self.materialization_version != B5_P1_BATCH_MATERIALIZATION_VERSION:
            raise ValueError("unsupported B5 P1 batch materialization version")
        if self.batch_id_scheme != BATCH_ID_SCHEME_V2:
            raise ValueError("B5 P1 batch must use v2 structure-bound identity")
        if len(self.batch_id) != 16 or any(c not in "0123456789abcdef" for c in self.batch_id):
            raise ValueError("invalid B5 P1 batch id")
        if self.child_index < 0 or self.seed != B5_P1_BATCH_SEED:
            raise ValueError("invalid deterministic B5 P1 batch index/seed")
        for value in (
            self.generation_config_hash,
            self.structure_sha256,
            self.source_execution_plan_hash,
            self.source_execution_unit_hash,
            self.source_b5_structure_unit_hash,
            self.input_structure_hash,
        ):
            require_hash(value)
        if structure_dict_sha256(dict(self.structure_dict)) != self.structure_sha256:
            raise ValueError("B5 P1 pending batch structure hash mismatch")
        if self.p0_state != "PLAUSIBLE":
            raise ValueError("only P0 PLAUSIBLE material units may enter P1 batch materialization")
        if self.split != "DEV":
            raise ValueError("B5 P1 pending batches may contain DEV only")


def _parent_id(unit: B5P1ExecutionUnit) -> str:
    return f"known-material-b5:{unit.material_key}:{unit.component_label}"


def _child_material_id(unit: B5P1ExecutionUnit) -> str:
    return f"known-material-b5-p1:{unit.material_key}:{unit.component_label}"


def materialize_b5_p1_pending_batches(
    plan: B5P1ExecutionPlan,
    *,
    structures_by_execution_unit_hash: Mapping[str, Mapping[str, Any]],
) -> tuple[B5P1PendingBatch, ...]:
    """Create deterministic run_batches-compatible records for all planned units."""
    result = []
    for child_index, unit in enumerate(plan.units):
        try:
            structure_dict = dict(structures_by_execution_unit_hash[unit.content_hash])
        except KeyError as exc:
            raise ValueError("P1 execution unit lacks materialized structure") from exc
        struct_sha = structure_dict_sha256(structure_dict)
        parent_id = _parent_id(unit)
        batch_id = make_batch_id(
            parent_id,
            child_index,
            B5_P1_BATCH_SEED,
            plan.content_hash,
            unit.checkpoint_id,
            structure_dict,
        )
        record = B5P1PendingBatch(
            materialization_version=B5_P1_BATCH_MATERIALIZATION_VERSION,
            batch_id_scheme=BATCH_ID_SCHEME_V2,
            batch_id=batch_id,
            child_index=child_index,
            seed=B5_P1_BATCH_SEED,
            parent_id=parent_id,
            child_material_id=_child_material_id(unit),
            generation_config_hash=plan.content_hash,
            checkpoint_id=unit.checkpoint_id,
            structure_sha256=struct_sha,
            structure_dict=structure_dict,
            material_key=unit.material_key,
            component_label=unit.component_label,
            representation_mode=unit.representation_mode,
            source_execution_plan_hash=plan.content_hash,
            source_execution_unit_hash=unit.content_hash,
            source_b5_structure_unit_hash=unit.source_b5_structure_unit_hash,
            input_structure_hash=unit.input_structure_hash,
            source_path=unit.source_path,
            mlip_protocol={
                "checkpoint_id": unit.checkpoint_id,
                "checkpoint_sha256": unit.checkpoint_sha256,
                "checkpoint_url": unit.checkpoint_url,
                "force_tol_ev_A": unit.force_tol_ev_A,
                "max_relax_steps": unit.max_relax_steps,
                "precision": unit.precision,
            },
            p0_state="PLAUSIBLE",
            split="DEV",
        )
        record.validate()
        result.append(record)
    return tuple(result)
