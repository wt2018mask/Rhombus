#!/usr/bin/env python3
"""Run canonical lightweight B2 failure controls and emit JSON evidence."""
from __future__ import annotations

import json
from pathlib import Path
import sys

from rudeus.science.known_material_failure_control import (
    load_failure_control_plan,
)
from rudeus.science.known_material_failure_control_execution import (
    run_failure_control_plan,
)


PLAN = Path("data/benchmarks/known_material/failure_control_plan_v1.json")


def main() -> None:
    report = run_failure_control_plan(
        load_failure_control_plan(PLAN),
        repo_root=Path("."),
    )
    print(json.dumps(report.to_dict(), sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(
            f"FAILURE_CONTROL_EXECUTION_FAILED: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        raise
