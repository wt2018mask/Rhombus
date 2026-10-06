import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_development_continuity_contract_is_self_consistent():
    subprocess.run(
        [sys.executable, "scripts/development/continuity.py", "check"],
        cwd=ROOT,
        check=True,
    )


def test_current_is_compact_and_latest_event_is_delta_only():
    current_path = ROOT / "data/development/CURRENT.json"
    current = json.loads(current_path.read_text(encoding="utf-8"))
    assert current["schema_version"] == "rhombus-development-continuity-v2"
    assert current_path.stat().st_size < 4096

    events = sorted((ROOT / "data/development/checkpoints").glob("*.json"))
    assert events
    latest = json.loads(events[-1].read_text(encoding="utf-8"))
    assert latest["schema_version"] == "rhombus-development-event-v1"
    assert events[-1].stat().st_size < 2048
    assert latest["index"] == current["checkpoint_index"]
    assert latest["pr"] == current["integration"]["pr"]
    assert latest["next_action"] == current["frontier"]["next_action"]
