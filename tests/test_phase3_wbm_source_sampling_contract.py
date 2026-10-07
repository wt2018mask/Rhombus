from __future__ import annotations

import json
from pathlib import Path

import pytest

from rhombus.domain import WBMSamplingRecord, deterministic_wbm_sample


ROOT = Path(__file__).resolve().parents[1]


def _rows() -> tuple[WBMSamplingRecord, ...]:
    return tuple(
        WBMSamplingRecord(
            material_id=f"wbm-{step}-{idx}",
            substitution_step=step,
            prototype_group=f"proto:{step}:{idx % 3}",
        )
        for step in range(1, 6)
        for idx in range(1, 6)
    )


def test_wbm_source_contract_forbids_outcome_based_selection() -> None:
    contract = json.loads(
        (ROOT / "data/development/phase3_wbm_source_contract_v1.json")
        .read_text(encoding="utf-8")
    )

    assert contract["status"] == "SOURCE_CONTRACT_FROZEN_DATA_NOT_YET_ADMITTED"
    assert contract["expected_structure_count"] == 256963
    assert contract["expected_unique_prototype_material_count"] == 215488
    assert contract["sampling_contract"]["outcome_blind"] is True
    assert "prediction_error" in contract["sampling_contract"]["forbidden_selection_inputs"]
    assert contract["authorization"]["empirical_calibration_use"] is False
    assert contract["authorization"]["unseen_generalization_claim"] is False
    assert contract["authorization"]["sealed_qualification_cohort_use"] is False


def test_deterministic_wbm_sample_is_input_order_invariant() -> None:
    rows = _rows()
    forward = deterministic_wbm_sample(
        rows,
        sample_size=10,
        sampling_version="rhombus-wbm-sampling-v1",
    )
    reverse = deterministic_wbm_sample(
        reversed(rows),
        sample_size=10,
        sampling_version="rhombus-wbm-sampling-v1",
    )

    assert forward == reverse
    assert len(forward) == 10
    assert {row.substitution_step for row in forward} == {1, 2, 3, 4, 5}


def test_sampling_version_changes_identity_without_using_outcomes() -> None:
    rows = _rows()
    v1 = deterministic_wbm_sample(
        rows,
        sample_size=10,
        sampling_version="rhombus-wbm-sampling-v1",
    )
    v2 = deterministic_wbm_sample(
        rows,
        sample_size=10,
        sampling_version="rhombus-wbm-sampling-v2",
    )

    assert tuple(row.material_id for row in v1) != tuple(row.material_id for row in v2)


def test_sampling_requires_each_populated_substitution_step_to_be_represented() -> None:
    rows = _rows()

    with pytest.raises(ValueError, match="at least the number"):
        deterministic_wbm_sample(
            rows,
            sample_size=4,
            sampling_version="rhombus-wbm-sampling-v1",
        )


def test_sampling_rejects_duplicate_material_ids() -> None:
    row = WBMSamplingRecord("wbm-1-1", 1, "proto:a")
    with pytest.raises(ValueError, match="unique"):
        deterministic_wbm_sample(
            (row, row),
            sample_size=1,
            sampling_version="rhombus-wbm-sampling-v1",
        )
