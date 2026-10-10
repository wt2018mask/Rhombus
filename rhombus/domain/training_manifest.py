"""Checkpoint-bound training-selection evidence, authenticated independently.

Dataset families and a verified prefix are insufficient. All selected-frame,
preprocessing and label artifacts are inspected and bound to the exact model.
EXTERNAL receipts require trust anchors provisioned outside this evidence.
No download, source processing, training or scientific authorization occurs.
"""

from __future__ import annotations

import hashlib

from rhombus.evidence.receipts import (
    bounded_text,
    digest,
    evidence_sha256,
    exact_fields,
    integer,
    read_evidence_json,
    verify_evidence_receipt,
)
from .mpa0_publisher_digest import PUBLIC_SHA256, MODEL, RELEASE_URL, MACE_REPO_COMMIT

SCHEMA = "rhombus-checkpoint-training-lineage-v1"
SOURCES = ("MPTrj", "sAlex")


def _artifact(artifacts, sha):
    digest(sha)
    raw = artifacts.get(sha)
    if not isinstance(raw, bytes) or hashlib.sha256(raw).hexdigest() != sha:
        raise ValueError("missing or mismatched training artifact bytes")
    return read_evidence_json(raw)


def verify_training_lineage_manifest(
    *, manifest, artifacts, receipts, trusted_issuers, trusted_rule_bindings=None
):
    exact_fields(
        manifest,
        (
            "schema_version",
            "scope",
            "checkpoint",
            "sources",
            "development_group",
            "identity_scheme",
        ),
        "training manifest",
    )
    if (
        manifest["schema_version"] != SCHEMA
        or manifest["scope"] not in ("SYNTHETIC", "EXTERNAL")
        or manifest["identity_scheme"] != "STEWARD_CANONICAL_MATERIAL_TOKEN_V1"
    ):
        raise ValueError("unsupported training manifest")
    bounded_text(manifest["development_group"])
    checkpoint = manifest["checkpoint"]
    exact_fields(
        checkpoint,
        (
            "asset_name",
            "release_url",
            "publisher_revision",
            "publisher_reported_sha256",
            "independent_observation",
        ),
        "checkpoint",
    )
    if (
        checkpoint["asset_name"],
        checkpoint["release_url"],
        checkpoint["publisher_revision"],
        checkpoint["publisher_reported_sha256"],
    ) != (MODEL, RELEASE_URL, MACE_REPO_COMMIT, PUBLIC_SHA256):
        raise ValueError("incorrect exact checkpoint binding")
    observation = checkpoint["independent_observation"]
    exact_fields(
        observation,
        ("sha256", "byte_length", "hash_scope", "method"),
        "checkpoint observation",
    )
    if observation != {
        "sha256": PUBLIC_SHA256,
        "byte_length": 79_462_305,
        "hash_scope": "FULL_FILE",
        "method": "INDEPENDENT_SHA256_READ",
    }:
        raise ValueError("checkpoint bytes not independently observed in full")
    rows = manifest["sources"]
    if (
        not isinstance(rows, list)
        or len(rows) != 2
        or not isinstance(receipts, list)
        or len(receipts) != 7
    ):
        raise ValueError(
            "complete MPTrj/sAlex evidence and seven independent receipts required"
        )
    context = evidence_sha256(manifest)
    required = [
        ("checkpoint_observer", "checkpoint_rehashed", evidence_sha256(observation))
    ]
    selected_tokens = set()
    dataset_seen = set()
    frame_seen = set()
    source_counts = {}
    for source in rows:
        exact_fields(
            source,
            (
                "dataset_id",
                "source_observation",
                "selected_frame_count",
                "selected_frames_sha256",
                "preprocessing_sha256",
                "energy_labels_sha256",
            ),
            "source lineage",
        )
        dataset = source["dataset_id"]
        if dataset not in SOURCES or dataset in dataset_seen:
            raise ValueError("duplicate/unsupported source dataset")
        dataset_seen.add(dataset)
        observed = source["source_observation"]
        exact_fields(
            observed,
            ("sha256", "byte_length", "hash_scope", "method"),
            "source observation",
        )
        digest(observed["sha256"])
        integer(observed["byte_length"], high=10**15)
        if (
            observed["hash_scope"] != "FULL_FILE"
            or observed["method"] != "INDEPENDENT_SHA256_READ"
        ):
            raise ValueError(
                "prefix/dataset-family observation is not complete original source identity"
            )
        count = integer(source["selected_frame_count"], high=100_000)
        for kind, key in (
            ("frames", "selected_frames_sha256"),
            ("preprocessing", "preprocessing_sha256"),
            ("energy_labels", "energy_labels_sha256"),
        ):
            value = _artifact(artifacts, source[key])
            shared = (
                "schema_version",
                "checkpoint_sha256",
                "source_sha256",
                "dataset_id",
            )
            extra = (
                ("selection_complete", "frames")
                if kind == "frames"
                else ("rule", "publisher_evidence_revision")
                if kind == "preprocessing"
                else ("labels", "publisher_evidence_revision")
            )
            exact_fields(value, shared + extra, kind)
            if (
                value["schema_version"] != "rhombus-checkpoint-" + kind + "-v1"
                or value["checkpoint_sha256"] != PUBLIC_SHA256
                or value["source_sha256"] != observed["sha256"]
                or value["dataset_id"] != dataset
            ):
                raise ValueError("selected artifact checkpoint/source binding mismatch")
            if kind == "frames":
                frames = value["frames"]
                if (
                    value["selection_complete"] is not True
                    or not isinstance(frames, list)
                    or len(frames) != count
                ):
                    raise ValueError("incomplete checkpoint-selected frames")
                dataset_frames = set()
                for frame in frames:
                    exact_fields(
                        frame,
                        ("frame_id", "source_record_id", "material_token"),
                        "selected frame",
                    )
                    frame_id = bounded_text(frame["frame_id"])
                    bounded_text(frame["source_record_id"])
                    token = bounded_text(frame["material_token"])
                    identity = (dataset, "frame", frame_id)
                    source_identity = (dataset, "record", frame["source_record_id"])
                    if identity in frame_seen or source_identity in frame_seen:
                        raise ValueError(
                            "duplicate selected frame/source record identity"
                        )
                    frame_seen.update((identity, source_identity))
                    dataset_frames.add(frame_id)
                    selected_tokens.add(token)
            else:
                bounded_text(value["publisher_evidence_revision"])
                if kind == "preprocessing":
                    bounded_text(value["rule"])
                else:
                    labels = value["labels"]
                    if not isinstance(labels, list) or len(labels) != count:
                        raise ValueError("incomplete training energy-label selection")
                    seen = set()
                    for label in labels:
                        exact_fields(
                            label, ("frame_id", "energy_field", "unit"), "energy label"
                        )
                        frame_id = bounded_text(label["frame_id"])
                        bounded_text(label["energy_field"])
                        if frame_id in seen or label["unit"] != "eV":
                            raise ValueError(
                                "duplicate/unsupported energy-label selection"
                            )
                        seen.add(frame_id)
                    if seen != dataset_frames:
                        raise ValueError("energy labels do not cover selected frames")
        source_counts[dataset] = count
        required.extend(
            [
                ("source_observer", "source_rehashed", evidence_sha256(observed)),
                ("publisher", "selection_attested", evidence_sha256(source)),
                ("lineage_auditor", "selection_audited", evidence_sha256(source)),
            ]
        )
    if dataset_seen != set(SOURCES):
        raise ValueError("missing required source family")
    groups = {}
    receipt_ids = set()
    for receipt, (role, event, subject) in zip(receipts, required):
        authority = verify_evidence_receipt(
            receipt,
            trusted_issuers=trusted_issuers,
            role=role,
            event=event,
            subject_sha256=subject,
            context_sha256=context,
            scope=manifest["scope"],
        )
        if authority.independence_group == manifest["development_group"]:
            raise ValueError(
                "development assertion is not independent training provenance"
            )
        receipt_id = evidence_sha256(receipt)
        if receipt_id in receipt_ids:
            raise ValueError("duplicate training receipt")
        receipt_ids.add(receipt_id)
        groups.setdefault(role, set()).add(authority.independence_group)
    if (
        any(
            groups["publisher"] & groups[role]
            for role in ("checkpoint_observer", "source_observer", "lineage_auditor")
        )
        or groups["lineage_auditor"] & groups["source_observer"]
    ):
        raise ValueError("publisher/observer/auditor independence not established")
    rules_verified = trusted_rule_bindings is not None
    if rules_verified:
        exact_fields(trusted_rule_bindings, SOURCES, "host-approved checkpoint rules")
        for source in rows:
            expected = {
                "preprocessing_sha256": source["preprocessing_sha256"],
                "energy_labels_sha256": source["energy_labels_sha256"],
            }
            if trusted_rule_bindings[source["dataset_id"]] != expected:
                raise ValueError("unsupported preprocessing/energy-label rule binding")
    external = manifest["scope"] == "EXTERNAL"
    return {
        "schema_version": "rhombus-training-lineage-verification-v1",
        "manifest_sha256": context,
        "checkpoint_publisher_reported_sha256": PUBLIC_SHA256,
        "checkpoint_independent_observation_authenticated": external,
        "full_source_observations_authenticated": external,
        "selected_frame_artifacts_verified": True,
        "selected_frame_counts": source_counts,
        "checkpoint_bound_rules_authenticated": external and rules_verified,
        "ready_for_membership_audit": external and rules_verified,
        "exact_training_frames_attested": False,
        "scientific_verdict": "INDETERMINATE",
        "exposure_claim_authorized": False,
        "unseen_generalization_authorized": False,
        "status": "INDEPENDENT_REVIEW_PACKAGE_AUTHENTICATED"
        if external
        else "SYNTHETIC_CHAIN_ONLY_UNATTESTED",
        "blockers": ["SEPARATE_SCIENTIFIC_MEMBERSHIP_AUDIT_REQUIRED"]
        + ([] if external else ["SYNTHETIC_METADATA_NOT_REAL_TRAINING_PROVENANCE"])
        + (
            []
            if rules_verified
            else ["CHECKPOINT_PREPROCESSING_LABEL_RULES_UNATTESTED"]
        ),
    }


def audit_verified_training_overlap(
    *,
    manifest,
    artifacts,
    receipts,
    trusted_issuers,
    evaluation_material_tokens,
    trusted_rule_bindings=None,
):
    verified = verify_training_lineage_manifest(
        manifest=manifest,
        artifacts=artifacts,
        receipts=receipts,
        trusted_issuers=trusted_issuers,
        trusted_rule_bindings=trusted_rule_bindings,
    )
    if not verified["ready_for_membership_audit"]:
        raise ValueError("training selection not independently authenticated")
    if (
        not isinstance(evaluation_material_tokens, list)
        or len(evaluation_material_tokens) > 100_000
    ):
        raise ValueError("invalid evaluation token list")
    for token in evaluation_material_tokens:
        bounded_text(token)
    if len(set(evaluation_material_tokens)) != len(evaluation_material_tokens):
        raise ValueError("duplicate evaluation material")
    trained = {
        row["material_token"]
        for source in manifest["sources"]
        for row in _artifact(artifacts, source["selected_frames_sha256"])["frames"]
    }
    return {
        "overlapping_material_tokens": sorted(
            trained & set(evaluation_material_tokens)
        ),
        "identity_scheme": manifest["identity_scheme"],
        "lineage_manifest_sha256": verified["manifest_sha256"],
        "scope": manifest["scope"],
        "unseen_generalization_authorized": False,
        "scientific_qualification_authorized": False,
    }
