"""RT-P1-04: replay, retries and concurrency may never submit science."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
RECOVERY_COMMIT = "643b8a260b6fcff78bb02f3a63f348c29fd91317"


def workflow(name):
    return yaml.safe_load((ROOT / ".github/workflows" / name).read_text())


def test_automatic_main_push_launcher_disarmed():
    row = json.loads((ROOT / "data/development/phase3_salex_kaggle_launch_v1.json").read_text())
    assert row["armed"] is False
    assert row["authorization"]["dispatch_kaggle_full_run_controller"] is False
    launch = workflow("r2-phase3-salex-kaggle-launch.yml")
    triggers = launch.get("on", launch.get(True))
    assert "push" not in triggers
    assert set(launch["jobs"]) == {"contract"}


def test_controller_condition_cannot_be_overridden_by_production_variable():
    controller = workflow("r2-phase3-salex-kaggle-full-run.yml")["jobs"]["controller"]
    condition = controller["if"]
    assert "KAGGLE_PRODUCTION_ENABLED" not in condition
    assert "inputs.operation == 'resume'" in condition
    assert "inputs.operation == 'retrieve'" in condition
    assert RECOVERY_COMMIT in condition
    body = json.dumps(controller)
    assert "kernels_push" not in body
    assert "datasets_create_new" not in body


def guard(operation, commit):
    steps = workflow("r2-phase3-salex-kaggle-full-run.yml")["jobs"]["controller"]["steps"]
    assert steps[0]["name"] == "Reject new submissions without durable consumption"
    env = dict(os.environ, OPERATION=operation, REQUESTED_COMMIT=commit)
    return subprocess.run(["bash", "-euo", "pipefail", "-c", steps[0]["run"]], env=env,
                          text=True, capture_output=True)


@pytest.mark.parametrize("operation,commit", [
    ("submit", RECOVERY_COMMIT), ("submit", ""), ("submit", "a" * 40),
    ("unauthorized", RECOVERY_COMMIT), ("retrieve", "b" * 40), ("resume", ""),
])
def test_unauthorized_dispatch_rejected_before_credentials(operation, commit):
    assert guard(operation, commit).returncode != 0


def test_retry_replay_concurrent_submission_is_always_rejected():
    # Each invocation is a separate process, as workflow retries would be.
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda _: guard("submit", RECOVERY_COMMIT), range(12)))
    assert all(result.returncode != 0 for result in results)


@pytest.mark.parametrize("operation", ["resume", "retrieve"])
def test_exact_historical_recovery_remains_available(operation):
    assert guard(operation, RECOVERY_COMMIT).returncode == 0
