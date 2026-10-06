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


def test_current_matches_latest_immutable_checkpoint():
    current = json.loads(
        (ROOT / "data/development/CURRENT.json").read_text(encoding="utf-8")
    )
    checkpoints = sorted((ROOT / "data/development/checkpoints").glob("*.json"))
    assert checkpoints
    latest = json.loads(checkpoints[-1].read_text(encoding="utf-8"))
    assert latest == current
