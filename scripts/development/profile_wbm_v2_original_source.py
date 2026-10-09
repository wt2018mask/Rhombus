"""Zero-network v2 composition candidate profile from frozen WBM gzip bytes.

No prototype labels or source-target SQLite creation; compare-cost proxy only.
The entire compressed original source SHA256 is checked before parsing ANY
structures and all original WBM initial structures are checked before output.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
import os
from pathlib import Path
import stat
from typing import BinaryIO
import re
import sys

from pymatgen.core import Structure

from rhombus.domain.structure_protocols import CANDIDATE_FINGERPRINT_PROTOCOL_ID
from rhombus.domain.mptrj_source_overlap import WBM_SHA256, WBM_COUNT

MAX_COMPRESSED_BYTES = 2 * 1024 * 1024 * 1024
MAX_JSONL_LINE_BYTES = 4 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 6 * 1024 * 1024 * 1024
SHA256 = re.compile(r"[a-f0-9]{64}\Z")


class WBMSourceProfileError(ValueError):
    """Original WBM source or bounded profile is invalid."""


def _pairs_no_duplicates(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise WBMSourceProfileError("duplicate JSON field in WBM source")
        out[key] = value
    return out


def _frozen_source_sha256(source: BinaryIO, *, max_bytes: int) -> tuple[str, int]:
    """Hash and rewind the SAME open regular file used by the gzip parser."""
    metadata = os.fstat(source.fileno())
    if not stat.S_ISREG(metadata.st_mode):
        raise WBMSourceProfileError("existing nonsymlink WBM source file required")
    size = metadata.st_size
    if size < 1 or size > max_bytes:
        raise WBMSourceProfileError("WBM gzip source exceeds bounded byte budget")
    source.seek(0)
    digest = hashlib.sha256()
    observed = 0
    while chunk := source.read(1024 * 1024):
        observed += len(chunk)
        if observed > max_bytes:
            raise WBMSourceProfileError("WBM gzip source exceeds bounded byte budget")
        digest.update(chunk)
    if observed != size:
        raise WBMSourceProfileError("WBM gzip source changed while hashing")
    source.seek(0)
    return digest.hexdigest(), size


def profile_frozen_wbm_gzip(
    path: Path,
    *,
    expected_source_sha256: str = WBM_SHA256,
    expected_records: int = WBM_COUNT,
    allow_fixture_identity: bool = False,
) -> dict:
    """Read-only two-pass frozen-gzip verification and bounded candidate proxy.

    The only authorized default inputs are the original WBM archive and frozen
    row count. Overrides are test fixtures, never an operator CLI option.
    """
    if type(allow_fixture_identity) is not bool:
        raise WBMSourceProfileError("fixture override must be a boolean")
    if (not allow_fixture_identity
            and (expected_source_sha256 != WBM_SHA256
                 or expected_records != WBM_COUNT)):
        raise WBMSourceProfileError("noncanonical source identity prohibited")
    if (not isinstance(expected_source_sha256, str)
            or not SHA256.fullmatch(expected_source_sha256)
            or type(expected_records) is not int
            or expected_records < 1 or expected_records > WBM_COUNT):
        raise WBMSourceProfileError("invalid source SHA256 or bounded row count")
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise WBMSourceProfileError("existing nonsymlink WBM source file required")
    with path.open("rb") as source:
        initial_stat = os.fstat(source.fileno())
        initial_path_stat = path.stat()
        if (path.is_symlink()
                or not stat.S_ISREG(initial_stat.st_mode)
                or (initial_stat.st_dev, initial_stat.st_ino)
                != (initial_path_stat.st_dev, initial_path_stat.st_ino)):
            raise WBMSourceProfileError("WBM source path changed during opening")
        sha, compressed_bytes = _frozen_source_sha256(
            source, max_bytes=MAX_COMPRESSED_BYTES
        )
        if sha != expected_source_sha256:
            raise WBMSourceProfileError("original WBM compressed SHA256 mismatch")
        counts: dict[str, Counter[int]] = defaultdict(Counter)
        ids: set[str] = set()
        rows = 0
        plain_bytes = 0
        try:
            with gzip.GzipFile(fileobj=source, mode="rb") as handle:
                while raw := handle.readline(MAX_JSONL_LINE_BYTES + 1):
                    if len(raw) > MAX_JSONL_LINE_BYTES:
                        raise WBMSourceProfileError("unbounded WBM JSONL line")
                    plain_bytes += len(raw)
                    if plain_bytes > MAX_UNCOMPRESSED_BYTES:
                        raise WBMSourceProfileError("WBM decompressed byte budget exceeded")
                    if not raw.endswith(b"\n") or not raw.strip():
                        raise WBMSourceProfileError("malformed or unterminated WBM JSONL record")
                    payload = json.loads(
                        raw, object_pairs_hook=_pairs_no_duplicates,
                        parse_constant=lambda c: (_ for _ in ()).throw(
                            WBMSourceProfileError("nonfinite WBM JSON")
                        ),
                    )
                    if not isinstance(payload, dict):
                        raise WBMSourceProfileError("WBM row must be a JSON object")
                    mid = payload.get("material_id")
                    if (not isinstance(mid, str) or not mid.strip()
                            or len(mid) > 512 or mid in ids):
                        raise WBMSourceProfileError("duplicate/invalid WBM material ID")
                    ids.add(mid)
                    structure = Structure.from_dict(payload["initial_structure"])
                    site_count = len(structure)
                    if site_count < 1 or site_count > 100_000:
                        raise WBMSourceProfileError("invalid original WBM site count")
                    formula = structure.composition.element_composition.reduced_formula
                    if not formula:
                        raise WBMSourceProfileError("empty reduced WBM composition")
                    counts[formula][site_count] += 1
                    rows += 1
                    if rows > expected_records:
                        raise WBMSourceProfileError("more WBM records than frozen count")
        except (OSError, EOFError, KeyError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
            raise WBMSourceProfileError("invalid or incomplete WBM original JSONL gzip") from exc
        final_sha, final_bytes = _frozen_source_sha256(
            source, max_bytes=MAX_COMPRESSED_BYTES
        )
        final_stat = os.fstat(source.fileno())
        final_path_stat = path.stat()
        if (sha != final_sha or compressed_bytes != final_bytes
                or path.is_symlink()
                or (initial_stat.st_dev, initial_stat.st_ino)
                != (final_stat.st_dev, final_stat.st_ino)
                or (initial_stat.st_dev, initial_stat.st_ino)
                != (final_path_stat.st_dev, final_path_stat.st_ino)):
            raise WBMSourceProfileError(
                "WBM source changed between verification and profiling"
            )
    if rows != expected_records:
        raise WBMSourceProfileError(
            f"incomplete WBM source row count: observed={rows} expected={expected_records}"
        )
    bucket_sizes = [sum(by_sites.values()) for by_sites in counts.values()]
    old_sitecounts = [n for c in counts.values() for n in c.values()]
    mixed = sum(len(c) > 1 for c in counts.values())
    return {
        "schema_version": "rhombus-phase3-original-wbm-v2-direct-candidate-profile-v1",
        "status": "ORIGINAL_WBM_BYTES_VERIFIED_INDEX_FREE_RESOURCE_PROXY_ONLY",
        "wbm_original_gzip_sha256": sha,
        "wbm_original_gzip_bytes": compressed_bytes,
        "wbm_decompressed_jsonl_bytes": plain_bytes,
        "wbm_initial_structure_count": rows,
        "candidate_fingerprint_protocol_id": CANDIDATE_FINGERPRINT_PROTOCOL_ID,
        "v2_composition_bucket_count": len(counts),
        "v1_composition_sitecount_subbucket_count": len(old_sitecounts),
        "v2_buckets_with_multiple_sitecounts": mixed,
        "v2_largest_composition_bucket_targets": max(bucket_sizes),
        "v1_largest_composition_sitecount_subbucket_targets": max(old_sitecounts),
        "v2_index_only_pair_proxy": sum(n * n for n in bucket_sizes),
        "v1_index_only_pair_proxy": sum(n * n for n in old_sitecounts),
        "mptrj_runtime_estimate_authorized": False,
        "salex_full_runtime_estimate_authorized": False,
        "full_source_transfer_authorized": False,
        "exact_mace_mpa0_training_selection_attested": False,
        "unseen_generalization_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wbm-gzip", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        dest = args.report
        if (dest.is_symlink() or dest.exists()
                or not dest.parent.is_dir()
                or dest.resolve() == args.wbm_gzip.resolve()):
            raise WBMSourceProfileError("new distinct report destination required")
        result = profile_frozen_wbm_gzip(args.wbm_gzip)
        with dest.open("x", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
        print("WBM_V2_DIRECT_ORIGINAL_SOURCE_PROFILE_VERIFIED_NO_NETWORK")
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print(f"WBM_V2_DIRECT_ORIGINAL_SOURCE_PROFILE_FAIL_CLOSED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
