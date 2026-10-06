from dataclasses import replace

from rudeus.science.known_material_b5_p0 import B5P0UnitObservation
from rudeus.science.known_material_b5_p0_material_semantics import (
    MaterialP0Disposition,
    aggregate_material_p0,
)


def observation(*, key="m", label="a", mode="DIRECT", neutrality=True, pauling=True, geometry=True):
    item = B5P0UnitObservation(
        execution_version="known-material-b5-p0-raw-execution-v1",
        structure_unit_hash="1" * 64,
        material_key=key,
        component_label=label,
        representation_mode=mode,
        input_structure_hash="2" * 64,
        execution_status="COMPLETED",
        input_formula="Li2O",
        existence_state=(
            "PLAUSIBLE"
            if neutrality is True and pauling is True and geometry is True
            else "FAIL"
        ),
        passed=neutrality is True and pauling is True and geometry is True,
        neutrality_ok=neutrality,
        pauling_ok=pauling,
        geometry_ok=geometry,
        details={},
    )
    item.validate()
    return item


def test_direct_all_true_is_material_plausible():
    result = aggregate_material_p0((observation(),))
    assert result.disposition == MaterialP0Disposition.PLAUSIBLE.value


def test_applicable_false_is_material_fail():
    result = aggregate_material_p0((observation(neutrality=False),))
    assert result.disposition == MaterialP0Disposition.FAIL.value
    assert result.applicable_failed_checks == ("neutrality",)


def test_unsupported_false_never_becomes_material_plausible():
    result = aggregate_material_p0(
        (
            observation(
                mode="ENSEMBLE",
                neutrality=False,
            ),
            observation(
                label="b",
                mode="ENSEMBLE",
                neutrality=False,
            ),
        ),
        unsupported_checks=("neutrality",),
    )
    assert result.disposition == MaterialP0Disposition.INDETERMINATE.value
    assert result.applicable_failed_checks == ()
    assert result.unsupported_checks == ("neutrality",)


def test_phase_set_requires_all_components_to_avoid_applicable_failure():
    result = aggregate_material_p0(
        (
            observation(key="p", label="low", mode="PHASE_SET"),
            observation(
                key="p",
                label="high",
                mode="PHASE_SET",
                geometry=False,
            ),
        )
    )
    assert result.disposition == MaterialP0Disposition.FAIL.value
    assert result.applicable_failed_checks == ("geometry",)
