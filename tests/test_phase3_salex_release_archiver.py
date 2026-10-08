"""Offline safety regression tests for frozen sAlex DRAFT release archival."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "scripts/release/archive_salex_evidence.py"
spec = importlib.util.spec_from_file_location("salex_release", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def sha(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


@pytest.fixture
def frozen(tmp_path, monkeypatch):
    root = tmp_path / "inputs"
    root.mkdir()
    blobs = {name: (name.encode("utf-8") + b"\0binary") for name in module.EXPECTED_PARTS}
    manifest = {
        "frozen_source_commit": module.SOURCE_COMMIT,
        "provenance": {"original_receipt_raw_bytes_available": False},
        "science": {"unseen_generalization_claim_authorized": False},
        "files": [],
        "validation": {},
    }
    for name, body in blobs.items():
        (root / name).write_bytes(body)
        manifest["files"].append({"name": name, "size_bytes": len(body), "sha256": sha(body)})
    membership = b"".join(blobs[n] for n in module.EXPECTED_PARTS[:5])
    overlap = blobs[module.EXPECTED_PARTS[5]]
    digests = {"membership": sha(membership), "overlap": sha(overlap)}
    monkeypatch.setattr(module, "EXPECTED_SOURCE_DIGESTS", digests)
    manifest["validation"]["compressed_membership_sha256"] = digests["membership"]
    manifest["validation"]["compressed_overlap_sha256"] = digests["overlap"]
    summary = b'{"salex_membership_row_count":10447765,"wbm_target_count":256963}'
    (root / module.SUMMARY_NAME).write_bytes(summary)
    monkeypatch.setattr(module, "EXPECTED_SUMMARY_DIGEST", sha(summary))
    manifest["validation"]["summary_json_sha256"] = sha(summary)
    path = tmp_path / module.MANIFEST_NAME
    path.write_text(json.dumps(manifest))
    return root, path, manifest


def test_full_local_dry_run_and_no_remote_calls(frozen, monkeypatch, capsys):
    root, path, _ = frozen
    monkeypatch.setattr(module, "gh", lambda *a, **k: pytest.fail("dry-run touched GitHub"))
    files = module.validate_local(root, path)
    assert len(files) == 8
    assert set(files) == set(module.EXPECTED_PARTS + [module.SUMMARY_NAME, module.MANIFEST_NAME])
    assert "SALEX_RELEASE_LOCAL_SHA256_PASS" in capsys.readouterr().out


def test_mutated_source_part_rejected(frozen):
    root, path, _ = frozen
    with (root / module.EXPECTED_PARTS[0]).open("ab") as stream:
        stream.write(b"BAD")
    with pytest.raises(module.ArchivalError, match="byte-size mismatch"):
        module.validate_local(root, path)


def test_missing_summary_fails(frozen):
    root, path, _ = frozen
    (root / module.SUMMARY_NAME).unlink()
    with pytest.raises(module.ArchivalError, match="summary JSON is missing"):
        module.validate_local(root, path)


def test_synthetic_receipt_authorization_is_rejected(frozen):
    root, path, manifest = frozen
    manifest["provenance"]["original_receipt_raw_bytes_available"] = True
    path.write_text(json.dumps(manifest))
    with pytest.raises(module.ArchivalError, match="receipt-state"):
        module.validate_local(root, path)


def test_scientific_claim_promotion_rejected(frozen):
    root, path, manifest = frozen
    manifest["science"]["unseen_generalization_claim_authorized"] = True
    path.write_text(json.dumps(manifest))
    with pytest.raises(module.ArchivalError, match="authorization"):
        module.validate_local(root, path)


def test_unexpected_remote_asset_fails_closed(frozen):
    root, path, _ = frozen
    files = module.validate_local(root, path)
    with pytest.raises(module.ArchivalError, match="unexpected"):
        module.validate_assets({"assets": [{"name": "unapproved-secret.txt"}]}, files)


def test_remote_digest_mismatch_fails_closed(frozen):
    root, path, _ = frozen
    files = module.validate_local(root, path)
    name, file = next(iter(files.items()))
    with pytest.raises(module.ArchivalError, match="digest/state mismatch"):
        module.validate_assets({"assets": [{
            "name": name, "size": file.stat().st_size,
            "digest": "sha256:" + "0" * 64, "state": "uploaded"
        }]}, files)


def test_existing_draft_upload_is_idempotent_never_published(frozen, monkeypatch):
    root, path, _ = frozen
    files = module.validate_local(root, path)
    assets = []
    calls = []
    monkeypatch.setattr(module.shutil, "which", lambda executable: "/usr/bin/gh")
    def fake_metadata(_tag):
        return {"tag_name": module.TAG, "draft": True, "target_commitish": module.SOURCE_COMMIT, "assets": assets}
    def fake_gh(args, **kwargs):
        calls.append(args)
        assert args[:2] == ["release", "upload"]
        assert "--clobber" not in args
        file = Path(args[3])
        assets.append({"name": file.name, "size": file.stat().st_size, "digest": "sha256:" + sha(file.read_bytes()), "state": "uploaded"})
        return {}
    monkeypatch.setattr(module, "verify_release_metadata", fake_metadata)
    monkeypatch.setattr(module, "gh", fake_gh)
    module.create_or_resume_draft(files)
    assert len(calls) == 8
    module.create_or_resume_draft(files)
    assert len(calls) == 8  # every already-verified file is skipped


def test_remote_digest_missing_never_overwrites(frozen, monkeypatch):
    root, path, _ = frozen
    files = module.validate_local(root, path)
    name, file = next(iter(files.items()))
    monkeypatch.setattr(module.shutil, "which", lambda executable: "/usr/bin/gh")
    monkeypatch.setattr(module, "verify_release_metadata", lambda tag: {
        "tag_name": module.TAG, "draft": True,
        "target_commitish": module.SOURCE_COMMIT,
        "assets": [{"name": name, "size": file.stat().st_size, "digest": None, "state": "uploaded"}],
    })
    monkeypatch.setattr(module, "gh", lambda *a, **k: pytest.fail("must not upload"))
    with pytest.raises(module.ArchivalError, match="digest/state mismatch"):
        module.create_or_resume_draft(files)


def test_draft_release_allows_lazy_tag_but_rejects_wrong_existing_tag(monkeypatch):
    release = {
        "tag_name": module.TAG,
        "draft": True,
        "target_commitish": module.SOURCE_COMMIT,
        "assets": [],
    }
    def lazy_api(resource, *, allow_not_found=False):
        return None if "/git/ref/tags/" in resource else release
    monkeypatch.setattr(module, "github_api", lazy_api)
    assert module.verify_release_metadata(module.TAG) == release

    def wrong_tag_api(resource, *, allow_not_found=False):
        if "/git/ref/tags/" in resource:
            return {"object": {"type": "commit", "sha": "0" * 40}}
        return release
    monkeypatch.setattr(module, "github_api", wrong_tag_api)
    with pytest.raises(module.ArchivalError, match="existing release tag"):
        module.verify_release_metadata(module.TAG)
