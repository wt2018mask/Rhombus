"""Pure offline WBM v2 source profile fixtures; no remote transfer or Kaggle."""
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import pytest
from pymatgen.core import Lattice, Structure

from scripts.development import profile_wbm_v2_original_source as mod


def _structure():
    return Structure(Lattice.cubic(5), ["Na", "Cl"], [[0, 0, 0], [.5, .5, .5]])


def _rows():
    simple = _structure()
    double = simple.copy()
    double.make_supercell([2, 1, 1])
    different = Structure(
        Lattice.cubic(4), ["Li", "O"], [[0, 0, 0], [.5, .5, .5]]
    )
    return [
        {"material_id": "wbm-a", "initial_structure": simple.as_dict()},
        {"material_id": "wbm-b", "initial_structure": double.as_dict()},
        {"material_id": "wbm-c", "initial_structure": different.as_dict()},
    ]


def _make_archive(tmp_path: Path, rows=None, raw=None):
    compressed = tmp_path / "wbm.jsonl.gz"
    if raw is None:
        raw = b"".join(
            (json.dumps(row, sort_keys=True) + "\n").encode()
            for row in (_rows() if rows is None else rows)
        )
    with gzip.open(compressed, "wb") as out:
        out.write(raw)
    return compressed, hashlib.sha256(compressed.read_bytes()).hexdigest()


def _fixture_profile(path, sha, count=3):
    return mod.profile_frozen_wbm_gzip(
        path, expected_source_sha256=sha, expected_records=count,
        allow_fixture_identity=True
    )


def test_real_original_style_gzip_v2_cross_sitecount_profile(tmp_path):
    path, sha = _make_archive(tmp_path)
    got = _fixture_profile(path, sha)
    assert got["wbm_original_gzip_sha256"] == sha
    assert got["wbm_initial_structure_count"] == 3
    assert got["v2_composition_bucket_count"] == 2
    assert got["v1_composition_sitecount_subbucket_count"] == 3
    assert got["v2_buckets_with_multiple_sitecounts"] == 1
    assert got["v2_largest_composition_bucket_targets"] == 2
    assert got["v1_largest_composition_sitecount_subbucket_targets"] == 1
    assert got["v2_index_only_pair_proxy"] == 5
    assert got["v1_index_only_pair_proxy"] == 3
    assert got["candidate_fingerprint_protocol_id"] == (
        "rhombus-reduced-composition-candidate-fingerprint-v2"
    )
    assert got["mptrj_runtime_estimate_authorized"] is False
    assert got["unseen_generalization_authorized"] is False


def test_original_wbm_input_hash_is_mandatory(tmp_path):
    path, _ = _make_archive(tmp_path)
    with pytest.raises(mod.WBMSourceProfileError, match="SHA256 mismatch"):
        _fixture_profile(path, "0"*64)


def test_production_profile_refuses_fixture_identity_override(tmp_path):
    path, sha = _make_archive(tmp_path)
    with pytest.raises(mod.WBMSourceProfileError, match="noncanonical"):
        mod.profile_frozen_wbm_gzip(path, expected_source_sha256=sha,
                                    expected_records=3)
    with pytest.raises(mod.WBMSourceProfileError, match="SHA256 mismatch"):
        mod.profile_frozen_wbm_gzip(path)


def test_profile_rejects_duplicate_material_even_with_matching_source_sha(tmp_path):
    rows = _rows()
    rows[1]["material_id"] = rows[0]["material_id"]
    path, sha = _make_archive(tmp_path, rows)
    with pytest.raises(mod.WBMSourceProfileError, match="duplicate"):
        _fixture_profile(path, sha)


def test_profile_rejects_complete_hash_but_wrong_row_count(tmp_path):
    path, sha = _make_archive(tmp_path)
    with pytest.raises(mod.WBMSourceProfileError, match="incomplete"):
        _fixture_profile(path, sha, 4)
    with pytest.raises(mod.WBMSourceProfileError, match="more WBM"):
        _fixture_profile(path, sha, 2)


def test_profile_rejects_duplicate_json_field(tmp_path):
    row = _rows()[0]
    first = json.dumps(row).replace('"material_id": "wbm-a"',
                                    '"material_id": "wbm-a", "material_id": "wbm-a"')
    path, sha = _make_archive(tmp_path, raw=(first + "\n").encode())
    with pytest.raises(mod.WBMSourceProfileError, match="duplicate JSON field"):
        _fixture_profile(path, sha, 1)


def test_profile_rejects_missing_structure_and_unterminated_line(tmp_path):
    path, sha = _make_archive(
        tmp_path, raw=b'{"material_id":"wbm-a"}\n'
    )
    with pytest.raises(mod.WBMSourceProfileError, match="invalid or incomplete"):
        _fixture_profile(path, sha, 1)
    path.unlink()
    path, sha = _make_archive(
        tmp_path, raw=b'{"material_id":"wbm-a","initial_structure":{}}'
    )
    with pytest.raises(mod.WBMSourceProfileError, match="unterminated"):
        _fixture_profile(path, sha, 1)


def test_cli_never_writes_report_for_unauthenticated_archive(tmp_path):
    path, _ = _make_archive(tmp_path)
    report = tmp_path / "result.json"
    assert mod.main(["--wbm-gzip", str(path), "--report", str(report)]) == 1
    assert not report.exists()


def test_report_destination_must_not_overwrite_existing_path(tmp_path):
    path, _ = _make_archive(tmp_path)
    report = tmp_path / "result.json"
    report.write_text("PRESERVE")
    assert mod.main(["--wbm-gzip", str(path), "--report", str(report)]) == 1
    assert report.read_text() == "PRESERVE"


def test_profile_rejects_symlink_input(tmp_path):
    path, sha = _make_archive(tmp_path)
    link = tmp_path / "link.jsonl.gz"
    link.symlink_to(path)
    with pytest.raises(mod.WBMSourceProfileError, match="nonsymlink"):
        _fixture_profile(link, sha)


def test_verified_gzip_path_replacement_after_hash_is_rejected(tmp_path, monkeypatch):
    original_path, sha = _make_archive(tmp_path)
    replacement = tmp_path / "replacement.jsonl.gz"
    with gzip.open(replacement, "wb") as out:
        out.write(b'{"material_id":"different"}\n')
    real_hash = mod._frozen_source_sha256
    calls = 0

    def replace_after_hash(source, *, max_bytes):
        nonlocal calls
        result = real_hash(source, max_bytes=max_bytes)
        calls += 1
        if calls == 1:
            replacement.replace(original_path)
        return result

    monkeypatch.setattr(mod, "_frozen_source_sha256", replace_after_hash)
    with pytest.raises(mod.WBMSourceProfileError, match="source changed"):
        _fixture_profile(original_path, sha)
    assert calls == 2


def test_verified_gzip_in_place_mutation_during_profile_is_rejected(tmp_path, monkeypatch):
    path, sha = _make_archive(tmp_path)
    real_hash = mod._frozen_source_sha256
    calls = 0

    def corrupt_before_final_hash(source, *, max_bytes):
        nonlocal calls
        calls += 1
        if calls == 2:
            with path.open("r+b") as writer:
                writer.seek(0)
                writer.write(b"corrupted")
        return real_hash(source, max_bytes=max_bytes)

    monkeypatch.setattr(mod, "_frozen_source_sha256", corrupt_before_final_hash)
    with pytest.raises(mod.WBMSourceProfileError, match="source changed"):
        _fixture_profile(path, sha)
    assert calls == 2


def test_verified_gzip_uses_one_open_descriptor_and_two_hash_passes(tmp_path, monkeypatch):
    path, sha = _make_archive(tmp_path)
    real_hash = mod._frozen_source_sha256
    descriptors = []

    def record_descriptor(source, *, max_bytes):
        descriptors.append(source.fileno())
        return real_hash(source, max_bytes=max_bytes)

    monkeypatch.setattr(mod, "_frozen_source_sha256", record_descriptor)
    result = _fixture_profile(path, sha)
    assert result["wbm_initial_structure_count"] == 3
    assert len(descriptors) == 2 and descriptors[0] == descriptors[1]
