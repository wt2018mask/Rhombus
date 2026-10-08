"""No-network tests for a repeatable real 256KiB MPTrj source observation."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import io
import json
import shutil

import pytest
from pymatgen.core import Lattice, Structure

from scripts.development import reobserve_mptrj_frozen_prefix as replay
from scripts.development import probe_mptrj_source_prefix as probe

TOTAL = 12_188_168_685


def prior():
    return replay.read_frozen_first_frame()


def test_frozen_real_evidence_preflight_uses_original_git_archive():
    receipt = prior()
    assert receipt["observation"]["prefix_sha256"] == replay.EXPECTED_SOURCE_SHA_PREFIX
    assert receipt["observation"]["first_frame_structure"]["site_count"] == 28
    assert receipt["observation"]["first_frame_structure"]["reduced_formula"] == "Sm2CuAs3O"


def test_identical_real_receipt_comparison_is_diagnostic_not_scientific_promoted():
    source = prior()
    current = deepcopy(source)
    current["source_metadata"]["redirect_host"] = "different-cdn-verified-https.example"
    result = replay.compare_bounded_mptrj_observations(current, source)
    assert result["status"] == "SAME_256K_PREFIX_SHA256_AND_FIRST_FRAME_ONLY"
    assert result["prefix_bytes"] == 262144
    assert result["prefix_sha256"] == replay.EXPECTED_SOURCE_SHA_PREFIX
    for key in ("full_original_source_sha256_verified", "mace_mpa0_training_membership_attested",
                "execute_exposure_audit", "empirical_calibration_use", "unseen_generalization_claim"):
        assert result[key] is False


@pytest.mark.parametrize(("field", "value"), [
    ("prefix_sha256", "0" * 64),
    ("first_material_id", "mp-999"),
    ("first_frame_id", "other-task"),
])
def test_new_sample_mismatch_fails_closed(field, value):
    source = prior()
    new = deepcopy(source)
    new["observation"][field] = value
    if field != "prefix_sha256":
        # Keep the self-consistent schema while departing from the actual prior observation.
        structure_field = "material_id" if field == "first_material_id" else "frame_id"
        new["observation"]["first_frame_structure"][structure_field] = value
    with pytest.raises(replay.MPTrjReobservationError, match="differ|disagreement"):
        replay.compare_bounded_mptrj_observations(new, source)


@pytest.mark.parametrize(("field", "value"), [
    ("site_count", 29),
    ("reduced_formula", "Sm2CuAs2O"),
])
def test_parser_semantic_drift_detected_even_when_digest_same(field, value):
    source = prior()
    new = deepcopy(source)
    new["observation"]["first_frame_structure"][field] = value
    with pytest.raises(replay.MPTrjReobservationError, match="disagreement"):
        replay.compare_bounded_mptrj_observations(new, source)


def test_energy_label_presence_drift_is_not_silently_accepted():
    source = prior()
    new = deepcopy(source)
    new["observation"]["first_frame_structure"]["energy_fields_present"]["energy_per_atom"] = False
    with pytest.raises(replay.MPTrjReobservationError, match="disagreement"):
        replay.compare_bounded_mptrj_observations(new, source)


def test_frozen_archive_modification_fails_before_remote_get(tmp_path, monkeypatch):
    shutil.copytree(replay.EVIDENCE_DIR, tmp_path / "evidence")
    monkeypatch.setattr(replay, "EVIDENCE_DIR", tmp_path / "evidence")
    archive = replay.EVIDENCE_DIR / "diagnostic.zip"
    archive.write_bytes(archive.read_bytes()[:-1] + b"X")
    mock_get = []
    monkeypatch.setattr(replay, "probe_https_range", lambda **kw: mock_get.append(kw))
    with pytest.raises(ValueError):
        replay.reobserve_frozen_mptrj_prefix()
    assert mock_get == []


def test_cli_requires_opt_in_before_any_remote_get(monkeypatch, capsys):
    monkeypatch.setattr(replay, "reobserve_frozen_mptrj_prefix",
                        lambda: (_ for _ in ()).throw(AssertionError("must not run")))
    assert replay.main([]) == 1
    report = capsys.readouterr()
    assert report.out == ""
    assert "explicit --reobserve" in report.err


def test_expected_range_get_is_single_256k_and_does_not_persist(tmp_path, monkeypatch):
    # In this unit test, a synthetic *source* produces a new synthetic
    # baseline. The real pinned digest tests above are independent.
    structure = Structure(Lattice.cubic(4), ["Li", "O"], [[0, 0, 0], [0.5, 0.5, 0.5]])
    raw = json.dumps({"mp-synthetic": {"frame-0": {
        "uncorrected_total_energy": -1.2, "corrected_total_energy": -1.1,
        "energy_per_atom": -0.55, "structure": structure.as_dict(),
    }}}).encode()
    raw += b" " * (262144 - len(raw))

    class Response:
        status = 206
        headers = {
            "Content-Range": f"bytes 0-262143/{TOTAL}",
            "Content-Length": "262144",
        }
        def __init__(self):
            self.stream = io.BytesIO(raw)
        def read(self, n):
            assert n <= 8192
            return self.stream.read(n)
        def geturl(self):
            return "https://s3-eu-west-1.amazonaws.com/data/example"
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False

    requests = []
    def fake_urlopen(req, timeout):
        assert req.full_url == probe.CANONICAL_DOWNLOAD_URL
        assert req.get_header("Range") == "bytes=0-262143"
        assert timeout == 30
        requests.append(req)
        return Response()

    new = probe.probe_https_range(
        expected_total=TOTAL, prefix_bytes=262144,
        require_complete_frame=True, open_url=fake_urlopen,
    )
    old = deepcopy(new)
    old["source_metadata"]["redirect_host"] = "prior-cdn.example"
    assert replay.compare_bounded_mptrj_observations(new, old)["prefix_sha256"] == hashlib.sha256(raw).hexdigest()
    assert len(requests) == 1
    assert list(tmp_path.iterdir()) == []


def test_real_anchor_and_new_mocked_probe_one_read_and_zero_writes(tmp_path, monkeypatch):
    saved = prior()
    calls = []
    monkeypatch.setattr(replay, "canonical_source", lambda: {"size": TOTAL})
    def fake_probe(**kwargs):
        calls.append(kwargs)
        return deepcopy(saved)
    monkeypatch.setattr(replay, "probe_https_range", fake_probe)
    before = sorted(p.name for p in tmp_path.iterdir())
    report = replay.reobserve_frozen_mptrj_prefix(open_url=lambda *args, **kwargs: None)
    assert len(calls) == 1
    assert calls[0]["prefix_bytes"] == 262144
    assert calls[0]["require_complete_frame"] is True
    assert report["status"] == "SAME_256K_PREFIX_SHA256_AND_FIRST_FRAME_ONLY"
    assert sorted(p.name for p in tmp_path.iterdir()) == before


def test_no_remote_get_if_registry_source_size_changes(monkeypatch):
    called = []
    monkeypatch.setattr(replay, "canonical_source", lambda: {"size": TOTAL - 1})
    monkeypatch.setattr(replay, "probe_https_range", lambda **kwargs: called.append(kwargs))
    with pytest.raises(replay.MPTrjReobservationError, match="source size changed"):
        replay.reobserve_frozen_mptrj_prefix()
    assert not called
