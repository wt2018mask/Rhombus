"""Local multipart checkpoint artifact regression tests."""
import json
import pytest
from rhombus.domain.checkpoint_bundle import pack_checkpoint_parts, verify_checkpoint_parts


def setup(tmp_path):
    src = tmp_path / "source.sqlite"
    src.write_bytes(b"abcdef" * 11)
    out = tmp_path / "bundle"
    out.mkdir()
    return src, out


def test_roundtrip_and_no_scientific_authorization(tmp_path):
    src,out = setup(tmp_path)
    meta = pack_checkpoint_parts(source=src, output_dir=out, bundle_id="s1", part_bytes=13)
    verify = verify_checkpoint_parts(output_dir=out, bundle_id="s1")
    assert verify["verified_bytes"] == len(src.read_bytes())
    assert verify["verified_parts"] == len(meta["parts"])
    assert verify["claim_authorized"] is False
    assert verify["external_durability_verified"] is False


def test_tampered_part_rejected(tmp_path):
    src,out = setup(tmp_path)
    pack_checkpoint_parts(source=src, output_dir=out, bundle_id="s1", part_bytes=13)
    (out / "s1.part-00000").write_bytes(b"x"*13)
    with pytest.raises(ValueError, match="checksum"):
        verify_checkpoint_parts(output_dir=out, bundle_id="s1")


def test_missing_part_and_forged_manifest_rejected(tmp_path):
    src,out = setup(tmp_path)
    pack_checkpoint_parts(source=src, output_dir=out, bundle_id="s1", part_bytes=13)
    m = out / "s1.bundle.json"
    doc = json.loads(m.read_text())
    doc["claim_authorized"] = True
    m.write_text(json.dumps(doc))
    with pytest.raises(ValueError, match="unauthorized"):
        verify_checkpoint_parts(output_dir=out, bundle_id="s1")
    doc["claim_authorized"] = False
    m.write_text(json.dumps(doc))
    (out/"s1.part-00001").unlink()
    with pytest.raises(ValueError, match="missing"):
        verify_checkpoint_parts(output_dir=out, bundle_id="s1")


def test_no_overwrite_and_traversal_rejected(tmp_path):
    src,out = setup(tmp_path)
    pack_checkpoint_parts(source=src, output_dir=out, bundle_id="s1")
    with pytest.raises(FileExistsError):
        pack_checkpoint_parts(source=src, output_dir=out, bundle_id="s1")
    with pytest.raises(ValueError, match="bundle_id"):
        pack_checkpoint_parts(source=src, output_dir=out, bundle_id="../escape")
