"""Repair P1 result input-hash provenance without changing scientific results.

This utility is intentionally narrow. It verifies that each done record still
contains the exact frozen pending input (batch_id, declared structure hash, and
canonical structure_dict hash). Only then may it replace a divergent
result.input_structure_sha256 with the frozen batch hash. The previous value is
retained in an explicit provenance repair record.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rudeus.mlip.sharding import structure_dict_sha256, write_json_atomic


REPAIR_ID = "p1-result-input-hash-from-frozen-batch-v1"


def repair_done_input_hashes(
    pending_dir: str | Path,
    done_dir: str | Path,
) -> dict:
    pending_dir = Path(pending_dir)
    done_dir = Path(done_dir)

    pending_files = {p.stem: p for p in pending_dir.glob("*.json")}
    done_files = {p.stem: p for p in done_dir.glob("*.json")}
    if set(pending_files) != set(done_files):
        raise ValueError("pending/done batch sets do not exactly match")

    repaired = []
    unchanged = []

    for batch_id in sorted(pending_files):
        pending = json.loads(pending_files[batch_id].read_text(encoding="utf-8"))
        done = json.loads(done_files[batch_id].read_text(encoding="utf-8"))

        if pending.get("batch_id") != batch_id or done.get("batch_id") != batch_id:
            raise ValueError(f"batch_id mismatch: {batch_id}")

        frozen_sha = str(pending.get("structure_sha256", ""))
        if not frozen_sha:
            raise ValueError(f"pending missing structure_sha256: {batch_id}")
        if str(done.get("structure_sha256", "")) != frozen_sha:
            raise ValueError(f"done top-level structure_sha256 mismatch: {batch_id}")

        pending_struct = pending.get("structure_dict")
        done_struct = done.get("structure_dict")
        if not isinstance(pending_struct, dict) or not isinstance(done_struct, dict):
            raise ValueError(f"missing structure_dict: {batch_id}")
        if structure_dict_sha256(pending_struct) != frozen_sha:
            raise ValueError(f"pending structure hash mismatch: {batch_id}")
        if structure_dict_sha256(done_struct) != frozen_sha:
            raise ValueError(f"done structure hash mismatch: {batch_id}")
        if pending_struct != done_struct:
            raise ValueError(f"pending/done structure_dict differs: {batch_id}")

        result = done.get("result")
        if not isinstance(result, dict):
            raise ValueError(f"done missing result: {batch_id}")
        old = result.get("input_structure_sha256")
        if old == frozen_sha:
            unchanged.append(batch_id)
            continue

        repairs = done.setdefault("provenance_repairs", [])
        if not isinstance(repairs, list):
            raise ValueError(f"malformed provenance_repairs: {batch_id}")
        repairs.append({
            "repair_id": REPAIR_ID,
            "field": "result.input_structure_sha256",
            "old_value": old,
            "new_value": frozen_sha,
            "reason": (
                "runtime Structure serialization hash diverged from the exact "
                "frozen batch input hash; scientific result fields unchanged"
            ),
        })
        result["input_structure_sha256"] = frozen_sha
        done["result"] = result
        write_json_atomic(done_files[batch_id], done)
        repaired.append(batch_id)

    return {
        "repair_id": REPAIR_ID,
        "n_batches": len(pending_files),
        "n_repaired": len(repaired),
        "n_unchanged": len(unchanged),
        "repaired_batch_ids": repaired,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Repair P1 frozen-input hash provenance.")
    parser.add_argument("--pending", required=True)
    parser.add_argument("--done", required=True)
    args = parser.parse_args()

    report = repair_done_input_hashes(args.pending, args.done)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
