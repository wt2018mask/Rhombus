"""Deterministic full-suite pytest planner and cross-platform shard runner.

The plan uses local timing evidence where available and conservative cost
classes for clone/process-heavy tests. Longest-estimated-duration-first (LPT)
assignment keeps known expensive modules apart while remaining reproducible.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
LINUX_SHARD_COUNT = 5
WINDOWS_MODULES = {
    "tests/test_kaggle_local_preparation.py",
    "tests/test_pre_heldout_no_change.py",
}

# Direct timings supplied from the completed local Chunk 6 run.
OBSERVED_SECONDS = {
    "tests/test_mlip.py": 51,
    "tests/test_kaggle_pass_identity.py": 32,
    "tests/test_m6b_generic_kaggle_contract.py": 27,
}

# The local report identified several 20–32 second cases in this module.
# 120 seconds is a conservative module-level planning estimate, not a claim
# that a fresh GitHub runner will have the same performance.
ESTIMATED_SECONDS = {
    "tests/test_local_execution.py": 120,
    "tests/test_kaggle_local_preparation.py": 75,
    "tests/test_code_bundle.py": 45,
    "tests/test_evidence.py": 40,
    "tests/test_execution_receipts.py": 35,
    "tests/test_git_receipts.py": 35,
    "tests/test_s2_code_bundle.py": 30,
    "tests/test_compute_backend.py": 30,
    "tests/test_followups.py": 25,
    "tests/test_calibration.py": 25,
    "tests/test_pre_heldout_no_change.py": 25,
}

GIT_PROCESS_MODULES = {
    "tests/test_code_bundle.py",
    "tests/test_evidence.py",
    "tests/test_execution_receipts.py",
    "tests/test_followups.py",
    "tests/test_git_receipts.py",
    "tests/test_s2_code_bundle.py",
}


def discover_modules() -> list[str]:
    return sorted(
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "tests").rglob("test_*.py")
        if path.is_file()
    )


def estimated_seconds(module: str) -> int:
    if module in OBSERVED_SECONDS:
        return OBSERVED_SECONDS[module]
    if module in ESTIMATED_SECONDS:
        return ESTIMATED_SECONDS[module]
    if module.startswith("tests/test_kaggle_"):
        return 22
    if module in GIT_PROCESS_MODULES:
        return 30
    if "calibration" in module or "qualification" in module:
        return 24
    return 8


def build_plan() -> list[dict[str, Any]]:
    modules = discover_modules()
    if not modules:
        raise RuntimeError("no tests/test_*.py modules were discovered")

    missing_windows = WINDOWS_MODULES - set(modules)
    if missing_windows:
        raise RuntimeError(
            "Windows module configuration references missing files: "
            + ", ".join(sorted(missing_windows))
        )

    portable = [module for module in modules if module not in WINDOWS_MODULES]
    linux_shards = [
        {
            "id": f"linux-{index + 1}",
            "os": "ubuntu-latest",
            "modules": [],
            "estimated_seconds": 0,
        }
        for index in range(LINUX_SHARD_COUNT)
    ]

    # Deterministic LPT: place the heaviest remaining module on the currently
    # lightest shard; lexical module order and shard ID break all ties.
    for module in sorted(portable, key=lambda item: (-estimated_seconds(item), item)):
        shard = min(
            linux_shards,
            key=lambda item: (item["estimated_seconds"], item["id"]),
        )
        shard["modules"].append(module)
        shard["estimated_seconds"] += estimated_seconds(module)

    for shard in linux_shards:
        shard["modules"].sort()

    windows = sorted(WINDOWS_MODULES)
    windows_shard = {
        "id": "windows-1",
        "os": "windows-latest",
        "modules": windows,
        "estimated_seconds": sum(estimated_seconds(module) for module in windows),
    }
    plan = linux_shards + [windows_shard]
    verify_plan(modules, plan)
    return plan


def verify_plan(
    expected_modules: list[str], plan: list[dict[str, Any]]
) -> None:
    assigned = [module for shard in plan for module in shard["modules"]]
    duplicates = sorted(
        module for module in set(assigned) if assigned.count(module) > 1
    )
    missing = sorted(set(expected_modules) - set(assigned))
    unexpected = sorted(set(assigned) - set(expected_modules))
    if duplicates or missing or unexpected or len(assigned) != len(expected_modules):
        raise RuntimeError(
            "shard coverage invalid: "
            f"duplicates={duplicates}, missing={missing}, unexpected={unexpected}"
        )

    windows_modules = {
        module
        for shard in plan
        if shard["os"] == "windows-latest"
        for module in shard["modules"]
    }
    if windows_modules != WINDOWS_MODULES:
        raise RuntimeError(
            "platform assignment invalid: Windows modules must be assigned "
            "exactly once to the Windows runner"
        )


def matrix_payload(plan: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "include": [
            {
                "id": shard["id"],
                "os": shard["os"],
                "modules": shard["modules"],
                "estimated_seconds": shard["estimated_seconds"],
            }
            for shard in plan
        ]
    }


def write_summary(plan: list[dict[str, Any]]) -> None:
    modules = discover_modules()
    verify_plan(modules, plan)
    print(f"Verified {len(modules)} modules across {len(plan)} shards.")
    print("| Shard | Runner | Modules | Estimated seconds | Assigned modules |")
    print("|---|---|---:|---:|---|")
    for shard in plan:
        print(
            f"| {shard['id']} | {shard['os']} | {len(shard['modules'])} | "
            f"{shard['estimated_seconds']} | "
            f"{', '.join(shard['modules'])} |"
        )


def run_shard(shard_id: str, plan: list[dict[str, Any]]) -> int:
    selected = next((item for item in plan if item["id"] == shard_id), None)
    if selected is None:
        raise SystemExit(f"unknown shard ID: {shard_id}")

    artifacts = ROOT / "artifacts"
    artifacts.mkdir(exist_ok=True)
    log_path = artifacts / f"pytest-{shard_id}.log"
    junit_path = artifacts / f"pytest-{shard_id}.xml"
    freeze = subprocess.run(
        [sys.executable, "-m", "pip", "freeze"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    (artifacts / f"pip-freeze-{shard_id}.txt").write_text(
        freeze.stdout, encoding="utf-8"
    )

    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "-ra",
        "--durations=20",
        f"--junitxml={junit_path}",
        *selected["modules"],
    ]
    print(f"SHARD={shard_id} RUNNER={selected['os']}", flush=True)
    print(f"MODULE_COUNT={len(selected['modules'])}", flush=True)
    for module in selected["modules"]:
        print(f"MODULE={module}", flush=True)
    print("COMMAND=" + json.dumps(command), flush=True)

    with log_path.open("w", encoding="utf-8", newline="") as log:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        assert process.stdout is not None
        for line in process.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            log.write(line)
            log.flush()
        return process.wait()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix-json", action="store_true")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--run-shard")
    args = parser.parse_args()
    plan = build_plan()

    if args.matrix_json:
        print(json.dumps(matrix_payload(plan), separators=(",", ":")))
        return 0
    if args.summary:
        write_summary(plan)
        return 0
    if args.run_shard:
        return run_shard(args.run_shard, plan)

    write_summary(plan)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
