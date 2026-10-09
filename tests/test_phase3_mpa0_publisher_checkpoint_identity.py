"""Offline evidence scope and tamper tests for upstream MACE-MPA-0 digest."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from rhombus.domain.mpa0_publisher_digest import (
    PUBLIC_SHA256, review_reported_mpa0_checkpoint_identity,
)
from rhombus.domain.mpa0_training_lineage import (
    TrainingDatasetLineageEvidence, assess_mace_mpa0_training_lineage_review,
)

RECORD = Path(__file__).resolve().parents[1] / (
    "data/development/phase3_mpa0_publisher_checkpoint_identity_v1.json"
)


def evidence():
    return json.loads(RECORD.read_text(encoding="utf-8"))


def test_upstream_reported_checkpoint_sha_is_not_training_attestation():
    entry = evidence()
    result = review_reported_mpa0_checkpoint_identity(entry)
    assert len(PUBLIC_SHA256) == 64
    assert result["checkpoint_reported_sha256"] == PUBLIC_SHA256
    assert result["checkpoint_publisher_sha256_found"] is True
    assert result["checkpoint_independently_verified"] is False
    assert all(result[k] is False for k in (
        "exact_training_frames_attested", "mptrj_full_source_verified",
        "exposure_audit_authorized", "empirical_calibration_authorized",
        "unseen_generalization_authorized",
    ))
    assert entry["publisher"]["release_same_digest_asserted_by_upstream"] is True
    assert entry["release"]["github_release_digest_independently_verified"] is False
    assert set(entry["declared_training_families"]) == {"MPTrj", "sAlex"}


@pytest.mark.parametrize(("section", "key", "value"), [
    ("publisher", "reported_model_sha256", "0"*64),
    ("publisher", "commit_sha", "0"*40),
    ("publisher", "source_file", "../unsafe"),
    ("publisher", "release_same_digest_asserted_by_upstream", False),
    ("release", "asset_size_bytes", 42),
    ("release", "github_release_digest_independently_verified", True),
    ("limits_and_claims", "exact_mptrj_training_frames_attested", True),
    ("limits_and_claims", "exposure_audit_authorized", True),
    ("limits_and_claims", "unseen_generalization_authorized", True),
])
def test_wrong_publisher_binding_or_science_promotion_fails_closed(section,key,value):
    d=deepcopy(evidence())
    d[section][key]=value
    with pytest.raises(ValueError):
        review_reported_mpa0_checkpoint_identity(d)


def test_source_family_names_and_fake_full_package_cannot_prove_membership():
    _ = review_reported_mpa0_checkpoint_identity(evidence())
    # Publisher-reported SHA is NOT a locally rehashed frozen checkpoint.
    report = assess_mace_mpa0_training_lineage_review(
        (
            TrainingDatasetLineageEvidence(dataset_id="MPTrj"),
            TrainingDatasetLineageEvidence(
                dataset_id="sAlex",
                exact_source_sha256=(
                    "48eb3664d95331e7fd84bfe1f04f5e741600bffcfb1253334c82dae92cebf1ef"
                ),
            ),
        ),
        checkpoint_sha256=None,
        checkpoint_release_url=evidence()["release"]["url"],
    )
    assert report.ready_for_independent_review is False
    assert report.exact_training_frames_attested is False
    assert "checkpoint full-file SHA256 not independently frozen" in report.blockers
    assert "MPTrj: missing canonical source SHA256" in report.blockers
    assert "sAlex: missing checkpoint-selected frame manifest SHA256" in report.blockers
    assert report.exposure_audit_authorized is False
    assert report.unseen_generalization_authorized is False
