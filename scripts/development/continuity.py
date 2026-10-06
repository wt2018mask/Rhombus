#!/usr/bin/env python3
"""Rhombus durable development-continuity contract.

CURRENT.json is the machine-readable source of truth.
DEVELOPMENT_HANDOFF.md is a deterministic human rendering.
checkpoints/*.json is append-only history.

Every pull request must advance all three surfaces.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CURRENT = ROOT / "data" / "development" / "CURRENT.json"
CHECKPOINT_DIR = ROOT / "data" / "development" / "checkpoints"
HANDOFF = ROOT / "docs" / "DEVELOPMENT_HANDOFF.md"
SCHEMA_VERSION = "rhombus-development-continuity-v1"

REQUIRED_TOP_LEVEL = {
    "schema_version", "checkpoint_index", "checkpoint_id", "recorded_date",
    "canonical_branch", "project_mode", "architecture_reference",
    "integration", "last_completed_task", "current_frontier",
    "critical_invariants", "canonical_recovery_files", "recovery_protocol",
    "completion_contract",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def render_markdown(state: dict[str, Any]) -> str:
    integration = state["integration"]
    task = state["last_completed_task"]
    frontier = state["current_frontier"]
    completion = state["completion_contract"]
    pr = integration.get("pull_request")
    pr_text = f"`#{pr}`" if pr is not None else "`PENDING`"

    lines = [
        "# Rhombus Development Handoff",
        "",
        "> **Canonical recovery entry point.** This file is generated from "
        "`data/development/CURRENT.json`. Do not edit it by hand.",
        "",
        f"- **Schema:** `{state['schema_version']}`",
        f"- **Checkpoint:** `{state['checkpoint_index']:04d}` / "
        f"`{state['checkpoint_id']}`",
        f"- **Recorded date:** {state['recorded_date']}",
        f"- **Canonical branch:** `{state['canonical_branch']}`",
        f"- **Project mode:** `{state['project_mode']}`",
        f"- **Architecture:** `{state['architecture_reference']}`",
        "",
        "## Integration state",
        "",
        f"- Task branch: `{integration['task_branch']}`",
        f"- Base main SHA: `{integration['base_main_sha']}`",
        f"- Pull request: {pr_text}",
        f"- Task status: `{integration['task_status']}`",
        "",
        "## Last completed task",
        "",
        f"**{task['title']}**",
        "",
        task["purpose"],
        "",
        f"- Previous completed PR: `#{task['previous_completed_pr']}`",
        f"- Previous main SHA: `{task['previous_main_sha']}`",
        "",
        "Outcomes:",
    ]
    lines.extend(f"- {item}" for item in task["outcomes"])
    lines.extend([
        "", "## Current frontier", "",
        f"**Program:** {frontier['program']}", "",
        "Scientific state:",
    ])
    lines.extend(f"- {item}" for item in frontier["scientific_state"])
    lines.extend([
        "", "**Next exact action:**", "", frontier["next_action"], "",
        "**Blocked on:**",
    ])
    if frontier["blocked_on"]:
        lines.extend(f"- {item}" for item in frontier["blocked_on"])
    else:
        lines.append("- Nothing currently recorded.")

    lines.extend(["", "## Critical invariants", ""])
    lines.extend(f"- {item}" for item in state["critical_invariants"])
    lines.extend(["", "## Canonical recovery files", ""])
    lines.extend(f"- `{item}`" for item in state["canonical_recovery_files"])
    lines.extend(["", "## Recovery protocol", ""])
    lines.extend(
        f"{index}. {item}"
        for index, item in enumerate(state["recovery_protocol"], start=1)
    )
    lines.extend([
        "", "## Completion contract", "", completion["rule"], "",
        "Every pull request must update:",
    ])
    lines.extend(
        f"- `{item}`"
        for item in completion["required_on_every_pull_request"]
    )
    lines.extend([
        "",
        "If a future chat has no prior context, the repository files above "
        "are sufficient to resume from this checkpoint.",
        "",
    ])
    return "\n".join(lines)


def validate_state(state: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = REQUIRED_TOP_LEVEL - set(state)
    if missing:
        errors.append(f"CURRENT missing keys: {sorted(missing)}")
    if state.get("schema_version") != SCHEMA_VERSION:
        errors.append(
            f"schema_version must be {SCHEMA_VERSION!r}, "
            f"got {state.get('schema_version')!r}"
        )
    index = state.get("checkpoint_index")
    if not isinstance(index, int) or index < 1:
        errors.append("checkpoint_index must be a positive integer")
    if state.get("canonical_branch") != "main":
        errors.append("canonical_branch must be 'main'")
    frontier = state.get("current_frontier", {})
    if not str(frontier.get("next_action", "")).strip():
        errors.append("current_frontier.next_action must be non-empty")
    if not state.get("recovery_protocol"):
        errors.append("recovery_protocol must be non-empty")
    required = set(
        state.get("completion_contract", {}).get(
            "required_on_every_pull_request", []
        )
    )
    expected = {
        "data/development/CURRENT.json",
        "docs/DEVELOPMENT_HANDOFF.md",
        "one newly added data/development/checkpoints/*.json file",
    }
    if required != expected:
        errors.append("completion_contract required files changed unexpectedly")
    return errors


def checkpoint_files() -> list[tuple[int, Path]]:
    rows: list[tuple[int, Path]] = []
    if not CHECKPOINT_DIR.exists():
        return rows
    for path in CHECKPOINT_DIR.glob("*.json"):
        match = re.match(r"^(\d{4})-", path.name)
        if match:
            rows.append((int(match.group(1)), path))
    return sorted(rows)


def validate_repository() -> list[str]:
    errors: list[str] = []
    if not CURRENT.exists():
        return [f"missing {CURRENT.relative_to(ROOT)}"]
    state = load_json(CURRENT)
    errors.extend(validate_state(state))

    checkpoints = checkpoint_files()
    if not checkpoints:
        errors.append("no immutable development checkpoints found")
        return errors

    latest_index, latest_path = checkpoints[-1]
    if latest_index != state.get("checkpoint_index"):
        errors.append(
            f"CURRENT checkpoint_index={state.get('checkpoint_index')} but "
            f"latest immutable checkpoint is {latest_index:04d}"
        )
    latest_state = load_json(latest_path)
    if latest_state != state:
        errors.append(
            "CURRENT.json is not JSON-equivalent to the highest-index "
            f"checkpoint {latest_path.relative_to(ROOT)}"
        )

    rendered = render_markdown(state)
    if not HANDOFF.exists():
        errors.append(f"missing {HANDOFF.relative_to(ROOT)}")
    elif HANDOFF.read_text(encoding="utf-8") != rendered:
        errors.append(
            "DEVELOPMENT_HANDOFF.md is stale; run "
            "`python scripts/development/continuity.py write`"
        )
    return errors


def changed_paths(base_ref: str) -> list[tuple[str, str]]:
    proc = subprocess.run(
        ["git", "diff", "--name-status", f"{base_ref}...HEAD"],
        cwd=ROOT, check=True, text=True, capture_output=True,
    )
    rows: list[tuple[str, str]] = []
    for line in proc.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            rows.append((parts[0], parts[-1]))
    return rows


def validate_pr(base_ref: str, pr_number: int) -> list[str]:
    errors = validate_repository()
    rows = changed_paths(base_ref)
    by_path = {path: status for status, path in rows}

    for required in (
        "data/development/CURRENT.json",
        "docs/DEVELOPMENT_HANDOFF.md",
    ):
        if required not in by_path:
            errors.append(
                "pull request did not update required continuity file: "
                + required
            )

    checkpoint_rows = [
        (status, path)
        for status, path in rows
        if path.startswith("data/development/checkpoints/")
        and path.endswith(".json")
    ]
    added = [path for status, path in checkpoint_rows if status.startswith("A")]
    non_added = [
        (status, path)
        for status, path in checkpoint_rows
        if not status.startswith("A")
    ]
    if len(added) != 1:
        errors.append(
            "each pull request must add exactly one immutable development "
            f"checkpoint; added={added}"
        )
    if non_added:
        errors.append(
            "existing development checkpoints are append-only and may not "
            f"be modified/deleted: {non_added}"
        )

    state = load_json(CURRENT)
    if state.get("integration", {}).get("pull_request") != pr_number:
        errors.append(
            "CURRENT integration.pull_request must equal this PR number "
            f"({pr_number})"
        )
    if (
        state.get("integration", {}).get("task_status")
        != "COMPLETE_PENDING_MERGE"
    ):
        errors.append(
            "CURRENT integration.task_status must be COMPLETE_PENDING_MERGE "
            "before a task PR can merge"
        )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check")
    sub.add_parser("write")
    pr = sub.add_parser("check-pr")
    pr.add_argument("--base-ref", required=True)
    pr.add_argument("--pr-number", required=True, type=int)
    args = parser.parse_args()

    if args.command == "write":
        state = load_json(CURRENT)
        errors = validate_state(state)
        if errors:
            print("\n".join(f"ERROR: {e}" for e in errors), file=sys.stderr)
            return 1
        HANDOFF.parent.mkdir(parents=True, exist_ok=True)
        HANDOFF.write_text(render_markdown(state), encoding="utf-8")
        return 0

    errors = (
        validate_pr(args.base_ref, args.pr_number)
        if args.command == "check-pr"
        else validate_repository()
    )
    if errors:
        print("\n".join(f"ERROR: {e}" for e in errors), file=sys.stderr)
        return 1
    print("DEVELOPMENT_CONTINUITY_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
