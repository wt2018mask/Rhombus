"""P2 550 K NVT worker: stability screen over P1 KEEP_FOR_P2 records.

Usage (CPU pilot, short protocol):
    python -m rudeus.mlip.run_p2 --p1-done data/batches/done \\
        --out data/batches/p2 --shard 0 --of 1 --device cpu \\
        --worker local --equil-steps 200 --prod-steps 600

Reads P1 done records (KEEP_FOR_P2 + relaxed structure only), runs the
deterministic NVT protocol, writes atomic data/batches/p2/<batch_id>.json.
P2 sets dynamic_state only — never transport, never diffusion claims.
"""

from __future__ import annotations

import argparse

import yaml

from rudeus.mlip.gitpush import commit_done_files, push_branch
from rudeus.mlip.gpu_diagnostic import resolve_device
from rudeus.mlip.p2 import (
    P2_PROTOCOL_DEFAULTS,
    load_authorization_manifest,
    run_p2_batches,
)
from rudeus.mlip.relax import (
    default_model_path,
    ensure_checkpoint,
    load_calculator,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one P2 shard.")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--p1-done", default="data/batches/done")
    parser.add_argument("--out", default="data/batches/p2")
    parser.add_argument("--shard", type=int, default=0)
    parser.add_argument("--of", type=int, default=1)
    parser.add_argument("--device", default="auto",
                        help="auto|cpu|cuda (auto = cuda if available)")
    parser.add_argument("--worker", default="worker")
    parser.add_argument("--retry-errors", action="store_true",
                        help="recompute batches with ERROR records (default: skip)")
    parser.add_argument("--equil-steps", type=int, default=0,
                        help="override protocol equil_steps (0 = config default)")
    parser.add_argument("--prod-steps", type=int, default=0,
                        help="override protocol production_steps (0 = config default)")
    parser.add_argument("--sample-interval", type=int, default=0,
                        help="override protocol sample_interval_steps (0 = default)")
    parser.add_argument("--git-commit", action="store_true",
                        help="commit ONLY p2 outputs after the run (aborts if "
                             "unrelated files are staged)")
    parser.add_argument("--push-to", default="",
                        help="push HEAD to this worker branch (never main); "
                             "auth comes from the environment")
    parser.add_argument("--authorized-manifest",
                        default="data/batches/audit/p2_production_authorized_44.json",
                        help="execution allowlist: only batch IDs listed with "
                             "verdict AUTHORIZED are processed (fail closed)")
    parser.add_argument("--gpu-diagnostic", action="store_true",
                        help="run the single-candidate GPU execution-path "
                             "diagnostic instead of the campaign (no MD "
                             "campaign, no commits, no manifest changes)")
    parser.add_argument("--batch-id", default="",
                        help="candidate batch ID for --gpu-diagnostic")
    args = parser.parse_args()

    with open(args.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    mcfg = cfg["mlip"]
    protocol = dict(P2_PROTOCOL_DEFAULTS)
    protocol.update(cfg.get("p2", {}))
    if args.equil_steps:
        protocol["equil_steps"] = args.equil_steps
    if args.prod_steps:
        protocol["production_steps"] = args.prod_steps
    if args.sample_interval:
        protocol["sample_interval_steps"] = args.sample_interval

    # Execution allowlist: fail closed BEFORE expensive init. Only batch IDs
    # explicitly listed in an AUTHORIZED manifest may be processed.
    try:
        allowlist = load_authorization_manifest(args.authorized_manifest)
    except ValueError as e:
        print(f"STOP: {e}")
        raise SystemExit(1)
    print(f"authorized candidates: {len(allowlist)} "
          f"({args.authorized_manifest})")

    device = resolve_device(args.device)

    if args.gpu_diagnostic:
        from rudeus.mlip.gpu_diagnostic import (
            resolve_diagnostic_candidate,
            run_diagnostic,
        )
        if not args.batch_id:
            print("STOP: --gpu-diagnostic requires --batch-id <id>")
            raise SystemExit(2)
        candidate = resolve_diagnostic_candidate(args.p1_done, args.batch_id)
        model_path = ensure_checkpoint(mcfg["checkpoint_url"],
                                       default_model_path(),
                                       mcfg["checkpoint_sha256"])
        calc = load_calculator(model_path, device=device,
                               dtype=cfg.get("p2", {}).get("dtype", "float32"))
        import json as _json
        report = run_diagnostic(candidate, calc,
                                {"device": device,
                                 "checkpoint_sha256": mcfg["checkpoint_sha256"]},
                                protocol, seed=7)
        print(_json.dumps(report, indent=1, default=str))
        return

    model_path = ensure_checkpoint(mcfg["checkpoint_url"],
                                   default_model_path(),
                                   mcfg["checkpoint_sha256"])
    print(f"checkpoint verified: {model_path}")
    calc = load_calculator(model_path, device=device,
                           dtype=cfg.get("p2", {}).get("dtype", "float32"))
    print(f"calculator on {device}")
    try:
        import torch as _torch2
        _params = list(calc.models[0].parameters())
        _actual = str(_params[0].device) if _params else "unknown-no-params"
        _mem = ""
        if _actual.startswith("cuda"):
            _mem = f", cuda_mem_GB={_torch2.cuda.memory_allocated() / 1e9:.2f}"
        print(f"calculator actual device: {_actual}{_mem}", flush=True)
    except Exception as _e:
        # Observability only: never fail startup over a device probe.
        print(f"calculator actual device: unverified ({type(_e).__name__})",
              flush=True)
    calc_info = {"checkpoint_name": mcfg["primary_checkpoint"],
                 "mace_version": __import__("mace").__version__,
                 "url": mcfg["checkpoint_url"],
                 "sha256": mcfg["checkpoint_sha256"],
                 "device": device,
                 "dtype": cfg.get("p2", {}).get("dtype", "float32")}
    from rudeus.mlip.validation import collect_backend_versions
    calc_info.update({k: v for k, v in collect_backend_versions().items()
                      if k not in calc_info})
    try:
        import os as _os
        import torch as _torch
        calc_info["torch_num_threads"] = _torch.get_num_threads()
        calc_info["env_threads"] = {
            k: _os.environ.get(k) for k in
            ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS")}
    except Exception:
        pass

    from rudeus.mlip.calibration import make_md_runner
    md_runner = make_md_runner(calc, calc_info,
                               {"session": args.worker, "device": device})

    summary = run_p2_batches(args.p1_done, args.out, args.shard, args.of,
                             md_runner, protocol,
                             {"session": args.worker, "device": device},
                             retry_errors=args.retry_errors,
                             allowlist=allowlist)
    print(f"p2 shard {args.shard}/{args.of}: {summary}")

    if args.git_commit:
        msg = (f"p2 {args.worker} shard {args.shard}/{args.of}: "
               f"{summary.get('processed', 0)} processed, "
               f"{summary.get('errored', 0)} errored")
        info = commit_done_files(".", args.out, msg)
        print(f"committed {len(info['files'])} p2 files as {info['commit']}")
    if args.push_to:
        pushed = push_branch(".", args.push_to)
        print(f"pushed to {pushed['remote']}/{pushed['branch']}")


if __name__ == "__main__":
    main()
