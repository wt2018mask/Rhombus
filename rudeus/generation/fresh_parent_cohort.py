"""Pure, evidence-backed manifest construction for explicit fresh cohorts.

This module validates caller-supplied identities and exclusion evidence only.
It does not retrieve parents, infer omitted identities, or authorize execution.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Mapping, Sequence


_SCHEMA_VERSION = "candidate-supply-v2-fresh-parent-cohort-v1"
_EXCLUSION_STATES = {"COMPLETE", "PARTIAL", "UNRESOLVED"}
_EXCLUSION_AUTHORITATIVE_KINDS = {
    "DIAGNOSTIC_TOURNAMENT",
    "HISTORICAL_GENERATION",
    "PRIOR_USE",
}


def _mapping(value, label):
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a mapping")
    return value


def _nonempty_text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _identity_list(value, label, *, allow_empty=False):
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an explicit ordered list")
    if not allow_empty and not value:
        raise ValueError(f"{label} must not be empty")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{label} contains an invalid identity")
    if len(set(value)) != len(value):
        raise ValueError(f"{label} contains duplicate identities")
    return list(value)


def _canonical_digest(value):
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("manifest inputs must be finite JSON-compatible values") from exc
    return hashlib.sha256(encoded).hexdigest()


def _parent_identity(record):
    if isinstance(record, Mapping):
        parent_id = _nonempty_text(record.get("parent_id"), "parent_id")
        source_dataset = _nonempty_text(record.get("source_dataset"), "source_dataset")
        source_ref = _nonempty_text(record.get("source_ref"), "source_ref")
        structure_sha256 = record.get("structure_sha256")
        provenance = copy.deepcopy(record.get("provenance"))
        eligible = record.get("eligible")
        if type(eligible) is not bool:
            raise ValueError("mapping parent records must declare boolean eligible")
    else:
        try:
            parent_id = _nonempty_text(record.parent_id, "parent_id")
            source_dataset = _nonempty_text(record.source_dataset, "source_dataset")
            source_ref = _nonempty_text(record.source_ref, "source_ref")
            structure_sha256 = record.structure_sha256
            provenance = copy.deepcopy(record.provenance)
            eligible = getattr(record, "eligible", True)
        except AttributeError as exc:
            raise ValueError("parent records must expose source identity fields") from exc
        if type(eligible) is not bool:
            raise ValueError("parent record eligible must be a boolean")
    if parent_id != f"{source_dataset}:{source_ref}":
        raise ValueError("parent_id is not canonical for source_dataset/source_ref")
    if eligible and not isinstance(structure_sha256, str):
        raise ValueError("eligible parent structure_sha256 must be a string")
    if structure_sha256 is not None and not isinstance(structure_sha256, str):
        raise ValueError("structure_sha256 must be a string or None")
    _mapping(provenance, "parent provenance")
    return {
        "parent_id": parent_id,
        "source_dataset": source_dataset,
        "source_ref": source_ref,
        "structure_sha256": structure_sha256,
        "provenance": provenance,
        "eligible": eligible,
    }


def _validate_source_identity(source_identity):
    source = _mapping(source_identity, "source_identity")
    for field in ("source_dataset", "source_schema_version", "source_artifact_id",
                  "content_sha256"):
        _nonempty_text(source.get(field), f"source_identity.{field}")
    universe_ids = _identity_list(
        source.get("ordered_parent_ids"), "source ordered_parent_ids"
    )
    return copy.deepcopy(dict(source)), set(universe_ids)


def _validate_exclusion_evidence(evidence, selected_ids):
    if not isinstance(evidence, list) or not evidence:
        raise ValueError("exclusion_evidence must be a non-empty list")

    retained = copy.deepcopy(evidence)
    statuses = {}
    for index, raw_item in enumerate(retained):
        item = _mapping(raw_item, f"exclusion_evidence[{index}]")
        cohort_id = _nonempty_text(item.get("cohort_id"), "exclusion cohort_id")
        if cohort_id in statuses:
            raise ValueError(f"duplicate exclusion cohort identity: {cohort_id}")
        status = item.get("status")
        if status not in _EXCLUSION_STATES:
            raise ValueError(f"invalid exclusion status for {cohort_id}")
        source_provenance = _mapping(
            item.get("source_identity"), f"{cohort_id}.source_identity"
        )
        if not source_provenance:
            raise ValueError(f"{cohort_id}.source_identity must not be empty")
        statuses[cohort_id] = status

        if status == "COMPLETE":
            excluded_ids = _identity_list(
                item.get("ordered_parent_ids"),
                f"{cohort_id}.ordered_parent_ids",
                allow_empty=True,
            )
            if item.get("kind") == "DOWNSTREAM_CHILD_LINEAGE" or "child_rows" in item:
                child_rows = item.get("child_rows")
                if not isinstance(child_rows, list) or not child_rows:
                    raise ValueError(f"{cohort_id}.child_rows must be a non-empty list")
                child_ids = []
                lineage_parents = []
                for row_index, row in enumerate(child_rows):
                    row = _mapping(row, f"{cohort_id}.child_rows[{row_index}]")
                    child_ids.append(_nonempty_text(
                        row.get("child_material_id"), "child_material_id"
                    ))
                    lineage_parents.append(_nonempty_text(
                        row.get("parent_id"), "parent_id"
                    ))
                if len(set(child_ids)) != len(child_ids):
                    raise ValueError(f"{cohort_id}.child_rows contains duplicate children")
                child_count = item.get("child_output_count")
                if (type(child_count) is not int or child_count != len(child_rows)
                        or excluded_ids != list(dict.fromkeys(lineage_parents))):
                    raise ValueError(f"{cohort_id} child lineage does not match parent evidence")
            overlap = selected_ids.intersection(excluded_ids)
            if overlap:
                raise ValueError(
                    f"selected parents overlap COMPLETE exclusion {cohort_id}: "
                    f"{sorted(overlap)}"
                )

    return retained, statuses


def build_candidate_supply_v2_fresh_parent_cohort_manifest(
    parent_records,
    *,
    source_identity,
    exclusion_evidence,
    cohort_config,
):
    """Validate explicit cohort evidence and return a detached deterministic manifest.

    Freshness is fully verified only when each explicitly required prior-use
    source supplies COMPLETE parent identities. Child-output counts do not
    define parent cohort sizes. The result never authorizes runtime generation.
    """
    if (not isinstance(parent_records, Sequence)
            or isinstance(parent_records, (str, bytes, bytearray))):
        raise ValueError("parent_records must be an ordered sequence")

    source, source_ids = _validate_source_identity(source_identity)
    config = _mapping(cohort_config, "cohort_config")
    cohort_id = _nonempty_text(config.get("cohort_id"), "cohort_id")
    required_sources = _identity_list(
        config.get("required_exclusion_sources"),
        "cohort required_exclusion_sources",
    )
    records_by_id = {}
    for record in parent_records:
        identity = _parent_identity(record)
        parent_id = identity["parent_id"]
        if identity["source_dataset"] != source["source_dataset"]:
            raise ValueError(
                "parent record source_dataset does not match bound source dataset"
            )
        if parent_id in records_by_id:
            raise ValueError(f"duplicate parent record identity: {parent_id}")
        if parent_id not in source_ids:
            raise ValueError(f"parent record is outside bound source universe: {parent_id}")
        records_by_id[parent_id] = identity

    retained_evidence, statuses = _validate_exclusion_evidence(
        exclusion_evidence, set()
    )
    excluded_ids = set()
    for item in retained_evidence:
        if (item["status"] == "COMPLETE"
                and item.get("kind") in _EXCLUSION_AUTHORITATIVE_KINDS):
            excluded_ids.update(item.get("ordered_parent_ids", []))
    selected_ids = sorted(
        parent_id
        for parent_id, identity in records_by_id.items()
        if identity["eligible"] and parent_id not in excluded_ids
    )
    if not selected_ids:
        raise ValueError("derived fresh-parent cohort is empty")

    if "ordered_parent_ids" in config:
        asserted_ids = _identity_list(
            config.get("ordered_parent_ids"), "cohort ordered_parent_ids"
        )
        if asserted_ids != selected_ids:
            raise ValueError(
                "cohort ordered_parent_ids does not match derived membership"
            )

    rule = copy.deepcopy(_mapping(config.get("selection_rule"), "selection_rule"))
    rule_identity = _nonempty_text(rule.get("policy_id"), "selection_rule.policy_id")
    config_identity = copy.deepcopy(
        _mapping(config.get("selection_config_identity"), "selection_config_identity")
    )
    _nonempty_text(config_identity.get("schema_version"),
                   "selection_config_identity.schema_version")
    _nonempty_text(config_identity.get("content_sha256"),
                   "selection_config_identity.content_sha256")

    missing_required = [name for name in required_sources if name not in statuses]
    required_complete = all(statuses.get(name) == "COMPLETE" for name in required_sources)
    if required_complete:
        verification_state = "VERIFIED"
    elif any(statuses.get(name) == "UNRESOLVED" for name in required_sources):
        verification_state = "UNRESOLVED"
    else:
        verification_state = "PARTIAL"

    manifest = {
        "schema_version": _SCHEMA_VERSION,
        "artifact_type": "CANDIDATE_SUPPLY_V2_FRESH_PARENT_COHORT",
        "cohort_id": cohort_id,
        "ordered_parent_ids": list(selected_ids),
        "parent_count": len(selected_ids),
        "parents": [copy.deepcopy(records_by_id[parent_id]) for parent_id in selected_ids],
        "source_identity": source,
        "selection": {
            "rule": rule,
            "rule_identity": rule_identity,
            "config_identity": config_identity,
        },
        "exclusion_evidence": retained_evidence,
        "freshness": {
            "verification_state": verification_state,
            "freshness_fully_verified": required_complete,
            "required_exclusion_sources": list(required_sources),
            "missing_required_exclusion_sources": missing_required,
        },
        "authorization": {"runtime_generation_authorized": False},
    }
    manifest["manifest_identity"] = _canonical_digest(manifest)
    return manifest
