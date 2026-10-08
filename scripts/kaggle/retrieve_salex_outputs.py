"""Read-only Kaggle output recovery.

Primary: existing kernel output. Fallback: operator-created private Kaggle
dataset containing the eight exact artifacts from the completed kernel.
Never submits a kernel. Never logs provider output or credential values.
Independent receipt and SHA256 checks run in the calling workflow.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

KERNEL = "wt2018mask/rhombus-salexcpu-643b8a260b6f"
DATASET_RE = re.compile(r"wt2018mask/[a-z0-9][a-z0-9-]{2,100}\Z")
INDEX_PART_RE = re.compile(r"rhombus_phase3_salex_membership\.sqlite\.zst\.part\d{4}\Z")
OVERLAP_PART_RE = re.compile(r"rhombus_phase3_wbm_salex_overlap\.jsonl\.zst\.part\d{4}\Z")
SMALL_FILES = {"rhombus_phase3_salex_run_receipt.json", "rhombus_phase3_salex_summary.json"}
MAX_TOTAL = 950 * 1024 * 1024
MAX_PART = 128 * 1024 * 1024
MAX_ZIP = 950 * 1024 * 1024


def expected_name(name: str) -> bool:
    return name in SMALL_FILES or bool(INDEX_PART_RE.fullmatch(name) or OVERLAP_PART_RE.fullmatch(name))


def required_files_present(root: Path) -> bool:
    return all((root / name).is_file() and (root / name).stat().st_size > 0 for name in SMALL_FILES)


def safe_provider_class(body: str) -> str:
    """Classify provider response without exposing its untrusted content."""
    if re.search(r"\b(401|403)\b|permission|unauthorized|forbidden", body, re.I):
        return "ACCESS_OR_AUTH"
    if re.search(r"\b404\b|not found", body, re.I):
        return "NOT_FOUND"
    if re.search(r"timed? ?out|connection|rate.?limit|429", body, re.I):
        return "NETWORK_OR_THROTTLE"
    return "EMPTY_OR_UNEXPECTED_OUTPUT"


def call_kaggle(args: list[str], *, timeout: int = 600) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "kaggle", *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def retrieve_kernel(root: Path, kernel: str, attempts: int, delay: float = 15.0) -> None:
    if kernel != KERNEL:
        raise ValueError("kernel ref does not match immutable production binding")
    for attempt in range(1, attempts + 1):
        shutil.rmtree(root, ignore_errors=True)
        root.mkdir(parents=True, exist_ok=True)
        try:
            result = call_kaggle(["kernels", "output", kernel, "-p", str(root), "--force"], timeout=900)
        except subprocess.TimeoutExpired:
            print(f"KAGGLE_KERNEL_OUTPUT_PROBE attempt={attempt} reason=TIMEOUT")
        else:
            if result.returncode == 0 and required_files_present(root):
                print(f"KAGGLE_KERNEL_OUTPUT_RECEIPT_PRESENT attempt={attempt}")
                return
            print(
                f"KAGGLE_KERNEL_OUTPUT_PROBE attempt={attempt} rc={result.returncode} "
                f"reason={safe_provider_class(result.stdout or '')} "
                f"files={sum(1 for x in root.iterdir() if x.is_file())}"
            )
        if attempt < attempts:
            time.sleep(delay)
    raise ValueError("kernel output unavailable; do not submit a new kernel; use a verified private recovery dataset")


def retrieve_dataset(root: Path, dataset_ref: str) -> None:
    if not DATASET_RE.fullmatch(dataset_ref):
        raise ValueError("recovery dataset must belong to approved wt2018mask namespace")
    with tempfile.TemporaryDirectory(prefix="rhombus-salex-dataset-") as tmp:
        directory = Path(tmp)
        result = call_kaggle(["datasets", "download", "-d", dataset_ref, "-p", str(directory), "--force"], timeout=900)
        if result.returncode != 0:
            raise ValueError(f"Kaggle dataset download failed ({safe_provider_class(result.stdout or '')})")
        zips = list(directory.glob("*.zip"))
        if len(zips) != 1 or zips[0].stat().st_size > MAX_ZIP:
            raise ValueError("expected exactly one bounded Kaggle dataset ZIP")
        root.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zips[0]) as archive:
            members = [entry for entry in archive.infolist() if not entry.is_dir()]
            names = [member.filename for member in members]
            if len(names) != len(set(names)) or len(names) > 24:
                raise ValueError("duplicate or excessive dataset entries")
            accepted = [member for member in members if expected_name(member.filename)]
            if not all(name in [member.filename for member in accepted] for name in SMALL_FILES):
                raise ValueError("dataset missing receipt or summary")
            size = 0
            for member in accepted:
                # No nested paths, links, executable metadata or decompression bombs.
                if Path(member.filename).name != member.filename or member.file_size > MAX_PART:
                    raise ValueError("unsafe or oversized science artifact")
                if (member.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError("symlink entry rejected")
                size += member.file_size
                if size > MAX_TOTAL:
                    raise ValueError("dataset artifacts exceed size budget")
                with archive.open(member) as source, (root / member.filename).open("xb") as dest:
                    shutil.copyfileobj(source, dest, length=8 * 1024 * 1024)
        if not required_files_present(root):
            raise ValueError("dataset extraction did not produce mandatory evidence")
    print("KAGGLE_RECOVERY_DATASET_FILES_PRESENT (not yet independently verified)")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kernel", required=True)
    parser.add_argument("--dataset", default="")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=3)
    opts = parser.parse_args()
    if not 1 <= opts.attempts <= 5:
        parser.error("attempts must be between 1 and 5")
    if opts.kernel != KERNEL:
        parser.error("unexpected immutable kernel ref")
    try:
        if opts.output.is_symlink():
            raise ValueError("output directory cannot be a symlink")
        if opts.output.exists():
            shutil.rmtree(opts.output)
        if opts.dataset:
            retrieve_dataset(opts.output, opts.dataset)
        else:
            retrieve_kernel(opts.output, opts.kernel, opts.attempts)
    except (ValueError, OSError, zipfile.BadZipFile) as exc:
        # Errors above do not embed untrusted provider stdout.
        print(f"KAGGLE_RECOVERY_SOURCE_UNAVAILABLE: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
