import json

import pytest

from rudeus.science.contracts import ClaimAssessment, Verdict, digest
from rudeus.science.negative_controls import NControlSpec, NObservation, n_record
from rudeus.science.xcheck import (
    XComparisonSpec,
    XInputBinding,
    XModelIdentity,
    XObservation,
    x_record,
)
from rudeus.science.xnsout_production import (
    XNSOUTProductionError,
    build_xnsout_records,
    persist_xnsout_records,
)


def primary():
    return ClaimAssessment(
        claim_id="claim",
        claim_hash=digest("claim"),
        protocol_hash=digest("protocol"),
        verdict=Verdict.PASS,
        assumptions={},
        applicability={},
        statistical_sufficiency={},
        reason_codes=("primary",),
        supporting_evidence=(digest("primary-evidence"),),
        conflicting_evidence=(),
        unresolved_requirements=(),
    )


def xrec(cross_value=0.9e-9):
    pm = XModelIdentity(
        model_name="primary",
        model_family="mace",
        checkpoint_sha256=digest("primary-checkpoint"),
        code_revision=digest("primary-code"),
        implementation_id="primary",
        training_data_id="primary-training",
    )
    cm = XModelIdentity(
        model_name="cross",
        model_family="independent",
        checkpoint_sha256=digest("cross-checkpoint"),
        code_revision=digest("cross-code"),
        implementation_id="cross",
        training_data_id="cross-training",
    )
    binding = XInputBinding(
        candidate_id="candidate",
        structure_sha256=digest("structure"),
        protocol_hash=digest("protocol"),
        quantity="D_self",
        units="m2/s",
        conditions={"temperature_K": 550.0, "species": ["Li"], "reference_frame": "simulation_cell"},
    )
    comparison = XComparisonSpec(
        quantity="D_self",
        units="m2/s",
        relative_tolerance=0.25,
        justification="provisional integration criterion",
    )
    po = XObservation(
        model_hash=pm.content_hash,
        input_binding_hash=binding.content_hash,
        quantity="D_self",
        units="m2/s",
        value=1.0e-9,
        evidence_hash=digest("primary-x"),
        estimator_id="free_intercept_OLS_MSD",
    )
    co = XObservation(
        model_hash=cm.content_hash,
        input_binding_hash=binding.content_hash,
        quantity="D_self",
        units="m2/s",
        value=cross_value,
        evidence_hash=digest(["cross-x", cross_value]),
        estimator_id="free_intercept_OLS_MSD",
    )
    return x_record(
        primary_model=pm,
        cross_model=cm,
        primary_binding=binding,
        cross_binding=binding,
        comparison=comparison,
        primary_observation=po,
        cross_observation=co,
    )


def nrec(observed=False):
    spec = NControlSpec(
        control_id="known-negative",
        target_claim_hash=digest("claim"),
        protocol_hash=digest("n-protocol"),
        control_kind="known_negative_transport",
        expected=False,
        scope={"quantity": "decisive_diffusion", "domain": "synthetic-negative"},
        justification="provisional integration control",
    )
    obs = NObservation(
        control_id=spec.control_id,
        protocol_hash=spec.protocol_hash,
        observed=observed,
        scope=spec.scope,
        evidence_hashes=(digest(["n-evidence", observed]),),
        producer_identity="synthetic-negative-v1",
    )
    return n_record(spec, obs)


def test_build_xnsout_records_replays_inputs_and_preserves_pass():
    bundle = build_xnsout_records(
        primary=primary(),
        x_records=(xrec(),),
        n_records=(nrec(False),),
    )
    assert bundle["stage"] == "XNSOUT"
    assert bundle["final_disposition"] == "SUPPORTED"
    assert bundle["final_claim_verdict"] == "PASS"
    assert bundle["s_record"]["stage"] == "S"
    assert bundle["out_record"]["stage"] == "OUT"


def test_build_xnsout_records_propagates_falsification():
    bundle = build_xnsout_records(
        primary=primary(),
        x_records=(xrec(),),
        n_records=(nrec(True),),
    )
    assert bundle["final_disposition"] == "CONFLICTED"
    assert bundle["final_claim_verdict"] == "INDETERMINATE"


def test_build_xnsout_records_rejects_tampered_x_record():
    record = xrec()
    record["assessment"]["reason_codes"] = ["forged"]
    with pytest.raises(ValueError, match="X assessment replay mismatch"):
        build_xnsout_records(primary=primary(), x_records=(record,), n_records=(nrec(False),))


def test_build_xnsout_records_rejects_n_targeting_other_claim():
    record = nrec(False)
    record["control_spec"]["target_claim_hash"] = digest("other")
    record["assessment"]["target_claim_hash"] = digest("other")
    # Make N record internally replayable by updating its assessment via a fresh record.
    spec = NControlSpec.from_dict(record["control_spec"])
    obs = NObservation.from_dict(record["observation"])
    record = n_record(spec, obs)
    with pytest.raises(XNSOUTProductionError, match="different primary claim"):
        build_xnsout_records(primary=primary(), x_records=(xrec(),), n_records=(record,))


def test_persistence_is_idempotent_and_refuses_different_overwrite(tmp_path):
    bundle = build_xnsout_records(
        primary=primary(),
        x_records=(xrec(),),
        n_records=(nrec(False),),
    )
    s_path = tmp_path / "s.json"
    out_path = tmp_path / "out.json"

    first = persist_xnsout_records(bundle=bundle, s_path=s_path, out_path=out_path)
    second = persist_xnsout_records(bundle=bundle, s_path=s_path, out_path=out_path)
    assert first == second

    assert json.loads(s_path.read_text())["stage"] == "S"
    assert json.loads(out_path.read_text())["stage"] == "OUT"

    conflicted = build_xnsout_records(
        primary=primary(),
        x_records=(xrec(0.1e-9),),
        n_records=(nrec(False),),
    )
    with pytest.raises(XNSOUTProductionError, match="refusing to overwrite"):
        persist_xnsout_records(bundle=conflicted, s_path=s_path, out_path=out_path)
