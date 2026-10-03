"""Pure manifest builder for an explicitly prepared Candidate Supply v2 source universe.

Acquisition and parsing happen before this boundary. This module validates the
supplied evidence; it does not reconstruct a historical cohort or authorize work.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Mapping


_SCHEMA_VERSION = "candidate-supply-v2-source-universe-v1"
_CORE_KEYS = (
    "schema_version",
    "source_snapshot",
    "selection_config",
    "considered_records",
    "eligible_parent_ids",
    "counts",
)
_PARSE_STATES = {"SUCCESS", "FAILED", "NOT_ATTEMPTED"}
_ELIGIBILITY_FLAGS = (
    "require_source_row",
    "require_cif",
    "require_parse_success",
    "require_ordered_structure",
)


def _mapping(value, label):
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a mapping")
    return value


def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _boolean(value, label):
    if type(value) is not bool:
        raise ValueError(f"{label} must be a boolean")
    return value


def _canonical_digest(core):
    try:
        encoded = json.dumps(
            core, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("source-universe evidence must be finite JSON data") from exc
    return hashlib.sha256(encoded).hexdigest()


def _source_snapshot(source_identity):
    snapshot = copy.deepcopy(dict(_mapping(source_identity, "source_identity")))
    for field in (
        "source_dataset", "source_schema_version", "source_artifact_id",
        "source_repository_commit", "source_repository_tree",
    ):
        _text(snapshot.get(field), f"source_identity.{field}")
    data_identity = _mapping(
        snapshot.get("source_data_identity"), "source_identity.source_data_identity"
    )
    if not data_identity:
        raise ValueError("source_data_identity must not be empty")
    return snapshot


def _selection(selection_config):
    config = copy.deepcopy(dict(_mapping(selection_config, "selection_config")))
    if config.get("ordering_rule") != "PARENT_ID_LEXICAL":
        raise ValueError("unsupported source-universe ordering rule")
    rule = _mapping(config.get("eligibility_rule"), "eligibility_rule")
    if set(rule) != set(_ELIGIBILITY_FLAGS):
        raise ValueError("eligibility_rule must declare the supported gates")
    for flag in _ELIGIBILITY_FLAGS:
        _boolean(rule[flag], f"eligibility_rule.{flag}")
    identity = _mapping(
        config.get("selection_config_identity"), "selection_config_identity"
    )
    _text(identity.get("schema_version"), "selection_config_identity.schema_version")
    _text(identity.get("content_sha256"), "selection_config_identity.content_sha256")
    if any(key in config for key in (
        "n_considered", "n_parse_success", "n_parse_failure", "n_eligible", "counts"
    )):
        raise ValueError("selection_config cannot supply derived record counts")
    if "historical_comparison" in config:
        historical = _mapping(config["historical_comparison"], "historical_comparison")
        count = historical.get("historical_perturbable_count")
        if type(count) is not int or count < 0:
            raise ValueError("historical_perturbable_count must be nonnegative")
    return config


def _record(raw, index, source_dataset, rule):
    record = copy.deepcopy(dict(_mapping(raw, f"source_records[{index}]")))
    parent_id = _text(record.get("parent_id"), f"source_records[{index}].parent_id")
    if record.get("source_dataset") != source_dataset:
        raise ValueError(f"source dataset mismatch for {parent_id}")
    source_ref = _text(record.get("source_ref"), f"{parent_id}.source_ref")
    if parent_id != f"{source_dataset}:{source_ref}":
        raise ValueError(f"noncanonical parent identity: {parent_id}")
    source_row = _boolean(record.get("source_row_present"), f"{parent_id}.source_row_present")
    cif = _boolean(record.get("cif_present"), f"{parent_id}.cif_present")
    state = record.get("parse_state")
    if state not in _PARSE_STATES:
        raise ValueError(f"invalid parse_state for {parent_id}")
    if state in {"SUCCESS", "FAILED"} and not cif:
        raise ValueError(f"parse result without CIF for {parent_id}")
    if state == "SUCCESS":
        _text(record.get("structure_sha256"), f"{parent_id}.structure_sha256")
        _boolean(record.get("structure_ordered"), f"{parent_id}.structure_ordered")
        if record.get("parse_error") is not None:
            raise ValueError(f"successful parse has an error for {parent_id}")
    elif state == "FAILED":
        _text(record.get("parse_error"), f"{parent_id}.parse_error")
        if record.get("structure_sha256") is not None:
            raise ValueError(f"failed parse has a structure hash for {parent_id}")
    else:
        if record.get("structure_sha256") is not None:
            raise ValueError(f"unattempted parse has a structure hash for {parent_id}")
    _mapping(record.get("provenance"), f"{parent_id}.provenance")

    reasons = []
    if rule["require_source_row"] and not source_row:
        reasons.append("SOURCE_ROW_MISSING")
    if rule["require_cif"] and not cif:
        reasons.append("CIF_MISSING")
    if rule["require_parse_success"] and state != "SUCCESS":
        if state == "FAILED":
            reasons.append("CIF_PARSE_FAILED")
        elif cif:
            reasons.append("CIF_PARSE_NOT_ATTEMPTED")
    if rule["require_ordered_structure"] and state == "SUCCESS":
        if not record["structure_ordered"]:
            reasons.append("STRUCTURE_NOT_ORDERED")
    eligible = _boolean(record.get("eligible"), f"{parent_id}.eligible")
    if eligible != (not reasons):
        raise ValueError(f"eligibility contradicts declared rule for {parent_id}")
    supplied_reasons = record.get("ineligibility_reasons")
    if not isinstance(supplied_reasons, list) or supplied_reasons != reasons:
        raise ValueError(f"ineligibility reasons contradict declared rule for {parent_id}")
    return record


def build_candidate_supply_v2_source_universe_manifest(
    source_records, *, source_identity, selection_config,
):
    """Validate explicit source evidence and bind it to a deterministic digest."""
    snapshot = _source_snapshot(source_identity)
    config = _selection(selection_config)
    if not isinstance(source_records, list) or not source_records:
        raise ValueError("source_records must be an explicit non-empty list")
    records = []
    seen = set()
    for index, raw in enumerate(source_records):
        record = _record(raw, index, snapshot["source_dataset"], config["eligibility_rule"])
        parent_id = record["parent_id"]
        if parent_id in seen:
            raise ValueError(f"duplicate parent identity: {parent_id}")
        seen.add(parent_id)
        records.append(record)
    parent_ids = [record["parent_id"] for record in records]
    if parent_ids != sorted(parent_ids):
        raise ValueError("source_records violate declared lexical parent-ID ordering")
    eligible_ids = [record["parent_id"] for record in records if record["eligible"]]
    counts = {
        "n_considered": len(records),
        "n_parse_success": sum(record["parse_state"] == "SUCCESS" for record in records),
        "n_parse_failure": sum(record["parse_state"] == "FAILED" for record in records),
        "n_eligible": len(eligible_ids),
    }
    core = {
        "schema_version": _SCHEMA_VERSION,
        "source_snapshot": snapshot,
        "selection_config": config,
        "considered_records": records,
        "eligible_parent_ids": eligible_ids,
        "counts": counts,
    }
    digest = _canonical_digest({key: core[key] for key in _CORE_KEYS})
    source = copy.deepcopy(snapshot)
    source["content_sha256"] = digest
    source["ordered_parent_ids"] = list(eligible_ids)
    return {
        **core,
        "content_sha256": digest,
        "source_identity": source,
    }
