"""Repair P2 FixCom-v2 provenance metadata without rerunning MD.

The affected execution used the explicit FixCom constraint implementation but
config.yaml still labeled the protocol as p2-adaptive-v1-provisional. This tool
verifies each existing trajectory artifact against its recorded canonical hash,
then rewrites only protocol-identifying metadata and all dependent hash bindings.

Scientific trajectory coordinates, verdicts, and metrics are unchanged.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

import yaml

from rudeus.mlip.p2 import P2_PROTOCOL_DEFAULTS, protocol_config_hash
from rudeus.mlip.p2_traj import (
    load_traj_artifact,
    verify_traj_artifact,
    write_traj_artifact,
)
from rudeus.mlip.sharding import write_json_atomic

OLD_VERSION = "p2-adaptive-v1-provisional"
NEW_VERSION = "p2-adaptive-v2-fixcom-constraint-provisional"
REPAIR_ID = "p2-fixcom-v2-provenance-metadata-repair-v1"


def corrected_protocol_from_config(config_path: str | Path) -> Dict[str, Any]:
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    protocol = dict(P2_PROTOCOL_DEFAULTS)
    protocol.update(cfg.get("p2", {}))
    if protocol.get("p2_protocol_version") != NEW_VERSION:
        raise ValueError(
            f"config does not declare corrected P2 version {NEW_VERSION!r}"
        )
    return protocol


def repair_p2_fixcom_provenance(
    p2_dir: str | Path,
    repo_root: str | Path,
    config_path: str | Path,
) -> Dict[str, Any]:
    p2_dir = Path(p2_dir)
    repo_root = Path(repo_root)
    protocol = corrected_protocol_from_config(config_path)
    new_cfg_hash = protocol_config_hash(protocol)

    repaired = []
    unchanged = []

    for result_path in sorted(p2_dir.glob("*.json")):
        rec = json.loads(result_path.read_text(encoding="utf-8"))
        result = rec.get("result") or {}
        job = rec.get("job") or {}
        batch_id = str(rec.get("batch_id", result_path.stem))
        if batch_id != result_path.stem:
            raise ValueError(f"batch_id/filename mismatch: {result_path.name}")

        art = result.get("trajectory_artifact") or {}
        rel = art.get("path")
        old_art_sha = art.get("sha256")
        if not rel or not old_art_sha:
            raise ValueError(f"missing trajectory binding: {batch_id}")

        art_path = repo_root / rel
        payload = verify_traj_artifact(art_path, old_art_sha)

        old_version = result.get("p2_protocol_version")
        if old_version == NEW_VERSION:
            unchanged.append(batch_id)
            continue
        if old_version != OLD_VERSION:
            raise ValueError(
                f"unexpected result protocol version for {batch_id}: {old_version!r}"
            )
        if payload.get("p2_protocol_version") != OLD_VERSION:
            raise ValueError(
                f"unexpected artifact protocol version for {batch_id}: "
                f"{payload.get('p2_protocol_version')!r}"
            )

        # Validate that the only protocol-definition defect is the stale
        # protocol-version label before any mutation.
        old_protocol = result.get("p2_protocol")
        if not isinstance(old_protocol, dict):
            raise ValueError(f"missing p2_protocol: {batch_id}")
        expected_old = dict(protocol)
        expected_old["p2_protocol_version"] = OLD_VERSION
        if old_protocol != expected_old:
            raise ValueError(
                f"P2 protocol differs beyond stale version label: {batch_id}"
            )
        old_cfg_hash = protocol_config_hash(old_protocol)
        if result.get("p2_config_hash") != old_cfg_hash:
            raise ValueError(f"result config hash mismatch before repair: {batch_id}")
        if job.get("p2_config_hash") != old_cfg_hash:
            raise ValueError(f"job config hash mismatch before repair: {batch_id}")
        if payload.get("p2_config_hash") != old_cfg_hash:
            raise ValueError(f"artifact config hash mismatch before repair: {batch_id}")

        # Rewrite canonical artifact metadata only; trajectory arrays remain
        # byte-identical in logical value.
        payload["p2_protocol_version"] = NEW_VERSION
        payload["p2_config_hash"] = new_cfg_hash
        new_art_sha = write_traj_artifact(art_path, payload)

        # Update all dependent JSON bindings.
        result["p2_protocol"] = dict(protocol)
        result["p2_protocol_version"] = NEW_VERSION
        result["p2_config_hash"] = new_cfg_hash

        if isinstance(result.get("trajectory_artifact"), dict):
            result["trajectory_artifact"]["sha256"] = new_art_sha

        prov = result.get("provenance") or {}
        if prov.get("trajectory_sha256") != old_art_sha:
            raise ValueError(
                f"provenance trajectory hash mismatch before repair: {batch_id}"
            )
        prov["trajectory_sha256"] = new_art_sha
        result["provenance"] = prov

        events = result.get("evidence_events") or []
        if len(events) != 1:
            raise ValueError(f"unexpected evidence event count: {batch_id}")
        event = events[0]
        if event.get("artifact_hash") != old_art_sha:
            raise ValueError(f"evidence artifact hash mismatch: {batch_id}")
        event["artifact_hash"] = new_art_sha
        conditions = event.get("conditions") or {}
        conditions["p2_protocol_version"] = NEW_VERSION
        conditions["p2_config_hash"] = new_cfg_hash
        event["conditions"] = conditions
        result["evidence_events"] = events

        job["p2_protocol"] = dict(protocol)
        job["p2_config_hash"] = new_cfg_hash

        repairs = rec.setdefault("provenance_repairs", [])
        if not isinstance(repairs, list):
            raise ValueError(f"malformed provenance_repairs: {batch_id}")
        repairs.append({
            "repair_id": REPAIR_ID,
            "old_protocol_version": OLD_VERSION,
            "new_protocol_version": NEW_VERSION,
            "old_p2_config_hash": old_cfg_hash,
            "new_p2_config_hash": new_cfg_hash,
            "old_trajectory_sha256": old_art_sha,
            "new_trajectory_sha256": new_art_sha,
            "scientific_trajectory_changed": False,
            "scientific_verdict_changed": False,
            "reason": (
                "runtime used explicit FixCom-v2 implementation while config "
                "overrode the provenance label with the stale v1 version"
            ),
        })

        rec["job"] = job
        rec["result"] = result
        write_json_atomic(result_path, rec)

        # Post-write fail-closed verification of the new canonical binding.
        verify_traj_artifact(art_path, new_art_sha)
        repaired.append(batch_id)

    return {
        "repair_id": REPAIR_ID,
        "n_results": len(repaired) + len(unchanged),
        "n_repaired": len(repaired),
        "n_unchanged": len(unchanged),
        "new_p2_config_hash": new_cfg_hash,
        "repaired_batch_ids": repaired,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--p2-dir", required=True)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()

    report = repair_p2_fixcom_provenance(
        args.p2_dir, args.repo_root, args.config
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
