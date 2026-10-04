"""Prepare explicit source records for a Candidate Supply v2 universe manifest.

This module consumes caller-provided rows and an injected structure provider.
It performs no source acquisition, scientific ranking, or generation work.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping


_SCHEMA_VERSION = "candidate-supply-v2-source-record-preparation-v1"
_PROVIDER_PARSE_FAILED = object()
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


def _snapshot(source_snapshot):
    snapshot = copy.deepcopy(dict(_mapping(source_snapshot, "source_snapshot")))
    for field in (
        "source_name", "source_dataset", "source_schema_version",
        "source_artifact_id", "source_repository_commit",
        "source_repository_tree",
    ):
        _text(snapshot.get(field), f"source_snapshot.{field}")
    data_identity = _mapping(
        snapshot.get("source_data_identity"), "source_snapshot.source_data_identity"
    )
    if not data_identity:
        raise ValueError("source_snapshot.source_data_identity must not be empty")
    return snapshot


def _config(selection_config, source_dataset):
    config = copy.deepcopy(dict(_mapping(selection_config, "selection_config")))
    namespace = _text(config.get("source_namespace"), "source_namespace")
    if namespace != source_dataset:
        raise ValueError("source_namespace must match source_snapshot.source_dataset")
    for field in ("source_id_field", "structure_ref_field"):
        _text(config.get(field), field)
    if config.get("ordering_rule") != "PARENT_ID_LEXICAL":
        raise ValueError("unsupported source preparation ordering rule")
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
    return config


def _canonical_parent_id(raw_identity, namespace):
    raw_identity = _text(raw_identity, "source row identity")
    if ":" in raw_identity:
        prefix, source_ref = raw_identity.split(":", 1)
        if prefix != namespace or not source_ref or ":" in source_ref:
            raise ValueError(f"ambiguous source row identity: {raw_identity}")
    else:
        source_ref = raw_identity
    return f"{namespace}:{source_ref}", source_ref


def _structure_facts(value, parent_id):
    if isinstance(value, Mapping):
        structure_sha256 = value.get("structure_sha256")
        ordered = value.get("is_ordered")
    else:
        structure_sha256 = getattr(value, "structure_sha256", None)
        ordered = getattr(value, "is_ordered", None)
    structure_sha256 = _text(structure_sha256, f"{parent_id}.structure_sha256")
    ordered = _boolean(ordered, f"{parent_id}.is_ordered")
    return structure_sha256, ordered


def _eligibility(source_row_present, cif_present, parse_state, structure_ordered, rule):
    reasons = []
    if rule["require_source_row"] and not source_row_present:
        reasons.append("SOURCE_ROW_MISSING")
    if rule["require_cif"] and not cif_present:
        reasons.append("CIF_MISSING")
    if rule["require_parse_success"] and parse_state != "SUCCESS":
        if parse_state == "FAILED":
            reasons.append("CIF_PARSE_FAILED")
        elif cif_present:
            reasons.append("CIF_PARSE_NOT_ATTEMPTED")
    if rule["require_ordered_structure"] and parse_state == "SUCCESS":
        if not structure_ordered:
            reasons.append("STRUCTURE_NOT_ORDERED")
    return not reasons, reasons


def prepare_candidate_supply_v2_source_records(
    source_rows,
    *,
    source_snapshot,
    structure_provider,
    selection_config,
):
    """Prepare ordered, auditable records from explicit rows and provider facts."""
    snapshot = _snapshot(source_snapshot)
    config = _config(selection_config, snapshot["source_dataset"])
    if not isinstance(source_rows, list) or not source_rows:
        raise ValueError("source_rows must be an explicit non-empty list")
    if not callable(structure_provider):
        raise ValueError("structure_provider must be callable")

    prepared_inputs = []
    seen = set()
    id_field = config["source_id_field"]
    structure_field = config["structure_ref_field"]
    namespace = config["source_namespace"]
    for index, raw_row in enumerate(source_rows):
        row = copy.deepcopy(dict(_mapping(raw_row, f"source_rows[{index}]")))
        parent_id, source_ref = _canonical_parent_id(row.get(id_field), namespace)
        if parent_id in seen:
            raise ValueError(f"duplicate canonical parent identity: {parent_id}")
        seen.add(parent_id)
        structure_ref = row.get(structure_field)
        if structure_ref is not None:
            _text(structure_ref, f"{parent_id}.{structure_field}")
        prepared_inputs.append((parent_id, source_ref, structure_ref, row))

    parent_ids = [entry[0] for entry in prepared_inputs]
    if parent_ids != sorted(parent_ids):
        raise ValueError("source_rows violate declared lexical parent-ID ordering")

    records = []
    rule = config["eligibility_rule"]
    for parent_id, source_ref, structure_ref, row in prepared_inputs:
        source_row_present = True
        structure_present = structure_ref is not None
        structure_state = "STRUCTURE_MISSING"
        cif_present = False
        parse_state = "NOT_ATTEMPTED"
        parse_error = None
        structure_sha256 = None
        structure_ordered = None

        if structure_present:
            try:
                supplied_structure = structure_provider(parent_id)
            except Exception:
                supplied_structure = _PROVIDER_PARSE_FAILED
            if supplied_structure is _PROVIDER_PARSE_FAILED:
                structure_state = "STRUCTURE_PRESENT"
                cif_present = True
                parse_state = "FAILED"
                parse_error = "PARSE_FAILED"
            elif supplied_structure is not None:
                structure_state = "STRUCTURE_PRESENT"
                cif_present = True
                parse_state = "SUCCESS"
                structure_sha256, structure_ordered = _structure_facts(
                    supplied_structure, parent_id
                )

        eligible, reasons = _eligibility(
            source_row_present, cif_present, parse_state,
            structure_ordered, rule,
        )
        records.append({
            "parent_id": parent_id,
            "source_dataset": snapshot["source_dataset"],
            "source_ref": source_ref,
            "source_row_present": source_row_present,
            "cif_present": cif_present,
            "structure_state": structure_state,
            "parse_state": parse_state,
            "parse_error": parse_error,
            "structure_sha256": structure_sha256,
            "structure_ordered": structure_ordered,
            "eligible": eligible,
            "ineligibility_reasons": reasons,
            "provenance": {"source_row": row},
        })

    return {
        "schema_version": _SCHEMA_VERSION,
        "source_snapshot": snapshot,
        "source_identity": copy.deepcopy(snapshot),
        "selection_config": config,
        "records": records,
    }
