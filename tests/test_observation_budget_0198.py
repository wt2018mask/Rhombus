"""Analytic/synthetic falsifiers; source replay remains exposed retrospective data."""
import copy
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

import pytest

from rhombus.qualification import observation_budget as m


def test_exact_uniform_budget_control_and_regret_units():
    subsets = m.select_subsets([600, 650, 700], 2, "UNIFORM_WITHOUT_REPLACEMENT_EXACT")
    assert subsets == [(0, 1), (0, 2), (1, 2)]
    r = m.score_subsets([1e-5, 1e-4, 1e-3], subsets, budget=2)
    assert r["expected_regret_log10"] == pytest.approx(1 / 3)
    assert r["source_maximum_recovery_fraction"] == pytest.approx(2 / 3)
    assert r["worst_subset_regret_log10"] == 1
    # Same k, same revealed condition count in every subset, no lucky seed.
    assert all(len(s["observed_indices"]) == 2 for s in r["subset_results"])


def test_metadata_selection_independent_of_values_and_input_order():
    assert m.select_subsets([700, 600, 650], 2, "HOTTEST_FIRST") == [(0, 2)]
    assert m.select_subsets([700, 600, 650], 2, "COLDEST_FIRST") == [(1, 2)]
    selected = m.select_subsets([600, 650, 700], 1, "HOTTEST_FIRST")
    a = m.score_subsets([1, 2, 4], selected, budget=1)
    b = m.score_subsets([1, 4, 2], selected, budget=1)
    assert a["subset_results"][0]["observed_indices"] == b["subset_results"][0]["observed_indices"]
    assert a["expected_regret_log10"] == 0 < b["expected_regret_log10"]


def test_exhaustive_budget_zero_regret_and_ties_not_false_failure():
    r = m.score_subsets([1, 1, 1], [(0, 1, 2)], budget=3)
    assert r["expected_regret_log10"] == 0
    assert r["source_maximum_recovery_fraction"] == 1
    assert m.assess_target_label_stress([1, 1, 1], [0])["source_winner_index"] is None


def test_target_stress_constructs_real_boundary_tie_and_reversal():
    values = [1, 2, 4]
    gap = math.log10(4) - math.log10(2)
    radius = gap / 2
    r = m.assess_target_label_stress(values, [0, .99 * radius, radius, 1.01 * radius])
    assert [s["unique_winner_certified"] for s in r["stress_scenarios"]] == [True, True, False, False]
    assert r["minimum_Linf_target_label_shift_to_tie_log10"] == pytest.approx(radius)
    assert math.log10(4) - radius == pytest.approx(math.log10(2) + radius)
    assert math.log10(4) - 1.01 * radius < math.log10(2) + 1.01 * radius
    assert r["is_measured_EIS_error"] is False


@pytest.mark.parametrize("values,subsets,budget", [
    ([1, 0, 4], [(0,)], 1), ([1, True, 4], [(0,)], 1),
    ([1, float("nan"), 4], [(0,)], 1), ([1, 2, 4], [(0, 1)], 1),
    ([1, 2, 4], [(0, 0)], 2), ([1, 2, 4], [(3,)], 1),
    ([1, 2, 4], [(True,)], 1), ([1, 2, 4], [(0,), (0,)], 1),
    ([1, 2, 4], [], 1), ([1, 2, 4], [(0,)], True),
])
def test_invalid_values_costs_duplicates_or_out_of_bounds_fail(values, subsets, budget):
    with pytest.raises(ValueError):
        m.score_subsets(values, subsets, budget=budget)


@pytest.mark.parametrize("temperatures,budget,policy", [
    ([600, 600, 700], 1, "HOTTEST_FIRST"),
    ([600, 650, float("inf")], 1, "HOTTEST_FIRST"),
    ([600, 650, 700], 0, "HOTTEST_FIRST"),
    ([600, 650, 700], True, "HOTTEST_FIRST"),
    ([600, 650, 700], 1, "UNDECLARED"),
])
def test_invalid_allocation_rejected(temperatures, budget, policy):
    with pytest.raises(ValueError):
        m.select_subsets(temperatures, budget, policy)


def test_source_identity_is_pinned_and_no_reserved_test_or_network_read(tmp_path, monkeypatch):
    protocol, source, groups = m.load_study()
    assert len(groups) == 6 and all(len(g) == 3 for g in groups)
    assert source["official_OBELiX_TEST_121_read"] is False
    original = Path.read_bytes
    reads = []
    def audited(path):
        reads.append(str(path))
        return original(path)
    monkeypatch.setattr(Path, "read_bytes", audited)
    m.load_study()
    assert {str(m.ROOT / m.PROTOCOL_PATH), str(m.ROOT / protocol["input_path"])} == set(reads)
    # Tamper with source receipt: refuse before using any rows or outcomes.
    dest = tmp_path / m.PROTOCOL_PATH
    dest.parent.mkdir(parents=True)
    dest.write_bytes(original(m.ROOT / m.PROTOCOL_PATH))
    src = tmp_path / protocol["input_path"]
    changed = copy.deepcopy(source)
    changed["table_mapping"][0]["total_ionic_conductivity_S_cm"] *= 1000
    src.write_text(json.dumps(changed))
    with pytest.raises(ValueError, match="receipt changed"):
        m.load_study(tmp_path)


def test_frozen_protocol_drift_fails_before_input_read(tmp_path):
    path = tmp_path / m.PROTOCOL_PATH
    path.parent.mkdir(parents=True)
    path.write_text("{}")
    with pytest.raises(ValueError, match="protocol changed"):
        m.load_study(tmp_path)


def test_cli_preserves_existing_observation(tmp_path):
    output = tmp_path / "existing.json"
    output.write_text("preserve")
    result = subprocess.run([sys.executable, "-m", "scripts.science.observation_budget_0198",
                             "--output", str(output)], capture_output=True, text=True)
    assert result.returncode != 0 and "already exists" in result.stderr
    assert output.read_text() == "preserve"


def test_retained_actual_result_is_source_protocol_code_and_content_bound():
    result = json.loads((m.ROOT / "data/development/observation_budget_0198_result_v1.json").read_text())
    protocol, _, _ = m.load_study()
    assert result["protocol_sha256"] == m.PROTOCOL_SHA256
    assert result["source_receipt_sha256"] == protocol["input_sha256"]
    assert result["computation_code_sha256"] == hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest()
    assert {r["series"] for r in result["series_results"]} == set(protocol["series"])
    assert len(result["series_results"]) == 6 and result["source_conditions"] == 18
    assert result["source_groups"] == 1 and result["new_independent_sources"] == 0
    assert not result["TEST121_accessed"] and not result["scientific_GO"] and not result["production_enabled"]
    assert all(c["conditional_regret"] is None and c["predictions_executed"] == 0 for c in result["model_comparators"])
    from rhombus.tools.evidence_query import _verify_evidence_row
    row = _verify_evidence_row(result["evidence_records"][0], lineno=1)
    assert row["scientific_verdict"] == "INDETERMINATE"
    assert row["applicability"]["domain_status"] == "UNQUALIFIED"
