"""Manual-only bounded 1MiB MPTrj multi-frame observation; metadata only.

Explicit --observe flag required for one logical HTTPS Range operation.
Neither a source sample nor a complete dataset is persisted or attested.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import urllib.error
import urllib.request

from scripts.development.inspect_mptrj_prefix_frames import inspect_mptrj_capped_prefix
from scripts.development.probe_mptrj_source_prefix import MAX_PREFIX_BYTES, DEFAULT_PREFIX_BYTES, probe_https_range
from scripts.development.reobserve_mptrj_frozen_prefix import read_frozen_first_frame
from scripts.development.verify_mptrj_probe_receipt import _unique_pairs
from scripts.development.verify_mptrj_source import canonical_source

MAX_REPORT_BYTES = 16 * 1024
SHA256 = re.compile(r"[a-f0-9]{64}\Z")
FALSE_FIELDS = (
    "raw_source_saved", "full_source_verified",
    "mace_mpa0_training_frames_attested", "execute_exposure_audit",
    "empirical_calibration_use", "unseen_generalization_claim",
)


class ManualMultiFrameError(ValueError):
    """Invalid bounded source observation or unsupported scientific claim."""


def observe_real_bounded_multiframe(*, open_url=urllib.request.urlopen) -> dict:
    """A bounded explicit 1MiB prefix read; no source-byte file or background job."""
    prior = read_frozen_first_frame()  # Verifies actual saved 0080 ZIP before GET.
    registry = canonical_source()
    if registry["size"] != prior["source_metadata"]["expected_total_size_bytes_from_registry"]:
        raise ManualMultiFrameError("canonical source and original receipt disagree")
    captured: list[bytes] = []
    receipt = probe_https_range(
        expected_total=registry["size"], prefix_bytes=MAX_PREFIX_BYTES,
        require_complete_frame=True, open_url=open_url,
        sample_capture=captured.append,
    )
    if len(captured) != 1 or len(captured[0]) != MAX_PREFIX_BYTES:
        raise ManualMultiFrameError("bounded raw prefix capture incomplete")
    raw = captured.pop()
    parsed = inspect_mptrj_capped_prefix(raw, frozen_receipt=prior)
    if parsed["sample_sha256"] != receipt["observation"]["prefix_sha256"]:
        raise ManualMultiFrameError("source-byte digest and HTTP probe receipt disagree")
    summary = {
        "schema_version": "rhombus-phase3-mptrj-real-1mib-manual-frames-v1",
        "status": "ONE_MIB_FIRST_N_FRAMES_DIAGNOSTIC_ONLY",
        "source_file_id": registry["file_id"],
        "source_total_bytes_declared": registry["size"],
        "prefix_bytes": MAX_PREFIX_BYTES,
        "first_256k_sha256": parsed["frozen_first_256k_sha256"],
        "prefix_1mib_sha256": parsed["sample_sha256"],
        "redirect_host": receipt["source_metadata"]["redirect_host"],
        "complete_frame_count": parsed["complete_frame_count"],
        "complete_frames": parsed["complete_frames"],
        "tail_status": parsed["tail_status"],
        **{key: False for key in FALSE_FIELDS},
    }
    validate_manual_multiframe_summary(summary, prior=prior)
    return summary


def validate_manual_multiframe_summary(summary: object, *, prior: dict | None = None) -> dict:
    """Offline metadata validation, not proof of Github origin or complete source."""
    required = {
        "schema_version", "status", "source_file_id", "source_total_bytes_declared",
        "prefix_bytes", "first_256k_sha256", "prefix_1mib_sha256",
        "redirect_host", "complete_frame_count", "complete_frames", "tail_status",
        *FALSE_FIELDS,
    }
    if not isinstance(summary, dict) or set(summary) != required:
        raise ManualMultiFrameError("unknown fields or incomplete bounded schema")
    if (summary["schema_version"] != "rhombus-phase3-mptrj-real-1mib-manual-frames-v1"
            or summary["status"] != "ONE_MIB_FIRST_N_FRAMES_DIAGNOSTIC_ONLY"):
        raise ManualMultiFrameError("unknown diagnostic status/schema")
    if (type(summary["source_file_id"]) is not int or summary["source_file_id"] != 41619375
            or type(summary["source_total_bytes_declared"]) is not int
            or summary["source_total_bytes_declared"] != 12_188_168_685
            or type(summary["prefix_bytes"]) is not int or summary["prefix_bytes"] != MAX_PREFIX_BYTES):
        raise ManualMultiFrameError("wrong source or source range length")
    if (any(summary[key] is not False for key in FALSE_FIELDS)
            or not isinstance(summary["redirect_host"], str)
            or not 1 <= len(summary["redirect_host"]) <= 253
            or any(c in summary["redirect_host"] for c in ("/", "\\", "@", " ", ":"))):
        raise ManualMultiFrameError("unsupported authorization or invalid redirect host")
    if any(not isinstance(summary[k], str) or not SHA256.fullmatch(summary[k])
           for k in ("first_256k_sha256", "prefix_1mib_sha256")):
        raise ManualMultiFrameError("source hash malformed")
    if prior is None:
        prior = read_frozen_first_frame()
    if summary["first_256k_sha256"] != prior["observation"]["prefix_sha256"]:
        raise ManualMultiFrameError("source 256KiB fingerprint differs from frozen real observation")
    frames = summary["complete_frames"]
    n = summary["complete_frame_count"]
    if (type(n) is not int or not 1 <= n <= 16
            or not isinstance(frames, list) or len(frames) != n):
        raise ManualMultiFrameError("invalid complete frame count")
    if summary["tail_status"] not in (
        "FRAME_CAP_REACHED_TAIL_NOT_INSPECTED",
        "TAIL_UNVERIFIED_FRAME_INCOMPLETE_OR_INVALID",
        "TAIL_UNVERIFIED_TRUNCATED_OR_MALFORMED",
        "ROOT_MAPPING_CLOSED_WITHIN_PREFIX_NOT_FULL_SOURCE",
    ):
        raise ManualMultiFrameError("untrusted tail coverage status")
    expected = prior["observation"]["first_frame_structure"]
    if not isinstance(frames[0], dict) or any(
        frames[0].get(k) != expected[k] for k in
        ("material_id", "frame_id", "site_count", "reduced_formula", "energy_fields_present")
    ):
        raise ManualMultiFrameError("first frame differs from original real source observation")
    seen = set()
    for frame in frames:
        if not isinstance(frame, dict) or set(frame) != {
            "material_id", "frame_id", "source_locator", "site_count",
            "reduced_formula", "energy_fields_present", "complete_frame_parsed",
        }:
            raise ManualMultiFrameError("complete-frame metadata invalid")
        pair = (frame["material_id"], frame["frame_id"])
        if (not all(isinstance(v, str) and 0 < len(v) <= 2048 for v in pair)
                or pair in seen or frame["complete_frame_parsed"] is not True
                or type(frame["site_count"]) is not int or not 1 <= frame["site_count"] <= 100000
                or not isinstance(frame["reduced_formula"], str) or not frame["reduced_formula"]):
            raise ManualMultiFrameError("duplicate or invalid frame identity/structure")
        seen.add(pair)
        flags = frame["energy_fields_present"]
        if (not isinstance(flags, dict)
                or set(flags) != {"uncorrected_total_energy", "corrected_total_energy", "energy_per_atom"}
                or any(type(v) is not bool for v in flags.values())):
            raise ManualMultiFrameError("energy-presence evidence malformed")
    if len(json.dumps(summary, separators=(",", ":"), allow_nan=False).encode()) > MAX_REPORT_BYTES:
        raise ManualMultiFrameError("metadata exceeds 16KiB")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--observe", action="store_true", help="explicitly permit bounded source GET")
    modes.add_argument("--verify", type=Path, help="verify existing bounded metadata without GET")
    parser.add_argument("--report", type=Path, help="new metadata file; no overwriting")
    args = parser.parse_args(argv)
    try:
        if args.observe:
            if args.report is None or args.report.is_symlink() or args.report.exists():
                raise ManualMultiFrameError("new regular metadata report path required")
            summary = observe_real_bounded_multiframe()
            raw = (json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
            if len(raw) > MAX_REPORT_BYTES:
                raise ManualMultiFrameError("JSON metadata file exceeds budget")
            with args.report.open("xb") as file:
                file.write(raw)
            print("MPTRJ_REAL_1MIB_MULTIFRAME_OBSERVED_DIAGNOSTIC_ONLY")
        else:
            if args.report is not None or args.verify.is_symlink() or not args.verify.is_file():
                raise ManualMultiFrameError("invalid existing verification file")
            if not 1 <= args.verify.stat().st_size <= MAX_REPORT_BYTES:
                raise ManualMultiFrameError("metadata report outside allowed byte budget")
            with args.verify.open("rb") as file:
                summary = json.loads(file.read(MAX_REPORT_BYTES + 1).decode(), object_pairs_hook=_unique_pairs)
            validate_manual_multiframe_summary(summary)
            print("MPTRJ_1MIB_MULTIFRAME_METADATA_VALIDATED_NON_AUTHORITATIVE")
        return 0
    except (ValueError, OSError, TypeError, UnicodeError, OverflowError, urllib.error.URLError) as exc:
        print(f"MPTRJ_MANUAL_MULTIFRAME_FAIL_CLOSED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
