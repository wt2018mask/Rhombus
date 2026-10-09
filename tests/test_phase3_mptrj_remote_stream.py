"""Small offline HTTPS response fixtures; never read a live Figshare source."""
from __future__ import annotations

from hashlib import md5, sha256
import io
import json
import urllib.request

import pytest
from pymatgen.core import Lattice, Structure

from scripts.development import verify_mptrj_remote_stream as remote
from scripts.development.verify_mptrj_source import FIGSHARE_FILENAME


def sample():
    s = Structure(Lattice.cubic(4), ["Li", "O"], [[0, 0, 0], [.5, .5, .5]])
    return json.dumps({"mp-test-1": {
        "first": {"structure": s.as_dict(), "energy_per_atom": -2},
        "second": {"structure": s.as_dict(), "uncorrected_total_energy": -4.5},
    }}).encode()


class Response:
    def __init__(self, payload, *, status=200, url="https://s3-eu-west-1.amazonaws.com/bucket/source.json",
                 headers=None):
        self.data = io.BytesIO(payload)
        self.status = status
        self.url = url
        self.headers = {"Content-Length": str(len(payload))}
        if headers:
            self.headers.update(headers)
        self.requested = []
    def read(self, n):
        assert 0 <= n <= 65536
        self.requested.append(n)
        return self.data.read(n)
    def geturl(self):
        return self.url
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False


def prepare(monkeypatch, payload=None):
    payload = sample() if payload is None else payload
    expected = {"file_id": 41619375, "file_name": FIGSHARE_FILENAME,
                "size": len(payload), "md5": md5(payload).hexdigest()}
    monkeypatch.setattr(remote, "canonical_source", lambda: expected)
    monkeypatch.setattr(remote, "OFFICIAL_MPTRJ_FRAMES", 2)
    return payload, expected


def test_exact_200_single_response_full_md5_sha256_frames_no_disk(monkeypatch):
    payload, meta = prepare(monkeypatch)
    calls = []
    response = Response(payload)
    def fake_open(req, timeout):
        assert req.full_url == remote.CANONICAL_DOWNLOAD_URL
        assert req.get_header("Accept-encoding") == "identity"
        assert timeout == 120
        calls.append(req)
        return response
    progress = []
    report = remote.verify_remote_mptrj_full_stream(
        open_url=fake_open, on_progress=lambda frames, n: progress.append((frames, n)),
        progress_every_frames=1,
    )
    assert len(calls) == 1
    assert [p[0] for p in progress] == [1, 2]
    assert report["source_identity"]["computed_sha256"] == sha256(payload).hexdigest()
    assert report["source_identity"]["computed_md5"] == meta["md5"]
    assert report["frame_coverage"]["parsed_frames"] == 2
    assert report["source_transport"]["raw_source_bytes_staged_on_disk"] is False
    assert report["model_training_lineage"]["exact_mace_mpa0_training_frame_selection"] == "UNATTESTED"
    assert report["authorization"]["execute_wbm_training_exposure_audit"] is False
    assert response.requested and max(response.requested) <= 65536


@pytest.mark.parametrize("response_kwargs", [
    {"status": 206},
    {"status": 201},
    {"url": "http://s3-eu-west-1.amazonaws.com/data"},
    {"url": "https://untrusted.example/data"},
    {"url": "https://figshare.com.evil.example/data"},
    {"headers": {"Content-Length": "0"}},
    {"headers": {"Content-Length": "not-a-number"}},
    {"headers": {"Content-Length": "-1"}},
    {"headers": {"Content-Encoding": "gzip"}},
    {"headers": {"Content-Range": "bytes 0-9/100"}},
    {"headers": {"Transfer-Encoding": "chunked"}},
])
def test_bad_http_response_rejected_without_consuming_body(monkeypatch, response_kwargs):
    payload, _ = prepare(monkeypatch)
    response = Response(payload, **response_kwargs)
    with pytest.raises(remote.MPTrjRemoteStreamError):
        remote.verify_remote_mptrj_full_stream(open_url=lambda *a, **k: response)
    assert response.requested == []


def test_truncated_body_or_incomplete_frames_never_authorizes_source(monkeypatch):
    payload, metadata = prepare(monkeypatch)
    short = payload[:-23]
    response = Response(short, headers={"Content-Length": str(metadata["size"])})
    with pytest.raises(ValueError):
        remote.verify_remote_mptrj_full_stream(open_url=lambda *a, **k: response)


def test_wrong_publisher_md5_detected_only_after_complete_stream(monkeypatch):
    payload, metadata = prepare(monkeypatch)
    monkeypatch.setattr(remote, "canonical_source",
                        lambda: {**metadata, "md5": "0" * 32})
    with pytest.raises(ValueError, match="MD5 mismatch"):
        remote.verify_remote_mptrj_full_stream(
            open_url=lambda *a, **k: Response(payload),
        )


def test_missing_frame_count_never_yields_verified_receipt(monkeypatch):
    payload, _ = prepare(monkeypatch)
    monkeypatch.setattr(remote, "OFFICIAL_MPTRJ_FRAMES", 3)
    with pytest.raises(ValueError, match="frame count mismatch"):
        remote.verify_remote_mptrj_full_stream(
            open_url=lambda *a, **k: Response(payload),
        )


def test_preflight_is_offline_and_prohibits_report(monkeypatch, tmp_path, capsys):
    payload, _ = prepare(monkeypatch)
    monkeypatch.setattr(remote, "verify_remote_mptrj_full_stream",
                        lambda **_: (_ for _ in ()).throw(AssertionError("unexpected GET")))
    assert remote.main(["--preflight"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "PREFLIGHT_ONLY_NO_NETWORK"
    assert result["expected_bytes"] == len(payload)
    assert result["full_source_execution_authorized"] is False
    assert remote.main(["--preflight", "--report", str(tmp_path/"report.json")]) == 1


def test_full_cli_requires_explicit_authorization_and_clean_output_target(tmp_path, monkeypatch):
    payload, _ = prepare(monkeypatch)
    opened = []
    monkeypatch.setattr(remote, "verify_remote_mptrj_full_stream",
                        lambda **_: opened.append(True))
    report = tmp_path/"result.json"
    report.write_text("original")
    assert remote.main(["--execute-full-download", "--report", str(report)]) == 1
    assert not opened
    assert report.read_text() == "original"
    assert remote.main(["--execute-full-download"]) == 1
    assert not opened


def test_full_cli_writes_scientifically_closed_report_only_after_pass(tmp_path, monkeypatch, capsys):
    payload, _ = prepare(monkeypatch)
    verified = remote.verify_remote_mptrj_full_stream(
        open_url=lambda *a, **k: Response(payload),
    )
    monkeypatch.setattr(remote, "verify_remote_mptrj_full_stream", lambda **_: verified)
    report = tmp_path/"whole.json"
    assert remote.main(["--execute-full-download", "--report", str(report)]) == 0
    stored = json.loads(report.read_text())
    assert stored["source_identity"]["computed_sha256"] == sha256(payload).hexdigest()
    assert stored["authorization"]["unseen_generalization_claim"] is False
    assert "MPTRJ_ORIGINAL_SOURCE_WHOLE_STREAM_IDENTITY_PASS" in capsys.readouterr().out



@pytest.mark.parametrize("redirect_url", [
    "http://s3-eu-west-1.amazonaws.com/bucket/source.json",
    "https://untrusted.example/source.json",
    "https://localhost/private",
    "https://127.0.0.1/data",
    "https://169.254.169.254/latest/meta-data",
    "https://figshare.com.evil.example/data",
    "https://figshare.com:8443/files/41619375",
    "https://user@figshare.com/files/41619375",
    "https://figshare.com:bogus/files/41619375",
    "ftp://figshare.com/files/41619375",
])
def test_untrusted_intermediate_redirect_denied_before_network_follow(redirect_url):
    handler = remote._PublisherOnlyRedirects()
    first = urllib.request.Request(remote.CANONICAL_DOWNLOAD_URL)
    with pytest.raises(remote.MPTrjRemoteStreamError):
        handler.redirect_request(first, None, 302, "Found", {}, redirect_url)


@pytest.mark.parametrize("redirect_url", [
    "https://ndownloader.figshare.com/files/41619375",
    "https://api.figshare.com/v2/file/download/41619375",
    "https://s3-eu-west-1.amazonaws.com/bucket/source?X-Amz-Signature=abc",
])
def test_https_approved_publisher_redirects_preserve_fetchability(redirect_url):
    handler = remote._PublisherOnlyRedirects()
    first = urllib.request.Request(remote.CANONICAL_DOWNLOAD_URL)
    next_request = handler.redirect_request(
        first, None, 302, "Found", {}, redirect_url,
    )
    assert next_request.full_url == redirect_url


def test_default_full_stream_uses_private_redirect_guard_not_global_urlopen(monkeypatch):
    payload, metadata = prepare(monkeypatch)
    observed = []
    class FakeOpener:
        def open(self, request, *, timeout):
            assert request.full_url == remote.CANONICAL_DOWNLOAD_URL
            assert timeout == 120
            return Response(payload)
    def fake_build_opener(*handlers):
        observed.extend(handlers)
        return FakeOpener()
    monkeypatch.setattr(remote.urllib.request, "build_opener", fake_build_opener)
    monkeypatch.setattr(
        remote.urllib.request, "urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("global urlopen must not be used"),
        ),
    )
    result = remote.verify_remote_mptrj_full_stream()
    assert len(observed) == 1
    assert observed[0] is remote._PublisherOnlyRedirects
    assert result["source_identity"]["computed_md5"] == metadata["md5"]


def test_malformed_final_port_rejected_before_body_read(monkeypatch):
    payload, _ = prepare(monkeypatch)
    response = Response(payload, url="https://figshare.com:invalid/files/41619375")
    with pytest.raises(remote.MPTrjRemoteStreamError, match="malformed"):
        remote.verify_remote_mptrj_full_stream(
            open_url=lambda *_args, **_kwargs: response,
        )
    assert response.requested == []
