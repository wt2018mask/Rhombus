"""Read-only, evidence-first planning for exact model training lineage.

A declared SHA, dataset family, or synthetic receipt is never equivalent to an
independent full-file observation or an authenticated selected-frame audit.
The report contains requirement codes only, never selected-frame material IDs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping

from .mpa0_publisher_digest import PUBLIC_SHA256, MODEL, RELEASE_URL, MACE_REPO_COMMIT
from .training_manifest import SOURCES, SCHEMA, verify_training_lineage_manifest

READINESS_SCHEMA = "rhombus-training-lineage-readiness-v1"
MAX_MANIFEST_BYTES = 256 * 1024
_SHA = re.compile(r"^[0-9a-f]{64}$")
_SOURCE_ARTIFACTS = (
    ("selected_frames_sha256", "SELECTED_FRAME_LIST"),
    ("preprocessing_sha256", "PREPROCESSING_RULES"),
    ("energy_labels_sha256", "ENERGY_LABEL_MAPPING"),
)


def _nested(obj: Any, *keys: str) -> Any:
    for key in keys:
        if not isinstance(obj, Mapping):
            return None
        obj = obj.get(key)
    return obj


def _sha(value: Any) -> bool:
    return isinstance(value, str) and _SHA.fullmatch(value) is not None


def _full_observation(value: Any) -> bool:
    return (
        isinstance(value, Mapping)
        and _sha(value.get("sha256"))
        and type(value.get("byte_length")) is int
        and value["byte_length"] > 0
        and value.get("hash_scope") == "FULL_FILE"
        and value.get("method") == "INDEPENDENT_SHA256_READ"
    )


def _has_observed_checkpoint(value: Any) -> bool:
    return (
        _full_observation(value)
        and value["sha256"] == PUBLIC_SHA256
        and value["byte_length"] == 79_462_305
    )


def assess_training_lineage_readiness(
    *,
    manifest: Mapping[str, Any] | None = None,
    artifacts: Mapping[str, bytes] | None = None,
    receipts: list[dict[str, Any]] | None = None,
    trusted_issuers: Mapping[str, Any] | None = None,
    trusted_rule_bindings: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Report missing evidence; call strict authenticator ONLY if complete.

    Passing untrusted content in the manifest cannot authorize scientific
    generalization. Trusted issuers must be independently host-provisioned.
    """
    if manifest is not None and not isinstance(manifest, Mapping):
        raise ValueError("training manifest must be an object")
    report: dict[str, Any] = {
        "schema_version": READINESS_SCHEMA,
        "model_id": MODEL,
        "publisher_reported_checkpoint_sha256": PUBLIC_SHA256,
        "checkpoint_publisher_revision": MACE_REPO_COMMIT,
        "source_families": list(SOURCES),
        "status": "BLOCKED",
        "scientific_verdict": "INDETERMINATE",
        "independently_authenticated": False,
        "ready_for_membership_audit": False,
        "exact_training_frames_attested": False,
        "unseen_generalization_authorized": False,
        "scientific_qualification_authorized": False,
        "scope": "NOT_SUBMITTED",
        "requirements": [],
        "blockers": [],
        "limitations": [
            "DECLARED_METADATA_IS_NOT_INDEPENDENT_OBSERVATION",
            "EXACT_SELECTED_TRAINING_MEMBERSHIP_REQUIRES_SEPARATE_AUDIT",
            "LEGACY_PUBLIC_B3_IS_NOT_INDEPENDENT_BLINDED_EVALUATION",
        ],
    }
    requirements = report["requirements"]

    def add(code: str, declared: bool) -> None:
        requirements.append({
            "requirement": code,
            "declaration_status": "DECLARED_UNVERIFIED" if declared else "MISSING",
            "independently_authenticated": False,
        })

    current = manifest or {}
    report["scope"] = current.get("scope", "NOT_SUBMITTED")
    if current and (current.get("schema_version") != SCHEMA
                    or current.get("scope") not in ("SYNTHETIC", "EXTERNAL")
                    or current.get("identity_scheme") != "STEWARD_CANONICAL_MATERIAL_TOKEN_V1"):
        report["blockers"].append("MANIFEST_SCHEMA_SCOPE_OR_IDENTITY_INVALID")
    checkpoint = _nested(current, "checkpoint")
    identity = (
        isinstance(checkpoint, Mapping)
        and checkpoint.get("asset_name") == MODEL
        and checkpoint.get("release_url") == RELEASE_URL
        and checkpoint.get("publisher_revision") == MACE_REPO_COMMIT
        and checkpoint.get("publisher_reported_sha256") == PUBLIC_SHA256
    )
    add("EXACT_PUBLISHER_CHECKPOINT_IDENTITY", bool(identity))
    add(
        "INDEPENDENT_MODEL_BINARY_FULL_SHA256",
        _has_observed_checkpoint(_nested(checkpoint, "independent_observation")),
    )

    sources = current.get("sources", [])
    if not isinstance(sources, list) or len(sources) > 2:
        report["blockers"].append("SOURCE_MANIFEST_SHAPE_INVALID")
        sources = []
    keyed: dict[str, Mapping[str, Any]] = {}
    for row in sources:
        if not isinstance(row, Mapping) or row.get("dataset_id") not in SOURCES:
            report["blockers"].append("UNKNOWN_SOURCE_FAMILY")
            continue
        key = row["dataset_id"]
        if key in keyed:
            report["blockers"].append("DUPLICATE_SOURCE_FAMILY")
        else:
            keyed[key] = row

    for dataset in SOURCES:
        row = keyed.get(dataset, {})
        prefix = dataset.upper()
        add(prefix + "_ORIGINAL_SOURCE_FULL_SHA256",
            _full_observation(row.get("source_observation")))
        count = row.get("selected_frame_count")
        add(prefix + "_CHECKPOINT_SELECTED_FRAME_COUNT",
            type(count) is int and 0 <= count <= 100_000)
        for field, name in _SOURCE_ARTIFACTS:
            value = row.get(field)
            present = _sha(value) and (
                isinstance(artifacts, Mapping) and isinstance(artifacts.get(value), bytes)
                and hashlib.sha256(artifacts[value]).hexdigest() == value
            )
            add(prefix + "_" + name + "_BYTES_SHA256", bool(present))
    add("INDEPENDENT_ROLE_BOUND_SIGNATURE_RECEIPTS",
        isinstance(receipts, list) and len(receipts) == 7)
    add("HOST_PROVISIONED_TRUST_ANCHORS",
        bool(trusted_issuers))
    add("HOST_APPROVED_SOURCE_PREPROCESSING_RULES",
        trusted_rule_bindings is not None)

    report["missing_requirements"] = [
        row["requirement"] for row in requirements if row["declaration_status"] == "MISSING"
    ]
    inputs_provided = (
        manifest is not None and artifacts is not None
        and receipts is not None and trusted_issuers is not None
    )
    if inputs_provided and not report["missing_requirements"] and not report["blockers"]:
        try:
            verified = verify_training_lineage_manifest(
                manifest=manifest, artifacts=artifacts, receipts=receipts,
                trusted_issuers=trusted_issuers,
                trusted_rule_bindings=trusted_rule_bindings,
            )
        except (ValueError, TypeError, KeyError, AttributeError):
            report["blockers"].append("STRICT_TRAINING_LINEAGE_AUTHENTICATION_REJECTED")
        else:
            # The strict verifier itself deliberately refuses scientific PASS.
            report["independently_authenticated"] = bool(
                verified["checkpoint_independent_observation_authenticated"]
                and verified["full_source_observations_authenticated"]
            )
            report["ready_for_membership_audit"] = bool(verified["ready_for_membership_audit"])
            if report["ready_for_membership_audit"]:
                report["status"] = "READY_FOR_SEPARATE_MEMBERSHIP_AUDIT"
            else:
                report["blockers"].append("INDEPENDENT_TRAINING_PROVENANCE_NOT_ATTESTED")
            report["limitations"].extend(verified["blockers"])
    if not report["ready_for_membership_audit"]:
        report["blockers"].append("EXACT_SELECTED_TRAINING_MEMBERSHIP_UNATTESTED")
    report["blockers"] = sorted(set(report["blockers"]))
    return report


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise ValueError("duplicate training manifest field")
        output[key] = value
    return output


def _reject_constant(value: str) -> None:
    raise ValueError("nonfinite training manifest numeric constant")


def main(argv: list[str] | None = None) -> int:
    """Create an honest missing-evidence report without downloading the model."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest-json", type=Path,
                        help="Optional small untrusted training manifest declaration")
    args = parser.parse_args(argv)
    manifest = None
    if args.manifest_json is not None:
        with args.manifest_json.open("rb") as source:
            raw = source.read(MAX_MANIFEST_BYTES + 1)
        if len(raw) > MAX_MANIFEST_BYTES:
            parser.error("training manifest exceeds 256KiB limit")
        try:
            manifest = json.loads(
                raw, object_pairs_hook=_no_duplicate_keys,
                parse_constant=_reject_constant,
            )
        except (ValueError, UnicodeError) as exc:
            parser.error("invalid JSON training declaration")
    result = assess_training_lineage_readiness(manifest=manifest)
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
