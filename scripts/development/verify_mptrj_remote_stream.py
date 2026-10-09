"""Explicit full MPTrj source stream identity with zero raw-source disk staging.

NOT automatically executed. One HTTPS GET of the pinned original 12.2GB
Figshare source can be explicitly authorized on a suitable compute backend.
The original streaming JSON reader confirms every frame, source size and
published MD5, and computes a local SHA256 in the SAME pass. A source
identity pass is NOT an MACE-MPA-0 model-training membership attestation.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from rhombus.domain.mptrj_integrity import verify_complete_mptrj_source
from scripts.development.probe_mptrj_source_prefix import CANONICAL_DOWNLOAD_URL
from scripts.development.verify_mptrj_frames import OFFICIAL_MPTRJ_FRAMES
from scripts.development.verify_mptrj_source import (
    FIGSHARE_FILE_ID, FIGSHARE_FILENAME, SourceEvidenceError, canonical_source,
)

# Cloud object/CDN host classes observed or intended by the publisher.
# Redirects to any other domain fail closed; no arbitrary URL is accepted.
_ALLOWED_HOST = re.compile(
    r"(?:[a-z0-9-]+\.)*figshare\.com|s3(?:[.-][a-z0-9-]+)*\.amazonaws\.com\Z"
)


class MPTrjRemoteStreamError(ValueError):
    """Whole-source request is not safely bounded to the exact publisher file."""


def _checked_https_publisher_endpoint(url: str) -> str:
    """Inspect *every* redirect destination before the HTTP client follows it.

    Checking only response.geturl() after urlopen() is too late: the default
    urllib handler can already have requested an untrusted intermediate URL.
    """
    if not isinstance(url, str):
        raise MPTrjRemoteStreamError("non-string original-source URL")
    try:
        endpoint = urllib.parse.urlsplit(url)
        hostname = endpoint.hostname
        port = endpoint.port
        username = endpoint.username
        password = endpoint.password
    except ValueError as exc:
        raise MPTrjRemoteStreamError("malformed source URL or port") from exc
    if (endpoint.scheme != "https" or not hostname
            or username is not None or password is not None
            or port not in (None, 443)
            or not _ALLOWED_HOST.fullmatch(hostname.lower())):
        raise MPTrjRemoteStreamError("untrusted original-source HTTPS endpoint")
    return hostname.lower()


class _PublisherOnlyRedirects(urllib.request.HTTPRedirectHandler):
    """Fail before following any HTTP or unrelated-domain redirect."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _checked_https_publisher_endpoint(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _open_trusted_original(request: urllib.request.Request, *, timeout: int):
    """Construct a scoped opener; do not mutate urllib's process-global opener."""
    _checked_https_publisher_endpoint(request.full_url)
    opener = urllib.request.build_opener(_PublisherOnlyRedirects)
    return opener.open(request, timeout=timeout)


def validate_full_stream_response(response, *, expected_size: int) -> str:
    """Reject HTTP 206, source-length drift and untrusted final endpoints."""
    if getattr(response, "status", None) != 200:
        raise MPTrjRemoteStreamError("full-stream request must return HTTP 200, not a partial range")
    final_hostname = _checked_https_publisher_endpoint(response.geturl())
    headers = response.headers
    if headers.get("Content-Encoding", "identity").strip().lower() != "identity":
        raise MPTrjRemoteStreamError("compressed HTTP entity cannot be treated as original MPTrj bytes")
    if headers.get("Transfer-Encoding"):
        raise MPTrjRemoteStreamError("ambiguous transfer encoding for original MPTrj bytes")
    announced = headers.get("Content-Length")
    if (not isinstance(announced, str) or not announced.isdecimal()
            or int(announced) != expected_size):
        raise MPTrjRemoteStreamError("Content-Length differs from pinned whole-source byte size")
    if headers.get("Content-Range") is not None:
        raise MPTrjRemoteStreamError("unexpected Content-Range on full source response")
    return final_hostname


def verify_remote_mptrj_full_stream(
    *, open_url=None,
    on_progress=None,
    progress_every_frames: int = 5_000,
) -> dict:
    """One no-retry, non-persistent whole-source operation after CLI opt-in."""
    if type(progress_every_frames) is not int or progress_every_frames <= 0:
        raise MPTrjRemoteStreamError("invalid full-stream progress interval")
    source = canonical_source()
    if source["file_id"] != FIGSHARE_FILE_ID or source["file_name"] != FIGSHARE_FILENAME:
        raise MPTrjRemoteStreamError("pinned Figshare source identity changed")
    request = urllib.request.Request(
        CANONICAL_DOWNLOAD_URL,
        headers={
            "User-Agent": "Rhombus-Phase3-full-source-one-pass/1",
            "Accept-Encoding": "identity",
        },
    )
    if CANONICAL_DOWNLOAD_URL != f"https://ndownloader.figshare.com/files/{FIGSHARE_FILE_ID}":
        raise MPTrjRemoteStreamError("canonical full-source URL differs from frozen Figshare file ID")
    # A deliberately injected fake open_url is for offline testing only.
    # Production *always* uses a per-request redirect-restricted opener.
    if open_url is None:
        open_url = _open_trusted_original
    # No local file or cache; on transport/read error, no success result exists.
    with open_url(request, timeout=120) as response:
        redirect_host = validate_full_stream_response(response, expected_size=source["size"])
        result = verify_complete_mptrj_source(
            response,
            expected_size=source["size"],
            expected_md5=source["md5"],
            expected_frames=OFFICIAL_MPTRJ_FRAMES,
            on_progress=on_progress,
            progress_every_frames=progress_every_frames,
        )
    if (result["source_identity"]["byte_count"] != source["size"]
            or result["frame_coverage"]["parsed_frames"] != OFFICIAL_MPTRJ_FRAMES):
        raise MPTrjRemoteStreamError("source full-stream verifier returned incomplete coverage")
    result["source_transport"] = {
        "method": "ONE_FULL_HTTPS_GET_PINNED_FIGSHARE_SOURCE",
        "canonical_file_id": FIGSHARE_FILE_ID,
        "final_redirect_hostname": redirect_host,
        "http_status": 200,
        "declared_content_length": source["size"],
        "raw_source_bytes_staged_on_disk": False,
        "source_validation_requires_full_stream": True,
    }
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true",
                      help="validate pinned metadata and print expected budget; NO GET")
    mode.add_argument("--execute-full-download", action="store_true",
                      help="explicitly authorize reading the complete ~12.2GB original")
    parser.add_argument("--report", type=Path, help="new JSON verification report; never overwrite")
    parser.add_argument("--progress-every-frames", type=int, default=5000)
    args = parser.parse_args(argv)
    try:
        if args.progress_every_frames <= 0:
            raise SourceEvidenceError("progress interval must be positive")
        source = canonical_source()
        if args.preflight:
            if args.report is not None:
                raise SourceEvidenceError("preflight must not write a report")
            print(json.dumps({
                "status": "PREFLIGHT_ONLY_NO_NETWORK",
                "figshare_file_id": source["file_id"],
                "expected_bytes": source["size"],
                "expected_frames": OFFICIAL_MPTRJ_FRAMES,
                "expected_publisher_md5": source["md5"],
                "streaming_without_raw_source_disk": True,
                "full_source_execution_authorized": False,
                "mace_mpa0_training_membership_attested": False,
            }, sort_keys=True))
            return 0
        if (args.report is None or args.report.is_symlink()
                or args.report.exists()):
            raise SourceEvidenceError("new non-symlink report path required before full network read")
        start = time.monotonic()
        def progress(frames: int, bytes_read: int) -> None:
            print(
                "MPTRJ_REMOTE_FULL_STREAM_PROGRESS_UNVERIFIED "
                f"completed_frames={frames} prefetched_bytes={bytes_read} "
                f"elapsed_seconds={time.monotonic()-start:.1f}",
                file=sys.stderr, flush=True,
            )
        print(
            f"MPTRJ_REMOTE_FULL_STREAM_START_UNVERIFIED "
            f"expected_bytes={source['size']} expected_frames={OFFICIAL_MPTRJ_FRAMES}",
            file=sys.stderr, flush=True,
        )
        result = verify_remote_mptrj_full_stream(
            on_progress=progress, progress_every_frames=args.progress_every_frames,
        )
        with args.report.open("x", encoding="utf-8") as out:
            json.dump(result, out, sort_keys=True, indent=2, allow_nan=False)
            out.write("\n")
        print("MPTRJ_ORIGINAL_SOURCE_WHOLE_STREAM_IDENTITY_PASS")
        print("MACE_MPA0_TRAINING_SELECTION_UNATTESTED; WBM_EXPOSURE_AUDIT_NOT_AUTHORIZED")
        return 0
    except (OSError, ValueError, TypeError, OverflowError, urllib.error.URLError) as exc:
        print(f"MPTRJ_REMOTE_FULL_STREAM_FAIL_CLOSED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
