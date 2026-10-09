"""Opt-in full-source MPTrj↔WBM overlap; never checkpoint training exposure.

No source GET, MPTrj download or local staging by default. Requires existing
canonical WBM initial-structure target SQLite built from frozen source. The
full MPTrj response is read once with on-frame callbacks; all partial match
sets are discarded on failure. No report is written unless original source
file MD5, frame count and source size are all verified.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
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
) -> dict:
    with MPTrjWBMSourceObserver(db_path, **(observer_options or {})) as observer:
        args = {"on_frame": observer.observe, "on_progress": on_progress}
        if open_url is not None:
            args["open_url"] = open_url
        full_source = verify_remote_mptrj_full_stream(**args)
        return observer.verified_source_summary(full_source)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--preflight", action="store_true",
                       help="WBM-target and canonical source identity check; no network")
    modes.add_argument("--execute-full-download", action="store_true",
                       help="Explicit ~12.2GB original Figshare read and source-only WBM comparison")
    parser.add_argument("--wbm-target-db", type=Path, required=True)
    parser.add_argument("--report", type=Path, help="new report, never overwrite")
    args = parser.parse_args(argv)
    try:
        if args.preflight and args.report is not None:
            raise ValueError("no output report in offline preflight")
        if not args.preflight and (args.report is None or args.report.is_symlink()
                                   or args.report.exists()):
            raise ValueError("new non-symlink report required before full-source network read")
        frozen = canonical_source()
        with MPTrjWBMSourceObserver(args.wbm_target_db) as inspected:
            count = inspected.wbm_count
        if args.preflight:
            print(json.dumps({
                "status": "PREFLIGHT_ONLY_NO_NETWORK",
                "original_mptrj_bytes_declared": frozen["size"],
                "wbm_initial_structure_count": count,
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
        evidence = run_source_only_overlap(args.wbm_target_db, on_progress=progress)
        with args.report.open("x", encoding="utf-8") as report:
            json.dump(evidence, report, sort_keys=True, indent=2, allow_nan=False)
            report.write("\n")
        print("MPTRJ_WBM_SOURCE_ONLY_OVERLAP_COMPLETE_MODEL_TRAINING_UNKNOWN")
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print(f"MPTRJ_WBM_SOURCE_OVERLAP_FAIL_CLOSED: {type(exc).__name__}: {exc}",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
