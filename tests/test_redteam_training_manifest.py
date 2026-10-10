from rhombus.domain.training_manifest import verify_training_lineage_manifest


def test_fabricated_metadata_cannot_attest_training_frames():
    import pytest

    with pytest.raises(ValueError):
        verify_training_lineage_manifest(
            manifest={}, artifacts={}, receipts=[], trusted_issuers={}
        )


import copy
import hashlib
import json
import pytest

from rhombus.domain.training_manifest import audit_verified_training_overlap
from rhombus.domain.mpa0_publisher_digest import PUBLIC_SHA256
from rhombus.evidence.receipts import canonical_bytes
from tests.redteam_batch_b_fixtures import lineage_fixture, reattest_lineage


def mutate_artifact(value, source, key, change):
    artifact = json.loads(value["artifacts"][source[key]])
    change(artifact)
    raw = canonical_bytes(artifact)
    sha = hashlib.sha256(raw).hexdigest()
    value["artifacts"][sha] = raw
    source[key] = sha
    reattest_lineage(value)


def test_complete_synthetic_provenance_does_not_authorize_real_membership():
    result = verify_training_lineage_manifest(**lineage_fixture())
    assert result["checkpoint_publisher_reported_sha256"] == PUBLIC_SHA256
    assert result["selected_frame_counts"] == {"MPTrj": 1, "sAlex": 1}
    assert not result["checkpoint_independent_observation_authenticated"]
    assert not result["ready_for_membership_audit"]
    assert not result["exact_training_frames_attested"]
    assert not result["unseen_generalization_authorized"]


@pytest.mark.parametrize(
    "mutation",
    [
        "prefix",
        "wrong_model",
        "wrong_size",
        "missing_family",
        "duplicate_family",
        "missing_artifact",
        "changed_bytes",
        "wrong_checkpoint_binding",
        "wrong_source_binding",
        "duplicate_frame",
        "incomplete_frames",
        "duplicate_labels",
        "missing_label",
        "unsupported_label",
        "fabricated_signature",
        "scope_promotion",
        "unsupported_schema",
        "shared_publisher_auditor",
        "missing_receipt",
        "source_digest",
    ],
)
def test_training_manifest_adversarial_rejection(mutation):
    value = lineage_fixture()
    manifest = value["manifest"]
    source = manifest["sources"][0]
    if mutation == "prefix":
        source["source_observation"]["hash_scope"] = "PREFIX_1MIB"
    elif mutation == "wrong_model":
        manifest["checkpoint"]["publisher_reported_sha256"] = "b" * 64
    elif mutation == "wrong_size":
        manifest["checkpoint"]["independent_observation"]["byte_length"] = 1048576
    elif mutation == "missing_family":
        manifest["sources"].pop()
    elif mutation == "duplicate_family":
        manifest["sources"][1] = copy.deepcopy(source)
    elif mutation == "source_digest":
        source["source_observation"]["sha256"] = "not-a-sha"
    elif mutation == "missing_artifact":
        del value["artifacts"][source["selected_frames_sha256"]]
    elif mutation == "changed_bytes":
        value["artifacts"][source["selected_frames_sha256"]] += b" "
    elif mutation == "wrong_checkpoint_binding":
        mutate_artifact(
            value,
            source,
            "selected_frames_sha256",
            lambda a: a.update(checkpoint_sha256="b" * 64),
        )
    elif mutation == "wrong_source_binding":
        mutate_artifact(
            value,
            source,
            "preprocessing_sha256",
            lambda a: a.update(source_sha256="b" * 64),
        )
    elif mutation == "duplicate_frame":
        source["selected_frame_count"] = 2
        mutate_artifact(
            value,
            source,
            "selected_frames_sha256",
            lambda a: a["frames"].append(copy.deepcopy(a["frames"][0])),
        )
    elif mutation == "incomplete_frames":
        mutate_artifact(
            value,
            source,
            "selected_frames_sha256",
            lambda a: a.update(selection_complete=False),
        )
    elif mutation == "duplicate_labels":
        mutate_artifact(
            value,
            source,
            "energy_labels_sha256",
            lambda a: a["labels"].append(copy.deepcopy(a["labels"][0])),
        )
    elif mutation == "missing_label":
        mutate_artifact(
            value, source, "energy_labels_sha256", lambda a: a.update(labels=[])
        )
    elif mutation == "unsupported_label":
        mutate_artifact(
            value,
            source,
            "energy_labels_sha256",
            lambda a: a["labels"][0].update(unit="arbitrary"),
        )
    elif mutation == "unsupported_schema":
        manifest["schema_version"] = "unknown"
    elif mutation == "shared_publisher_auditor":
        from dataclasses import replace

        value["trusted_issuers"]["auditor"] = replace(
            value["trusted_issuers"]["auditor"],
            independence_group=value["trusted_issuers"]["publisher"].independence_group,
        )
    if mutation not in ("fabricated_signature", "scope_promotion", "missing_receipt"):
        reattest_lineage(value)
    if mutation == "fabricated_signature":
        value["receipts"][2]["signature"] = "a" * 128
    if mutation == "missing_receipt":
        value["receipts"].pop()
    if mutation == "scope_promotion":
        manifest["scope"] = "EXTERNAL"
        reattest_lineage(value)
    with pytest.raises(ValueError):
        verify_training_lineage_manifest(**value)


def test_synthetic_selection_cannot_drive_authoritative_overlap():
    with pytest.raises(ValueError, match="not independently authenticated"):
        audit_verified_training_overlap(
            **lineage_fixture(),
            evaluation_material_tokens=["synthetic-training-material-0"],
        )


def test_unknown_preprocessing_and_label_rules_remain_blocked_even_with_authenticated_assertions():
    # EXTERNAL here simulates a host-policy branch using TEST_ONLY keys.
    value = lineage_fixture(scope="EXTERNAL")
    result = verify_training_lineage_manifest(**value)
    assert not result["ready_for_membership_audit"]
    rules = {
        source["dataset_id"]: {
            "preprocessing_sha256": source["preprocessing_sha256"],
            "energy_labels_sha256": source["energy_labels_sha256"],
        }
        for source in value["manifest"]["sources"]
    }
    rules["MPTrj"]["preprocessing_sha256"] = "b" * 64
    with pytest.raises(ValueError, match="unsupported preprocessing"):
        verify_training_lineage_manifest(**value, trusted_rule_bindings=rules)


def test_host_approved_synthetic_rule_fixtures_exercise_overlap_without_qualification():
    value = lineage_fixture(scope="EXTERNAL")  # Test keys are never production anchors.
    rules = {
        source["dataset_id"]: {
            "preprocessing_sha256": source["preprocessing_sha256"],
            "energy_labels_sha256": source["energy_labels_sha256"],
        }
        for source in value["manifest"]["sources"]
    }
    report = audit_verified_training_overlap(
        **value,
        trusted_rule_bindings=rules,
        evaluation_material_tokens=[
            "synthetic-training-material-0",
            "synthetic-unseen-material",
        ],
    )
    assert report["overlapping_material_tokens"] == ["synthetic-training-material-0"]
    assert not report["scientific_qualification_authorized"]
    assert not report["unseen_generalization_authorized"]
