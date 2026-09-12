"""P1 GPU/CPU worker: run one shard of pending batches to done files.

Usage (Kaggle, shard 0 of 4, GPU):
    python -m rudeus.mlip.run_p1 --pending data/batches/pending \\
        --done /kaggle/output/done --shard 0 --of 4 --device cuda \\
        --worker kaggle-notebook-1

Resume-safe: batches with a done file are skipped; missing ones re-run.
"""

from __future__ import annotations

import argparse

import yaml

from rudeus.mlip.relax import (
    default_model_path,
    ensure_checkpoint,
    load_calculator,
    relax_structure,
)
from rudeus.mlip.sharding import run_batches


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one P1 shard.")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--pending", default="data/batches/pending")
    parser.add_argument("--done", required=True)
    parser.add_argument("--shard", type=int, default=0)
    parser.add_argument("--of", type=int, default=1)
    parser.add_argument("--device", default="auto",
                        help="auto|cpu|cuda (auto = cuda if available)")
    parser.add_argument("--worker", default="worker")
    args = parser.parse_args()

    with open(args.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    mcfg = cfg["mlip"]

    device = args.device
    if device == "auto":
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            device = "cpu"

    model_path = ensure_checkpoint(mcfg["checkpoint_url"],
                                   default_model_path(),
                                   mcfg["checkpoint_sha256"])
    print(f"checkpoint verified: {model_path}")
    calc = load_calculator(model_path, device=device, dtype=mcfg["precision"])
    print(f"calculator on {device} ({mcfg['precision']})")
    ckpt_block = {"name": mcfg["primary_checkpoint"],
                  "mace_version": __import__("mace").__version__,
                  "url": mcfg["checkpoint_url"],
                  "sha256": mcfg["checkpoint_sha256"]}

    def relax_fn(structure_dict):
        result = relax_structure(
            structure_dict, calc,
            force_tol_ev_A=mcfg["force_tol_ev_A"],
            max_steps=mcfg["max_relax_steps"],
            mace_precision=mcfg["precision"],
            worker_info={"session": args.worker, "device": device},
        )
        result["mlip_checkpoint"] = ckpt_block
        return result

    summary = run_batches(args.pending, args.done, args.shard, args.of,
                          relax_fn, {"session": args.worker, "device": device})
    print(f"shard {args.shard}/{args.of}: {summary}")


if __name__ == "__main__":
    main()
