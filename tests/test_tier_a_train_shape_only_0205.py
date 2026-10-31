"""Synthetic and owner-optional negative tests; NO target/energy/force decoding."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import zipfile
from copy import deepcopy

import pytest
from rhombus.benchmark.tier_a_train_shape_only import scan_pinned_train_initial_shapes


def _xyz(*, nframes=5, symbols=("Li", "O"), wrong_order=False, truncate=False,
         oversized_line=False):
    parts = []
    for frame in range(nframes):
        order = symbols[::-1] if wrong_order and frame == 1 else symbols
        parts.append(f"{len(order)}\n".encode())
        parts.append(b'Lattice="1 0 0 0 1 0 0 0 1" Properties=species:S:1:pos:R:3:energies:R:1 E_SECRET_MARKER\n')
        for i, symbol in enumerate(order):
            if truncate and frame == nframes - 1 and i == len(order) - 1:
                continue
            parts.append(f"{symbol} 0 0 0 E_SECRET_MARKER\n".encode() if not oversized_line else f"{symbol} ".encode() + b"Z"*17000 + b"\n")
    return b"".join(parts)


def _fixture(tmp_path, **changes):
    members = [f"nebDFT2k/mp-{j}_0_1_0_0_0_init.xyz" for j in range(1, 5)]
    zipped = tmp_path/"synthetic.zip"
    identities=[]
    with zipfile.ZipFile(zipped,"w",compression=zipfile.ZIP_DEFLATED) as z:
        for j,name in enumerate(members):
            data = _xyz(**changes) if j == 0 else _xyz()
            z.writestr(name, data)
            identities.append({"edge_id": name.split("/")[-1].removesuffix("_init.xyz"),
                               "group_id": f"CHEMSYS:Li-T{j}", "zip_member":name,
                               "raw_uncompressed_bytes":len(data),
                               "raw_uncompressed_sha256":sha256(data).hexdigest()})
        z.writestr("nebDFT2k/heldout_relaxed.xyz",b"DO_NOT_OPEN_SECRET_REFERENCE")
    return zipped, identities


def _audit(zipped, identities):
    return scan_pinned_train_initial_shapes(
        archive=zipped, identities=identities,
        archive_sha256=sha256(zipped.read_bytes()).hexdigest(),
        archive_size_bytes=zipped.stat().st_size)


def test_shape_only_valid_ignores_energy_like_fields_and_sealed_member(tmp_path):
    zipped, items=_fixture(tmp_path)
    report=_audit(zipped,items)
    assert [x["initial_frames"] for x in report["shape_rows"]]==[5]*4
    assert [x["atoms_per_frame"] for x in report["shape_rows"]]==[2]*4
    assert [x["lithium_atoms_per_frame"] for x in report["shape_rows"]]==[1]*4
    assert "E_SECRET_MARKER" not in json.dumps(report)
    assert "DO_NOT_OPEN_SECRET_REFERENCE" not in json.dumps(report)
    assert report["execution_authorized"] is False
    assert report["single_li_hop_physically_verified"] is False

@pytest.mark.parametrize("kw,expected",[
    ({"wrong_order":True},"ORDER_MISMATCH"),
    ({"truncate":True},"TRUNCATED"),
    ({"symbols":("O","O")},"LI_ABSENT"),
    ({"oversized_line":True},"LINE_TOO_LONG"),
    ({"nframes":17},"FRAME_BUDGET"),
])
def test_malformed_geometry_structure_rejected(tmp_path,kw,expected):
    zipped,items=_fixture(tmp_path,**kw)
    with pytest.raises(ValueError,match=expected):_audit(zipped,items)


def test_expected_member_sha_mismatch(tmp_path):
    zipped,items=_fixture(tmp_path)
    items[0]["raw_uncompressed_sha256"]="0"*64
    with pytest.raises(ValueError,match="SHA256_OR_LENGTH_MISMATCH"):_audit(zipped,items)


def test_zip_sha_mismatch(tmp_path):
    zipped,items=_fixture(tmp_path)
    with pytest.raises(ValueError,match="ARCHIVE_SHA256_MISMATCH"):
        scan_pinned_train_initial_shapes(archive=zipped,identities=items,
            archive_sha256="0"*64,archive_size_bytes=zipped.stat().st_size)


def test_member_path_injection_rejected(tmp_path):
    zipped,items=_fixture(tmp_path)
    items[0]["zip_member"]="../nebDFT2k/heldout_relaxed.xyz"
    with pytest.raises(ValueError,match="UNSAFE_OR_MISMATCHED_INPUT_PATH"):_audit(zipped,items)


def test_duplicate_group_rejected(tmp_path):
    zipped,items=_fixture(tmp_path)
    items[0]["group_id"]=items[1]["group_id"]
    with pytest.raises(ValueError,match="DUPLICATE_MEMBER_OR_CHEMISTRY_GROUP"):_audit(zipped,items)


def test_unexpected_extra_identity_fields_rejected(tmp_path):
    zipped,items=_fixture(tmp_path)
    items[0]["em_dft"]=1.0
    with pytest.raises(ValueError,match="INPUT_IDENTITY_EXACT_FIELDS_REQUIRED"):_audit(zipped,items)


def test_unexpected_archive_size_rejected(tmp_path):
    zipped,items=_fixture(tmp_path)
    with pytest.raises(ValueError,match="ARCHIVE_UNTRUSTED_SIZE_OR_TYPE"):
        scan_pinned_train_initial_shapes(archive=zipped,identities=items,
          archive_sha256=sha256(zipped.read_bytes()).hexdigest(),archive_size_bytes=1)


def test_extra_noninitial_members_never_needed(tmp_path):
    zipped,items=_fixture(tmp_path)
    report=_audit(zipped,items)
    assert report["relaxed_or_heldout_inputs_opened"] is False
