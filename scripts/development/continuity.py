#!/usr/bin/env python3
"""Compact Rhombus development-continuity contract.

Normal recovery reads CURRENT.json only. Historical checkpoints are tiny,
append-only events for audit, not replay requirements. Detailed science is
dereferenced only through CURRENT.refs when needed.
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
CURRENT_SCHEMA = "rhombus-development-continuity-v2"
EVENT_SCHEMA = "rhombus-development-event-v1"

REQUIRED_CURRENT = {
    "schema_version", "checkpoint_index", "recorded_date", "mode",
    "integration", "frontier", "state_codes", "refs",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def checkpoint_files() -> list[tuple[int, Path]]:
    rows: list[tuple[int, Path]] = []
    if not CHECKPOINT_DIR.exists():
        return rows
    for path in CHECKPOINT_DIR.glob("*.json"):
        m = re.match(r"^(\d{4})-", path.name)
        if m:
            rows.append((int(m.group(1)), path))
    return sorted(rows)


def validate_current(state: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = REQUIRED_CURRENT - set(state)
    if missing:
        errors.append(f"CURRENT missing keys: {sorted(missing)}")
    if state.get("schema_version") != CURRENT_SCHEMA:
        errors.append(f"CURRENT schema must be {CURRENT_SCHEMA}")
    idx = state.get("checkpoint_index")
    if not isinstance(idx, int) or idx < 1:
        errors.append("checkpoint_index must be a positive integer")
    integration = state.get("integration", {})
    if integration.get("status") != "COMPLETE_PENDING_MERGE":
        errors.append("integration.status must be COMPLETE_PENDING_MERGE")
    frontier = state.get("frontier", {})
    if not str(frontier.get("next_action", "")).strip():
        errors.append("frontier.next_action must be non-empty")
    refs = state.get("refs", {})
    for key in ("architecture", "policy", "handoff"):
        if key not in refs:
            errors.append(f"CURRENT.refs missing {key}")
    return errors


def validate_latest_event(state: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    rows = checkpoint_files()
    if not rows:
        return ["no development checkpoint events found"]
    latest_idx, latest_path = rows[-1]
    if latest_idx != state.get("checkpoint_index"):
        errors.append(
            f"CURRENT checkpoint_index={state.get('checkpoint_index')} but "
            f"latest event index={latest_idx}"
        )
    event = load_json(latest_path)
    if event.get("schema_version") != EVENT_SCHEMA:
        errors.append(f"latest event schema must be {EVENT_SCHEMA}")
    if event.get("index") != latest_idx:
        errors.append("latest event index does not match filename")
    if event.get("pr") != state.get("integration", {}).get("pr"):
        errors.append("latest event PR does not match CURRENT.integration.pr")
    if event.get("next_action") != state.get("frontier", {}).get("next_action"):
        errors.append("latest event next_action does not match CURRENT frontier")
    return errors


def render_markdown(state: dict[str, Any]) -> str:
    i = state["integration"]
    f = state["frontier"]
    refs = state["refs"]
    blockers = ", ".join(f["blockers"]) if f["blockers"] else "none"
    codes = ", ".join(f"`{x}`" for x in state["state_codes"])
    ref_lines = "\n".join(f"- **{k}:** `{v}`" for k, v in refs.items())
    return (
        "# Rhombus Development Handoff\n\n"
        "> Generated from `data/development/CURRENT.json`. Normal recovery "
        "should read CURRENT first and dereference only what the next action needs.\n\n"
        f"- Checkpoint: `{state['checkpoint_index']:04d}`\n"
        f"- Mode: `{state['mode']}`\n"
        f"- PR: `#{i['pr']}`\n"
        f"- Branch: `{i['branch']}`\n"
        f"- Status: `{i['status']}`\n"
        f"- Phase: `{f['phase']}`\n"
        f"- Next action: `{f['next_action']}`\n"
        f"- Blockers: {blockers}\n\n"
        "## State codes\n\n"
        f"{codes}\n\n"
        "## Evidence / policy pointers\n\n"
        f"{ref_lines}\n\n"
        "Historical checkpoint events are audit-only and are not read during "
        "normal recovery.\n"
    )


def validate_repository() -> list[str]:
    if not CURRENT.exists():
        return ["missing data/development/CURRENT.json"]
    state = load_json(CURRENT)
    errors = validate_current(state)
    errors.extend(validate_latest_event(state))
    rendered = render_markdown(state)
    if not HANDOFF.exists():
        errors.append("missing docs/DEVELOPMENT_HANDOFF.md")
    elif HANDOFF.read_text(encoding="utf-8") != rendered:
        errors.append(
            "DEVELOPMENT_HANDOFF.md is stale; run "
            "python scripts/development/continuity.py write"
        )
    return errors


def changed_paths(base_ref: str) -> list[tuple[str, str]]:
    p = subprocess.run(
        ["git", "diff", "--name-status", f"{base_ref}...HEAD"],
        cwd=ROOT, check=True, text=True, capture_output=True,
    )
    rows = []
    for line in p.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            rows.append((parts[0], parts[-1]))
    return rows


def validate_pr(base_ref: str, pr_number: int) -> list[str]:
    errors = validate_repository()
    rows = changed_paths(base_ref)
    paths = {path: status for status, path in rows}
    for required in (
        "data/development/CURRENT.json",
        "docs/DEVELOPMENT_HANDOFF.md",
    ):
        if required not in paths:
            errors.append(f"PR did not update continuity file: {required}")

    checkpoint_rows = [
        (status, path) for status, path in rows
        if path.startswith("data/development/checkpoints/")
        and path.endswith(".json")
    ]
    added = [path for status, path in checkpoint_rows if status.startswith("A")]
    altered = [
        (status, path) for status, path in checkpoint_rows
        if not status.startswith("A")
    ]
    if len(added) != 1:
        errors.append(
            "each PR must add exactly one compact checkpoint event; "
            f"added={added}"
        )
    if altered:
        errors.append(
            "previous checkpoint events are append-only: "
            f"{altered}"
        )

    state = load_json(CURRENT)
    if state.get("integration", {}).get("pr") != pr_number:
        errors.append(
            f"CURRENT.integration.pr must equal this PR ({pr_number})"
        )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check")
    sub.add_parser("write")
    p = sub.add_parser("check-pr")
    p.add_argument("--base-ref", required=True)
    p.add_argument("--pr-number", required=True, type=int)
    args = parser.parse_args()

    if args.command == "write":
        state = load_json(CURRENT)
        errors = validate_current(state)
        if errors:
            print("\n".join(f"ERROR: {e}" for e in errors), file=sys.stderr)
            return 1
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
