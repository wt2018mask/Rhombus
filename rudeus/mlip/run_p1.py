"""P1 GPU/CPU worker: run one shard of pending batches to done files.

Usage (Kaggle, shard 0 of 4, GPU):
    python -m rudeus.mlip.run_p1 --pending data/batches/pending \\
        --done /kaggle/output/done --shard 0 --of 4 --device cuda \\
        --worker kaggle-notebook-1

Resume-safe: batches with a done file are skipped; missing ones re-run.
Post-relaxation, each relaxed result is annotated with parent-collapse
novelty (existing StructureMatcher machinery). Optional --git-commit /
--push-to commit ONLY done files to a dedicated worker branch (never main).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from rudeus.mlip.analysis import annotate_post_relax_novelty
from rudeus.mlip.gitpush import commit_done_files, push_branch
from rudeus.mlip.relax import (
    default_model_path,
    ensure_checkpoint,
    load_calculator,
    relax_structure,
)
from rudeus.mlip.sharding import (
    assign_shard,
    run_batches,
    write_json_atomic,
)


def resolve_parent_dict(parent_id: str, obelix_repo=None):
    """Load a parent structure dict for collapse comparison, or None."""
    if obelix_repo is None or not str(parent_id).startswith("obelix:"):
        return None
    try:
        from rudeus.empirical.obelix import OBELiXDataset
        ds = OBELiXDataset(obelix_repo)
        struct = ds.get_structure(str(parent_id).split(":", 1)[1])
        return struct.as_dict() if struct is not None else None
    except Exception:
        return None


def annotate_shard_collapse(done_dir, shard_index, n_shards, obelix_repo=None):
    """Tag post_relax_novelty on this shard's done files (atomic rewrites).

    Siblings accumulate in sorted batch_id order (including pre-existing done
    files), so the annotation is deterministic across resumes.
    """
    from pymatgen.analysis.structure_matcher import StructureMatcher

    done_dir = Path(done_dir)
    matcher = StructureMatcher()
    siblings = []
    annotated = 0
    for done_file in sorted(done_dir.glob("*.json")):
        if not assign_shard(done_file.stem, shard_index, n_shards):
            continue
        with open(done_file, encoding="utf-8") as f:
            payload = json.load(f)
        result = payload.get("result") or {}
        relaxed = result.get("relaxed_structure_dict")
        parent = resolve_parent_dict(payload.get("parent_id", ""), obelix_repo)
        tag = annotate_post_relax_novelty(relaxed, parent, siblings, matcher)
        if result.get("post_relax_novelty") != tag:
            result["post_relax_novelty"] = tag
            payload["result"] = result
            write_json_atomic(done_file, payload)
            annotated += 1
        if relaxed is not None:
            siblings.append((payload.get("batch_id", done_file.stem), relaxed))
    return {"annotated": annotated, "siblings_seen": len(siblings)}


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
    parser.add_argument("--parent-source", default="none",
                        help="none|obelix: where to resolve parent structures "
                             "for post-relax collapse comparison")
    parser.add_argument("--obelix-repo", default="",
                        help="OBELiX repo path (defaults to config datasets.obelix_repo)")
    parser.add_argument("--git-commit", action="store_true",
                        help="commit ONLY done files after the run (aborts if "
                             "unrelated files are staged)")
    parser.add_argument("--push-to", default="",
                        help="push HEAD to this worker branch (never main); "
                             "auth comes from the environment")
    parser.add_argument("--retry-errors", action="store_true",
                        help="recompute batches with ERROR records (default: skip)")
    parser.add_argument("--retry-skipped", action="store_true",
                        help="recompute batches with SKIPPED verdicts, e.g. "
                             "DISORDERED_UNSUPPORTED_FOR_MLIP (default: skip; "
                             "safe: deterministic inputs re-yield the same record)")
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
                          relax_fn, {"session": args.worker, "device": device},
                          retry_errors=args.retry_errors,
                          retry_skipped=args.retry_skipped)
    print(f"shard {args.shard}/{args.of}: {summary}")

    obelix_repo = (args.obelix_repo or cfg.get("datasets", {}).get("obelix_repo", "")
                   ) if args.parent_source == "obelix" else None
    collapse = annotate_shard_collapse(args.done, args.shard, args.of,
                                       obelix_repo=obelix_repo)
    print(f"post-relax collapse annotation: {collapse}")

    if args.git_commit:
        msg = (f"p1 {args.worker} shard {args.shard}/{args.of}: "
               f"{summary.get('processed', 0)} processed, "
               f"{summary.get('errored', 0)} errored")
        info = commit_done_files(".", args.done, msg)
        print(f"committed {len(info['files'])} done files as {info['commit']}")
    if args.push_to:
        pushed = push_branch(".", args.push_to)
        print(f"pushed to {pushed['remote']}/{pushed['branch']}")


if __name__ == "__main__":
    main()
