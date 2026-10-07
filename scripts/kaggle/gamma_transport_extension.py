"""Kaggle driver for the authorized gamma-LiAlO2 transport-evidence extension.

This script is executed inside a private Kaggle kernel. It consumes only the
GitHub-staged source bundle, checks the frozen execution environment, rebuilds
the legacy extension authorization from bound sources, runs the one-shot
extension, then reclassifies the resulting trajectory.

No scientific threshold is changed here.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

DATASET = Path("/kaggle/input/rhombus-gamma-transport-extension")
WORK = Path("/kaggle/working/rhombus-gamma-extension")
BATCH_ID = "df4431260652d2ea"
REPO_URL = "https://github.com/wt2018mask/Rhombus.git"


def run(*args: str, cwd: Path | None = None) -> None:
    subprocess.run(args, cwd=cwd, check=True)


def main() -> None:
    commit = (DATASET / "source_commit.txt").read_text(encoding="utf-8").strip()
    if len(commit) != 40:
        raise RuntimeError("invalid exact source commit")

    if WORK.exists():
        shutil.rmtree(WORK)
    run("git", "clone", "--no-checkout", REPO_URL, str(WORK))
    run("git", "checkout", commit, cwd=WORK)

    # Install only after exact source is checked out.
    run(
        "python", "-m", "pip", "install", "-q",
        "mace-torch==0.3.16", "ase==3.29.0", "pymatgen==2026.9.24",
        "smact", "pyyaml",
    )
    run("python", "-m", "pip", "install", "--no-deps", "-e", ".", cwd=WORK)

    for name in ("p1", "p2", "p25"):
        (WORK / "artifacts" / name).mkdir(parents=True, exist_ok=True)
    (WORK / "artifacts" / "extension").mkdir(parents=True, exist_ok=True)
    (WORK / "artifacts" / "extension-traj").mkdir(parents=True, exist_ok=True)

    shutil.copy2(
        DATASET / "p1" / f"{BATCH_ID}.json",
        WORK / "artifacts" / "p1" / f"{BATCH_ID}.json",
    )
    shutil.copy2(
        DATASET / "p2" / f"{BATCH_ID}.json",
        WORK / "artifacts" / "p2" / f"{BATCH_ID}.json",
    )

    wrapper = json.loads(
        (DATASET / "transport" / f"{BATCH_ID}.transport-regime.json").read_text(
            encoding="utf-8"
        )
    )
    legacy = wrapper.get("legacy_result")
    if not isinstance(legacy, dict):
        raise RuntimeError("transport artifact lacks bound legacy classifier result")
    (WORK / "artifacts" / "p25" / f"{BATCH_ID}.json").write_text(
        json.dumps({"batch_id": BATCH_ID, "result": legacy}, indent=2),
        encoding="utf-8",
    )

    # Source P2 binding points to this exact trajectory path.
    p2 = json.loads(
        (WORK / "artifacts" / "p2" / f"{BATCH_ID}.json").read_text(
            encoding="utf-8"
        )
    )
    binding = p2["result"]["trajectory_artifact"]
    expected_sha = (
        "b68c805b8f69bb2346ad3f5337cf5df64d9dd0c882af74bed397dcc00af34f02"
    )
    if binding["sha256"] != expected_sha:
        raise RuntimeError("source P2 trajectory SHA mismatch")
    target = WORK / binding["path"]
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DATASET / "p2_traj" / f"{BATCH_ID}.npz", target)

    auth = WORK / "artifacts" / "extension-authorization.json"
    run(
        "python", "-m", "rudeus.mlip.freeze_p25_extension_authorization",
        "--p1-dir", "artifacts/p1",
        "--p2-dir", "artifacts/p2",
        "--p25-dir", "artifacts/p25",
        "--out", str(auth),
        cwd=WORK,
    )

    frozen = json.loads(
        (DATASET / "v2_authorization.json").read_text(encoding="utf-8")
    )
    generated = json.loads(auth.read_text(encoding="utf-8"))
    if generated["n_authorized"] != 1:
        raise RuntimeError("extension cohort is not exactly one candidate")
    row = generated["candidates"][0]
    if row["batch_id"] != BATCH_ID:
        raise RuntimeError("wrong extension candidate")
    if generated["transition_protocol_hash"] != frozen["transition"]["protocol_hash"]:
        raise RuntimeError("transition protocol hash differs from v2 authorization")

    run(
        "python", "-m", "rudeus.mlip.run_p25_extension",
        "--p1-done", "artifacts/p1",
        "--source-p2", "artifacts/p2",
        "--source-p25", "artifacts/p25",
        "--authorized-manifest", str(auth),
        "--environment-manifest",
        str(DATASET / "kaggle_t4_environment.json"),
        "--out", "artifacts/extension",
        "--traj-out", "artifacts/extension-traj",
        "--device", "cuda",
        "--worker", "kaggle-r2-gamma-transport-extension",
        cwd=WORK,
    )

    ext = json.loads(
        (WORK / "artifacts" / "extension" / f"{BATCH_ID}.json").read_text(
            encoding="utf-8"
        )
    )
    from rhombus.transport import classify_transport_regime

    classified = classify_transport_regime(
        stability_payload=ext,
        worker_info={"session": "kaggle-r2-gamma-transport-extension-classify"},
    )
    result = {
        "schema_version": "r2-gamma-transport-extension-result-v1",
        "batch_id": BATCH_ID,
        "source_commit": commit,
        "transition_protocol_hash": generated["transition_protocol_hash"],
        "extension_result": ext["result"],
        "transport_regime": classified,
    }
    out = Path("/kaggle/working/rhombus_gamma_transport_extension_result.json")
    out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print("RHOMBUS_GAMMA_EXTENSION_RESULT", classified["transport_state"])


if __name__ == "__main__":
    main()
