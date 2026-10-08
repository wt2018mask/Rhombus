"""No-network tests for bounded original MPTrj byte-range probing."""
from __future__ import annotations

import hashlib
import io
import json

import pytest

from scripts.development import probe_mptrj_source_prefix as probe


EXPECTED_TOTAL = 12_188_168_685


def fixture_bytes(length=4096):
    structure = '{"@module":"pymatgen.core.structure","@class":"Structure","sites":[]}'
    first = ('{"mp-example":{"task/a-1":{"energy_per_atom":-1.5,'
             '"structure":' + structure + '}}}').encode()
    assert len(first) < length
    return first + b" " * (length - len(first))


class FakeResponse:
    def __init__(self, payload, *, status=206, headers=None,
                 url="https://s3.mock.example/redirected-object"):
        self.buffer = io.BytesIO(payload)
        self.status = status
        self.headers = headers if headers is not None else {
            "Content-Range": f"bytes 0-{len(payload)-1}/{EXPECTED_TOTAL}",
            "Content-Length": str(len(payload)),
        }
        self.url = url
        self.bytes_read = 0
        self.read_called = False

    def geturl(self):
        return self.url

    def read(self, count):
        self.read_called = True
        if count < 0 or count > 8192:
            raise AssertionError("unbounded network body read")
        data = self.buffer.read(count)
        self.bytes_read += len(data)
        return data

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def _run(payload=None, *, n=4096, status=206, headers=None, url=None):
    if payload is None:
        payload = fixture_bytes(n)
    response = FakeResponse(
        payload, status=status,
        headers=headers, url=url or "https://example-s3.test/signed",
    )
    observed = {}

    def urlopen(request, *, timeout):
        observed["url"] = request.full_url
        observed["range"] = request.get_header("Range")
        observed["encoding"] = request.get_header("Accept-encoding")
        observed["timeout"] = timeout
        return response

    return response, observed, lambda: probe.probe_https_range(
        expected_total=EXPECTED_TOTAL, prefix_bytes=n, open_url=urlopen,
    )


def test_reads_only_exact_https_range_and_records_non_authoritative_observation():
    response, request, run = _run()
    record = run()
    assert request["url"] == "https://ndownloader.figshare.com/files/41619375"
    assert request["range"] == "bytes=0-4095"
    assert request["timeout"] <= 30
    assert response.bytes_read == 4096
    assert record["source_metadata"]["server_content_range_total_declared"] == EXPECTED_TOTAL
    assert record["observation"]["first_material_id"] == "mp-example"
    assert record["observation"]["first_frame_id"] == "task/a-1"
    assert record["observation"]["prefix_sha256"] == hashlib.sha256(fixture_bytes()).hexdigest()
    assert record["observation"]["complete_frame_parsed"] is False
    assert record["observation"]["complete_original_source_hashed"] is False
    assert record["authorization"]["execute_exposure_audit"] is False
    assert record["authorization"]["unseen_generalization_claim"] is False


def test_ignoring_range_http_200_aborts_without_reading_large_body():
    response, _, run = _run(status=200)
    with pytest.raises(probe.PrefixProbeError, match="206"):
        run()
    assert response.read_called is False


@pytest.mark.parametrize("headers", [
    {"Content-Range": f"bytes 0-4094/{EXPECTED_TOTAL}"},
    {"Content-Range": f"bytes 0-4095/{EXPECTED_TOTAL-1}"},
    {"Content-Range": "bytes */12188168685"},
    {"Content-Length": "4096"},
    {"Content-Range": f"bytes 0-4095/{EXPECTED_TOTAL}", "Content-Length": "1234"},
    {"Content-Range": f"bytes 0-4095/{EXPECTED_TOTAL}", "Content-Encoding": "gzip"},
])
def test_rejects_bad_range_headers(headers):
    response, _, run = _run(headers=headers)
    with pytest.raises(probe.PrefixProbeError):
        run()
    assert not response.read_called


def test_rejects_truncated_or_overlong_body():
    _, _, short = _run(payload=fixture_bytes(4096)[:-1])
    with pytest.raises(probe.PrefixProbeError, match="truncated"):
        short()
    _, _, long = _run(payload=fixture_bytes(4096)+b"a")
    with pytest.raises(probe.PrefixProbeError, match="exceeds"):
        long()


def test_refuses_insecure_redirect():
    response, _, run = _run(url="http://insecure.example/path")
    with pytest.raises(probe.PrefixProbeError, match="HTTPS"):
        run()
    assert not response.read_called


@pytest.mark.parametrize("n", [0, -1, 1024*1024+1])
def test_rejects_invalid_requested_prefix_budget_without_network(n):
    called = []
    with pytest.raises(probe.PrefixProbeError, match="budget"):
        probe.probe_https_range(expected_total=EXPECTED_TOTAL, prefix_bytes=n,
                               open_url=lambda *args, **kwargs: called.append(True))
    assert not called


def test_rejects_prefix_with_missing_structure_key():
    raw = b'{"mp-test":{"a":{"energy_per_atom":-1.0}}}'
    with pytest.raises(probe.PrefixProbeError, match="insufficient"):
        probe.inspect_first_frame_prefix(raw)


def test_rejects_invalid_root_or_structure_value():
    with pytest.raises(probe.PrefixProbeError):
        probe.inspect_first_frame_prefix(b'["not-a-dataset"]')
    with pytest.raises(probe.PrefixProbeError, match="not an object"):
        probe.inspect_first_frame_prefix(b'{"mp-a":{"frame-b":{"structure":[]}}}')


def test_prefix_truncation_never_claims_valid_frame():
    data = b'{"mp-a":{"task-a":{"energy_per_atom":-1.0,"structure":'
    with pytest.raises(probe.PrefixProbeError):
        probe.inspect_first_frame_prefix(data)


def test_cli_is_opt_in_and_never_overwrites_report(tmp_path, monkeypatch):
    report = tmp_path / "probe.json"
    assert probe.main(["--report", str(report)]) == 1
    assert not report.exists()
    mock = {
        "schema_version": "fixture",
        "observation": {"complete_original_source_hashed": False},
        "authorization": {"unseen_generalization_claim": False},
    }
    monkeypatch.setattr(probe, "canonical_source", lambda: {"size": EXPECTED_TOTAL})
    monkeypatch.setattr(probe, "probe_https_range", lambda **_: mock)
    assert probe.main(["--probe", "--report", str(report)]) == 0
    assert json.loads(report.read_text()) == mock
    assert probe.main(["--probe", "--report", str(report)]) == 1
    assert json.loads(report.read_text()) == mock


def test_probe_does_not_download_full_corpus_or_authorize_model_claims():
    from pathlib import Path
    script = (Path(__file__).resolve().parents[1] /
              "scripts/development/probe_mptrj_source_prefix.py").read_text()
    assert "Range" in script
    assert "MAX_PREFIX_BYTES = 1024 * 1024" in script
    assert "if status != 206" in script
    assert '"execute_exposure_audit": False' in script
    assert '"unseen_generalization_claim": False' in script
    assert "urlretrieve" not in script
