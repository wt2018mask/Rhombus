"""Synthetic, target-free negative controls for the 0204 paired budget contract."""
from __future__ import annotations

from copy import deepcopy
import json
import math

import pytest

from rhombus.benchmark.tier_a_preflight import (
    build_metadata_registry, select_train_only_pilot, ZIP_BYTES, ZIP_SHA256,
)
from rhombus.benchmark.tier_a_budget_contract import (
    CAP_FIELDS, PHASES, RECEIPT_SCHEMA, _sha,
    audit_paired_receipts, inspect_budget_draft, make_execution_disabled_budget_draft,
)


def fixtures():
    raw = []
    for index, chem in enumerate(("Li-O", "Li-Na", "F-Li", "Cl-Li", "Li-Mg", "K-Li"), 1):
        raw.append({"material_id": f"mp-{index}",
                    "edge_id": f"mp-{index}_1_0_0_0_0", "chemsys": chem,
                    "has_specific_TM": "False", "published_split": "train"})
    raw.extend([
        {"material_id": "mp-30", "edge_id": "mp-30_1_0_0_0_0", "chemsys": "Li-S",
         "has_specific_TM": "False", "published_split": "val"},
        {"material_id": "mp-40", "edge_id": "mp-40_1_0_0_0_0", "chemsys": "Li-P",
         "has_specific_TM": "False", "published_split": "test"},
    ])
    reg = build_metadata_registry(raw)
    pilot = select_train_only_pilot(reg)
    protocol = {
        "schema_version": "rhombus-0204-tier-a-retrospective-energy-span-protocol-candidate-v1",
        "data_reference": {"owner_supplied_sha256": ZIP_SHA256, "archive_bytes": ZIP_BYTES},
        "decision": {"tier_a_benchmark": "BENCHMARK_NOT_FROZEN",
                     "tier_b": "TIER_B_NOT_FROZEN", "scientific": "SCIENTIFIC_NO_GO_ABSTAIN",
                     "baseline_execution": "NOT_AUTHORIZED", "performance_results": None},
        "candidate_experiment_protocol": {
            "scoring_allowed_now": False, "published_test_targets_remain_sealed": True,
            "decision_policy": {"delta_eV": None, "conditional_risk_if_accepted_zero": None},
            "equal_budget_accounting_draft": {
                "per_arm_per_edge_caps": {"wall_seconds": None, "cpu_seconds": None,
                                          "force_evaluations": None, "peak_rss_MiB": None},
                "total_pilot_caps": {"wall_seconds": None, "cpu_seconds": None,
                                     "number_of_arms": None},
            },
            "model_arms": [
                {"id": "MACE_MP_0_SMALL_PUBLISHER_EXAMPLE", "type": "reference strong MLIP candidate",
                 "checkpoint_sha256": None},
                {"id": "MACE_MPA_0_MEDIUM_RHOMBUS", "type": "reference strong MLIP candidate",
                 "checkpoint_sha256": "75428afe3a1d7d8062e19bcaabd5c433623cabf308242ec9fb493e38604fb638"},
            ],
        },
    }
    return reg, pilot, protocol


def ready_draft():
    reg, pilot, protocol = fixtures()
    draft = make_execution_disabled_budget_draft(reg, pilot, protocol)
    for e in draft["edges"]:
        e["initial_images_sha256"] = _sha(["synthetic-image-only", e["edge_id"]])
    for arm in draft["model_arms"]:
        if arm["checkpoint_sha256"] is None:
            arm["checkpoint_sha256"] = "a" * 64
    draft["neb"].update({"endpoint_fmax_ev_ang": 0.1, "neb_fmax_ev_ang": 0.1,
                         "endpoint_max_steps": 100, "neb_max_steps": 100, "spring_eV_ang2": 5.0})
    draft["per_arm_edge_caps"] = {"wall_seconds": 20.0, "cpu_seconds": 40.0,
                                  "energy_requests": 20, "force_requests": 50,
                                  "model_evaluations": 50, "peak_rss_mib": 512.0}
    draft["total_pilot_caps"] = {"wall_seconds": 1000.0, "cpu_seconds": 1000.0}
    return draft


def records(draft):
    result = []
    for edge in draft["edges"]:
        for arm in draft["model_arms"]:
            phases = {
                "input_read": {"wall_seconds": .1, "cpu_seconds": .1},
                "model_load": {"wall_seconds": .2, "cpu_seconds": .4},
                "endpoint_relax": {"wall_seconds": .3, "cpu_seconds": .6},
                "neb_optimize": {"wall_seconds": 1., "cpu_seconds": 1.5},
                "other_overhead": {"wall_seconds": .1, "cpu_seconds": .1},
            }
            result.append({
                "schema_version": RECEIPT_SCHEMA,
                "contract_sha256": _sha(draft),
                "edge_id": edge["edge_id"], "group_id": edge["group_id"],
                "arm_id": arm["arm_id"], "checkpoint_sha256": arm["checkpoint_sha256"],
                "initial_images_sha256": edge["initial_images_sha256"],
                "reported_status": "CONVERGED", "exception_code": None,
                "phases": phases,
                "total": {"wall_seconds": 1.7, "cpu_seconds": 2.7, "energy_requests": 3,
                          "force_requests": 5, "model_evaluations": 6, "peak_rss_mib": 100.},
                "observed_forces_ev_ang": {"endpoint_max": .05, "neb_max": .05},
            })
    return result


def test_unfilled_candidate_is_never_runnable():
    reg, pilot, proto = fixtures()
    x = make_execution_disabled_budget_draft(reg, pilot, proto)
    r = inspect_budget_draft(x)
    assert r["execution_authorized"] is False
    assert r["paired_rows_required"] == 8
    assert set(("INITIAL_IMAGE_HASHES_MISSING", "MODEL_CHECKPOINT_UNPINNED",
                "NEB_NUMERIC_SETTINGS_MISSING", "PER_ARM_PER_EDGE_CAPS_MISSING",
                "TOTAL_PILOT_CAPS_MISSING")).issubset(r["blockers"])
    assert x["scientific_status"] == "SCIENTIFIC_NO_GO_ABSTAIN"
    assert x["precomputed_bvse_cost"].startswith("UNATTESTED")
    with pytest.raises(ValueError, match="INCOMPLETE_DRAFT"):
        audit_paired_receipts(x, [])


def test_registry_pilot_binding_and_target_exposure():
    reg, pilot, proto = fixtures()
    invalid = deepcopy(pilot)
    invalid["selected"][0]["edge_id"] = "mp-999_0_0_0_0_0"
    with pytest.raises(ValueError, match="PILOT_NOT_BOUND_TO_REGISTRY"):
        make_execution_disabled_budget_draft(reg, invalid, proto)
    contaminated = deepcopy(proto)
    contaminated["candidate_experiment_protocol"]["decision_policy"]["delta_eV"] = .01
    with pytest.raises(ValueError, match="UNAPPROVED_DELTA"):
        make_execution_disabled_budget_draft(reg, pilot, contaminated)


def test_complete_draft_remains_not_authorized_and_has_paired_rows():
    d = ready_draft()
    a = inspect_budget_draft(d)
    assert a["execution_authorized"] is False
    assert a["benchmark"] == "BENCHMARK_NOT_FROZEN"
    assert "MODEL_CHECKPOINT_UNPINNED" not in a["blockers"]
    assert a["paired_rows_required"] == 8


def test_receipts_all_pairs_and_deterministic_aggregate():
    d = ready_draft()
    a = audit_paired_receipts(d, records(d))
    b = audit_paired_receipts(d, list(reversed(records(d))))
    assert a == b
    assert a["required_pairs"] == 8 and a["recorded_pairs"] == 8
    assert a["recorded_status_counts"] == {"CONVERGED": 8}
    assert a["all_within_budget"] is True
    assert a["total_observed"]["force_requests"] == 40
    assert a["execution_authorized"] is False
    assert a["performance_evaluation"] == "NOT_PERFORMED"


def test_failure_and_nonconvergence_retained_in_denominator():
    d, rec = ready_draft(), None
    rec = records(d)
    for x, status in zip(rec, ["TIMEOUT", "NONCONVERGED", "OUT_OF_MEMORY", "MODEL_ERROR"]):
        x["reported_status"] = status
        x["exception_code"] = status if status != "NONCONVERGED" else None
        x["observed_forces_ev_ang"] = {"endpoint_max": None, "neb_max": None}
    a = audit_paired_receipts(d, rec)
    assert a["required_pairs"] == 8
    assert a["recorded_status_counts"]["CONVERGED"] == 4
    for key in ("TIMEOUT", "NONCONVERGED", "OUT_OF_MEMORY", "MODEL_ERROR"):
        assert a["recorded_status_counts"][key] == 1


def test_no_silent_drop_of_failure_rows():
    d, r = ready_draft(), None
    r = records(d)
    with pytest.raises(ValueError, match="UNREPORTED"):
        audit_paired_receipts(d, r[:-1])
    bad = deepcopy(r)
    bad[-1] = deepcopy(bad[0])
    with pytest.raises(ValueError, match="DUPLICATE_PAIR"):
        audit_paired_receipts(d, bad)


@pytest.mark.parametrize("field", ["em_dft", "predicted_energy_span", "MAE", "test_loss", "target_value"])
def test_receipt_cannot_contain_targets_or_model_scores(field):
    d, r = ready_draft(), None
    r = records(d)
    r[0][field] = -1
    with pytest.raises(ValueError, match="EXACT_FIELDS"):
        audit_paired_receipts(d, r)


@pytest.mark.parametrize("mutate, match", [
    (lambda d: d.update(execution_authorized=True), "UNAUTHORIZED_SCIENTIFIC"),
    (lambda d: d.update(benchmark_status="FROZEN"), "UNAUTHORIZED_SCIENTIFIC"),
    (lambda d: d.update(observable="FORWARD_DIRECTIONAL_BARRIER"), "OBSERVABLE"),
    (lambda d: d.update(precomputed_bvse_cost="FREE"), "HIDDEN_INITIALIZATION"),
    (lambda d: d["runtime"].update(device="cuda"), "INCOMPARABLE_EXECUTION"),
    (lambda d: d["neb"].update(climbing=False), "INCOMPARABLE_NEB"),
    (lambda d: d["model_arms"][0].update(training_overlap="PROVEN_CLEAN"), "UNATTESTED_TRAINING"),
    (lambda d: d["edges"][0].update(group_id=d["edges"][1]["group_id"]), "EDGE_GROUP_DUPLICATION"),
    (lambda d: d.update(delta_eV=.05), "EXACT_FIELDS"),
    (lambda d: d["per_arm_edge_caps"].update(force_requests=True), "INVALID_NUMBER"),
    (lambda d: d["neb"].update(neb_fmax_ev_ang=float("nan")), "INVALID_NUMBER"),
])
def test_invalid_or_promoted_contract_fails_closed(mutate, match):
    d = ready_draft()
    mutate(d)
    with pytest.raises(ValueError, match=match):
        inspect_budget_draft(d)


@pytest.mark.parametrize("mutate,match", [
    (lambda r: r[0].update(contract_sha256="0"*64), "RECEIPT_PROTOCOL_CONTEXT"),
    (lambda r: r[0].update(checkpoint_sha256="0"*64), "RECEIPT_IDENTITY"),
    (lambda r: r[0].update(initial_images_sha256="0"*64), "RECEIPT_IDENTITY"),
    (lambda r: r[0].update(reported_status="OTHER"), "INVALID_REPORTED_STATUS"),
    (lambda r: r[0].update(reported_status="TIMEOUT"), "MISSING_FAILURE_REASON"),
    (lambda r: r[0]["total"].update(cpu_seconds=0.1), "UNACCOUNTED_PHASE_TIME"),
    (lambda r: r[0]["total"].update(wall_seconds=float("inf")), "INVALID_NUMBER"),
    (lambda r: r[0]["total"].update(energy_requests=-1), "INVALID_NUMBER"),
    (lambda r: r[0]["total"].update(model_evaluations=True), "INVALID_NUMBER"),
    (lambda r: r[0]["observed_forces_ev_ang"].update(neb_max=.11), "CONVERGENCE_CONTRADICTS"),
    (lambda r: r[0]["observed_forces_ev_ang"].update(endpoint_max=None), "CONVERGENCE_EVIDENCE"),
    (lambda r: r[0]["phases"]["neb_optimize"].update(cpu_seconds=.7), "UNACCOUNTED_PHASE_TIME"),
])
def test_malformed_or_self_contradicting_receipts_rejected(mutate, match):
    d = ready_draft()
    r = records(d)
    mutate(r)
    with pytest.raises(ValueError, match=match):
        audit_paired_receipts(d, r)


def test_cap_overrun_never_hidden_and_not_marked_success():
    d, r = ready_draft(), None
    r = records(d)
    d["per_arm_edge_caps"]["force_requests"] = 4
    for rec in r:
        rec["contract_sha256"] = _sha(d)
    a = audit_paired_receipts(d, r)
    assert a["recorded_pairs"] == 8
    assert a["all_within_budget"] is False
    assert a["effective_status_counts"]["BUDGET_VIOLATION"] == 8
    assert len(a["budget_overruns"]) == 8
    assert a["recorded_status_counts"]["CONVERGED"] == 8  # reported, not admitted


def test_total_budget_cap_violation_flag_is_not_an_additional_case():
    d = ready_draft()
    d["total_pilot_caps"]["cpu_seconds"] = 10
    r = records(d)
    for rec in r:
        rec["contract_sha256"] = _sha(d)
    a = audit_paired_receipts(d, r)
    assert a["all_within_budget"] is False
    assert a["total_cap_violations"] == ["cpu_seconds"]
    assert a["required_pairs"] == 8


def test_same_initial_images_bound_across_both_model_arms():
    d, r = ready_draft(), None
    r = records(d)
    assert all(r[2*i]["initial_images_sha256"] == r[2*i+1]["initial_images_sha256"] for i in range(4))
    r[1]["initial_images_sha256"] = "1" * 64
    with pytest.raises(ValueError, match="RECEIPT_IDENTITY"):
        audit_paired_receipts(d, r)


def test_model_identity_cannot_be_swapped_or_conflated():
    d = ready_draft()
    d["model_arms"][0]["checkpoint_sha256"] = d["model_arms"][1]["checkpoint_sha256"]
    with pytest.raises(ValueError, match="SAME_WEIGHTS"):
        inspect_budget_draft(d)
    d = ready_draft()
    d["model_arms"][1]["checkpoint_sha256"] = "f" * 64
    with pytest.raises(ValueError, match="RHOMBUS_MEDIUM_CHECKPOINT"):
        inspect_budget_draft(d)
    d = ready_draft()
    d["model_arms"][0]["arm_id"] = "WEAKER_MODEL_RENAMED"
    with pytest.raises(ValueError, match="REQUIRED_PUBLISHER_SMALL"):
        inspect_budget_draft(d)


def test_convergence_requires_real_work_counters_even_in_synthetic_telemetry():
    d, rec = ready_draft(), None
    rec = records(d)
    rec[0]["total"]["model_evaluations"] = 0
    with pytest.raises(ValueError, match="CLAIMED_CONVERGENCE_WITHOUT_MODEL_WORK"):
        audit_paired_receipts(d, rec)


def test_strict_json_loader_rejects_duplicates_and_nan(tmp_path):
    from scripts.benchmark.prepare_tier_a_budget_draft_0204 import load_json_strict
    p = tmp_path / "fake.json"
    p.write_text('{"foo": 1, "foo": 2}', encoding="utf-8")
    with pytest.raises(ValueError, match="DUPLICATE_JSON_KEY"):
        load_json_strict(p, 1000)
    p.write_text('{"foo": NaN}', encoding="utf-8")
    with pytest.raises(ValueError, match="NONFINITE_JSON_NUMBER"):
        load_json_strict(p, 1000)


def test_offline_cli_generates_only_nonexecuting_budget_draft(tmp_path, monkeypatch):
    import sys
    from scripts.benchmark import prepare_tier_a_budget_draft_0204 as cli
    reg, pilot, protocol = fixtures()
    for name, payload in (("registry", reg), ("pilot", pilot), ("protocol", protocol)):
        (tmp_path / f"{name}.json").write_text(json.dumps(payload), encoding="utf-8")
    out = tmp_path / "created"
    monkeypatch.setattr(sys, "argv", ["prog", "--registry", str(tmp_path / "registry.json"),
                                       "--pilot", str(tmp_path / "pilot.json"),
                                       "--protocol", str(tmp_path / "protocol.json"),
                                       "--out-dir", str(out)])
    assert cli.main() == 0
    draft = json.loads((out / "tier_a_equal_budget_execution_disabled_draft.json").read_text())
    assert draft["execution_authorized"] is False
    assert draft["per_arm_edge_caps"]["force_requests"] is None
    assert draft["model_arms"][0]["training_overlap"] == "UNKNOWN_TRAINING_OVERLAP"
    assert not any("em_dft" in str(row) for row in draft["edges"])
    with pytest.raises(ValueError, match="OUTPUT_MUST_BE_NEW"):
        cli.main()
