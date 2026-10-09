"""MPTrj complete-stream byte+frame identity fixture contracts. No large files."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import pytest
from pymatgen.core import Lattice, Structure

from rhombus.domain.mptrj import MPTrjFormatError
from rhombus.domain.mptrj_integrity import (
    MPTrjIntegrityError, verify_complete_mptrj_source,
)
from scripts.development import verify_mptrj_frames


def _fixture_bytes() -> bytes:
    structure = Structure(Lattice.cubic(4.0), ["Li", "O"], [[0, 0, 0], [0.5, 0.5, 0.5]]).as_dict()
    return json.dumps({
        "mp-test-1": {
            "task-a-0-0": {"structure": structure, "energy_per_atom": -1},
            "task-a-0-1": {"structure": structure, "force": [[0, 0, 0], [0, 0, 0]]},
        },
        "mp-test-2": {
            "task-b-1-0": {"structure": structure, "magmom": None},
        },
    }).encode()


def _verify(payload: bytes, *, expected_size=None, expected_md5=None,
            expected_frames=3, expected_sha256=None) -> dict:
    return verify_complete_mptrj_source(
        io.BytesIO(payload),
        expected_size=expected_size if expected_size is not None else len(payload),
        expected_md5=expected_md5 or hashlib.md5(payload).hexdigest(),
        expected_frames=expected_frames,
        expected_sha256=expected_sha256,
    )


def test_full_fixture_source_and_rows_validated_and_claims_closed():
    payload = _fixture_bytes()
    sha = hashlib.sha256(payload).hexdigest()
    proof = _verify(payload, expected_sha256=sha)
    assert proof["source_identity"]["computed_sha256"] == sha
    assert proof["source_identity"]["independent_sha256_matched"] is True
    assert proof["frame_coverage"]["parsed_frames"] == 3
    assert proof["frame_coverage"]["complete_json_consumed"] is True
    assert proof["model_training_lineage"]["exact_mace_mpa0_training_frame_selection"] == "UNATTESTED"
    assert proof["authorization"]["execute_wbm_training_exposure_audit"] is False
    assert proof["authorization"]["unseen_generalization_claim"] is False


def test_computed_sha256_not_spuriously_called_independently_verified():
    proof = _verify(_fixture_bytes())
    assert proof["source_identity"]["figshare_md5_matched"] is True
    assert proof["source_identity"]["independent_sha256_matched"] is False


def test_rejects_mismatched_size_before_producing_evidence():
    with pytest.raises(MPTrjIntegrityError, match="exceeded"):
        _verify(_fixture_bytes(), expected_size=1)
    with pytest.raises(MPTrjIntegrityError, match="size mismatch"):
        _verify(_fixture_bytes(), expected_size=len(_fixture_bytes()) + 1)


def test_rejects_mismatched_md5_and_sha256():
    with pytest.raises(MPTrjIntegrityError, match="MD5 mismatch"):
        _verify(_fixture_bytes(), expected_md5="0" * 32)
    with pytest.raises(MPTrjIntegrityError, match="SHA256 mismatch"):
        _verify(_fixture_bytes(), expected_sha256="f" * 64)


def test_rejects_insufficient_or_excess_frame_counts():
    with pytest.raises(MPTrjIntegrityError, match="count mismatch"):
        _verify(_fixture_bytes(), expected_frames=4)
    with pytest.raises(MPTrjIntegrityError, match="exceeded"):
        _verify(_fixture_bytes(), expected_frames=2)


def test_rejects_truncation_and_duplicate_material_or_frames():
    payload = _fixture_bytes()
    with pytest.raises(MPTrjFormatError):
        _verify(payload[:-30], expected_size=len(payload) - 30)
    repeated = payload.replace(b'"mp-test-2"', b'"mp-test-1"')
    with pytest.raises(MPTrjFormatError, match="duplicate material"):
        _verify(repeated)


def test_rejects_invalid_preflight_parameters():
    with pytest.raises(ValueError):
        _verify(_fixture_bytes(), expected_frames=0)
    with pytest.raises(ValueError):
        _verify(_fixture_bytes(), expected_md5="unknown")
    with pytest.raises(ValueError):
        _verify(_fixture_bytes(), expected_sha256="unknown")


def test_source_reader_refuses_unbounded_buffer():
    class Source(io.BytesIO):
        def read(self, size=-1):
            assert 0 <= size <= 65536, "unexpected unbounded frame read"
            return super().read(size)
    payload = _fixture_bytes()
    result = verify_complete_mptrj_source(
        Source(payload), expected_size=len(payload),
        expected_md5=hashlib.md5(payload).hexdigest(), expected_frames=3,
    )
    assert result["frame_coverage"]["parsed_frames"] == 3


def test_manual_cli_no_report_on_failed_stream_and_no_overwrite(tmp_path, monkeypatch):
    payload = _fixture_bytes()
    fixture_path = tmp_path / verify_mptrj_frames.FIGSHARE_FILENAME
    fixture_path.write_bytes(payload)
    report = tmp_path / "new-report.json"
    monkeypatch.setattr(
        verify_mptrj_frames, "canonical_source",
        lambda: {"size": len(payload), "md5": hashlib.md5(payload).hexdigest()},
    )
    monkeypatch.setattr(verify_mptrj_frames, "OFFICIAL_MPTRJ_FRAMES", 4)
    assert verify_mptrj_frames.main(["--source", str(fixture_path), "--report", str(report)]) == 1
    assert not report.exists()
    monkeypatch.setattr(verify_mptrj_frames, "OFFICIAL_MPTRJ_FRAMES", 3)
    assert verify_mptrj_frames.main(["--source", str(fixture_path), "--report", str(report)]) == 0
    evidence = json.loads(report.read_text(encoding="utf-8"))
    assert evidence["authorization"]["unseen_generalization_claim"] is False
    assert verify_mptrj_frames.main(["--source", str(fixture_path), "--report", str(report)]) == 1
    assert json.loads(report.read_text(encoding="utf-8")) == evidence


def test_original_figshare_license_erratum_is_corrected_append_only():
    root = Path(__file__).resolve().parents[1]
    orig = json.loads((root / "data/development/phase3_mptrj_figshare_metadata_v1.json").read_text())
    wrong = json.loads((root / "data/development/phase3_mptrj_figshare_license_correction_v1.json").read_text())
    final = json.loads((root / "data/development/phase3_mptrj_figshare_license_final_correction_v1.json").read_text())
    assert orig["canonical_source"]["license"] == "MIT"
    assert wrong["official_figshare_license"] == "CC BY 4.0"  # preserved erroneous historical artifact
    assert final["supersedes"].endswith("phase3_mptrj_figshare_license_correction_v1.json")
    assert final["verified_source_value"] == "MIT"
    assert final["source_article_id"] == 23713842
    assert final["authorization"]["unseen_generalization_claim"] is False



def test_progress_updates_only_after_complete_frames_not_verified_report():
    payload = _fixture_bytes()
    observed = []
    result = verify_complete_mptrj_source(
        io.BytesIO(payload),
        expected_size=len(payload),
        expected_md5=hashlib.md5(payload).hexdigest(),
        expected_frames=3,
        on_progress=lambda frames, prefetched: observed.append((frames, prefetched)),
        progress_every_frames=1,
    )
    assert [r[0] for r in observed] == [1, 2, 3]
    assert all(isinstance(r[1], int) and 0 <= r[1] <= len(payload) for r in observed)
    assert all(a[1] <= b[1] for a, b in zip(observed, observed[1:]))
    assert result["frame_coverage"]["parsed_frames"] == 3
    assert result["authorization"]["unseen_generalization_claim"] is False


def test_progress_callback_cannot_authorize_partial_or_failed_source():
    payload = _fixture_bytes()
    updates = []
    with pytest.raises(MPTrjIntegrityError, match="frame count exceeded"):
        verify_complete_mptrj_source(
            io.BytesIO(payload), expected_size=len(payload),
            expected_md5=hashlib.md5(payload).hexdigest(), expected_frames=2,
            on_progress=lambda n, b: updates.append((n, b)),
            progress_every_frames=1,
        )
    assert [r[0] for r in updates] == [1, 2]
    with pytest.raises(RuntimeError, match="abort progress"):
        verify_complete_mptrj_source(
            io.BytesIO(payload), expected_size=len(payload),
            expected_md5=hashlib.md5(payload).hexdigest(), expected_frames=3,
            on_progress=lambda *_: (_ for _ in ()).throw(RuntimeError("abort progress")),
            progress_every_frames=1,
        )


@pytest.mark.parametrize("progress_every", [0, -1, True, 1.5])
def test_invalid_progress_intervals_refused_before_reading(progress_every):
    with pytest.raises(ValueError, match="progress_every_frames"):
        verify_complete_mptrj_source(
            io.BytesIO(_fixture_bytes()), expected_size=1,
            expected_md5="0"*32, expected_frames=1,
            progress_every_frames=progress_every,
        )


def test_manual_full_file_progress_to_stderr_and_never_provisional_pass(tmp_path, monkeypatch, capsys):
    payload = _fixture_bytes()
    original = tmp_path / verify_mptrj_frames.FIGSHARE_FILENAME
    original.write_bytes(payload)
    result = tmp_path / "report.json"
    monkeypatch.setattr(
        verify_mptrj_frames, "canonical_source",
        lambda: {"size": len(payload), "md5": hashlib.md5(payload).hexdigest()},
    )
    monkeypatch.setattr(verify_mptrj_frames, "OFFICIAL_MPTRJ_FRAMES", 3)
    assert verify_mptrj_frames.main([
        "--source", str(original), "--report", str(result),
        "--progress-every-frames", "1",
    ]) == 0
    log = capsys.readouterr()
    assert "MPTRJ_FULL_STREAM_STARTED_UNVERIFIED" in log.err
    assert "MPTRJ_FULL_STREAM_PROGRESS_UNVERIFIED completed_frames=1" in log.err
    assert "MPTRJ_FULL_STREAM_PROGRESS_UNVERIFIED completed_frames=3" in log.err
    assert "MPTRJ_FULL_SOURCE_FRAME_IDENTITY_PASS" not in log.err
    assert "MPTRJ_FULL_SOURCE_FRAME_IDENTITY_PASS" in log.out
    assert json.loads(result.read_text())["frame_coverage"]["parsed_frames"] == 3


def test_report_existing_refused_before_large_source_read(tmp_path, monkeypatch):
    payload = _fixture_bytes()
    original = tmp_path / verify_mptrj_frames.FIGSHARE_FILENAME
    original.write_bytes(payload)
    report = tmp_path / "report.json"
    report.write_text("do not overwrite")
    monkeypatch.setattr(
        verify_mptrj_frames, "canonical_source",
        lambda: {"size": len(payload), "md5": hashlib.md5(payload).hexdigest()},
    )
    seen = []
    monkeypatch.setattr(
        verify_mptrj_frames, "verify_complete_mptrj_source",
        lambda *_args, **_kwargs: seen.append(True),
    )
    assert verify_mptrj_frames.main([
        "--source", str(original), "--report", str(report),
    ]) == 1
    assert seen == []
    assert report.read_text() == "do not overwrite"


def test_manual_full_source_mutation_detected_after_stream(tmp_path, monkeypatch, capsys):
    import os
    payload = _fixture_bytes()
    original = tmp_path / verify_mptrj_frames.FIGSHARE_FILENAME
    original.write_bytes(payload)
    report = tmp_path / "report.json"
    monkeypatch.setattr(
        verify_mptrj_frames, "canonical_source",
        lambda: {"size": len(payload), "md5": hashlib.md5(payload).hexdigest()},
    )
    monkeypatch.setattr(verify_mptrj_frames, "OFFICIAL_MPTRJ_FRAMES", 3)
    verifier = verify_mptrj_frames.verify_complete_mptrj_source

    def mutate_during_verification(*args, **kwargs):
        result = verifier(*args, **kwargs)
        now = original.stat().st_mtime_ns
        os.utime(original, ns=(now + 1000000000, now + 1000000000))
        return result

    monkeypatch.setattr(
        verify_mptrj_frames, "verify_complete_mptrj_source",
        mutate_during_verification,
    )
    assert verify_mptrj_frames.main(["--source", str(original), "--report", str(report)]) == 1
    assert not report.exists()
    logs = capsys.readouterr()
    assert "source changed" in logs.err
    assert "MPTRJ_FULL_SOURCE_FRAME_IDENTITY_PASS" not in logs.out
