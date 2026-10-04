"""Binding of certified Candidate Supply runtime-plan rows to generic tasks."""
from __future__ import annotations

import copy
import hashlib
from collections.abc import Mapping

from rudeus.execution.backend import TaskBundle
from rudeus.execution.code_bundle import CodeBundle, verify_bundle
from rudeus.execution.contracts import TaskSpec
from rudeus.science.contracts import canonical_bytes, digest, require_hash


PLAN_SCHEMA = "candidate-supply-v2-scheduler-runtime-plan-v1"


def bind_candidate_supply_work_item(
    runtime_plan,
    work_item,
    code_bundle,
    *,
    git_root,
    resource_requirements=None,
):
    """Return existing TaskSpec/TaskBundle records without executing the row.

    Scientific operator inputs define task identity. Runtime-plan and
    allocation lineage remain in provenance and the retained plan inventory.
    Backend choice and budgets remain outside TaskSpec scientific identity.
    """
    if runtime_plan.get("schema_version") != PLAN_SCHEMA:
        raise ValueError("unsupported Candidate Supply runtime-plan schema")
    if runtime_plan.get("execution_performed") is not False:
        raise ValueError("runtime plan must be non-executing input")
    plan_content = dict(runtime_plan)
    plan_identity = plan_content.pop("manifest_identity", None)
    if not isinstance(plan_identity, str) or digest(plan_content) != plan_identity:
        raise ValueError("runtime-plan manifest identity mismatch")
    matches = [row for row in runtime_plan.get("work_items", ())
               if row.get("work_item_id") == work_item.get("work_item_id")]
    if len(matches) != 1 or matches[0] != work_item:
        raise ValueError("work item is absent, ambiguous, or differs from certified plan")
    if not isinstance(code_bundle, CodeBundle):
        code_bundle = CodeBundle.from_dict(code_bundle)
    operator = work_item.get("operator_identity")
    parent = work_item.get("parent_id")
    lane = work_item.get("lane")
    allocation_id = work_item.get("allocation_unit_id")
    if not all((isinstance(parent, str) and parent, isinstance(lane, str) and lane,
                isinstance(allocation_id, str) and allocation_id, isinstance(operator, Mapping))):
        raise ValueError("runtime work-item scientific identity is incomplete")
    cohort_hash = runtime_plan["parent_cohort_identity"]["canonical_content_sha256"]
    require_hash(cohort_hash)
    plan_bytes = canonical_bytes(runtime_plan)
    plan_artifact_identity = digest(runtime_plan)
    protocol_hash = digest({
        "protocol": "candidate-supply-v2-work-item",
        "generation_config_hash": runtime_plan["generation_config_hash"],
        "operator_identity": operator,
    })
    scientific_inputs = {
        "operator_identity": copy.deepcopy(dict(operator)),
    }
    task_provenance = {
        "runtime_plan_schema": PLAN_SCHEMA,
        "runtime_plan_identity": plan_identity,
        "runtime_plan_artifact_identity": plan_artifact_identity,
        "parent_cohort_identity": copy.deepcopy(runtime_plan["parent_cohort_identity"]),
        "work_item": copy.deepcopy(work_item),
    }
    task = TaskSpec(
        candidate_id=parent,
        stage="CANDIDATE_SUPPLY_V2_WORK_ITEM",
        protocol_hash=protocol_hash,
        config=scientific_inputs,
        input_artifact_hashes=(cohort_hash,),
        dependencies=(),
        code_revision=code_bundle.code_revision,
        code_bundle_hash=code_bundle.bundle_hash,
        resource_requirements=resource_requirements or {},
        expected_outputs=("candidate_material",),
        retry_policy={"policy": "new-attempt-per-retry"},
        seed=work_item["seed"],
        provenance=task_provenance,
    )
    verify_bundle(code_bundle, code_bundle.bundle_hash, task, git_root=git_root)
    raw_hash = hashlib.sha256(plan_bytes).hexdigest()
    bundle = TaskBundle(
        task=task.to_dict(),
        task_content_hash=task.content_hash,
        code_bundle=code_bundle.to_dict(),
        bundle_hash=code_bundle.bundle_hash,
        retained_files=({
            "relative_path": f"blobs/{plan_artifact_identity}",
            "raw_sha256": raw_hash,
            "size_bytes": len(plan_bytes),
        },),
    )
    return task, bundle
