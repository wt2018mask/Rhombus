"""Fixture-only MPTrj nested JSON reader scientific contract tests."""
from __future__ import annotations

import io
import json

import pytest
from pymatgen.core import Lattice, Structure

from rhombus.domain.mptrj import (
    MPTrjFormatError, iter_mptrj_frames, iter_mptrj_membership_records,
)


def _structure():
    return Structure(
        Lattice.cubic(4.0),
        ["Li", "O"],
        [[0, 0, 0], [0.5, 0.5, 0.5]],
    ).as_dict()


def _fixture():
    return {
        "mp-1": {
            "t/1": {"structure": _structure(), "energy_per_atom": -2.1},
            "t~2": {"structure": _structure(), "force": [[0, 0, 0], [0, 0, 0]]},
        },
        "mp-2": {"run3": {"structure": _structure(), "magmom": 1.0}},
    }


def _source(obj) -> io.BytesIO:
    return io.BytesIO(json.dumps(obj, ensure_ascii=False).encode("utf-8"))


def test_streams_exact_frame_ids_and_rfc6901_locators():
    rows = list(iter_mptrj_frames(_source(_fixture())))
    assert [(r.material_id, r.frame_id, r.source_locator) for r in rows] == [
        ("mp-1", "t/1", "/mp-1/t~11"),
        ("mp-1", "t~2", "/mp-1/t~02"),
        ("mp-2", "run3", "/mp-2/run3"),
    ]
    assert all(len(row.structure) == 2 for row in rows)
    assert rows[0].structure.composition.element_composition.reduced_formula == Structure.from_dict(_structure()).composition.element_composition.reduced_formula


def test_produces_diagnostic_membership_one_frame_at_a_time():
    records = list(iter_mptrj_membership_records(
        _source(_fixture()),
        fingerprint=lambda structure: "a" * 64,
        prototype_group=lambda structure: "synthetic-fixture-group",
    ))
    assert len(records) == 3
    assert [r.record_id for r in records] == ["/mp-1/t~11", "/mp-1/t~02", "/mp-2/run3"]
    assert all(r.dataset_id == "MPTrj" and r.site_count == 2 for r in records)
    assert all(r.prototype_group == "synthetic-fixture-group" for r in records)


@pytest.mark.parametrize("raw", [
    b"[]",
    b'{"mp-1":[]}',
    b'{"mp-1":{"frame-1":[]}}',
    b'{"mp-1":{"frame-1":{}}}',
    b'{"mp-1":{"frame-1":{"structure":[]}}}',
    b'{"mp-1":{"frame-1":{"structure":null}}}',
    b'{"mp-1":{"frame-1":{"structure":{}}}}',
    b'{}',
    b'{"mp-1": {',
])
def test_rejects_missing_malformed_or_incomplete_structure(raw):
    with pytest.raises((MPTrjFormatError, ValueError)):
        list(iter_mptrj_frames(io.BytesIO(raw)))


def test_rejects_duplicate_material_ids():
    raw = b'{"mp-1":{},"mp-1":{}}'
    with pytest.raises(MPTrjFormatError, match="duplicate material"):
        list(iter_mptrj_frames(io.BytesIO(raw)))


def test_rejects_duplicate_frame_ids():
    raw = b'{"mp-1":{"a":{},"a":{}}}'
    with pytest.raises(MPTrjFormatError):
        list(iter_mptrj_frames(io.BytesIO(raw)))


def test_rejects_duplicate_inner_frame_keys():
    structure = json.dumps(_structure()).encode()
    raw = b'{"mp-1":{"frame-1":{"structure":' + structure + b',"structure":' + structure + b'}}}'
    with pytest.raises(MPTrjFormatError, match="duplicate JSON member"):
        list(iter_mptrj_frames(io.BytesIO(raw)))


@pytest.mark.parametrize("extra", [b"{}", b"null", b"garbage"])
def test_rejects_second_top_level_json_or_trailing_garbage(extra):
    raw = json.dumps(_fixture()).encode() + extra
    with pytest.raises((MPTrjFormatError, ValueError)):
        list(iter_mptrj_frames(io.BytesIO(raw)))


def test_rejects_event_and_scalar_budget():
    src = _source(_fixture()).getvalue()
    with pytest.raises(MPTrjFormatError, match="event budget"):
        list(iter_mptrj_frames(io.BytesIO(src), max_frame_events=2))
    with pytest.raises(MPTrjFormatError, match="scalar budget"):
        list(iter_mptrj_frames(io.BytesIO(src), max_frame_scalar_chars=2))


def test_rejects_key_caps_and_invalid_limits():
    src = _source(_fixture()).getvalue()
    with pytest.raises(MPTrjFormatError, match="material-ID"):
        list(iter_mptrj_frames(io.BytesIO(src), max_material_keys=1))
    with pytest.raises(MPTrjFormatError, match="frame-ID"):
        list(iter_mptrj_frames(io.BytesIO(src), max_frames_per_material=1))
    with pytest.raises(ValueError, match="resource limits"):
        list(iter_mptrj_frames(io.BytesIO(src), max_frame_events=0))


def test_fixture_stream_is_incremental_and_never_reads_entire_input():
    class BoundedRead(io.BytesIO):
        def __init__(self, data):
            super().__init__(data)
            self.max_requested = 0
        def read(self, size=-1):
            assert 0 <= size <= 65536, "unbounded source read forbidden"
            self.max_requested = max(self.max_requested, size)
            return super().read(size)

    source = BoundedRead(_source(_fixture()).getvalue())
    assert len(list(iter_mptrj_frames(source))) == 3
    assert source.max_requested <= 65536


def test_original_license_record_and_new_correcting_erratum_both_traceable():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    wrong = json.loads((root / "data/development/phase3_mptrj_figshare_license_correction_v1.json").read_text())
    corrected = json.loads((root / "data/development/phase3_mptrj_figshare_license_final_correction_v1.json").read_text())
    assert wrong["official_figshare_license"] == "CC BY 4.0"  # historical error preserved
    assert corrected["verified_source_value"] == "MIT"
    assert corrected["source_article_id"] == 23713842
    assert corrected["authorization"]["unseen_generalization_claim"] is False
    assert corrected["authorization"]["execute_exposure_audit"] is False
