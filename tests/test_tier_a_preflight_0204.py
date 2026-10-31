"""Fast, synthetic and real-metadata-only controls. Never process energy targets."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from rhombus.benchmark.tier_a_preflight import (
    INDEX_HEADER, PILOT_SEED, ZIP_BYTES, ZIP_SHA256,
    build_metadata_registry, conditional_false_acceptance_risk,
    load_verified_owner_index, parse_index_allowlist,
    readiness_blockers, select_train_only_pilot,
)


# Model/NEB/DFT are never imported; test targets are intentionally fake.
def sample_blob(*rows, target=b"LABEL_SHOULD_STAY_OPAQUE") -> bytes:
    data = [INDEX_HEADER]
    for m, edge, chem, flag, split in rows:
        data.append(b",".join((m.encode(), edge.encode(), chem.encode(), flag.encode(),
                               target, b"NEVER_DECODE", split.encode())))
    return b"\n".join(data) + b"\n"


def small_rows():
    return [
        ("mp-1", "mp-1_1_0_0_0_0", "Li-O", "True", "train"),
        ("mp-2", "mp-2_1_0_0_0_0", "O-Li", "False", "test"),
        ("mp-3", "mp-3_1_0_0_0_0", "Cl-Li", "False", "val"),
        ("mp-4", "mp-4_1_0_0_0_0", "Li-P", "False", "train"),
        ("mp-5", "mp-5_1_0_0_0_0", "Li-S", "False", "test"),
    ]


def full_train_fixture():
    blob_rows = list(small_rows())
    for i, chem in enumerate(("Li-As", "Li-Br", "Li-I", "Li-Na", "Li-N", "Li-P-S"), start=6):
        blob_rows.append((f"mp-{i}", f"mp-{i}_1_0_0_0_0", chem, "False", "train"))
    return parse_index_allowlist(sample_blob(*blob_rows))


def previous_candidate():
    # Synthetic policy fixture, not an unauthorized copy/edit of owner evidence.
    return {
        "schema_version": "rhombus-0204-tier-a-retrospective-energy-span-protocol-candidate-v1",
        "data_reference": {"owner_supplied_sha256": ZIP_SHA256, "archive_bytes": ZIP_BYTES},
        "decision": {
            "tier_a_benchmark": "BENCHMARK_NOT_FROZEN",
            "tier_b": "TIER_B_NOT_FROZEN",
            "scientific": "SCIENTIFIC_NO_GO_ABSTAIN",
            "baseline_execution": "NOT_AUTHORIZED",
            "performance_results": None,
        },
        "candidate_experiment_protocol": {
            "scoring_allowed_now": False,
            "published_test_targets_remain_sealed": True,
            "decision_policy": {"conditional_risk_if_accepted_zero": None, "delta_eV": None},
            "equal_budget_accounting_draft": {
                "per_arm_per_edge_caps": {
                    "wall_seconds": None, "cpu_seconds": None,
                    "force_evaluations": None, "peak_rss_MiB": None,
                },
                "total_pilot_caps": {
                    "wall_seconds": None, "cpu_seconds": None, "number_of_arms": None,
                },
            },
            "model_arms": [
                {"id": "MACE_MPA_0_MEDIUM_RHOMBUS", "type": "reference strong MLIP candidate",
                 "checkpoint_sha256": "75428afe3a1d7d8062e19bcaabd5c433623cabf308242ec9fb493e38604fb638"},
                {"id": "MACE_MP_0_SMALL_PUBLISHER_EXAMPLE", "type": "reference strong MLIP candidate",
                 "checkpoint_sha256": None},
            ],
        },
    }


def test_parse_index_allowlist_opaque_target_invariance():
    a = parse_index_allowlist(sample_blob(*small_rows(), target=b"NO_TARGET_VALUE"))
    b = parse_index_allowlist(sample_blob(*small_rows(), target=b"9999999999"))
    assert a == b
    assert all(set(x) == {"material_id", "edge_id", "chemsys", "has_specific_TM", "published_split"} for x in a)
    assert a[1]["chemsys"] == "Li-O"


def test_split_group_precedence_test_gt_val_gt_train():
    registry = build_metadata_registry(parse_index_allowlist(sample_blob(*small_rows())))
    assert registry["counts"]["retained_edges"] == {"train": 1, "val": 1, "test": 2}
    assert registry["counts"]["excluded_by_published_split"]["train"] == 1
    assert registry["rows_sha256"]
    assert {r["candidate_split"] for r in registry["rows"] if r["published_split"] == "test"} == {"test"}


def test_split_group_order_independence_and_metadata_digest():
    rows = parse_index_allowlist(sample_blob(*small_rows()))
    first = build_metadata_registry(rows)
    second = build_metadata_registry(list(reversed(rows)))
    assert first == second


@pytest.mark.parametrize("bad", [
    INDEX_HEADER.replace(b"em_dft", b"reaction_energy") + b"\n",
    INDEX_HEADER + b"\nmp-1,mp-1_1_0_0_0_0,\"Li-O\",True,a,b,train\n",
    INDEX_HEADER + b"\nmp-1,mp-1_1_0_0_0_0,Li-O,True,a,b,train,EXTRA\n",
    INDEX_HEADER + b"\nmp-1,mp-1_1_0_0_0_0,Li-O,True,a,b,unknown\n",
    INDEX_HEADER + b"\nmp-1,mp-1_1_0_0_0_0,O,True,a,b,train\n",
])
def test_invalid_csv_fail_closed(bad):
    with pytest.raises(ValueError):
        parse_index_allowlist(bad)


def test_duplicate_edge_fails_closed():
    x = small_rows()[0]
    with pytest.raises(ValueError, match="DUPLICATE_EDGE_ID"):
        parse_index_allowlist(sample_blob(x, x))


def test_material_leakage_fails_closed():
    x = ("mp-1", "mp-1_2_0_0_0_0", "Li-Cl", "False", "test")
    with pytest.raises(ValueError, match="MATERIAL_CROSSES_PUBLISHED_SPLIT"):
        parse_index_allowlist(sample_blob(small_rows()[0], x))


def test_injected_target_field_rejected_after_parsing():
    rows = full_train_fixture()
    rows[0]["em_dft"] = "INVALID_EXPOSED_LABEL"
    with pytest.raises(ValueError, match="NON_ALLOWLIST"):
        build_metadata_registry(rows)


def test_deterministic_four_group_pilot_no_heldout():
    registry = build_metadata_registry(full_train_fixture())
    p = select_train_only_pilot(registry)
    assert p["n_edges"] == 4
    assert p["sampling_seed"] == PILOT_SEED
    assert len({x["group_id"] for x in p["selected"]}) == 4
    assert all(x["published_split"] == "train" for x in p["selected"])
    assert p == select_train_only_pilot(build_metadata_registry(list(reversed(full_train_fixture()))))
    assert p["status"] == "TRAIN_METADATA_PROPOSAL_NOT_RUN_NOT_AUTHORIZED"


def test_tampered_group_assignment_detected():
    reg = build_metadata_registry(full_train_fixture())
    reg["rows"][0]["candidate_split"] = "test"
    with pytest.raises(ValueError, match="REGISTRY_ROWS_HASH_MISMATCH"):
        select_train_only_pilot(reg)


def test_tamper_after_digest_recomputed_still_detected():
    from rhombus.benchmark.tier_a_preflight import _digest
    reg = build_metadata_registry(full_train_fixture())
    row = next(x for x in reg["rows"] if x["candidate_split"] == "train")
    row["candidate_split"] = "test"
    reg["rows_sha256"] = _digest(reg["rows"])
    with pytest.raises(ValueError, match="REGISTRY_SPLIT_OR_GROUP_TAMPERED"):
        select_train_only_pilot(reg)


def test_risk_zero_coverage_undefined_and_invalid_counts():
    assert conditional_false_acceptance_risk(accepted=0, severe=0) is None
    assert conditional_false_acceptance_risk(accepted=4, severe=1) == 0.25
    for accepted, severe in ((0, 1), (-1, 0), (3, 4), (True, 0)):
        with pytest.raises(ValueError, match="INVALID_ACCEPTED_OR_SEVERE_COUNT"):
            conditional_false_acceptance_risk(accepted=accepted, severe=severe)


def test_original_draft_cannot_authorize_science():
    p = previous_candidate()
    x = readiness_blockers(p)
    assert x["execution_authorized"] is False
    assert x["benchmark"] == "BENCHMARK_NOT_FROZEN"
    assert "OWNER_SEPARATE_COMPUTE_APPROVAL_MISSING" in x["blockers"]
    assert "PER_ARM_BUDGET_CAPS_UNSET" in x["blockers"]
    assert "CHECKPOINTS_NOT_ALL_PINNED" in x["blockers"]


@pytest.mark.parametrize("mutation,code", [
    (lambda p: p["decision"].update(tier_a_benchmark="FROZEN"), "IMPROPER_SCIENTIFIC"),
    (lambda p: p["candidate_experiment_protocol"].update(scoring_allowed_now=True), "HELDOUT_EMBARGO"),
    (lambda p: p["candidate_experiment_protocol"].update(published_test_targets_remain_sealed=False), "HELDOUT_EMBARGO"),
    (lambda p: p["candidate_experiment_protocol"]["decision_policy"].update(delta_eV=0.1), "UNAPPROVED_DELTA"),
    (lambda p: p["candidate_experiment_protocol"]["decision_policy"].update(conditional_risk_if_accepted_zero=0), "ZERO_COVERAGE"),
    (lambda p: p["decision"].update(performance_results={"mae": 0.03}), "UNAUTHORIZED_PERFORMANCE"),
    (lambda p: p["data_reference"].update(owner_supplied_sha256="0" * 64), "SOURCE_IDENTITY"),
])
def test_promotion_and_heldout_embargo_fail_closed(mutation, code):
    x = deepcopy(previous_candidate())
    mutation(x)
    with pytest.raises(ValueError, match=code):
        readiness_blockers(x)


def test_real_source_metadata_only_full_counts_if_available():
    # Optional real ZIP integration; CI must not require owner-provided private file.
    import os
    archive = os.environ.get("RHOMBUS_0204_OWNER_LITRAJ_ZIP")
    if not archive:
        pytest.skip("Owner archive only exists in authorized local environment")
    rows = load_verified_owner_index(Path(archive))
    reg = build_metadata_registry(rows)
    c = reg["counts"]
    assert c["all_edges"] == 1681
    assert c["unique_material_ids"] == 867
    assert c["unique_chemsys"] == 277
    assert c["chemsys_across_multiple_original_splits"] == 148
    assert c["retained_edges"] == {"train": 619, "val": 165, "test": 220}
    assert c["excluded_edges"] == 677
    p = select_train_only_pilot(reg)
    assert p["n_edges"] == 4
    assert reg["archive_owner_sha256"] == ZIP_SHA256


def test_actual_external_handoff_protocol_if_available():
    import os
    path = os.environ.get("RHOMBUS_0204_TIER_A_CANDIDATE_PROTOCOL")
    if not path:
        pytest.skip("External owner handoff protocol is not shipped in repository")
    x = readiness_blockers(json.loads(Path(path).read_text("utf-8")))
    assert x["execution_authorized"] is False
    assert x["tier_a_protocol"] == "TIER_A_PROTOCOL_DRAFT_READY"
