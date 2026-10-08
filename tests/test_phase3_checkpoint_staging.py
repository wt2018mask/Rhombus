"""Pure local checkpoint staging tests; no Kaggle or network needed."""
import hashlib
import json
from pathlib import Path

import pytest

from rhombus.domain.checkpoint_staging import stage_verified_checkpoint


def stage(tmp_path, *, expected=None, checkpoint_id="segment-0001"):
    src = tmp_path / "source.sqlite"
    if not src.exists():
        src.write_bytes(b"synthetic finalized bytes for staging")
    output = tmp_path / "artifacts"
    output.mkdir(exist_ok=True)
    sha = hashlib.sha256(src.read_bytes()).hexdigest()
    return stage_verified_checkpoint(
        finalized_source=src, trusted_directory=output,
        checkpoint_id=checkpoint_id, expected_sha256=expected or sha,
        source_sha256="a" * 64, row_count=3,
    )


def test_stages_content_and_manifest_without_scientific_claim(tmp_path):
    manifest = stage(tmp_path)
    artifact = tmp_path / "artifacts" / "segment-0001.sqlite"
    stored = json.loads((tmp_path / "artifacts" / "segment-0001.manifest.json").read_text())
    assert manifest == stored
    assert hashlib.sha256(artifact.read_bytes()).hexdigest() == manifest["artifact_sha256"]
    assert manifest["external_durability_verified"] is False
    assert manifest["source_stream_verified"] is False
    assert manifest["claim_authorized"] is False


def test_never_overwrites_prior_checkpoint(tmp_path):
    stage(tmp_path)
    with pytest.raises(FileExistsError):
        stage(tmp_path)
    assert len(list((tmp_path / "artifacts").glob("*.sqlite"))) == 1


def test_rejects_bad_hash_and_cleans_temporary_copy(tmp_path):
    with pytest.raises(ValueError, match="hash mismatch"):
        stage(tmp_path, expected="b" * 64)
    assert list((tmp_path / "artifacts").iterdir()) == []


@pytest.mark.parametrize("unsafe", ["../escape", "/etc/passwd", "UPPER", "", "space name"])
def test_checkpoint_names_are_safe(tmp_path, unsafe):
    with pytest.raises(ValueError, match="checkpoint_id"):
        stage(tmp_path, checkpoint_id=unsafe)


def test_wal_marker_rejected(tmp_path):
    src = tmp_path / "source.sqlite"
    src.write_bytes(b"sqlite bytes")
    Path(str(src) + "-wal").write_bytes(b"wal")
    with pytest.raises(ValueError, match="not finalized"):
        stage(tmp_path)


def test_symlink_file_rejected(tmp_path):
    real = tmp_path / "real.sqlite"
    real.write_bytes(b"data")
    link = tmp_path / "link.sqlite"
    try:
        link.symlink_to(real)
    except (NotImplementedError, OSError):
        pytest.skip("symlinks unavailable")
    out = tmp_path / "out"
    out.mkdir()
    with pytest.raises(ValueError, match="symlink"):
        stage_verified_checkpoint(
            finalized_source=link, trusted_directory=out,
            checkpoint_id="a", expected_sha256=hashlib.sha256(b"data").hexdigest(),
            source_sha256="a"*64, row_count=1,
        )
