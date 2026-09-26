import pytest

from rudeus.science.contracts import digest
from rudeus.science.x_orchestration import (
    XComparisonOrchestrationError,
    build_x_comparison_record,
    comparison_spec_from_mapping,
)
from rudeus.science.xcheck import (
    XComparisonSpec,
    XInputBinding,
    XModelIdentity,
    XObservation,
    verify_x_record,
)


def model(name, family, checkpoint, implementation, training):
    return XModelIdentity(
        model_name=name,
        model_family=family,
        checkpoint_sha256=digest(checkpoint),
        code_revision=digest(name + "-code"),
        implementation_id=implementation,
        training_data_id=training,
    )


def binding(protocol_hash=None):
    return XInputBinding(
        candidate_id="candidate",
        structure_sha256=digest("relaxed"),
        protocol_hash=protocol_hash or digest("p3"),
        quantity="D_self",
        units="m2/s",
        conditions={
            "temperature_K": 550.0,
            "species": ["Li"],
            "reference_frame": "simulation_cell",
        },
    )


def observation(m, b, value, evidence):
    return XObservation(
        model_hash=m.content_hash,
        input_binding_hash=b.content_hash,
        quantity="D_self",
        units="m2/s",
        value=value,
        evidence_hash=digest(evidence),
        estimator_id="free_intercept_OLS_MSD",
    )


def comparison():
    return XComparisonSpec(
        quantity="D_self",
        units="m2/s",
        relative_tolerance=0.25,
        justification="provisional test-only criterion",
        status="PROVISIONAL",
    )


def fixtures():
    pm = model("MACE", "MACE", "mace", "primary", "mace-training")
    cm = model("MatterSim", "M3GNet-MatterSim", "mattersim", "cross", "mattersim-training")
    b = binding()
    po = observation(pm, b, 2.0e-10, "primary-traj")
    co = observation(cm, b, 1.8e-10, "cross-traj")
    return pm, cm, b, po, co


def test_orchestration_builds_replay_verifiable_record_only_with_explicit_spec():
    pm, cm, b, po, co = fixtures()
    record = build_x_comparison_record(
        primary_model=pm,
        cross_model=cm,
        primary_binding=b,
        cross_binding=b,
        primary_observation=po,
        cross_observation=co,
        comparison=comparison(),
    )
    assert record["stage"] == "X"
    assert verify_x_record(record) == record


def test_orchestration_rejects_missing_tolerance_spec():
    pm, cm, b, po, co = fixtures()
    with pytest.raises(XComparisonOrchestrationError, match="refusing to invent tolerance"):
        build_x_comparison_record(
            primary_model=pm,
            cross_model=cm,
            primary_binding=b,
            cross_binding=b,
            primary_observation=po,
            cross_observation=co,
            comparison=None,
        )


def test_orchestration_rejects_scope_mismatch_before_x_record():
    pm, cm, b, po, co = fixtures()
    other = binding(protocol_hash=digest("other"))
    co_other = observation(cm, other, 1.8e-10, "cross-traj")
    with pytest.raises(XComparisonOrchestrationError, match="identical scientific scope"):
        build_x_comparison_record(
            primary_model=pm,
            cross_model=cm,
            primary_binding=b,
            cross_binding=other,
            primary_observation=po,
            cross_observation=co_other,
            comparison=comparison(),
        )


@pytest.mark.parametrize(
    "mapping,match",
    [
        (None, "no default tolerance"),
        (
            {
                "quantity": "D_self",
                "units": "m2/s",
                "justification": "missing tolerance",
                "status": "PROVISIONAL",
            },
            "invalid explicit X comparison spec",
        ),
        (
            {
                "quantity": "D_self",
                "units": "m2/s",
                "relative_tolerance": 0.25,
                "justification": "explicit",
                "status": "PROVISIONAL",
                "winner": "cross",
            },
            "unexpected comparison fields",
        ),
    ],
)
def test_comparison_spec_parser_never_defaults_or_accepts_extra_fields(mapping, match):
    with pytest.raises(XComparisonOrchestrationError, match=match):
        comparison_spec_from_mapping(mapping)


def test_comparison_spec_parser_preserves_explicit_values():
    spec = comparison_spec_from_mapping(
        {
            "quantity": "D_self",
            "units": "m2/s",
            "absolute_tolerance": None,
            "relative_tolerance": 0.25,
            "justification": "predeclared provisional criterion",
            "status": "PROVISIONAL",
        }
    )
    assert spec.relative_tolerance == 0.25
    assert spec.absolute_tolerance is None
