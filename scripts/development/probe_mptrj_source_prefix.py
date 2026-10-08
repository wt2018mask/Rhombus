"""Opt-in, size-capped Figshare MPTrj HTTPS Range prefix structure probe.

This does NOT verify file MD5/SHA256 or MACE-MPA-0 training frame selection.
A prefix cannot establish the full canonical file's byte identity, even when
Content-Range declares the expected original size. No fallback to HTTP 200.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import ijson

from scripts.development.verify_mptrj_source import canonical_source
from pymatgen.core import Structure
from rhombus.domain.mptrj import MPTrjFormatError, _read_frame
from rhombus.domain.mptrj_energy_labels import inspect_mptrj_frame_energy_labels

CANONICAL_DOWNLOAD_URL = "https://ndownloader.figshare.com/files/41619375"
DEFAULT_PREFIX_BYTES = 256 * 1024
MAX_PREFIX_BYTES = 1024 * 1024


class PrefixProbeError(ValueError):
    """A source prefix is unverifiable, malformed, or exceeds resource limits."""


def inspect_first_frame_prefix(prefix: bytes) -> dict[str, str]:
    """Observe only the initial material, frame and first Structure key.

    EOF is EXPECTED to occur later. Stop on the first complete structure-key
    token and following start_map; do not present a partial body as a verified
    pymatgen Structure. A bounded prefix that ends early fails closed.
    """
    material_id: str | None = None
    frame_id: str | None = None
    depth = 0
    expecting_structure_map = False
    try:
        for event, value in ijson.basic_parse(io.BytesIO(prefix), use_float=True):
            if expecting_structure_map:
                if event != "start_map":
                    raise PrefixProbeError("first frame structure is not an object")
                return {
                    "material_id": material_id or "",
                    "frame_id": frame_id or "",
                    "first_frame_structure_map_seen": "true",
                }
            if event in ("start_map", "start_array"):
                if depth == 0 and event != "start_map":
                    raise PrefixProbeError("MPTrj root must be an object")
                if depth == 1 and event != "start_map":
                    raise PrefixProbeError("material frames must be an object")
                if depth == 2 and event != "start_map":
                    raise PrefixProbeError("frame must be an object")
                depth += 1
            elif event in ("end_map", "end_array"):
                depth -= 1
            elif event == "map_key":
                if depth == 1 and material_id is None:
                    material_id = _validate_identifier(value, "material_id")
                elif depth == 2 and frame_id is None:
                    frame_id = _validate_identifier(value, "frame_id")
                elif depth == 3 and value == "structure":
                    if material_id is None or frame_id is None:
                        raise PrefixProbeError("structure encountered before source identifiers")
                    expecting_structure_map = True
            if depth < 0:
                raise PrefixProbeError("invalid JSON container depth")
    except (ijson.JSONError, UnicodeError, OverflowError) as exc:
        raise PrefixProbeError(
            "prefix did not establish a valid first-frame structure; "
            "truncated or invalid JSON"
        ) from exc
    raise PrefixProbeError("prefix budget insufficient to locate first structure object")


def _validate_identifier(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 2048:
        raise PrefixProbeError(f"first {name} missing or exceeds length limit")
    return value



def inspect_first_complete_frame_prefix(prefix: bytes) -> dict:
    """Validate the first complete frame and its pymatgen Structure in prefix.

    The remaining JSON document is intentionally not consumed or validated.
    A truncated first frame must fail without emitting any success evidence.
    """
    if not 1 <= len(prefix) <= MAX_PREFIX_BYTES:
        raise PrefixProbeError("sample exceeds 1 MiB bounded prefix budget")
    events = iter(ijson.basic_parse(io.BytesIO(prefix), use_float=True))

    def require(event_type: str, description: str) -> object:
        try:
            event, value = next(events)
        except StopIteration as exc:
            raise PrefixProbeError(f"truncated prefix before {description}") from exc
        if event != event_type:
            raise PrefixProbeError(f"invalid MPTrj first-frame layout at {description}")
        return value

    try:
        require("start_map", "root")
        material_id = _validate_identifier(require("map_key", "material_id"), "material_id")
        require("start_map", "material frame mapping")
        frame_id = _validate_identifier(require("map_key", "frame_id"), "frame_id")
        require("start_map", "first frame object")
        frame = _read_frame(
            events,
            max_frame_events=150_000,
            max_frame_scalar_chars=MAX_PREFIX_BYTES,
        )
        serialized = frame.get("structure")
        if not isinstance(serialized, dict):
            raise PrefixProbeError("first complete frame missing Structure object")
        try:
            structure = Structure.from_dict(serialized)
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise PrefixProbeError("first complete frame has invalid pymatgen Structure") from exc
        if len(structure) == 0:
            raise PrefixProbeError("first complete frame contains an empty Structure")
        provenance = inspect_mptrj_frame_energy_labels(frame)
    except (ijson.JSONError, MPTrjFormatError, UnicodeError, OverflowError) as exc:
        raise PrefixProbeError("truncated or malformed first complete MPTrj frame") from exc
    return {
        "material_id": material_id,
        "frame_id": frame_id,
        "site_count": len(structure),
        "reduced_formula": structure.composition.element_composition.reduced_formula,
        "energy_fields_present": {
            "uncorrected_total_energy": provenance.raw_vasp_total_energy_ev is not None,
            "corrected_total_energy": provenance.mp2020_corrected_total_energy_ev is not None,
            "energy_per_atom": provenance.chgnet_mp2020_corrected_energy_per_atom_ev is not None,
        },
        "complete_frame_parsed": True,
    }


def probe_https_range(
    *,
    expected_total: int,
    prefix_bytes: int = DEFAULT_PREFIX_BYTES,
    require_complete_frame: bool = False,
    open_url=urllib.request.urlopen,
) -> dict:
    """Fetch only explicit initial byte range; demand exact 206 Content-Range.

    Never stream beyond MAX_PREFIX_BYTES+1 even if origin ignores Range.
    Do not follow file-shaped URLs other than pinned canonical Figshare ID.
    The server's total-length header is metadata, NOT full source integrity.
    """
    if not 1 <= prefix_bytes <= MAX_PREFIX_BYTES:
        raise PrefixProbeError("prefix size exceeds explicit 1 MiB safety budget")
    if expected_total <= prefix_bytes:
        raise PrefixProbeError("expected source size must exceed requested prefix")
    req = urllib.request.Request(
        CANONICAL_DOWNLOAD_URL,
        headers={
            "User-Agent": "Rhombus-MPTrj-prefix-probe/1",
            "Range": f"bytes=0-{prefix_bytes-1}",
            "Accept-Encoding": "identity",
        },
    )
    with open_url(req, timeout=30) as response:
        status = getattr(response, "status", None)
        if status != 206:
            raise PrefixProbeError("server did not honor 206 Partial Content; abort")
        final_url = response.geturl()
        parsed = urllib.parse.urlparse(final_url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise PrefixProbeError("redirected range download must remain HTTPS")
        observed_range = response.headers.get("Content-Range", "")
        expected_range = f"bytes 0-{prefix_bytes-1}/{expected_total}"
        if observed_range.strip() != expected_range:
            raise PrefixProbeError("Content-Range does not match frozen Figshare size")
        encoding = response.headers.get("Content-Encoding", "identity").lower()
        if encoding not in ("", "identity"):
            raise PrefixProbeError("compressed transfer encoding invalidates byte range")
        stated_length = response.headers.get("Content-Length")
        if stated_length is not None and stated_length.strip() != str(prefix_bytes):
            raise PrefixProbeError("range payload content-length mismatch")
        output = bytearray()
        while len(output) < prefix_bytes:
            data = response.read(min(8192, prefix_bytes - len(output)))
            if not data:
                raise PrefixProbeError("truncated HTTP Range response")
            output.extend(data)
        if response.read(1):
            raise PrefixProbeError("HTTP Range response exceeds requested byte count")
        prefix = bytes(output)
        structure = inspect_first_frame_prefix(prefix)
        full_first_frame = inspect_first_complete_frame_prefix(prefix) if require_complete_frame else None
        if full_first_frame is not None and (
            full_first_frame["material_id"] != structure["material_id"]
            or full_first_frame["frame_id"] != structure["frame_id"]
        ):
            raise PrefixProbeError("first frame identity mismatch between preview and complete parse")
        return {
            "schema_version": "rhombus-phase3-mptrj-range-prefix-probe-v1",
            "source_metadata": {
                "figshare_file_id": 41619375,
                "expected_total_size_bytes_from_registry": expected_total,
                "server_content_range_total_declared": expected_total,
                "redirect_host": parsed.hostname,
            },
            "observation": {
                "prefix_size_bytes": len(prefix),
                "prefix_sha256": hashlib.sha256(prefix).hexdigest(),
                "first_material_id": structure["material_id"],
                "first_frame_id": structure["frame_id"],
                "first_frame_structure_object_start_seen": True,
                "complete_frame_parsed": full_first_frame is not None,
                "first_frame_structure": full_first_frame,
                "complete_original_source_hashed": False,
            },
            "training_lineage": {
                "mace_mpa0_exact_training_bytes_attested": False,
                "training_frame_selection_attested": False,
            },
            "authorization": {
                "execute_exposure_audit": False,
                "empirical_calibration_use": False,
                "unseen_generalization_claim": False,
            },
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", action="store_true", help="explicitly permit a capped remote Range GET")
    parser.add_argument("--prefix-bytes", type=int, default=DEFAULT_PREFIX_BYTES)
    parser.add_argument("--require-complete-frame", action="store_true", help="parse first full Structure inside same capped range")
    parser.add_argument("--report", type=Path, required=True, help="new report only; refuse overwrite")
    args = parser.parse_args(argv)
    try:
        if not args.probe:
            raise PrefixProbeError("--probe required; remote requests are never implicit")
        if args.report.is_symlink() or args.report.exists():
            raise PrefixProbeError("report path already exists or is a symlink")
        metadata = canonical_source()
        report = probe_https_range(
            expected_total=metadata["size"],
            prefix_bytes=args.prefix_bytes,
            require_complete_frame=args.require_complete_frame,
        )
        with args.report.open("x", encoding="utf-8") as out:
            json.dump(report, out, indent=2, sort_keys=True)
            out.write("\n")
        print("MPTRJ_PREFIX_FIRST_COMPLETE_FRAME_PARSED_NON_AUTHORITATIVE" if args.require_complete_frame else "MPTRJ_PREFIX_STRUCTURE_OBSERVED_NON_AUTHORITATIVE")
        print("ORIGINAL_SOURCE_NOT_VERIFIED; MACE_TRAINING_BYTES_UNATTESTED")
        return 0
    except (PrefixProbeError, OSError, ValueError, ijson.JSONError) as exc:
        print(f"MPTRJ_PREFIX_FAIL_CLOSED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
