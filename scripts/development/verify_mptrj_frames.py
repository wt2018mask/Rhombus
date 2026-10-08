"""Offline Phase 3 MPTrj full frame/byte consistency verifier (manual only).

Does not fetch upstream source, publish data, run Kaggle or authorize model
training exposure. Full original input is ~12.2 GB and is NOT bundled.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

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
    args = parser.parse_args(argv)
    try:
        metadata = canonical_source()
        source = args.source
        if source.is_symlink() or source.name != FIGSHARE_FILENAME:
            raise SourceEvidenceError("exact canonical filename and non-symlink source required")
        if not source.is_file() or source.stat().st_size != metadata["size"]:
            raise SourceEvidenceError("source missing or official source size mismatch")
        if args.report.is_symlink():
            raise SourceEvidenceError("report symlink refused")
        # No evidence is created until after complete JSON/frame/hash validation.
        with source.open("rb") as handle:
            report = verify_complete_mptrj_source(
                handle,
                expected_size=metadata["size"],
                expected_md5=metadata["md5"],
                expected_frames=OFFICIAL_MPTRJ_FRAMES,
            )
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
