"""Offline paired-checkpoint checks, including corruption and tampering."""
import hashlib
import json
import pytest
from rhombus.domain.checkpoint_staging import stage_verified_checkpoint
from rhombus.domain.checkpoint_restore import verify_staged_checkpoint


def staged(tmp_path):
    src = tmp_path / "source.sqlite"
    src.write_bytes(b"finalized synthetic bytes")
    out = tmp_path / "out"
    out.mkdir()
    stage_verified_checkpoint(finalized_source=src, trusted_directory=out,
        checkpoint_id="shard-0001", expected_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),
        source_sha256="a"*64, row_count=3)
    return out


def test_valid_pair_does_not_authorize_execution(tmp_path):
    result = verify_staged_checkpoint(trusted_directory=staged(tmp_path),checkpoint_id="shard-0001")
    assert result["artifact_bytes_verified"]
    assert not result["sqlite_integrity_verified"]
    assert not result["external_durability_verified"]
    assert not result["execution_authorized"]


def test_modified_bytes_are_rejected(tmp_path):
    path = staged(tmp_path)
    (path / "shard-0001.sqlite").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="SHA256"):
        verify_staged_checkpoint(trusted_directory=path,checkpoint_id="shard-0001")


def test_forged_manifest_is_rejected(tmp_path):
    path = staged(tmp_path)
    m = path / "shard-0001.manifest.json"
    data = json.loads(m.read_text())
    data["claim_authorized"] = True
    m.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="fail-closed"):
        verify_staged_checkpoint(trusted_directory=path,checkpoint_id="shard-0001")


def test_missing_pair_and_path_traversal_rejected(tmp_path):
    path = staged(tmp_path)
    (path / "shard-0001.manifest.json").unlink()
    with pytest.raises(ValueError, match="missing"):
        verify_staged_checkpoint(trusted_directory=path,checkpoint_id="shard-0001")
    with pytest.raises(ValueError, match="checkpoint_id"):
        verify_staged_checkpoint(trusted_directory=path,checkpoint_id="../escape")
