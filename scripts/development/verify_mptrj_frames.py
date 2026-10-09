"""Offline Phase 3 MPTrj full frame/byte consistency verifier (manual only).

Does not fetch upstream source, publish data, run Kaggle or authorize model
training exposure. Full original input is ~12.2 GB and is NOT bundled.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import stat
import sys
import time

from rhombus.domain.mptrj_integrity import verify_complete_mptrj_source
from scripts.development.verify_mptrj_source import (
    FIGSHARE_FILENAME,
    SourceEvidenceError,
    canonical_source,
)

OFFICIAL_MPTRJ_FRAMES = 1_580_395


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path, help="EXISTING original Figshare JSON only")
    parser.add_argument("--report", required=True, type=Path, help="New JSON report path; never overwrite")
    parser.add_argument("--progress-every-frames", type=int, default=5000,
                        help="Emit unverified stderr progress every N completed frames (default 5000)")
    args = parser.parse_args(argv)
    try:
        if args.progress_every_frames <= 0:
            raise SourceEvidenceError("--progress-every-frames must be positive")
        metadata = canonical_source()
        source = args.source
        if source.is_symlink() or source.name != FIGSHARE_FILENAME:
            raise SourceEvidenceError("exact canonical filename and non-symlink source required")
        if not source.is_file() or source.stat().st_size != metadata["size"]:
            raise SourceEvidenceError("source missing or official source size mismatch")
        if args.report.is_symlink() or args.report.exists():
            raise SourceEvidenceError("report already exists or is a symlink")
        original = source.stat()
        if not stat.S_ISREG(original.st_mode):
            raise SourceEvidenceError("canonical source must be a regular file")
        def identity(st):
            return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns)
        started = time.monotonic()
        def progress(completed_frames: int, stream_bytes_read: int) -> None:
            print(
                "MPTRJ_FULL_STREAM_PROGRESS_UNVERIFIED "
                f"completed_frames={completed_frames} "
                f"prefetched_source_bytes={stream_bytes_read} "
                f"elapsed_seconds={time.monotonic() - started:.1f}",
                file=sys.stderr, flush=True,
            )
        print(
            f"MPTRJ_FULL_STREAM_STARTED_UNVERIFIED "
            f"expected_bytes={metadata['size']} "
            f"expected_frames={OFFICIAL_MPTRJ_FRAMES}",
            file=sys.stderr, flush=True,
        )
        # No evidence is created until after complete JSON/frame/hash validation.
        with source.open("rb") as handle:
            if identity(os.fstat(handle.fileno())) != identity(original):
                raise SourceEvidenceError("canonical source changed between preflight and open")
            report = verify_complete_mptrj_source(
                handle,
                expected_size=metadata["size"],
                expected_md5=metadata["md5"],
                expected_frames=OFFICIAL_MPTRJ_FRAMES,
                on_progress=progress,
                progress_every_frames=args.progress_every_frames,
            )
            handle_after = os.fstat(handle.fileno())
        if (identity(handle_after) != identity(original)
                or identity(source.stat()) != identity(original)):
            raise SourceEvidenceError("canonical source changed during full verification")
        with args.report.open("x", encoding="utf-8") as output:
            json.dump(report, output, indent=2, sort_keys=True)
            output.write("\n")
        print("MPTRJ_FULL_SOURCE_FRAME_IDENTITY_PASS")
        print("MACE_MPA0_TRAINING_LINEAGE_UNATTESTED; EXPOSURE_AUDIT_NOT_AUTHORIZED")
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print(f"MPTRJ_FULL_SOURCE_FAIL_CLOSED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
