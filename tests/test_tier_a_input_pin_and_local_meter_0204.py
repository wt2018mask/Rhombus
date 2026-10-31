"""Fail-closed negative controls; no MACE, DFT, NEB or energy scoring."""
from __future__ import annotations

from copy import deepcopy
import io
import json
from pathlib import Path
import zipfile

import pytest

from rhombus.benchmark import tier_a_input_pin as pins
from rhombus.benchmark.tier_a_budget_contract import audit_paired_receipts, inspect_budget_draft
from rhombus.benchmark.tier_a_local_meter import LocalProcessMeter
from tests.test_tier_a_budget_contract_0204 import ready_draft, fixtures


def unpinned_draft():
    reg, pilot, proto = fixtures()
    from rhombus.benchmark.tier_a_budget_contract import make_execution_disabled_budget_draft
    return make_execution_disabled_budget_draft(reg, pilot, proto)


def fake_zip(path: Path, edges: list[str], *, duplicate=False, oversized=False):
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for j, edge in enumerate(edges):
            name = f"nebDFT2k/{edge}_init.xyz"
            z.writestr(name, (b"placeholder-not-energy-target\n" if not oversized else b"x" * (pins.MAX_INIT_XYZ_BYTES + 1)))
            if j == 0 and duplicate:
                z.writestr(name, b"other")
        z.writestr("nebDFT2k/heldout_relaxed.xyz", b"should-not-be-touched")


def test_synthetic_four_init_member_pinning_and_no_target_access(tmp_path, monkeypatch):
    d = unpinned_draft()
    monkeypatch.setattr(pins, "_verify_owner_zip", lambda path: None)
    archive = tmp_path / "synthetic.zip"
    fake_zip(archive, [e["edge_id"] for e in d["edges"]])
    updated, receipt = pins.pin_train_initial_xyz_bytes(d, archive)
    assert all(e["initial_images_sha256"] is None for e in d["edges"])
    assert len(receipt["identities"]) == 4
    assert all(e["initial_images_sha256"] is not None for e in updated["edges"])
    assert receipt["relaxed_dft_xyz_access"] == "NONE"
    assert receipt["target_columns_access"] == "NONE"
    assert "INITIAL_IMAGE_HASHES_MISSING" not in inspect_budget_draft(updated)["blockers"]
    assert receipt["execution_authorized"] is False
    # Do not serialize a target, prediction or raw energy.
    blob = json.dumps(receipt)
    assert "em_dft" not in blob and "predicted_energy" not in blob
    with pytest.raises(ValueError, match="DO_NOT_REPIN"):
        pins.pin_train_initial_xyz_bytes(updated, archive)


def test_duplicate_missing_or_oversized_xyz_rejected(tmp_path, monkeypatch):
    d = unpinned_draft()
    monkeypatch.setattr(pins, "_verify_owner_zip", lambda path: None)
    ids = [e["edge_id"] for e in d["edges"]]
    for label, selected, kw, match in (
        ("missing", ids[:3], {}, "INITIAL_XYZ_MISSING"),
        ("duplicate", ids, {"duplicate": True}, "INITIAL_XYZ_MISSING_OR_DUPLICATED"),
        ("oversized", ids, {"oversized": True}, "UNSAFE_INITIAL_XYZ_MEMBER"),
    ):
        archive = tmp_path / f"{label}.zip"
        fake_zip(archive, selected, **kw)
        with pytest.raises(ValueError, match=match):
            pins.pin_train_initial_xyz_bytes(d, archive)


def test_owner_zip_identity_fails_on_fake_zip(tmp_path):
    archive = tmp_path / "synthetic.zip"
    fake_zip(archive, ["mp-10_1_0_0_0_0"])
    with pytest.raises(ValueError, match="OWNER_ZIP_BYTES_NOT_VERIFIED"):
        pins._verify_owner_zip(archive)


def test_meter_cannot_imply_execution_approval():
    d = ready_draft()
    meter = LocalProcessMeter(d, arm_id=d["model_arms"][0]["arm_id"],
                              edge_id=d["edges"][0]["edge_id"])
    with meter.phase("input_read"):
        pass
    with meter.phase("model_load"):
        pass
    with meter.phase("endpoint_relax"):
        meter.record_call("energy")
        meter.record_call("force")
        meter.record_call("model_calculation")
    with meter.phase("neb_optimize"):
        meter.record_call("force")
        meter.record_call("model_calculation")
    env = meter.finish(status="NONCONVERGED")
    rec = env["receipt"]
    assert env["execution_authorized_by_meter"] is False
    assert env["model_executed_by_meter"] is False
    assert env["raw_energy_values_saved"] is False
    assert env["event_count"] == 5
    assert rec["reported_status"] == "NONCONVERGED"
    assert rec["total"]["force_requests"] == 2
    assert rec["total"]["model_evaluations"] == 2
    assert rec["total"]["wall_seconds"] >= sum(x["wall_seconds"] for x in rec["phases"].values()) - 1e-8
    assert rec["total"]["cpu_seconds"] >= sum(x["cpu_seconds"] for x in rec["phases"].values()) - 1e-8
    assert rec["total"]["peak_rss_mib"] > 0
    with pytest.raises(ValueError, match="METER_ALREADY_FINALIZED"):
        meter.record_call("force")


def test_meter_rejects_order_overlap_and_bad_events():
    d = ready_draft()
    meter = LocalProcessMeter(d, arm_id=d["model_arms"][0]["arm_id"],
                              edge_id=d["edges"][0]["edge_id"])
    with pytest.raises(ValueError, match="OUTSIDE_ALLOWED_PHASE"):
        meter.record_call("force")
    with meter.phase("input_read"):
        with pytest.raises(ValueError, match="OVERLAPPING"):
            with meter.phase("model_load"):
                pass
    with pytest.raises(ValueError, match="OVERLAPPING"):
        with meter.phase("input_read"):
            pass
    with pytest.raises(ValueError, match="INVALID_EXPLICIT"):
        with meter.phase("other_overhead"):
            pass
    with pytest.raises(ValueError, match="INVALID_COMPLETION_STATUS"):
        meter.finish(status="SCIENTIFIC_PASS")
    with pytest.raises(ValueError, match="FAILURE_CODE_REQUIRED"):
        meter.finish(status="TIMEOUT", exception_code=None)


def test_fault_in_phase_cannot_be_marked_converged():
    d = ready_draft()
    meter = LocalProcessMeter(d, arm_id=d["model_arms"][0]["arm_id"],
                              edge_id=d["edges"][0]["edge_id"])
    with pytest.raises(RuntimeError, match="synthetic"):
        with meter.phase("model_load"):
            raise RuntimeError("synthetic error only")
    with pytest.raises(ValueError, match="CANNOT_BECOME_SUCCESS"):
        meter.finish(status="CONVERGED", endpoint_max_force=0.01, neb_max_force=0.01)
    env = meter.finish(status="MODEL_ERROR", exception_code="MODEL_ERROR")
    assert env["receipt"]["reported_status"] == "MODEL_ERROR"


def test_metered_synthetic_eight_pairs_retained_and_audited():
    d = ready_draft()
    receipts = []
    for edge in d["edges"]:
        for arm in d["model_arms"]:
            meter = LocalProcessMeter(d, arm_id=arm["arm_id"], edge_id=edge["edge_id"])
            with meter.phase("endpoint_relax"):
                meter.record_call("force")
                meter.record_call("model_calculation")
            with meter.phase("neb_optimize"):
                meter.record_call("force")
                meter.record_call("model_calculation")
            receipts.append(meter.finish(status="NONCONVERGED")["receipt"])
    result = audit_paired_receipts(d, receipts)
    assert result["recorded_pairs"] == 8
    assert result["recorded_status_counts"] == {"NONCONVERGED": 8}
    assert result["performance_evaluation"] == "NOT_PERFORMED"
    assert result["execution_authorized"] is False


def test_meter_rejects_forged_metrics_or_unpinned_input():
    d = ready_draft()
    d["edges"][0]["initial_images_sha256"] = None
    with pytest.raises(ValueError, match="METER_IDENTITY_NOT_PINNED"):
        LocalProcessMeter(d, arm_id=d["model_arms"][0]["arm_id"], edge_id=d["edges"][0]["edge_id"])
    d = ready_draft()
    meter = LocalProcessMeter(d, arm_id=d["model_arms"][0]["arm_id"],
                              edge_id=d["edges"][0]["edge_id"])
    with pytest.raises(ValueError, match="INVALID_FORCE_DIAGNOSTIC"):
        meter.finish(status="NONCONVERGED", endpoint_max_force=float("nan"))
    with pytest.raises(ValueError, match="CONVERGENCE_REQUIRES"):
        meter.finish(status="CONVERGED")


@pytest.mark.parametrize("kind", ["simulated", "energy", "force", "model_calculation"])
def test_bad_phases_and_not_real_computations(kind):
    d = ready_draft()
    m = LocalProcessMeter(d, arm_id=d["model_arms"][0]["arm_id"], edge_id=d["edges"][0]["edge_id"])
    if kind == "simulated":
        with pytest.raises(ValueError, match="OUTSIDE_ALLOWED_PHASE"):
            m.record_call("simulated")
    else:
        with pytest.raises(ValueError, match="OUTSIDE_ALLOWED_PHASE"):
            m.record_call(kind)


def synthetic_envelopes(draft):
    out = []
    for edge in draft["edges"]:
        for arm in draft["model_arms"]:
            m = LocalProcessMeter(draft, arm_id=arm["arm_id"], edge_id=edge["edge_id"])
            with m.phase("endpoint_relax"):
                m.record_call("force")
                m.record_call("model_calculation")
            with m.phase("neb_optimize"):
                m.record_call("force")
                m.record_call("model_calculation")
            out.append(m.finish(status="NONCONVERGED"))
    return out


def test_event_envelope_cross_audit_is_count_only():
    from rhombus.benchmark.tier_a_local_meter import audit_local_meter_envelopes
    d = ready_draft()
    out = audit_local_meter_envelopes(d, synthetic_envelopes(d))
    assert out["recorded_pairs"] == 8
    assert out["meter_events_cross_checked"] == 32
    assert out["meter_source_authenticity"] == "NOT_INDEPENDENTLY_ATTESTED"
    assert out["performance_evaluation"] == "NOT_PERFORMED"


@pytest.mark.parametrize("tamper,match", [
    (lambda e: e[0].update(event_count=3), "INVALID_EVENT_SEQUENCE"),
    (lambda e: e[0]["receipt"]["total"].update(force_requests=999), "METER_EVENT_COUNTER_MISMATCH"),
    (lambda e: e[0].update(event_order_sha256="0"*64), "EVENT_HASH_MISMATCH"),
    (lambda e: e[0].update(execution_authorized_by_meter=True), "UNATTESTED_METER_PROMOTED"),
    (lambda e: e[0].update(em_dft=1), "UNKNOWN_METER_ENVELOPE_FIELDS"),
    (lambda e: e[0].update(raw_energy_values_saved=True), "UNATTESTED_METER_PROMOTED"),
])
def test_envelope_tampering_rejected(tamper, match):
    from rhombus.benchmark.tier_a_local_meter import audit_local_meter_envelopes
    d = ready_draft()
    envelopes = synthetic_envelopes(d)
    tamper(envelopes)
    with pytest.raises(ValueError, match=match):
        audit_local_meter_envelopes(d, envelopes)


def test_envelope_missing_pair_rejected():
    from rhombus.benchmark.tier_a_local_meter import audit_local_meter_envelopes
    d = ready_draft()
    envelopes = synthetic_envelopes(d)
    with pytest.raises(ValueError, match="COMPLETE_PAIRED_ENVELOPES_REQUIRED"):
        audit_local_meter_envelopes(d, envelopes[:-1])
