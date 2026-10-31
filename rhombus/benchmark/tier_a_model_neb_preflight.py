"""0204 Tier-A offline model-identity/NEB readiness *review*, never a runner.

Inputs are an already pinned owner-provided LiTraj TRAIN pilot and its byte
binding receipt. This module does NOT import MACE, ASE, torch or any calculator;
it never opens DFT targets, downloads artifacts or grants compute authorization.

File hashes establish byte identity, not model quality, pretrained overlap,
publisher signature or that the binary implements the advertised architecture.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import stat
from typing import Any, Mapping

from .tier_a_budget_contract import (
    MACE_MEDIUM_SHA256, REQUIRED_MODEL_IDS, _sha,
    inspect_budget_draft,
)
from .tier_a_input_pin import SCHEMA as INPUT_BINDING_SCHEMA
from .tier_a_preflight import ZIP_BYTES, ZIP_SHA256
from .tier_a_upstream_model_assets import (
    EXPECTED_ASSETS, create_candidate_asset_manifest, verify_candidate_asset_manifest,
)

SCHEMA = "rhombus-0204-tier-a-model-neb-offline-review-v1"
MAX_MODEL_BYTES = 2 * 1024 ** 3
MACE_UPSTREAM_SOURCE_COMMIT = "e37c8583a8b1b586e5888fa6dca86e8f591e2606"
MACE_UPSTREAM_SOURCE_FILE = (
    "https://github.com/ACEsuit/mace/blob/" + MACE_UPSTREAM_SOURCE_COMMIT
    + "/mace/calculators/foundations_models.py"
)
SHA_RE = re.compile(r"[0-9a-f]{64}\Z")
ARM_SOURCE_CATALOG = {
    "MACE_MP_0_SMALL_PUBLISHER_EXAMPLE": {
        "model_family": "MACE-MP-0 SMALL (NOT MPA-0 MEDIUM)",
        "source_url": "https://github.com/ACEsuit/mace-mp/releases/download/mace_mp_0/2023-12-10-mace-128-L0_energy_epoch-249.model",
        "origin": "PINNED_UPSTREAM_SOURCE_MAPPING_NOT_BINARY_HASH_ATTESTED",
    },
    "MACE_MPA_0_MEDIUM_RHOMBUS": {
        "model_family": "MACE-MPA-0 MEDIUM (NOT MACE-MP-0 SMALL)",
        "source_url": "https://github.com/ACEsuit/mace-mp/releases/download/mace_mpa_0/mace-mpa-0-medium.model",
        "origin": "HISTORICAL_RHOMBUS_0200_BYTE_IDENTITY_NOT_REHASHED_HERE",
    },
}
# Publication's example is not a per-row DFT computation receipt or a frozen
# Rhombus protocol. Both endpoints and NEB explicitly receive the SAME limits.
NEB_ILLUSTRATIVE_VALUES = {
    "endpoint_fmax_ev_ang": 0.1,
    "neb_fmax_ev_ang": 0.1,
    "endpoint_max_steps": 100,
    "neb_max_steps": 100,
    "spring_eV_ang2": 5.0,
}
_RUNTIME_FIELDS = (
    "python_version", "ase_version", "mace_torch_version", "torch_version",
    "numpy_version", "mace_source_commit", "calculator_adapter_sha256",
    "calculator_call_accounting", "thread_control_evidence",
)


def _exact(x: Any, required: tuple[str, ...] | set[str], where: str) -> None:
    if type(x) is not dict or set(x) != set(required):
        raise ValueError(f"{where}: EXACT_FIELDS_REQUIRED")


def _digest(x: Any, field: str) -> None:
    if type(x) is not str or SHA_RE.fullmatch(x) is None:
        raise ValueError(f"{field}: SHA256_REQUIRED")


def verify_local_binary_bytes(path: Path, *, expected_sha256: str | None = None,
                              expected_size_bytes: int | None = None) -> dict[str, Any]:
    """Read an explicit, local, regular file without loading/deserializing it.

    A check against an independently approved digest is only a *file integrity*
    check. The caller must still establish checkpoint provenance and training.
    """
    if expected_sha256 is not None:
        _digest(expected_sha256, "EXPECTED_MODEL")
    if expected_size_bytes is not None and (type(expected_size_bytes) is not int
                                           or not 0 < expected_size_bytes <= MAX_MODEL_BYTES):
        raise ValueError("INVALID_EXPECTED_MODEL_SIZE")
    p = Path(path)
    if p.is_symlink():
        raise ValueError("MODEL_SYMLINK_NOT_ACCEPTED")
    if not p.is_file():
        raise ValueError("MODEL_FILE_NOT_ACCESSIBLE")
    fd = os.open(p, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= MAX_MODEL_BYTES:
            raise ValueError("MODEL_FILE_TYPE_OR_SIZE_INVALID")
        if expected_size_bytes is not None and before.st_size != expected_size_bytes:
            raise ValueError("MODEL_SIZE_MISMATCH")
        h = sha256()
        read = 0
        with os.fdopen(fd, "rb", closefd=False) as stream:
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                read += len(chunk)
                if read > MAX_MODEL_BYTES:
                    raise ValueError("MODEL_TOO_LARGE")
                h.update(chunk)
        after = os.fstat(fd)
        if (read != before.st_size or before.st_size != after.st_size
                or before.st_mtime_ns != after.st_mtime_ns
                or before.st_ctime_ns != after.st_ctime_ns
                or before.st_ino != after.st_ino or before.st_dev != after.st_dev):
            raise ValueError("MODEL_FILE_CHANGED_DURING_READ")
        digest = h.hexdigest()
        if expected_sha256 is not None and digest != expected_sha256:
            raise ValueError("MODEL_SHA256_MISMATCH")
        return {
            "sha256": digest,
            "size_bytes": read,
            "verification": ("MATCHED_DECLARED_SHA256_AND_SIZE"
                             if expected_sha256 is not None and expected_size_bytes is not None else
                             "MATCHED_DECLARED_SHA256" if expected_sha256 is not None else
                             "OBSERVED_BYTES_ONLY_NOT_PINNED"),
            "publisher_signature": "NOT_INDEPENDENTLY_ATTESTED",
            "model_deserialized": False,
            "model_inference_executed": False,
        }
    finally:
        os.close(fd)


def verify_pilot_input_binding(draft: Mapping[str, Any], receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Bind original four TRAIN input bytes without re-reading target or ZIP."""
    inspect_budget_draft(draft)
    _exact(receipt, (
        "schema_version", "archive_owner_sha256", "publisher_authenticity",
        "archive_size_bytes", "operation", "relaxed_dft_xyz_access",
        "target_columns_access", "initial_member_count", "initial_total_uncompressed_bytes",
        "identities", "prior_draft_sha256", "pinned_draft_sha256",
        "execution_authorized", "scientific_status", "benchmark_status",
    ), "INPUT_BINDING_RECEIPT")
    if (receipt["schema_version"] != INPUT_BINDING_SCHEMA
            or receipt["archive_owner_sha256"] != ZIP_SHA256
            or receipt["archive_size_bytes"] != ZIP_BYTES
            or receipt["publisher_authenticity"] != "UNATTESTED"
            or receipt["target_columns_access"] != "NONE"
            or receipt["relaxed_dft_xyz_access"] != "NONE"
            or receipt["execution_authorized"] is not False
            or receipt["scientific_status"] != "SCIENTIFIC_NO_GO_ABSTAIN"
            or receipt["benchmark_status"] != "BENCHMARK_NOT_FROZEN"):
        raise ValueError("INPUT_BINDING_PROVENANCE_CONTRADICTION")
    if (receipt["operation"] != "SHA256_OF_ONLY_FOUR_INITIAL_XYZ_UNCOMPRESSED_MEMBER_BYTES_NO_XYZ_PARSE"
            or type(receipt["identities"]) is not list
            or type(receipt["initial_member_count"]) is not int
            or receipt["initial_member_count"] != 4
            or len(receipt["identities"]) != 4
            or type(receipt["initial_total_uncompressed_bytes"]) is not int
            or receipt["initial_total_uncompressed_bytes"] <= 0):
        raise ValueError("INPUT_BINDING_RECEIPT_INVALID")
    _digest(receipt["prior_draft_sha256"], "PRIOR_DRAFT")
    _digest(receipt["pinned_draft_sha256"], "PINNED_DRAFT")
    edges = {e["edge_id"]: e for e in draft["edges"]}
    names = set()
    total = 0
    for row in receipt["identities"]:
        _exact(row, ("edge_id", "group_id", "zip_member", "raw_uncompressed_bytes",
                     "raw_uncompressed_sha256"), "INPUT_MEMBER")
        eid = row["edge_id"]
        if type(eid) is not str or eid not in edges or eid in names:
            raise ValueError("INPUT_BINDING_EDGE_MISMATCH")
        names.add(eid)
        if (row["group_id"] != edges[eid]["group_id"]
                or row["zip_member"] != f"nebDFT2k/{eid}_init.xyz"
                or row["raw_uncompressed_sha256"] != edges[eid]["initial_images_sha256"]):
            raise ValueError("INPUT_BINDING_HASH_OR_GROUP_MISMATCH")
        if (type(row["raw_uncompressed_bytes"]) is not int
                or not 0 < row["raw_uncompressed_bytes"] <= 8 * 1024 * 1024):
            raise ValueError("INPUT_MEMBER_BYTES_INVALID")
        _digest(row["raw_uncompressed_sha256"], "INITIAL_XYZ")
        total += row["raw_uncompressed_bytes"]
    if names != set(edges) or total != receipt["initial_total_uncompressed_bytes"]:
        raise ValueError("INPUT_BINDING_COUNT_MISMATCH")
    return {
        "verified_unchanged_identity_rows": 4,
        "verified_uncompressed_bytes": total,
        "binding": "RECEIPT_INPUT_IDENTITIES_MATCH_DRAFT_NO_ZIP_RESCAN",
        "publisher_identity": "OWNER_PROVIDED_UNATTESTED",
    }


def propose_shared_neb_numeric_candidate(draft: Mapping[str, Any]) -> dict[str, Any]:
    """Author-review *candidate* values, never policy promotion or execution."""
    inspect_budget_draft(draft)
    proposed = deepcopy(draft)
    for key, value in NEB_ILLUSTRATIVE_VALUES.items():
        if proposed["neb"][key] is not None and proposed["neb"][key] != value:
            raise ValueError("EXISTING_NEB_SETTING_REQUIRES_SEPARATE_REVIEW")
        proposed["neb"][key] = value
    inspection = inspect_budget_draft(proposed)
    if inspection["execution_authorized"] is not False:
        raise ValueError("UNAUTHORIZED_RUN_PROMOTION")
    return proposed


def _check_runtime_declaration(runtime: Mapping[str, Any] | None,
                               draft: Mapping[str, Any]) -> dict[str, Any]:
    if runtime is None:
        return {"declaration_status": "NOT_PROVIDED", "declaration_sha256": None,
                "blockers": ["RUNTIME_VERSION_AND_CALCULATOR_ADAPTER_UNPINNED"]}
    _exact(runtime, _RUNTIME_FIELDS, "RUNTIME_DECLARATION")
    if any(type(runtime[k]) is not str or not runtime[k].strip() or len(runtime[k]) > 256
           for k in _RUNTIME_FIELDS):
        raise ValueError("RUNTIME_DECLARATION_FIELDS_MUST_BE_EXPLICIT")
    _digest(runtime["calculator_adapter_sha256"], "CALCULATOR_ADAPTER")
    if not re.fullmatch(r"[0-9a-f]{40}", runtime["mace_source_commit"]):
        raise ValueError("MACE_SOURCE_COMMIT_MUST_BE_PINNED")
    if runtime["calculator_call_accounting"] != "CALCULATOR_CALLBACK_INSTRUMENTED":
        raise ValueError("CALL_COUNTS_NOT_ATTESTED_BY_DECLARATION")
    if runtime["thread_control_evidence"] != "CPU_2_THREADS_PER_ARM_SEQUENTIAL":
        raise ValueError("RUNTIME_THREADS_MISMATCH")
    return {"declaration_status": "OWNER_DECLARED_NOT_INDEPENDENT_RUNTIME_ATTESTED",
            "declaration_sha256": _sha(runtime), "blockers": ["RUNTIME_DECLARATION_NOT_INDEPENDENT_ATTESTATION"]}


def inspect_offline_run_review(
    *, draft: Mapping[str, Any], input_binding_receipt: Mapping[str, Any],
    model_files: Mapping[str, Path] | None = None,
    runtime_declaration: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """One non-executing, non-scoring readiness report; output has no local paths."""
    contract = inspect_budget_draft(draft)
    inputs = verify_pilot_input_binding(draft, input_binding_receipt)
    if model_files is None:
        model_files = {}
    if type(model_files) is not dict or not set(model_files).issubset(REQUIRED_MODEL_IDS):
        raise ValueError("UNKNOWN_MODEL_ARM_FILE")
    declared_arms = {x["arm_id"]: x for x in draft["model_arms"]}
    files_report = {}
    blockers = set(contract["blockers"])
    for arm_id in sorted(REQUIRED_MODEL_IDS):
        arm = declared_arms[arm_id]
        checkpoint = arm["checkpoint_sha256"]
        catalog = ARM_SOURCE_CATALOG[arm_id]
        status = {"model_family": catalog["model_family"],
                  "canonical_source_url": catalog["source_url"],
                  "upstream_source_mapping": MACE_UPSTREAM_SOURCE_FILE,
                  "source_url_status": catalog["origin"],
                  "official_release_asset": {
                      "asset_id": EXPECTED_ASSETS[arm_id]["asset_id"],
                      "expected_size_bytes": EXPECTED_ASSETS[arm_id]["size_bytes"],
                      "github_digest": None,
                  },
                  "draft_checkpoint_sha256": checkpoint,
                  "file_status": "NOT_PROVIDED", "byte_observation": None}
        if arm_id not in model_files:
            blockers.add(f"{arm_id}:MODEL_FILE_NOT_PROVIDED")
        else:
            try:
                # The historical MPA-0 SHA is a binding, not permission to load.
                observation = verify_local_binary_bytes(
                    model_files[arm_id], expected_sha256=checkpoint,
                    expected_size_bytes=EXPECTED_ASSETS[arm_id]["size_bytes"],
                )
                status["byte_observation"] = observation
                if checkpoint is None:
                    status["file_status"] = "OBSERVED_UNPINNED"
                    blockers.add(f"{arm_id}:CHECKPOINT_REQUIRES_OWNER_PIN")
                else:
                    status["file_status"] = "MATCHED_DRAFT_BYTES"
            except (OSError, ValueError) as exc:
                status["file_status"] = "REJECTED"
                status["failure_code"] = str(exc)
                blockers.add(f"{arm_id}:MODEL_FILE_REJECTED")
        files_report[arm_id] = status
    runtime = _check_runtime_declaration(runtime_declaration, draft)
    blockers.update(runtime["blockers"])
    numeric_blockers = {
        "MODEL_CHECKPOINT_UNPINNED", "NEB_NUMERIC_SETTINGS_MISSING",
        "PER_ARM_PER_EDGE_CAPS_MISSING", "TOTAL_PILOT_CAPS_MISSING",
        "INITIAL_IMAGE_HASHES_MISSING",
    }
    unfilled = sorted(blockers.intersection(numeric_blockers))
    missing_models = sorted(b for b in blockers if ":" in b)
    return {
        "schema_version": SCHEMA,
        "official_release_asset_review": verify_candidate_asset_manifest(
            create_candidate_asset_manifest()),
        "task": "TIER_A_RETROSPECTIVE_LI_HOP_DISCRETE_NEB_ENERGY_SPAN",
        "evaluation_observable": "max(E_images)-min(E_images); NONDIRECTIONAL",
        "scientific_status": "SCIENTIFIC_NO_GO_ABSTAIN",
        "benchmark_status": "BENCHMARK_NOT_FROZEN",
        "operational_status": "NON_EXECUTING_OFFLINE_REVIEW_ONLY",
        "execution_authorized": False,
        "eligible_for_separate_owner_review": (
            not unfilled and not missing_models
            and runtime["declaration_status"] != "NOT_PROVIDED"
            and all(f["file_status"] == "MATCHED_DRAFT_BYTES" for f in files_report.values())
        ),
        "preflight_blockers": sorted(blockers),
        "draft_sha256": contract["draft_sha256"],
        "pilot_paired_rows_required": contract["paired_rows_required"],
        "input_binding": inputs,
        "models": files_report,
        "runtime": runtime,
        "unknown_scientific_issues": ["UNKNOWN_TRAINING_OVERLAP", "PUBLISHER_AUTHENTICITY_UNATTESTED",
                                      "REFERENCE_ELECTRONIC_METHOD_NOT_PER_ROW_ATTESTED",
                                      "NO_INDEPENDENT_SOURCE_OUT_BENCHMARK"],
        "calculation_performed": False,
        "heldout_targets_read": False,
        "model_deserialization_performed": False,
    }
