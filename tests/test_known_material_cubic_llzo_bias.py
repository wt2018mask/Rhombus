"""Cubic Al-LLZO representation-bias assessment tests."""
from pathlib import Path

from rudeus.science.known_material_cubic_llzo_bias import (
    assess_cubic_llzo_ensemble_bias,
)


CIF = Path(
    "data/benchmarks/known_material/structures/cod/7215448-r176453.cif"
)
SOURCE_HASH = "db5f259f418edca7111136c0bc3a48b7f7cccde87411d54c48ebf71821217eec"


def test_cubic_llzo_bias_assessment_freezes_actual_ensemble_deviation():
    assessment = assess_cubic_llzo_ensemble_bias(
        CIF, source_artifact_hash=SOURCE_HASH
    )

    assert assessment.formula_units_total == 256
    assert assessment.ensemble_formula_li == "6.0625"
    assert assessment.ensemble_formula_al == "0.1953125"
    assert assessment.formula_li_absolute_error == "0.0025"
    assert assessment.formula_al_absolute_error == "0.0006875"
    assert assessment.max_site_occupancy_absolute_error == (
        "0.0003645833333333333333333333"
    )
    assert assessment.member_atom_count_min == 371
    assert assessment.member_atom_count_max == 373


def test_cubic_llzo_bias_assessment_binds_unique_reproducible_realizations():
    first = assess_cubic_llzo_ensemble_bias(
        CIF, source_artifact_hash=SOURCE_HASH
    )
    second = assess_cubic_llzo_ensemble_bias(
        CIF, source_artifact_hash=SOURCE_HASH
    )

    assert first == second
    assert len(first.realization_hashes) == 16
    assert len(set(first.realization_hashes)) == 16
    assert first.source_artifact_hash == SOURCE_HASH
