"""Security scanner fails closed on credentials, symlinks and corrupt text."""
import importlib.util
from pathlib import Path
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/security/scan_outgoing_artifacts.py"
spec = importlib.util.spec_from_file_location("outgoing_scan", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_valid_recovery_bundle(tmp_path):
    (tmp_path / "receipt.json").write_text('{"status":"RETRIEVED_AND_INDEPENDENTLY_VERIFIED"}')
    assert module.scan_directory(tmp_path) == (1, 0)
    # A science hash does not clear an uninspected binary export.
    (tmp_path / "index.zst.part0000").write_bytes(b"binary")
    with pytest.raises(ValueError, match="opaque"):
        module.scan_directory(tmp_path)


@pytest.mark.parametrize("body", [
    "Authorization: Bearer fake_access_secret",
    "api_key=supersecretvalue",
    "github_pat_" + "x" * 35,
    "https://someone:password@example.invalid/thing",
])
def test_credential_patterns_fail_closed(tmp_path, body):
    (tmp_path / "receipt.json").write_text(body)
    with pytest.raises(ValueError):
        module.scan_directory(tmp_path)


def test_symlinks_and_unknown_artifacts_fail_closed(tmp_path):
    target = tmp_path / "data.json"
    target.write_text('{"a":1}')
    (tmp_path / "pointer.json").symlink_to(target)
    with pytest.raises(ValueError, match="symlink"):
        module.scan_directory(tmp_path)
    (tmp_path / "pointer.json").unlink()
    (tmp_path / "unknown.bin").write_bytes(b"abc")
    with pytest.raises(ValueError, match="extension"):
        module.scan_directory(tmp_path)


def test_no_text_evidence_fail_closed(tmp_path):
    with pytest.raises(ValueError, match="no text"):
        module.scan_directory(tmp_path)
