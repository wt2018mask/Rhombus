"""Focused tests for frozen S2 v2 population inventories.

Freeze-only: explicit ID/seed mappings, disjointness, deterministic hashes,
role bindings. No execution, no trajectories, no scores, no q_hat, no
qualification state, no historical evidence reads.
"""
from pathlib import Path

from rudeus.execution.contracts import ExecutionError
from rudeus.science import calibration_s2v2 as method
from rudeus.science import calibration_s2v2_populations as pop
from rudeus.science.contracts import digest


def test_exact_counts():
    assert len(pop.S2V2_DEV_A_SEEDS) == 99
    assert len(pop.S2V2_DEV_B_SEEDS) == 114
    assert len(pop.S2V2_HELDOUT_SEEDS) == 379
    assert pop.S2V2_DEV_A_RECORD["count"] == 99
    assert pop.S2V2_DEV_B_RECORD["count"] == 114
    assert pop.S2V2_HELDOUT_RECORD["count"] == 379


def test_one_to_one_mappings():
    for seeds in (pop.S2V2_DEV_A_SEEDS, pop.S2V2_DEV_B_SEEDS, pop.S2V2_HELDOUT_SEEDS):
        assert len(set(seeds)) == len(seeds)
        assert len(set(seeds.values())) == len(seeds)
        assert list(seeds) == sorted(seeds)
        assert all(isinstance(rep, str) and isinstance(seed, int)
                   and not isinstance(seed, bool) for rep, seed in seeds.items())


def test_pairwise_seed_disjointness():
    sets = [set(pop.S2V2_DEV_A_SEEDS.values()),
            set(pop.S2V2_DEV_B_SEEDS.values()),
            set(pop.S2V2_HELDOUT_SEEDS.values())]
    for left in range(3):
        for right in range(left + 1, 3):
            assert not sets[left] & sets[right]


def test_pairwise_id_disjointness():
    sets = [set(pop.S2V2_DEV_A_SEEDS), set(pop.S2V2_DEV_B_SEEDS),
            set(pop.S2V2_HELDOUT_SEEDS)]
    for left in range(3):
        for right in range(left + 1, 3):
            assert not sets[left] & sets[right]


def test_disjoint_from_historical_seeds():
    historical = {11, 12, 21, 22} | set(range(101, 109)) | set(range(201, 265))
    assert pop.S2V2_EXCLUDED_SEEDS == historical
    for seeds in (pop.S2V2_DEV_A_SEEDS, pop.S2V2_DEV_B_SEEDS, pop.S2V2_HELDOUT_SEEDS):
        assert not set(seeds.values()) & historical


def test_deterministic_hashes():
    assert digest(pop.S2V2_DEV_A_RECORD) == pop.S2V2_DEV_A_HASH
    assert digest(pop.S2V2_DEV_B_RECORD) == pop.S2V2_DEV_B_HASH
    assert digest(pop.S2V2_HELDOUT_RECORD) == pop.S2V2_HELDOUT_HASH
    assert digest(pop.S2V2_POPULATIONS) == pop.S2V2_POPULATIONS_HASH
    assert pop.assert_frozen_v2_populations() is None


def test_seed_change_moves_hash():
    altered = dict(pop.S2V2_DEV_A_SEEDS)
    first = sorted(altered)[0]
    altered[first] = altered[first] + 1000
    record = pop.build_s2v2_population_record(
        role=pop.S2V2_DEV_A_ROLE, split=pop.S2V2_DEV_A_SPLIT, seeds=altered)
    assert digest(record) != pop.S2V2_DEV_A_HASH


def test_role_change_moves_hash():
    record = pop.build_s2v2_population_record(
        role="altered-role", split=pop.S2V2_DEV_B_SPLIT, seeds=pop.S2V2_DEV_B_SEEDS)
    assert digest(record) != pop.S2V2_DEV_B_HASH


def test_heldout_has_no_outcome_fields():
    text = digest(pop.S2V2_HELDOUT_RECORD)  # hashable record, then field scan
    assert text == pop.S2V2_HELDOUT_HASH
    forbidden = ("outcome", "result", "interval", "quantile", "q_hat", "score",
                 "coverage", "bias", "verdict", "PASS", "FAIL")
    for key in pop.S2V2_HELDOUT_RECORD:
        assert key not in forbidden
        assert not any(word in key for word in forbidden)


def test_no_execution_path():
    text = Path(pop.__file__).read_text()
    for marker in ("materialize", "estimate_", "coverage_experiment", "glob(",
                   "read_bytes", ".json", "artifact_root", "store.root", "blobs",
                   "CalibrationStore", "QualificationRecord", "Uncertainty(",
                   ".bounds", "Verdict"):
        assert marker not in text, marker


def test_pooling_still_forbidden_and_method_unchanged():
    assert method.devb_pooling_after_inspection_allowed() is False
    assert method.S2V2_METHOD_HASH == (
        "3b6f1d0a7e8ca64f02c0bd68c6a7a0af88c40e36298eade055459c5e424bd28b")
    assert method.S2V2_CRITERION_HASH == (
        "4eb3c4ac4769d14cfcffe54de070dd90703271efc6694e9f11be9cb35185098b")
    assert pop.S2V2_DEV_A_RECORD["method_hash"] == method.S2V2_METHOD_HASH
    assert pop.S2V2_DEV_B_RECORD["method_hash"] == method.S2V2_METHOD_HASH
    assert pop.S2V2_HELDOUT_RECORD["method_hash"] == method.S2V2_METHOD_HASH
    assert pop.S2V2_POPULATIONS["method_hash"] == method.S2V2_METHOD_HASH


def test_explicit_ranges_and_ids():
    assert (min(pop.S2V2_DEV_A_SEEDS.values()), max(pop.S2V2_DEV_A_SEEDS.values())) == (265, 363)
    assert (min(pop.S2V2_DEV_B_SEEDS.values()), max(pop.S2V2_DEV_B_SEEDS.values())) == (364, 477)
    assert (min(pop.S2V2_HELDOUT_SEEDS.values()), max(pop.S2V2_HELDOUT_SEEDS.values())) == (478, 856)
    assert sorted(pop.S2V2_DEV_A_SEEDS)[0] == "s2v2-dev-a-001"
    assert sorted(pop.S2V2_DEV_A_SEEDS)[-1] == "s2v2-dev-a-099"
    assert sorted(pop.S2V2_DEV_B_SEEDS)[0] == "s2v2-dev-b-001"
    assert sorted(pop.S2V2_DEV_B_SEEDS)[-1] == "s2v2-dev-b-114"
    assert sorted(pop.S2V2_HELDOUT_SEEDS)[0] == "s2v2-heldout-001"
    assert sorted(pop.S2V2_HELDOUT_SEEDS)[-1] == "s2v2-heldout-379"
