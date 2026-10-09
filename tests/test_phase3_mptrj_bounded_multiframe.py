"""Offline first-N-frame diagnostic contracts, including strict REAL 256K anchor."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json

import pytest
from pymatgen.core import Lattice, Structure

from scripts.development import inspect_mptrj_prefix_frames as inspect
from scripts.development import probe_mptrj_source_prefix as probe


def frame(*, energy=True):
    structure = Structure(
        Lattice.cubic(4.2), ["Li", "O"], [[0, 0, 0], [.5, .5, .5]],
    )
    record = {"structure": structure.as_dict()}
    if energy:
        record.update(
            uncorrected_total_energy=-4.1,
            corrected_total_energy=-4.0,
            energy_per_atom=-2.0,
        )
    return record


def sample_and_anchor(*, count=3, size=262144, partial_tail=True):
    fragments = [
        '{"mp-1":{"frame-1":' + json.dumps(frame()),
        ',"frame-2":' + json.dumps(frame(energy=False)),
        '},"mp-2":{"frame-3":' + json.dumps(frame()),
    ]
    complete = fragments[:1] if count == 1 else fragments[:2] if count == 2 else fragments
    raw = "".join(complete) + (',"unfinished":{"structure":{"lattice":' if partial_tail else '}}')
    if not partial_tail and count != 3:
        raw = "".join(complete) + '}}'
    encoded = raw.encode()
    assert len(encoded) < size
    padded = encoded + b" " * (size - len(encoded))
    first = {"prefix_sha256": hashlib.sha256(padded[:262144]).hexdigest(),
             "first_frame_structure": {
                 "material_id": "mp-1",
                 "frame_id": "frame-1", "site_count": 2,
                 "reduced_formula": Structure.from_dict(frame()["structure"]).composition.element_composition.reduced_formula,
                 "energy_fields_present": {
                     "uncorrected_total_energy": True,
                     "corrected_total_energy": True,
                     "energy_per_atom": True,
                 },
             }}
    return padded, {"observation": first}


def test_complete_frames_only_are_retained_and_tail_is_never_certified():
    raw, anchor = sample_and_anchor()
    parsed = inspect.inspect_mptrj_capped_prefix(raw, frozen_receipt=anchor)
    assert parsed["complete_frame_count"] == 3
    assert [(v["material_id"], v["frame_id"]) for v in parsed["complete_frames"]] == [
        ("mp-1", "frame-1"), ("mp-1", "frame-2"), ("mp-2", "frame-3"),
    ]
    assert parsed["complete_frames"][0]["site_count"] == 2
    assert parsed["complete_frames"][1]["energy_fields_present"] == {
        "uncorrected_total_energy": False,
        "corrected_total_energy": False,
        "energy_per_atom": False,
    }
    assert "TAIL_UNVERIFIED" in parsed["tail_status"]
    assert parsed["sample_sha256"] == hashlib.sha256(raw).hexdigest()
    assert parsed["status"].endswith("TRAINING_UNATTESTED")
    for key in (
        "original_full_source_verified", "training_selected_frames_attested",
        "model_exposure_audit_authorized", "empirical_calibration_authorized",
        "unseen_generalization_claim_authorized",
    ):
        assert parsed[key] is False


def test_frame_limit_stops_after_two_complete_entries():
    raw, anchor = sample_and_anchor()
    result = inspect.inspect_mptrj_capped_prefix(raw, frozen_receipt=anchor, max_frames=2)
    assert result["complete_frame_count"] == 2
    assert result["tail_status"] == "FRAME_CAP_REACHED_TAIL_NOT_INSPECTED"


def test_allows_1mib_sample_but_preserves_only_256k_anchor():
    raw, anchor = sample_and_anchor(size=1048576)
    result = inspect.inspect_mptrj_capped_prefix(raw, frozen_receipt=anchor)
    assert result["sample_bytes"] == 1048576
    assert result["frozen_first_256k_sha256"] == anchor["observation"]["prefix_sha256"]


def test_changed_first_256k_is_rejected_even_if_valid_frames():
    raw, anchor = sample_and_anchor()
    altered = b" " + raw[1:]
    with pytest.raises(inspect.MPTrjMultiFrameError, match="frozen real observed"):
        inspect.inspect_mptrj_capped_prefix(altered, frozen_receipt=anchor)


def test_anchor_rejects_first_frame_metadata_drift_even_with_same_hash():
    raw, anchor = sample_and_anchor()
    modified = deepcopy(anchor)
    modified["observation"]["first_frame_structure"]["site_count"] = 7
    with pytest.raises(inspect.MPTrjMultiFrameError, match="first complete frame differs"):
        inspect.inspect_mptrj_capped_prefix(raw, frozen_receipt=modified)


@pytest.mark.parametrize("length", [0, 4, 262143, 262145, 1048577])
def test_sample_size_must_be_frozen_bounded_size(length):
    with pytest.raises(inspect.MPTrjMultiFrameError, match="exactly"):
        inspect.inspect_mptrj_capped_prefix(b" " * length, frozen_receipt={})


@pytest.mark.parametrize("limit", [0, -1, True, 17])
def test_rejects_invalid_frame_caps(limit):
    raw, anchor = sample_and_anchor()
    with pytest.raises(inspect.MPTrjMultiFrameError, match="16-frame budget"):
        inspect.inspect_mptrj_capped_prefix(raw, frozen_receipt=anchor, max_frames=limit)


def test_rejects_duplicate_frame_identifiers_or_nested_fields():
    src = json.dumps(frame())
    for prefix in (
        '{"mp-1":{"frame-1":' + src + ',"frame-1":' + src + '}}',
        '{"mp-1":{"frame-1":{"structure":' + json.dumps(frame()["structure"]) +
        ',"structure":' + json.dumps(frame()["structure"]) + '}}}',
    ):
        raw = prefix.encode()
        raw += b" " * (262144 - len(raw))
        anchor = {"observation": {"prefix_sha256": hashlib.sha256(raw).hexdigest()}}
        # Failure must not be turned into a partial "passed" observation.
        with pytest.raises(ValueError, match="duplicate"):
            inspect.inspect_mptrj_capped_prefix(raw, frozen_receipt=anchor)


def test_missing_first_complete_frame_fails_closed():
    raw = b'{"mp-1":{"first":{"structure":{"@module":"pymatgen.core.structure","sites":'
    raw += b" " * (262144 - len(raw))
    anchor = {"observation": {"prefix_sha256": hashlib.sha256(raw).hexdigest()}}
    with pytest.raises(ValueError, match="no complete|invalid"):
        inspect.inspect_mptrj_capped_prefix(raw, frozen_receipt=anchor)


def test_bounded_local_cli_does_not_make_network_requests(tmp_path, monkeypatch, capsys):
    raw, anchor = sample_and_anchor()
    target = tmp_path / "bounded.bin"
    target.write_bytes(raw)
    monkeypatch.setattr(inspect, "read_frozen_first_frame", lambda: anchor)
    result = inspect.inspect_local_mptrj_prefix(sample=target, max_frames=4)
    assert result["complete_frame_count"] == 3
    assert inspect.main(["--sample", str(target)]) == 0
    stdout = capsys.readouterr().out
    assert json.loads(stdout)["complete_frame_count"] == 3
    assert len(list(tmp_path.iterdir())) == 1
    link = tmp_path / "alias.bin"
    link.symlink_to(target)
    with pytest.raises(inspect.MPTrjMultiFrameError, match="regular"):
        inspect.inspect_local_mptrj_prefix(sample=link)


def test_first_real_anchor_is_enforced_by_default_when_supplied_sample_differs():
    raw, _ = sample_and_anchor()
    with pytest.raises(inspect.MPTrjMultiFrameError, match="frozen real observed"):
        inspect.inspect_mptrj_capped_prefix(raw)


def test_opt_in_local_probe_capture_1mib_fails_closed_pre_network(tmp_path, monkeypatch):
    from scripts.development import probe_mptrj_source_prefix as mod
    seen = []
    monkeypatch.setattr(mod, "canonical_source", lambda: {"size": 12188168685})
    monkeypatch.setattr(mod, "probe_https_range", lambda **kw: seen.append(kw))
    output, receipt = tmp_path / "raw.bin", tmp_path / "report.json"
    assert mod.main([
        "--probe", "--require-complete-frame", "--prefix-bytes", "500000",
        "--sample-output", str(output), "--report", str(receipt),
    ]) == 1
    assert seen == []


def test_opt_in_1mib_capture_receipt_uses_exact_bounded_sample(tmp_path, monkeypatch):
    from scripts.development import probe_mptrj_source_prefix as mod
    raw, _ = sample_and_anchor(size=1048576)
    monkeypatch.setattr(mod, "canonical_source", lambda: {"size": 12188168685})
    def fake_probe(*, sample_capture=None, **opts):
        assert opts["require_complete_frame"] is True
        assert opts["prefix_bytes"] == 1048576
        sample_capture(raw)
        return {"observation": {"prefix_sha256": hashlib.sha256(raw).hexdigest()}}
    monkeypatch.setattr(mod, "probe_https_range", fake_probe)
    output, receipt = tmp_path / "raw.bin", tmp_path / "report.json"
    assert mod.main([
        "--probe", "--require-complete-frame", "--prefix-bytes", "1048576",
        "--sample-output", str(output), "--report", str(receipt),
    ]) == 0
    assert output.read_bytes() == raw
    assert json.loads(receipt.read_text())["observation"]["prefix_sha256"] == hashlib.sha256(raw).hexdigest()
