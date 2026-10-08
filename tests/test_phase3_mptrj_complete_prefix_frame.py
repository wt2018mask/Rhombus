"""Offline only: complete first-frame extraction inside a capped MPTrj prefix."""
from __future__ import annotations

import hashlib
import io
import json

import pytest
from pymatgen.core import Lattice, Structure

from scripts.development import probe_mptrj_source_prefix as probe


EXPECTED_TOTAL = 12_188_168_685


def _prefix(length: int = 4096) -> bytes:
    structure = Structure(
        Lattice.cubic(4), ["Li", "O"], [[0, 0, 0], [0.5, 0.5, 0.5]],
    )
    payload = {
        "mp/a~b": {
            "task-0": {
                "uncorrected_total_energy": -30.1,
                "corrected_total_energy": -31.5,
                "energy_per_atom": -15.75,
                "structure": structure.as_dict(),
            },
            "task-1": {"structure": structure.as_dict()},
        },
    }
    encoded = json.dumps(payload).encode()
    assert len(encoded) < length
    return encoded + b" " * (length - len(encoded))


def test_first_frame_has_valid_structure_and_three_separate_energy_field_presences():
    observation = probe.inspect_first_complete_frame_prefix(_prefix())
    assert observation["material_id"] == "mp/a~b"
    assert observation["frame_id"] == "task-0"
    assert observation["site_count"] == 2
    assert observation["complete_frame_parsed"] is True
    assert observation["energy_fields_present"] == {
        "uncorrected_total_energy": True,
        "corrected_total_energy": True,
        "energy_per_atom": True,
    }
    assert "training" not in observation


def test_first_frame_may_finish_even_if_rest_of_json_is_incomplete():
    payload = _prefix().rstrip()
    # The first frame is intact but the outer frame/dataset maps are truncated.
    assert probe.inspect_first_complete_frame_prefix(payload[:-4])["site_count"] == 2


def test_first_frame_truncated_in_structure_must_fail_closed():
    raw = _prefix()
    at = raw.find(b'"sites"')
    assert at > 0
    with pytest.raises(probe.PrefixProbeError):
        probe.inspect_first_complete_frame_prefix(raw[:at+12])


def test_invalid_structure_not_accepted_as_complete_frame():
    raw = b'{"mp-1":{"t":{"structure":{"@module":"pymatgen.core.structure","@class":"Structure","sites":[]}}}}'
    with pytest.raises(probe.PrefixProbeError, match="invalid pymatgen Structure|empty Structure"):
        probe.inspect_first_complete_frame_prefix(raw)


def test_duplicate_source_field_fails_closed():
    real = json.dumps(Structure(Lattice.cubic(3), ["Li"], [[0, 0, 0]]).as_dict())
    raw = ('{"mp-a":{"t":{"structure":' + real + ',"structure":' + real + '}}}').encode()
    with pytest.raises(probe.PrefixProbeError, match="malformed|duplicate"):
        probe.inspect_first_complete_frame_prefix(raw)


def test_refuses_over_budget_or_empty_preview():
    with pytest.raises(probe.PrefixProbeError, match="budget"):
        probe.inspect_first_complete_frame_prefix(b"")
    with pytest.raises(probe.PrefixProbeError, match="budget"):
        probe.inspect_first_complete_frame_prefix(b"0" * (probe.MAX_PREFIX_BYTES + 1))


class _Response:
    def __init__(self, payload: bytes, status=206):
        self.stream = io.BytesIO(payload)
        self.status = status
        self.headers = {
            "Content-Range": f"bytes 0-{len(payload)-1}/{EXPECTED_TOTAL}",
            "Content-Length": str(len(payload)),
        }
        self.read_called = False

    def read(self, amount):
        assert 0 <= amount <= 8192
        self.read_called = True
        return self.stream.read(amount)

    def geturl(self):
        return "https://signed-figshare-bucket.example/object"

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def test_realistic_206_simulation_parses_one_structure_but_not_full_dataset():
    data = _prefix()
    response = _Response(data)
    result = probe.probe_https_range(
        expected_total=EXPECTED_TOTAL,
        prefix_bytes=len(data),
        require_complete_frame=True,
        open_url=lambda request, timeout: response,
    )
    assert response.read_called is True
    assert result["observation"]["first_frame_structure"]["site_count"] == 2
    assert result["observation"]["complete_frame_parsed"] is True
    assert result["observation"]["complete_original_source_hashed"] is False
    assert result["observation"]["prefix_sha256"] == hashlib.sha256(data).hexdigest()
    assert result["training_lineage"]["training_frame_selection_attested"] is False
    assert result["authorization"]["execute_exposure_audit"] is False
    assert result["authorization"]["unseen_generalization_claim"] is False


def test_http_200_rejected_before_read_even_in_complete_frame_mode():
    response = _Response(_prefix(), status=200)
    with pytest.raises(probe.PrefixProbeError, match="206"):
        probe.probe_https_range(
            expected_total=EXPECTED_TOTAL, prefix_bytes=4096,
            require_complete_frame=True,
            open_url=lambda request, timeout: response,
        )
    assert response.read_called is False


def test_invalid_energy_field_blocks_completion_not_silently_coerced():
    source = _prefix()
    mutated = source.replace(b'-15.75', b'"not-a-number"')
    with pytest.raises(ValueError, match="finite numeric"):
        probe.inspect_first_complete_frame_prefix(mutated)


def test_raw_prefix_data_is_never_reported_or_persisted_by_parser():
    result = probe.inspect_first_complete_frame_prefix(_prefix())
    assert set(result) == {
        "material_id", "frame_id", "site_count", "reduced_formula",
        "energy_fields_present", "complete_frame_parsed",
    }
