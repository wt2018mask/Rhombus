"""Structural admission of a capped MPTrj first-frame diagnostic receipt.

This is local metadata consistency validation only. A well-shaped JSON
receipt does NOT prove it came from Figshare, from GitHub Actions, from an
untampered source, or from MACE-MPA-0 training bytes. No scientific gate opens.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Mapping


class MPTrjProbeReceiptError(ValueError):
    """Untrusted or inconsistent limited-source observation report."""


TOTAL = 12_188_168_685
FILE_ID = 41619375
MAX_PREFIX_BYTES = 1024 * 1024
FIRST_FRAME_FIELDS = (
    "material_id", "frame_id", "site_count", "reduced_formula",
    "energy_fields_present", "complete_frame_parsed",
)
ENERGY_FIELDS = (
    "uncorrected_total_energy", "corrected_total_energy", "energy_per_atom",
)
SHA256_PATTERN = re.compile(r"[a-f0-9]{64}\Z")


def _keys(value: object, expected: set[str], label: str) -> Mapping:
    if not isinstance(value, dict) or set(value) != expected:
        raise MPTrjProbeReceiptError(f"{label} has missing or unexpected fields")
    return value


def _positive_int(value: object, label: str, *, maximum: int) -> int:
    if type(value) is not int or not 1 <= value <= maximum:
        raise MPTrjProbeReceiptError(f"{label} must be a bounded positive integer")
    return value


def _identity(value: object, label: str, *, max_len: int = 2048) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > max_len:
        raise MPTrjProbeReceiptError(f"{label} must be a bounded nonblank string")
    return value


def _false(value: object, label: str) -> None:
    if value is not False:
        raise MPTrjProbeReceiptError(f"{label} would promote an unsupported claim")


def validate_mptrj_first_frame_receipt(
    record: object,
    *,
    expected_prefix_bytes: int = 256 * 1024,
) -> dict:
    """Validate a small observation schema without authorizing an exposure audit."""
    _positive_int(expected_prefix_bytes, "requested prefix budget", maximum=MAX_PREFIX_BYTES)
    root = _keys(record, {
        "schema_version", "source_metadata", "observation",
        "training_lineage", "authorization",
    }, "receipt")
    if root["schema_version"] != "rhombus-phase3-mptrj-range-prefix-probe-v1":
        raise MPTrjProbeReceiptError("unsupported receipt schema")
    src = _keys(root["source_metadata"], {
        "figshare_file_id", "expected_total_size_bytes_from_registry",
        "server_content_range_total_declared", "redirect_host",
    }, "source_metadata")
    if type(src["figshare_file_id"]) is not int or src["figshare_file_id"] != FILE_ID:
        raise MPTrjProbeReceiptError("source file ID does not match frozen Figshare file")
    for key in ("expected_total_size_bytes_from_registry", "server_content_range_total_declared"):
        if type(src[key]) is not int or src[key] != TOTAL:
            raise MPTrjProbeReceiptError("source total size does not match frozen Figshare file")
    host = _identity(src["redirect_host"], "redirect_host", max_len=253)
    if any(ch in host for ch in ("/", "\\", "@", " ", ":")):
        raise MPTrjProbeReceiptError("redirect_host is not a hostname")

    obs = _keys(root["observation"], {
        "prefix_size_bytes", "prefix_sha256", "first_material_id",
        "first_frame_id", "first_frame_structure_object_start_seen",
        "complete_frame_parsed", "first_frame_structure",
        "complete_original_source_hashed",
    }, "observation")
    if type(obs["prefix_size_bytes"]) is not int or obs["prefix_size_bytes"] != expected_prefix_bytes:
        raise MPTrjProbeReceiptError("observed byte count differs from permitted request size")
    digest = obs["prefix_sha256"]
    if not isinstance(digest, str) or not SHA256_PATTERN.fullmatch(digest):
        raise MPTrjProbeReceiptError("prefix SHA256 is not a canonical digest")
    material_id = _identity(obs["first_material_id"], "first_material_id")
    frame_id = _identity(obs["first_frame_id"], "first_frame_id")
    if obs["first_frame_structure_object_start_seen"] is not True or obs["complete_frame_parsed"] is not True:
        raise MPTrjProbeReceiptError("first complete Structure has not been observed")
    _false(obs["complete_original_source_hashed"], "complete_original_source_hashed")
    first = _keys(obs["first_frame_structure"], set(FIRST_FRAME_FIELDS), "first_frame_structure")
    if first["material_id"] != material_id or first["frame_id"] != frame_id:
        raise MPTrjProbeReceiptError("first frame IDs disagree with prefix observation")
    _positive_int(first["site_count"], "site_count", maximum=100_000)
    _identity(first["reduced_formula"], "reduced_formula", max_len=512)
    if first["complete_frame_parsed"] is not True:
        raise MPTrjProbeReceiptError("structure frame completion is false")
    fields = _keys(first["energy_fields_present"], set(ENERGY_FIELDS), "energy_fields_present")
    if any(type(fields[key]) is not bool for key in ENERGY_FIELDS):
        raise MPTrjProbeReceiptError("energy fields must be presence booleans only")

    lineage = _keys(root["training_lineage"], {
        "mace_mpa0_exact_training_bytes_attested", "training_frame_selection_attested",
    }, "training_lineage")
    for key, value in lineage.items():
        _false(value, key)
    authorization = _keys(root["authorization"], {
        "execute_exposure_audit", "empirical_calibration_use", "unseen_generalization_claim",
    }, "authorization")
    for key, value in authorization.items():
        _false(value, key)

    # Hash of a metadata report is NOT the source-file hash or an attestation.
    canonical = json.dumps(root, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return {
        "schema_version": "rhombus-mptrj-prefix-receipt-schema-check-v1",
        "status": "DIAGNOSTIC_REPORT_SCHEMA_VALID_ONLY",
        "report_metadata_sha256": sha256(canonical).hexdigest(),
        "first_frame_site_count": first["site_count"],
        "full_source_byte_identity_verified": False,
        "github_workflow_origin_attested": False,
        "model_training_frame_membership_attested": False,
        "execute_exposure_audit": False,
        "unseen_generalization_claim": False,
    }
