import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from rudeus.execution.kaggle_backend import _valid_kernel_identity


_RUNNER_PATH = Path(__file__).resolve().parents[1] / "scripts/kaggle/run_generic_mobile_ion_e2e.py"
_RUNNER_SPEC = importlib.util.spec_from_file_location("_m6b_generic_runner_test", _RUNNER_PATH)
runner = importlib.util.module_from_spec(_RUNNER_SPEC)
sys.modules[_RUNNER_SPEC.name] = runner
_RUNNER_SPEC.loader.exec_module(runner)
DRIVER = runner._hardened_e2e_driver()


def _panel_row(parent_id, family, seed, index):
    pair_id = hashlib.sha256(json.dumps({
        "parent_id": parent_id, "sigma_A_provisional": DRIVER.M6B_SIGMA,
        "base_seed": seed,
    }, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    baseline_identity = f"baseline-{index}-{seed}"
    local_identity = f"local-{index}-{seed}"
    baseline = {
        "status": "GENERATED", "generated": True, "operator_name": "mobile-ion-displace",
        "operator_version": "mobile-ion-displace-v2", "operator_rng_identity": baseline_identity,
        "operator_rng_seed": index * 100 + seed, "child_material_id": f"base-{index}-{seed}",
        "child_structure_dict": {"sites": [index, seed]}, "novelty_tag": "novel",
        "novelty_matcher_version": "novelty-matcher-v2-same-cell", "p0_state": "PLAUSIBLE",
        "p0_plausible": True, "p0_neutrality_ok": True, "p0_pauling_ok": True,
        "p0_geometry_ok": True, "geometry_ok": True, "useful": True,
    }
    local = {
        "status": "ACCEPTED", "generated": True,
        "operator_name": DRIVER.M6A_OPERATOR_NAME,
        "operator_version": DRIVER.M6A_OPERATOR_VERSION,
        "operator_rng_identity": local_identity, "operator_rng_seed": index * 200 + seed,
        "child_material_id": f"local-{index}-{seed}",
        "child_structure_dict": {"sites": [index, seed, "d8"]}, "novelty_tag": "novel",
        "novelty_matcher_version": "novelty-matcher-v2-same-cell", "p0_state": "PLAUSIBLE",
        "p0_plausible": True, "p0_neutrality_ok": True, "p0_pauling_ok": True,
        "p0_geometry_ok": True, "geometry_ok": False, "useful": True,
    }
    return {
        "parent_id": parent_id, "chemical_family": family,
        "parent_source_structure_sha256": f"{index:064x}",
        "target_species": "Li", "sigma_A_provisional": DRIVER.M6B_SIGMA,
        "diagnostic_config_hash": DRIVER.M6B_CONFIG_IDENTITY, "base_seed": seed,
        "pair_id": pair_id, "pair_rng_identity": baseline_identity,
        "pair_rng_seed": baseline["operator_rng_seed"],
        "gaussian_local_rng_identity": local_identity,
        "gaussian_local_rng_seed": local["operator_rng_seed"],
        "arms": {"BASELINE_GAUSSIAN": baseline, "GAUSSIAN_LOCAL_D8": local},
    }


def _valid_m6b_panel():
    rows = []
    for index, (parent, family) in enumerate(zip(DRIVER.M6B_PARENT_IDS, DRIVER.M6B_PARENT_FAMILIES)):
        for seed in DRIVER.M6B_SEEDS:
            rows.append(_panel_row(parent, family, seed, index))
    details = [
        {"id": "BASELINE_GAUSSIAN", "operator_name": "mobile-ion-displace",
         "operator_version": "mobile-ion-displace-v2", "budget": None},
        {"id": "GAUSSIAN_LOCAL_D8", "operator_name": DRIVER.M6A_OPERATOR_NAME,
         "operator_version": DRIVER.M6A_OPERATOR_VERSION, "budget": 8},
    ]
    metadata = {
        "ordered_parent_ids": list(DRIVER.M6B_PARENT_IDS),
        "parent_chemical_families": list(DRIVER.M6B_PARENT_FAMILIES),
        "selection_rule": DRIVER.M6B_SELECTION_RULE,
        "ordered_cohort_identity": hashlib.sha256(json.dumps(
            list(DRIVER.M6B_PARENT_IDS), ensure_ascii=False, separators=(",", ":"),
        ).encode()).hexdigest(),
        "excluded_m6a_parent_ids": list(DRIVER.M6A_PARENT_IDS),
        "version_9_freeze_sha256": DRIVER.M6A_VERSION_9_FREEZE_SHA256,
        "version_9_panel_sha256": DRIVER.M6A_VERSION_9_PANEL_SHA256,
        "mobile_ion": "Li", "sigma_values_A_provisional": [DRIVER.M6B_SIGMA],
        "base_seeds": list(DRIVER.M6B_SEEDS),
        "diagnostic_config_hash": DRIVER.M6B_CONFIG_IDENTITY,
        "configurations": ["BASELINE_GAUSSIAN", "GAUSSIAN_LOCAL_D8"],
        "include_bounded_clearance": False,
        "gaussian_local_direction_budgets": [8],
        "configuration_details": details,
        "novelty_matcher_version": "novelty-matcher-v2-same-cell",
        "source_structure_hashes": [f"{i:064x}" for i in range(15)],
    }
    authorization = {name: False for name in (
        "scheduler_activation", "p1_eligibility", "operator_superiority",
        "automatic_promotion", "downstream_diffusion_claim", "threshold_modification",
    )}
    return {
        "schema_version": "candidate-supply-v2-operator-tournament-v1",
        "artifact_type": "OBSERVATIONAL_DIAGNOSTIC", "metadata": metadata,
        "authorization": authorization, "activation_authorized": False,
        "p1_eligibility_authorized": False, "downstream_scientific_claims_authorized": False,
        "rows": rows, "summary": {"test": "recomputed"},
    }


def test_m6b_selection_reproduces_family_strata_and_excludes_m6a():
    artifacts = runner._m6b_frozen_inputs(DRIVER)
    assert len(artifacts) == 2
    assert len(DRIVER.M6B_PARENT_IDS) == 15
    assert set(DRIVER.M6B_PARENT_IDS).isdisjoint(DRIVER.M6A_PARENT_IDS)
    assert [DRIVER.M6B_PARENT_FAMILIES.count(family) for family in
            ("halide", "other", "oxide", "oxyhalide", "sulfide")] == [3] * 5


def test_run_scoped_kernel_identity_is_narrowly_validated():
    assert _valid_kernel_identity("wt2018mask/rhombus-mobile-ion-e2e")
    assert _valid_kernel_identity("wt2018mask/rhombus-m6b-0123456789abcdef")
    assert not _valid_kernel_identity("wt2018mask/rhombus-m6b-latest")
    assert not _valid_kernel_identity("other/rhombus-m6b-0123456789abcdef")


def test_m6b_pre_registration_is_hash_bound_into_prepared_task(tmp_path):
    kernel_identity = "wt2018mask/rhombus-m6b-0123456789abcdef"
    task, bundle = runner._make_task(
        tmp_path, m6b_mode=True, kernel_identity=kernel_identity,
    )
    prereg_bytes = (tmp_path / "m6b-preregistration.json").read_bytes()
    prereg = json.loads(prereg_bytes)
    assert task.config["execution_mode"] == "M6B_PAIRED_DIAGNOSTIC"
    assert task.config["kernel_identity"] == kernel_identity
    assert task.config["preregistration_sha256"] == hashlib.sha256(prereg_bytes).hexdigest()
    assert prereg["parent_selection"]["ordered_parent_ids"] == list(DRIVER.M6B_PARENT_IDS)
    assert prereg["experiment"]["paired_identity_count"] == 45
    assert prereg["experiment"]["arm_observation_count"] == 90
    assert all(value is False for value in prereg["analysis_rules"].values()
               if isinstance(value, bool))
    assert bundle.task_content_hash == task.content_hash


def test_m6b_validator_is_paired_and_observational_not_outcome_gated(monkeypatch):
    import rudeus.generation.mobile_ion_diagnostic as diagnostic

    monkeypatch.setattr(diagnostic, "_tournament_summaries", lambda *args: {"test": "recomputed"})
    panel = _valid_m6b_panel()
    checks = DRIVER.validate_m6b_panel(panel, b"same", b"same")
    assert all(checks.values())
    # D8 geometry failure is retained as an observation, not rejected by the validator.
    assert sum(row["arms"]["GAUSSIAN_LOCAL_D8"]["geometry_ok"] is False
               for row in panel["rows"]) == 45


def test_m6b_validator_rejects_incomplete_pairs_and_nonidentical_passes(monkeypatch):
    import rudeus.generation.mobile_ion_diagnostic as diagnostic

    monkeypatch.setattr(diagnostic, "_tournament_summaries", lambda *args: {"test": "recomputed"})
    panel = _valid_m6b_panel()
    panel["rows"].pop()
    with pytest.raises(DRIVER.ScientificValidationFailure):
        DRIVER.validate_m6b_panel(panel, b"pass1", b"pass2")


def test_future_m6b_writer_emits_required_ordered_cohort_digest():
    panel = _valid_m6b_panel()
    del panel["metadata"]["ordered_cohort_identity"]
    class Parent:
        def __init__(self, index):
            self.structure = {"index": index}
    # The provenance helper calls the structure hash function; keep the test
    # focused on the emitted digest rather than pymatgen serialization.
    from rudeus.generation import mobile_ion_diagnostic
    original = mobile_ion_diagnostic.structure_sha256
    mobile_ion_diagnostic.structure_sha256 = lambda structure: f"{structure['index']:064x}"
    try:
        DRIVER._m6b_panel_provenance(panel, [Parent(i) for i in range(15)])
    finally:
        mobile_ion_diagnostic.structure_sha256 = original
    assert panel["metadata"]["ordered_cohort_identity"] == hashlib.sha256(json.dumps(
        list(DRIVER.M6B_PARENT_IDS), ensure_ascii=False,
        separators=(",", ":")).encode()).hexdigest()


def test_collection_outputs_retain_protected_sidecar_bytes(tmp_path):
    provider = tmp_path / "provider-output" / "rhombus_mobile_ion_e2e_output"
    provider.mkdir(parents=True)
    expected = {
        "mobile_ion_displace_e2e_report.json": b'{"report":1}\n',
        "g_candidate_supply_v2_mobile_ion_displace_diagnostic_panel.json": b'{"panel":1}\n',
        "generation-pass-identity-run.json": b'{"pass":1}\n',
        "protected-artifact-state-run.json": b'{"protected":1}\n',
    }
    for name, raw in expected.items():
        (provider / name).write_bytes(raw)
    output = "\n".join((
        f"LOCAL_RESULT_DIR={provider.parent}",
        f"LOCAL_REPORT_PATH={provider / 'mobile_ion_displace_e2e_report.json'}",
        f"LOCAL_ARTIFACT_PATH={provider / 'g_candidate_supply_v2_mobile_ion_displace_diagnostic_panel.json'}",
    ))
    retained_output = runner._retain_collection_outputs(output, tmp_path / "evidence")
    retained = tmp_path / "evidence" / "retrieved-output"
    assert {path.name for path in retained.iterdir()} == set(expected)
    assert {path.name: path.read_bytes() for path in retained.iterdir()} == expected
    assert f"LOCAL_REPORT_PATH={retained / 'mobile_ion_displace_e2e_report.json'}" in retained_output
    assert f"LOCAL_ARTIFACT_PATH={retained / 'g_candidate_supply_v2_mobile_ion_displace_diagnostic_panel.json'}" in retained_output


def test_collection_requires_report_bound_protected_sidecar(tmp_path):
    provider = tmp_path / "provider"
    provider.mkdir()
    report = provider / "mobile_ion_displace_e2e_report.json"
    sidecar = b'{"protected":1}\n'
    sidecar_name = "protected-artifact-state-run.json"
    report.write_text(json.dumps({"protected_artifact_state_artifact": {
        "relative_path": sidecar_name, "sha256": hashlib.sha256(sidecar).hexdigest(),
        "byte_length": len(sidecar)}}), encoding="utf-8")
    output = f"LOCAL_RESULT_DIR={provider}\nLOCAL_REPORT_PATH={report}\n"
    with pytest.raises(Exception, match="sidecar was not downloaded"):
        runner._retain_collection_outputs(output, tmp_path / "missing")
    (provider / sidecar_name).write_bytes(sidecar)
    retained_output = runner._retain_collection_outputs(output, tmp_path / "present")
    assert (tmp_path / "present" / "retrieved-output" / sidecar_name).read_bytes() == sidecar
    assert "LOCAL_REPORT_PATH=" in retained_output
    report.write_text(json.dumps({"protected_artifact_state_artifact": {
        "relative_path": r"..\protected-artifact-state-run.json",
        "sha256": hashlib.sha256(sidecar).hexdigest(), "byte_length": len(sidecar)}}),
        encoding="utf-8")
    with pytest.raises(Exception, match="unsafe protected-state sidecar path"):
        runner._retain_collection_outputs(output, tmp_path / "unsafe")
