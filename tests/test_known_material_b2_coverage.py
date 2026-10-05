"""B2 closure-coverage audit tests."""
import json
from pathlib import Path

import pytest

from rudeus.science.known_material_artifact_curation import (
    load_registry,
    load_retention_index,
)
from rudeus.science.known_material_b2_coverage import (
    B2_EXTERNAL_ASSESSMENT_VERSION,
    CoverageState,
    ExternalAssessmentEntry,
    ExternalAssessmentLedger,
    TRUTH_BUNDLE_CATALOG_VERSION,
    TruthBundleAvailability,
    TruthBundleCatalog,
    TruthBundleCatalogEntry,
    build_b2_coverage_audit,
    load_cataloged_truth_bundles,
    load_external_assessment_ledger,
    load_truth_bundle_catalog,
)
from rudeus.science.known_material_failure_control import (
    FailureControlExpectedBehavior,
    FailureControlKind,
    load_failure_control_plan,
)
from rudeus.science.known_material_failure_control_execution import (
    run_failure_control_plan,
)
from rudeus.science.known_material_representation_policy import (
    load_representation_evidence_ledger,
    load_representation_policy_registry,
)
from rudeus.science.known_material_structure_resolution import (
    ResolutionStatus,
    load_structure_resolution_manifest,
    resolve_structure_manifest,
)
from rudeus.science.known_material_universe import MaterialUniverseIntake


ROOT = Path("data/benchmarks/known_material")


def load_universe():
    return MaterialUniverseIntake.from_dict(
        json.loads(
            (ROOT / "b2_universe_intake_v1.json").read_text(encoding="utf-8")
        )
    )


def load_structure_ledger():
    return resolve_structure_manifest(
        load_structure_resolution_manifest(
            ROOT / "structure_resolution_manifest_v1.json"
        ),
        load_registry(ROOT / "artifact_registry_v1.json"),
        load_retention_index(ROOT / "artifact_retention_index_v1.json"),
        policy_registry=load_representation_policy_registry(
            ROOT / "representation_policy_registry_v1.json"
        ),
        policy_evidence_ledger=load_representation_evidence_ledger(
            ROOT / "representation_evidence_ledger_v1.json"
        ),
    )


def canonical_audit():
    catalog = load_truth_bundle_catalog(ROOT / "truth_bundle_catalog_v1.json")
    failure_control_plan = load_failure_control_plan(
        ROOT / "failure_control_plan_v1.json"
    )
    return build_b2_coverage_audit(
        load_universe(),
        load_structure_ledger(),
        truth_bundles=load_cataloged_truth_bundles(
            catalog,
            repo_root=Path("."),
        ),
        external_assessments=load_external_assessment_ledger(
            ROOT / "b2_external_assessment_v1.json"
        ),
        failure_control_plan=failure_control_plan,
        failure_control_report=run_failure_control_plan(
            failure_control_plan,
            repo_root=Path("."),
        ),
    )


def test_canonical_truth_catalog_contains_curated_li3n_bundle():
    catalog = load_truth_bundle_catalog(ROOT / "truth_bundle_catalog_v1.json")
    assert catalog.catalog_version == TRUTH_BUNDLE_CATALOG_VERSION
    assert tuple(entry.material_key for entry in catalog.entries) == (
        "li2s-microcrystalline",
        "li3n-crystalline",
        "lialo2-gamma",
    )
    bundles = load_cataloged_truth_bundles(catalog, repo_root=Path("."))
    assert set(bundles) == {
        "li2s-microcrystalline",
        "li3n-crystalline",
        "lialo2-gamma",
    }
    assert bundles["li3n-crystalline"].curation_state == "CURATED_FOR_B2"
    assert bundles["li2s-microcrystalline"].curation_state == "CURATED_FOR_B2"
    assert bundles["lialo2-gamma"].curation_state == "CURATED_FOR_B2"


def test_truth_catalog_paths_are_confined():
    with pytest.raises(ValueError, match="escapes"):
        TruthBundleCatalogEntry(
            material_key="m1",
            bundle_path="../../outside.json",
            file_sha256="1" * 64,
            bundle_content_hash="2" * 64,
        )


def test_cataloged_bundle_must_physically_exist(tmp_path):
    entry = TruthBundleCatalogEntry(
        material_key="m1",
        bundle_path=(
            "data/benchmarks/known_material/truth_bundles/m1.json"
        ),
        file_sha256="1" * 64,
        bundle_content_hash="2" * 64,
    )
    catalog = TruthBundleCatalog(
        catalog_version=TRUTH_BUNDLE_CATALOG_VERSION,
        entries=(entry,),
    )
    with pytest.raises(ValueError, match="is missing"):
        load_cataloged_truth_bundles(catalog, repo_root=tmp_path)


def test_external_assessments_are_data_driven_and_exposure_is_accounted():
    ledger = load_external_assessment_ledger(
        ROOT / "b2_external_assessment_v1.json"
    )
    assert ledger.ledger_version == B2_EXTERNAL_ASSESSMENT_VERSION
    states = {entry.assessment_id: entry.state for entry in ledger.entries}
    assert states == {
        "mlip_exposure_accounting": CoverageState.SATISFIED.value,
        "sample_size_power_rule": CoverageState.UNSATISFIED.value,
    }


def test_external_assessment_ledger_requires_all_required_axes():
    only_one = ExternalAssessmentEntry(
        assessment_id="mlip_exposure_accounting",
        state=CoverageState.UNASSESSED.value,
        rationale=("not audited",),
    )
    with pytest.raises(ValueError, match="missing required assessments"):
        ExternalAssessmentLedger(
            ledger_version=B2_EXTERNAL_ASSESSMENT_VERSION,
            entries=(only_one,),
        )


def test_satisfied_external_assessment_requires_evidence_refs():
    with pytest.raises(ValueError, match="requires evidence refs"):
        ExternalAssessmentEntry(
            assessment_id="mlip_exposure_accounting",
            state=CoverageState.SATISFIED.value,
            evidence_refs=(),
        )


def test_canonical_b2_audit_reports_actual_current_gaps():
    audit = canonical_audit()

    assert len(audit.material_records) == 9
    assert audit.role_counts == {
        "BORDERLINE": 3,
        "NEGATIVE": 2,
        "POSITIVE": 4,
    }
    assert audit.chemistry_family_count == 8
    structure_by_material = {
        item.material_key: item.status for item in load_structure_ledger().cases
    }
    li2s_ready = (
        structure_by_material["li2s-microcrystalline"]
        == ResolutionStatus.READY.value
    )
    li3n_ready = (
        structure_by_material["li3n-crystalline"]
        == ResolutionStatus.READY.value
    )
    gamma_ready = (
        structure_by_material["lialo2-gamma"]
        == ResolutionStatus.READY.value
    )
    tllzo_ready = (
        structure_by_material["llzo-tetragonal-undoped"]
        == ResolutionStatus.READY.value
    )
    expected_structure_counts = {
        ResolutionStatus.BLOCKED_POLICY.value: 1,
        ResolutionStatus.READY.value:
            int(li2s_ready) + int(li3n_ready) + int(gamma_ready)
            + int(tllzo_ready),
        ResolutionStatus.BLOCKED_MISSING_ARTIFACT.value:
            int(not li2s_ready) + int(not li3n_ready) + int(not gamma_ready)
            + int(not tllzo_ready),
    }
    expected_structure_counts = {
        key: value for key, value in expected_structure_counts.items() if value
    }
    assert audit.structure_status_counts == expected_structure_counts
    assert audit.truth_bundle_availability_counts == {
        TruthBundleAvailability.CURATED_FOR_B2.value: 3,
        TruthBundleAvailability.MISSING.value: 6,
    }
    assert audit.p2_5_self_diffusion_truth_count == 2
    assert audit.failure_control_requirement_count == 3
    assert audit.executable_failure_control_count == 3
    assert audit.failure_control_kind_counts == {
        FailureControlKind.INVALID_SCIENTIFIC_INPUT.value: 1,
        FailureControlKind.MODEL_DOMAIN_UNSUPPORTED.value: 1,
        FailureControlKind.REPRESENTATION_UNSUPPORTED.value: 1,
    }
    assert audit.executable_failure_control_ids == (
        "fc:p0:synthetic-overlap-v1",
        "fc:representation:llzo-fractional-occupancy-v1",
        "fc:model-domain:medium-mpa-0-v1",
    )
    assert audit.failure_control_pass_count == 3
    assert audit.failure_control_failed_ids == ()
    assert audit.failure_control_error_ids == ()
    assert audit.failure_control_expected_behaviors == {
        FailureControlKind.INVALID_SCIENTIFIC_INPUT.value:
            FailureControlExpectedBehavior.REJECT_INPUT.value,
        FailureControlKind.REPRESENTATION_UNSUPPORTED.value:
            FailureControlExpectedBehavior.BLOCK_BEFORE_EXECUTION.value,
        FailureControlKind.MODEL_DOMAIN_UNSUPPORTED.value:
            FailureControlExpectedBehavior.RETURN_UNKNOWN_OR_INDETERMINATE.value,
    }
    assert audit.failure_control_target_stages[
        FailureControlKind.INVALID_SCIENTIFIC_INPUT.value
    ] == ("P0",)
    assert "P2.5" in audit.failure_control_target_stages[
        FailureControlKind.MODEL_DOMAIN_UNSUPPORTED.value
    ]
    assert audit.missing_failure_control_kinds == ()
    assert audit.scorable_stage_counts["P0"] == 2
    assert audit.scorable_stage_counts["P2.5"] == 2
    assert all(
        value == 0
        for stage, value in audit.scorable_stage_counts.items()
        if stage not in {"P0", "P2.5"}
    )

    assert audit.checks["positive_control_present"] == CoverageState.SATISFIED.value
    assert audit.checks["negative_control_present"] == CoverageState.SATISFIED.value
    assert audit.checks["borderline_control_present"] == CoverageState.SATISFIED.value
    assert (
        audit.checks["failure_control_role_present_in_universe"]
        == CoverageState.UNSATISFIED.value
    )
    assert (
        audit.checks["failure_control_contract_defined"]
        == CoverageState.SATISFIED.value
    )
    assert (
        audit.checks["failure_control_executable_coverage"]
        == CoverageState.SATISFIED.value
    )
    assert (
        audit.checks["failure_control_executions_clean"]
        == CoverageState.SATISFIED.value
    )
    assert (
        audit.checks["chemistry_family_diversity_present"]
        == CoverageState.SATISFIED.value
    )
    assert (
        audit.checks["executable_structure_case_present"]
        == CoverageState.SATISFIED.value
    )
    assert (
        audit.checks["curated_truth_bundle_present"]
        == CoverageState.SATISFIED.value
    )
    assert (
        audit.checks["p2_5_self_diffusion_truth_present"]
        == CoverageState.SATISFIED.value
    )
    assert (
        audit.checks["mlip_exposure_accounting"]
        == CoverageState.SATISFIED.value
    )
    assert (
        audit.checks["sample_size_power_rule"]
        == CoverageState.UNSATISFIED.value
    )

    expected_blockers = {
        "SAMPLE_SIZE_POWER_RULE_UNSATISFIED",
    }
    assert set(audit.global_blockers) == expected_blockers
    assert audit.b3_split_authorized is False


def test_canonical_llzo_is_distinguished_from_unresolved_universe_members():
    audit = canonical_audit()
    by_key = {record.material_key: record for record in audit.material_records}

    llzo = by_key["llzo-cubic-al-stabilized"]
    assert llzo.structure_case_statuses == (
        ResolutionStatus.BLOCKED_POLICY.value,
    )
    assert "STRUCTURE_BLOCKED_POLICY" in llzo.blocker_codes
    assert "NO_STRUCTURE_RESOLUTION_SPEC" not in llzo.blocker_codes

    tllzo = by_key["llzo-tetragonal-undoped"]
    assert tllzo.proposed_role == "BORDERLINE"
    assert tllzo.structure_case_statuses in {
        (ResolutionStatus.BLOCKED_MISSING_ARTIFACT.value,),
        (ResolutionStatus.READY.value,),
    }
    assert "NO_STRUCTURE_RESOLUTION_SPEC" not in tllzo.blocker_codes
    assert tllzo.truth_bundle_availability == (
        TruthBundleAvailability.MISSING.value
    )
    assert tllzo.scorable_stages == ()

    li2s = by_key["li2s-microcrystalline"]
    assert "NO_STRUCTURE_RESOLUTION_SPEC" not in li2s.blocker_codes
    assert li2s.structure_case_statuses in {
        (ResolutionStatus.BLOCKED_MISSING_ARTIFACT.value,),
        (ResolutionStatus.READY.value,),
    }

    li3n = by_key["li3n-crystalline"]
    assert "NO_STRUCTURE_RESOLUTION_SPEC" not in li3n.blocker_codes
    assert li3n.structure_case_statuses == (
        ResolutionStatus.READY.value,
    )
    assert li3n.truth_bundle_availability == (
        TruthBundleAvailability.CURATED_FOR_B2.value
    )
    assert li3n.p2_5_self_diffusion_supported is True
    assert "TRUTH_BUNDLE_MISSING" not in li3n.blocker_codes
    assert "P2_5_SELF_DIFFUSION_TRUTH_NOT_SUPPORTED" not in li3n.blocker_codes

    gamma_lialo2 = by_key["lialo2-gamma"]
    assert gamma_lialo2.proposed_role == "NEGATIVE"
    assert gamma_lialo2.structure_case_statuses in {
        (ResolutionStatus.BLOCKED_MISSING_ARTIFACT.value,),
        (ResolutionStatus.READY.value,),
    }
    assert gamma_lialo2.truth_bundle_availability == (
        TruthBundleAvailability.CURATED_FOR_B2.value
    )
    assert "NO_STRUCTURE_RESOLUTION_SPEC" not in gamma_lialo2.blocker_codes
    assert gamma_lialo2.scorable_stages == ("P0", "P2.5")
    assert gamma_lialo2.p2_5_self_diffusion_supported is True
    assert "TRUTH_BUNDLE_MISSING" not in gamma_lialo2.blocker_codes
    assert "P2_5_SELF_DIFFUSION_TRUTH_NOT_SUPPORTED" not in gamma_lialo2.blocker_codes

    lgps = by_key["lgps-tetragonal-li10gep2s12"]
    assert lgps.structure_case_statuses == ()
    assert "NO_STRUCTURE_RESOLUTION_SPEC" in lgps.blocker_codes


def test_foreign_truth_bundle_key_fails_before_scientific_inference():
    with pytest.raises(ValueError, match="outside B2 universe"):
        build_b2_coverage_audit(
            load_universe(),
            load_structure_ledger(),
            truth_bundles={"not-in-universe": object()},
            external_assessments=load_external_assessment_ledger(
                ROOT / "b2_external_assessment_v1.json"
            ),
            failure_control_plan=load_failure_control_plan(
                ROOT / "failure_control_plan_v1.json"
            ),
            failure_control_report=run_failure_control_plan(
                load_failure_control_plan(
                    ROOT / "failure_control_plan_v1.json"
                ),
                repo_root=Path("."),
            ),
        )
