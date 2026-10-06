#!/usr/bin/env python3
"""Run the authorized B5 DEV P1 pending batches with the pinned MACE checkpoint."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from rudeus.mlip.relax import ensure_checkpoint, load_calculator, relax_structure
from rudeus.science.known_material_b5_p1_batch_materialization import B5P1PendingBatch
from rudeus.science.known_material_b5_p1_real_runner import (
    execute_b5_p1_batches,
    validate_uniform_p1_protocol,
)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pending-json", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--device", default="cuda")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = json.loads(Path(args.pending_json).read_text(encoding="utf-8"))
    batches = tuple(B5P1PendingBatch.from_dict(item) for item in payload["batches"])
    protocol = validate_uniform_p1_protocol(batches)

    model_path = ensure_checkpoint(
        protocol["checkpoint_url"],
        Path.home() / ".cache" / "rudeus" / "mace-mpa-0-medium.model",
        protocol["checkpoint_sha256"],
    )
    calc = load_calculator(
        model_path,
        device=args.device,
        dtype=protocol["precision"],
    )

    def run_one(structure_dict):
        return relax_structure(
            structure_dict,
            calc,
            force_tol_ev_A=float(protocol["force_tol_ev_A"]),
            max_steps=int(protocol["max_relax_steps"]),
            mace_precision=str(protocol["precision"]),
            worker_info={"stage": "B5_DEV_P1", "device": args.device},
        )

    result = execute_b5_p1_batches(
        batches,
        relax_fn=run_one,
        work_root=Path(args.out_dir),
        worker_info={"stage": "B5_DEV_P1", "device": args.device},
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
