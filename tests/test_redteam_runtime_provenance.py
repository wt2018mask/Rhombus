"""RT-P2-03: partial reproducibility records must be honest and secret-free."""
import hashlib
import json
from pathlib import Path
import re

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ["r2-fast-ci.yml", "r2-security-contract.yml", "development-continuity.yml",
             "r2-phase3-salex-kaggle-launch.yml", "r2-phase3-salex-kaggle-full-run.yml"]


def test_batch_workflows_pin_executable_actions_and_controller_packages():
    for name in WORKFLOWS:
        data = yaml.safe_load((ROOT / ".github/workflows" / name).read_text())
        for job in data["jobs"].values():
            for step in job["steps"]:
                if "uses" in step:
                    assert re.fullmatch(r"actions/[a-z-]+@[0-9a-f]{40}", step["uses"])
    controller = (ROOT / ".github/workflows/r2-phase3-salex-kaggle-full-run.yml").read_text()
    assert "--require-hashes -r rhombus-security-tools/scripts/ci/kaggle-controller-requirements.txt" in controller
    lock = (ROOT / "scripts/ci/kaggle-controller-requirements.txt").read_text()
    assert "kaggle==2.2.4" in lock
    assert "zstandard==0.25.0" in lock
    assert "--hash=sha256:" in lock
    assert controller.index("Checkout trusted recovery") < controller.index("Install Kaggle and verification runtime")


def test_runtime_records_actual_bytes_and_seed_without_environment_values(tmp_path, monkeypatch):
    from rhombus.evidence.runtime_provenance import collect_runtime_provenance
    monkeypatch.setenv("KAGGLE_API_TOKEN", "synthetic-never-export-this")
    data = tmp_path / "synthetic-data.txt"
    data.write_bytes(b"fixture only")
    record = collect_runtime_provenance(ROOT, random_seed=550, artifact_paths={"input": data})
    assert record["random_seed"] == 550
    assert record["source_commit"] and len(record["source_commit"]) == 40
    assert record["artifact_sha256"]["input"] == hashlib.sha256(b"fixture only").hexdigest()
    assert record["python"]
    assert record["packages"]["numpy"]
    assert record["bitwise_reproducibility_verified"] is False
    assert record["hardware"]["gpu_observation"] == "NOT_PROBED"
    assert "synthetic-never-export-this" not in json.dumps(record)
    assert "KAGGLE_API_TOKEN" not in json.dumps(record)


@pytest.mark.parametrize("seed", [True, "550", 1.9, -1])
def test_provenance_rejects_ambiguous_seed(seed):
    from rhombus.evidence.runtime_provenance import collect_runtime_provenance
    with pytest.raises(ValueError):
        collect_runtime_provenance(ROOT, random_seed=seed)


def test_driver_receipt_records_environment_without_new_execution():
    source = (ROOT / "scripts/kaggle/salex_phase3_full_run.py").read_text()
    assert '"runtime_provenance": collect_runtime_provenance(repo_root)' in source
    assert '"zstandard==0.25.0"' in source
