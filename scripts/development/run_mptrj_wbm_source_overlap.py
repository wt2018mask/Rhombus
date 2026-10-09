"""Opt-in full-source MPTrj↔WBM overlap; never checkpoint training exposure.

No source GET, MPTrj download or local staging by default. Requires existing
canonical WBM initial-structure target SQLite built from frozen source. The
full MPTrj response is read once with on-frame callbacks; all partial match
sets are discarded on failure. No report is written unless original source
file MD5, frame count and source size are all verified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time

from rhombus.domain.mptrj_source_overlap import MPTrjWBMSourceObserver
from scripts.development.verify_mptrj_remote_stream import verify_remote_mptrj_full_stream
from scripts.development.verify_mptrj_source import canonical_source


def run_source_only_overlap(
    db_path: Path,
    *,
    on_progress=None,
    open_url=None,  # injectable for offline tests only
    observer_options: dict | None = None,
    on_verified_targets=None,
    max_targets_per_composition_bucket: int | None = None,
) -> dict:
    with MPTrjWBMSourceObserver(db_path, **(observer_options or {})) as observer:
        if max_targets_per_composition_bucket is not None:
            if (type(max_targets_per_composition_bucket) is not int
                    or max_targets_per_composition_bucket < 1):
                raise ValueError("positive explicit composition bucket cap required")
            profile = observer.candidate_bucket_profile()
            if profile["largest_v2_composition_bucket_targets"] > max_targets_per_composition_bucket:
                raise ValueError("WBM v2 composition bucket exceeds approved comparison cap")
        args = {"on_frame": observer.observe, "on_progress": on_progress}
        if open_url is not None:
            args["open_url"] = open_url
        full_source = verify_remote_mptrj_full_stream(**args)
        summary = observer.verified_source_summary(full_source)
        if on_verified_targets is not None:
            if not callable(on_verified_targets):
                raise ValueError("on_verified_targets must be callable")
            summary["source_only_matched_wbm_rows_exported"] = on_verified_targets(
                observer.iter_verified_matched_targets(full_source)
            )
            if isinstance(on_verified_targets, _StagedTargetRows):
                if on_verified_targets.sha256 is None:
                    raise ValueError("verified matched-target writer did not finish")
                summary["source_only_matched_wbm_jsonl_sha256"] = on_verified_targets.sha256
        return summary



class _StagedTargetRows:
    """Publish one complete source-only JSONL artifact, never a partial file.

    The temporary file stores only WBM match flags and verified source hashes,
    never any source structure coordinates or raw MPTrj bytes. A hard link
    creates the destination atomically without overwriting an existing file.
    """

    def __init__(self, destination: Path):
        self.destination = destination
        self.temp_path: Path | None = None
        self.sha256: str | None = None

    def __call__(self, rows) -> int:
        if self.destination.is_symlink() or self.destination.exists():
            raise ValueError("target JSONL report must be a new file")
        count = 0
        digest = hashlib.sha256()
        self.sha256 = None
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=".mptrj-wbm-matched-",
            suffix=".jsonl.tmp", dir=str(self.destination.parent), delete=False,
        ) as out:
            self.temp_path = Path(out.name)
            for row in rows:
                if row.get("model_training_membership_attested") is not False:
                    raise ValueError("source-only row attempts model membership promotion")
                data = (json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
                out.write(data)
                digest.update(data)
                count += 1
        self.sha256 = digest.hexdigest()
        return count

    def publish(self) -> None:
        if self.temp_path is None:
            raise ValueError("no completed verified WBM source-only rows to publish")
        os.link(self.temp_path, self.destination)  # exclusive creation, never overwrite
        self.discard()

    def discard(self) -> None:
        if self.temp_path is not None:
            self.temp_path.unlink(missing_ok=True)
            self.temp_path = None
        self.sha256 = None

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--preflight", action="store_true",
                       help="WBM-target and canonical source identity check; no network")
    modes.add_argument("--execute-full-download", action="store_true",
                       help="Explicit ~12.2GB original Figshare read and source-only WBM comparison")
    parser.add_argument("--wbm-target-db", type=Path, required=True)
    parser.add_argument("--report", type=Path, help="new aggregate report, never overwrite")
    parser.add_argument("--matched-targets-jsonl", type=Path,
                        help="new SOURCE-ONLY WBM positive-target rows, never overwrite")
    parser.add_argument("--max-targets-per-composition-bucket", type=int,
                        help="mandatory for full download: explicit cap on WBM candidate comparisons per source frame")
    args = parser.parse_args(argv)
    try:
        if args.preflight and (args.report is not None or args.matched_targets_jsonl is not None):
            raise ValueError("no output report in offline preflight")
        if (args.max_targets_per_composition_bucket is not None
                and args.max_targets_per_composition_bucket < 1):
            raise ValueError("positive composition bucket cap required")
        if args.execute_full_download and args.max_targets_per_composition_bucket is None:
            raise ValueError("explicit WBM composition bucket resource cap required before full source download")
        if args.matched_targets_jsonl is not None:
            if (args.report is None or args.matched_targets_jsonl.is_symlink()
                    or args.matched_targets_jsonl.exists()
                    or args.matched_targets_jsonl.resolve() == args.report.resolve()
                    or not args.matched_targets_jsonl.parent.is_dir()):
                raise ValueError("new distinct target JSONL destination required before download")
        if not args.preflight and (args.report is None or args.report.is_symlink()
                                   or args.report.exists()):
            raise ValueError("new non-symlink report required before full-source network read")
        frozen = canonical_source()
        with MPTrjWBMSourceObserver(args.wbm_target_db) as inspected:
            count = inspected.wbm_count
            bucket_profile = inspected.candidate_bucket_profile()
        if (args.max_targets_per_composition_bucket is not None
                and bucket_profile["largest_v2_composition_bucket_targets"] > args.max_targets_per_composition_bucket):
            raise ValueError("WBM v2 composition bucket exceeds approved comparison cap")
        if args.preflight:
            print(json.dumps({
                "status": "PREFLIGHT_ONLY_NO_NETWORK",
                "original_mptrj_bytes_declared": frozen["size"],
                "wbm_initial_structure_count": count,
                "candidate_bucket_profile": bucket_profile,
                "run_authorized": False,
                "exact_mace_training_selection_attested": False,
            }, sort_keys=True))
            return 0
        started = time.monotonic()
        def progress(n, byte_count):
            print("MPTRJ_WBM_SOURCE_OVERLAP_PROGRESS_UNVERIFIED "
                  f"frames={n} prefetched_bytes={byte_count} "
                  f"elapsed_seconds={time.monotonic() - started:.1f}",
                  file=sys.stderr, flush=True)
        staged = (_StagedTargetRows(args.matched_targets_jsonl)
                  if args.matched_targets_jsonl is not None else None)
        aggregate_created = False
        matched_published = False
        try:
            evidence = run_source_only_overlap(
                args.wbm_target_db, on_progress=progress,
                on_verified_targets=staged,
                max_targets_per_composition_bucket=args.max_targets_per_composition_bucket,
            )
            with args.report.open("x", encoding="utf-8") as report:
                aggregate_created = True
                json.dump(evidence, report, sort_keys=True, indent=2, allow_nan=False)
                report.write("\n")
            if staged is not None:
                staged.publish()
                matched_published = True
        except BaseException:
            if staged is not None:
                staged.discard()
            if aggregate_created:
                args.report.unlink(missing_ok=True)
            if matched_published:
                args.matched_targets_jsonl.unlink(missing_ok=True)
            raise
        print("MPTRJ_WBM_SOURCE_ONLY_OVERLAP_COMPLETE_MODEL_TRAINING_UNKNOWN")
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print(f"MPTRJ_WBM_SOURCE_OVERLAP_FAIL_CLOSED: {type(exc).__name__}: {exc}",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
