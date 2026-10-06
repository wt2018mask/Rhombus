"""External sealed v2 qualification-cohort manifest tests."""
from dataclasses import replace
import json
from pathlib import Path

import pytest

from rudeus.science.known_material_b3_split import load_b3_split_freeze
from rudeus.science.known_material_qualification_cohort import (
    load_qualification_cohort_repair_plan,
)
from rudeus.science.known_material_qualification_manifest import (
    SEALED_QUALIFICATION_MANIFEST_VERSION,
    SealedQualificationCohortManifest,
    load_external_sealed_qualification_manifest,
    validate_sealed_qualification_manifest,
)
from scripts.benchmark.validate_sealed_qualification_cohort import (
    validate_external_manifest,
)


ROOT = Path(".")
DATA_ROOT = Path("data/benchmarks/known_material")


def _plan():
    return load_qualification_cohort_repair_plan(
        DATA_ROOT / "qualification_cohort_repair_plan_v1.json"
    )


def _v1_freeze():
    return load_b3_split_freeze(DATA_ROOT / "b3_split_freeze_v1.json")


def _member(
    *,
    benchmark_id: str,
    material_identity: str,
    truth_class: str,
    digit: str,
):
    return {
        "benchmark_id": benchmark_id,
        "split": "HELD_OUT",
        "material_identity": material_identity,
        "truth_class": truth_class,
        "truth_bundle_hash": digit * 64,
        "literature_evidence_hashes": ((hex((int(digit, 16) + 1) % 16)[2:]) * 64,),
        "expected_stage_outcomes_hash": (hex((int(digit, 16) + 2) % 16)[2:]) * 64,
        "structure_hash": (hex((int(digit, 16) + 3) % 16)[2:]) * 64,
        "source_artifact_hashes": ((hex((int(digit, 16) + 4) % 16)[2:]) * 64,),
    }


def _manifest_dict():
    plan = _plan()
    return {
        "manifest_version": SEALED_QUALIFICATION_MANIFEST_VERSION,
        "qualification_cohort_version": plan.qualification_cohort_version,
        "repair_plan_hash": plan.content_hash,
        "benchmark_protocol_hash": plan.benchmark_protocol_hash,
        "members": [
            _member(
                benchmark_id="km-v2pos001",
                material_identity="test-only-v2-positive",
                truth_class="POSITIVE",
                digit="1",
            ),
            _member(
                benchmark_id="km-v2neg001",
                material_identity="test-only-v2-negative",
                truth_class="NEGATIVE",
                digit="5",
            ),
            _member(
                benchmark_id="km-v2bor001",
                material_identity="test-only-v2-borderline",
                truth_class="BORDERLINE",
                digit="9",
            ),
        ],
    }


def _manifest():
    return SealedQualificationCohortManifest.from_dict(_manifest_dict())


def test_external_sealed_manifest_validates_to_secret_free_summary(tmp_path):
    path = tmp_path / "sealed-v2-manifest.json"
    payload = _manifest_dict()
    path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_external_sealed_qualification_manifest(path, repo_root=ROOT)
    validation = validate_sealed_qualification_manifest(
        loaded,
        repair_plan=_plan(),
        contaminated_v1_freeze=_v1_freeze(),
    )
    cli_validation = validate_external_manifest(
        repo_root=ROOT,
        manifest_path=path,
    )

    assert validation == cli_validation
    assert validation.member_count == 3
    assert validation.role_counts == {
        "POSITIVE": 1,
        "NEGATIVE": 1,
        "BORDERLINE": 1,
    }
    assert validation.external_sealed_state_validated is True
    assert validation.held_out_execution_authorized is False
    assert validation.production_search_authorized is False

    public_summary = json.dumps(validation.to_dict(), sort_keys=True)
    for member in loaded.members:
        assert member.benchmark_id not in public_summary
        assert member.material_identity not in public_summary
        assert member.truth_bundle_hash not in public_summary
        assert member.structure_hash not in public_summary


def test_external_manifest_path_must_remain_outside_repository():
    with pytest.raises(ValueError, match="outside the repository"):
        load_external_sealed_qualification_manifest(
            DATA_ROOT / "must-not-store-v2-sealed-manifest.json",
            repo_root=ROOT,
        )


def test_replacement_manifest_rejects_any_public_v1_material_identity():
    manifest = _manifest()
    v1_freeze = _v1_freeze()
    members = list(manifest.members)
    members[0] = replace(
        members[0],
        material_identity=v1_freeze.members[0].benchmark_id,
    )
    contaminated = replace(manifest, members=tuple(members))

    with pytest.raises(ValueError, match="reuses public v1 material identity"):
        validate_sealed_qualification_manifest(
            contaminated,
            repair_plan=_plan(),
            contaminated_v1_freeze=v1_freeze,
        )


def test_replacement_manifest_fails_closed_on_missing_role_quota():
    payload = _manifest_dict()
    payload["members"] = payload["members"][:2]
    manifest = SealedQualificationCohortManifest.from_dict(payload)

    with pytest.raises(ValueError, match="role quotas"):
        validate_sealed_qualification_manifest(
            manifest,
            repair_plan=_plan(),
            contaminated_v1_freeze=_v1_freeze(),
        )


def test_replacement_manifest_must_bind_canonical_repair_plan():
    manifest = replace(_manifest(), repair_plan_hash="0" * 64)

    with pytest.raises(ValueError, match="canonical repair plan"):
        validate_sealed_qualification_manifest(
            manifest,
            repair_plan=_plan(),
            contaminated_v1_freeze=_v1_freeze(),
        )
