"""Fixture-only tests: opt-in 256KiB byte capture and offline independent replay."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import io
import json

import pytest
from pymatgen.core import Lattice, Structure

from scripts.development.probe_mptrj_source_prefix import (
    DEFAULT_PREFIX_BYTES, PrefixProbeError, probe_https_range,
)
from scripts.development.replay_mptrj_prefix_sample import (
    MPTrjPrefixReplayError, main, replay_mptrj_prefix_sample,
)

TOTAL = 12_188_168_685


def prefix():
    struct = Structure(Lattice.cubic(4.0), ["Li", "O"], [[0, 0, 0], [0.5, 0.5, 0.5]])
    frame = {
        "uncorrected_total_energy": -30.1,
        "corrected_total_energy": -31.5,
        "energy_per_atom": -15.75,
        "structure": struct.as_dict(),
    }
    data = json.dumps({"mp-1": {"task-1": frame}}).encode()
    assert len(data) < DEFAULT_PREFIX_BYTES
    return data + b" " * (DEFAULT_PREFIX_BYTES - len(data))


class FakeResponse:
    def __init__(self, raw, status=206):
        self.stream = io.BytesIO(raw)
        self.status = status
        self.headers = {
            "Content-Range": f"bytes 0-{len(raw)-1}/{TOTAL}",
            "Content-Length": str(len(raw)),
        }
    def geturl(self):
        return "https://cdn.figshare.example/immutable-object"
    def read(self, n):
        return self.stream.read(n)
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False


def evidence(tmp_path):
    raw = prefix()
    captured = []
    report = probe_https_range(
        expected_total=TOTAL,
        prefix_bytes=len(raw),
        require_complete_frame=True,
        open_url=lambda request, timeout: FakeResponse(raw),
        sample_capture=captured.append,
    )
    assert captured == [raw]
    source = tmp_path / "observed-256k.bin"
    receipt = tmp_path / "receipt.json"
    source.write_bytes(captured[0])
    receipt.write_text(json.dumps(report), encoding="utf-8")
    return source, receipt, report


def test_offline_replay_checks_exact_captured_source_frame_and_energy(tmp_path):
    sample, receipt, report = evidence(tmp_path)
    paths_before = sorted(p.name for p in tmp_path.iterdir())
    result = replay_mptrj_prefix_sample(sample=sample, receipt=receipt)
    assert result["status"] == "LOCAL_PREFIX_BYTES_AND_FIRST_FRAME_CONCORDANT_ONLY"
    assert result["sample_bytes"] == DEFAULT_PREFIX_BYTES
    assert result["sample_sha256"] == hashlib.sha256(sample.read_bytes()).hexdigest()
    assert result["site_count"] == 2
    assert result["first_frame_id"] == "task-1"
    for field in (
        "full_source_sha256_verified", "github_origin_authenticated",
        "mace_mpa0_training_frames_attested", "execute_exposure_audit",
        "empirical_calibration_use", "unseen_generalization_claim",
    ):
        assert result[field] is False
    assert sorted(p.name for p in tmp_path.iterdir()) == paths_before
    assert main(["--sample", str(sample), "--receipt", str(receipt)]) == 0


def test_any_prefix_byte_mutation_rejected_by_sha(tmp_path):
    sample, receipt, _ = evidence(tmp_path)
    sample.write_bytes(b"!" + sample.read_bytes()[1:])
    with pytest.raises(MPTrjPrefixReplayError, match="SHA256"):
        replay_mptrj_prefix_sample(sample=sample, receipt=receipt)


def test_forged_receipt_frame_claim_fails_after_valid_digest(tmp_path):
    sample, receipt, report = evidence(tmp_path)
    modified = deepcopy(report)
    modified["observation"]["first_frame_structure"]["site_count"] = 99
    receipt.write_text(json.dumps(modified), encoding="utf-8")
    with pytest.raises(MPTrjPrefixReplayError, match="structure/energy"):
        replay_mptrj_prefix_sample(sample=sample, receipt=receipt)


@pytest.mark.parametrize("change", [
    "truncated", "oversized", "symlink",
])
def test_rejects_unbounded_truncated_or_symlink_samples(tmp_path, change):
    sample, receipt, _ = evidence(tmp_path)
    if change == "truncated":
        sample.write_bytes(sample.read_bytes()[:-1])
    elif change == "oversized":
        sample.write_bytes(sample.read_bytes() + b"x")
    else:
        link = tmp_path / "sample-link"
        link.symlink_to(sample)
        sample = link
    with pytest.raises(MPTrjPrefixReplayError):
        replay_mptrj_prefix_sample(sample=sample, receipt=receipt)


def test_diagnostic_report_invalid_or_duplicate_json_rejected(tmp_path):
    sample, receipt, report = evidence(tmp_path)
    raw = receipt.read_text()
    receipt.write_text(raw.replace(
        '"figshare_file_id": 41619375',
        '"figshare_file_id": 41619375, "figshare_file_id": 41619375',
    ))
    with pytest.raises(ValueError, match="duplicate"):
        replay_mptrj_prefix_sample(sample=sample, receipt=receipt)
    receipt.write_text("{}")
    with pytest.raises(ValueError):
        replay_mptrj_prefix_sample(sample=sample, receipt=receipt)


def test_opt_in_capture_never_runs_for_failed_206(tmp_path):
    captured = []
    with pytest.raises(PrefixProbeError, match="206"):
        probe_https_range(
            expected_total=TOTAL, prefix_bytes=DEFAULT_PREFIX_BYTES,
            require_complete_frame=True,
            open_url=lambda request, timeout: FakeResponse(prefix(), status=200),
            sample_capture=captured.append,
        )
    assert captured == []


def test_no_implicit_sample_capture(tmp_path):
    raw = prefix()
    report = probe_https_range(
        expected_total=TOTAL, prefix_bytes=DEFAULT_PREFIX_BYTES,
        require_complete_frame=True,
        open_url=lambda request, timeout: FakeResponse(raw),
    )
    assert report["observation"]["prefix_sha256"] == hashlib.sha256(raw).hexdigest()
    assert "prefix" not in report

def test_cli_opt_in_raw_prefix_output_is_exact_and_replayable(tmp_path, monkeypatch):
    from scripts.development import probe_mptrj_source_prefix as probe_module
    sample, receipt, report = evidence(tmp_path)
    raw = sample.read_bytes()
    new_sample, new_report = tmp_path / "explicit-sample.bin", tmp_path / "explicit-report.json"
    monkeypatch.setattr(probe_module, "canonical_source", lambda: {"size": TOTAL})
    def simulated_probe(*, sample_capture=None, **kwargs):
        assert kwargs["require_complete_frame"] is True
        assert kwargs["prefix_bytes"] == DEFAULT_PREFIX_BYTES
        assert sample_capture is not None
        sample_capture(raw)
        return report
    monkeypatch.setattr(probe_module, "probe_https_range", simulated_probe)
    assert probe_module.main([
        "--probe", "--require-complete-frame",
        "--prefix-bytes", str(DEFAULT_PREFIX_BYTES),
        "--report", str(new_report), "--sample-output", str(new_sample),
    ]) == 0
    assert new_sample.read_bytes() == raw
    assert replay_mptrj_prefix_sample(
        sample=new_sample, receipt=new_report,
    )["status"] == "LOCAL_PREFIX_BYTES_AND_FIRST_FRAME_CONCORDANT_ONLY"


def test_cli_sample_output_rejects_incompatible_flags_before_get(tmp_path, monkeypatch):
    from scripts.development import probe_mptrj_source_prefix as probe_module
    monkeypatch.setattr(probe_module, "canonical_source", lambda: {"size": TOTAL})
    def forbidden_get(**kwargs):
        raise AssertionError("must fail before any network/probe call")
    monkeypatch.setattr(probe_module, "probe_https_range", forbidden_get)
    out = tmp_path / "new-report.json"
    sample = tmp_path / "new-sample.bin"
    assert probe_module.main([
        "--probe", "--report", str(out), "--sample-output", str(sample),
    ]) == 1
    assert not out.exists() and not sample.exists()
    assert probe_module.main([
        "--probe", "--require-complete-frame", "--prefix-bytes", "262144",
        "--report", str(out), "--sample-output", str(out),
    ]) == 1
    assert not out.exists()
