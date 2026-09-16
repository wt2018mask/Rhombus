"""P2.5 transport-evidence worker: verified P2 artifacts -> F3 verdicts.

Usage (CPU-only; P2.5 is numpy analysis, no MLIP needed):
    python -m rudeus.mlip.run_p25 --p2-dir data/batches/p2 \\
        --out data/batches/p25 --shard 0 --of 1 --worker local

Reads bound P2 PASS results (p2_verdict PASS + trajectory_artifact
binding), verifies each artifact, canonically unwraps, runs the existing
F3 mobile-ion analysis with block-bootstrap uncertainty, writes atomic
data/batches/p25/<batch_id>.json. P2.5 sets transport_state only --
never existence, never dynamic stability, never conductivity claims.
"""

from __future__ import annotations

import argparse

from rudeus.mlip.gitpush import (
    GitSafetyError,
    p25_worker_branch,
    persist_p25_results,
    push_branch,
)
from rudeus.mlip.p25 import P25_DEFAULTS, p25_config_hash, run_p25_batches


def resolve_push_branch(push_to: str, worker: str, shard: int, of: int) -> str:
    """Resolve --push-to: 'auto' derives worker/p25/<worker>-s<shard>-of<of>."""
    if push_to == "auto":
        return p25_worker_branch(worker, shard, of)
    return push_to


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one P2.5 shard.")
    parser.add_argument("--p2-dir", default="data/batches/p2",
                        help="directory of bound P2 result JSON files")
    parser.add_argument("--out", default="data/batches/p25",
                        help="output directory for P2.5 result JSON files")
    parser.add_argument("--shard", type=int, default=0)
    parser.add_argument("--of", type=int, default=1)
    parser.add_argument("--worker", default="worker")
    parser.add_argument("--retry-errors", action="store_true",
                        help="recompute batches with ERROR records (default: skip)")
    parser.add_argument("--target-species", default="Li",
                        help="mobile-ion species for explicit sublattice "
                             "extraction (default: Li; never inferred)")
    parser.add_argument("--n-bootstrap", type=int, default=200,
                        help="block-bootstrap replicates for slope/alpha2 "
                             "uncertainty (default: 200)")
    parser.add_argument("--block-origins", type=int, default=20,
                        help="time origins per bootstrap block (default: 20; "
                             "provisional methodological parameter)")
    parser.add_argument("--ci-level", type=float, default=0.68,
                        help="bootstrap confidence level (default: 0.68)")
    parser.add_argument("--git-commit", action="store_true",
                        help="commit ONLY p25 outputs after the run (aborts if "
                             "unrelated files are staged)")
    parser.add_argument("--push-to", default="",
                        help="push HEAD to this worker branch (never main; "
                             "'auto' derives worker/p25/<worker>-s<shard>-of<of>)")
    args = parser.parse_args()

    config = dict(P25_DEFAULTS)
    config["target_species"] = args.target_species
    config["n_bootstrap"] = args.n_bootstrap
    config["block_origins"] = args.block_origins
    config["ci_level"] = args.ci_level
    print(f"p25 config: {config} (hash {p25_config_hash(config)})")

    summary = run_p25_batches(args.p2_dir, args.out, args.shard, args.of,
                              config,
                              {"session": args.worker},
                              retry_errors=args.retry_errors)
    print(f"p25 shard {args.shard}/{args.of}: {summary}")

    if args.git_commit:
        msg = (f"p25 {args.worker} shard {args.shard}/{args.of}: "
               f"{summary.get('processed', 0)} processed, "
               f"{summary.get('errored', 0)} errored")
        wrote = summary.get("wrote", [])
        if wrote:
            try:
                info = persist_p25_results(".", args.out, wrote, msg)
            except GitSafetyError as e:
                print(f"STOP: p25 commit failed ({e}); local results "
                      f"preserved in {args.out}, nothing staged/committed "
                      f"beyond the aborted attempt")
                raise SystemExit(1)
            print(f"committed {len(info['files'])} p25 files as {info['commit']}")
        else:
            # Idempotent rerun (resume skipped everything valid): no new
            # files, hence no commit. Never fall back to committing the
            # whole p25 directory (other workers' results live there).
            print("no new P2.5 results written by this invocation; "
                  "nothing to commit")
    if args.push_to:
        branch = resolve_push_branch(args.push_to, args.worker,
                                     args.shard, args.of)
        # Pushed even when nothing was newly committed: this retries a
        # previously failed push of the existing local commit without any
        # recomputation. A push failure keeps local results AND the local
        # commit; it only reports failure (exit 1), never resets.
        try:
            pushed = push_branch(".", branch)
        except GitSafetyError as e:
            print(f"STOP: p25 push to {branch} failed ({e}); local results "
                  f"in {args.out} and the local commit are preserved for "
                  f"later retry; do NOT retry with force")
            raise SystemExit(1)
        print(f"pushed to {pushed['remote']}/{pushed['branch']}")


if __name__ == "__main__":
    main()
