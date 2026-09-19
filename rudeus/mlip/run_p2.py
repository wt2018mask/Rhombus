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

from rudeus.mlip.gitpush import (
    GitSafetyError,
    p2_worker_branch,
    persist_p2_results,
    push_branch,
)
from rudeus.mlip.gpu_diagnostic import resolve_device
from rudeus.mlip.p2 import (
    P2_PROTOCOL_DEFAULTS,
    effective_production_tiers,
    load_authorization_manifest,
    run_p2_batches,
)
from rudeus.mlip.relax import (
    default_model_path,
    ensure_checkpoint,
    load_calculator,
)


def resolve_push_branch(push_to: str, worker: str, shard: int, of: int) -> str:
    """Resolve --push-to: 'auto' derives worker/p2/<worker>-s<shard>-of<of>."""
    if push_to == "auto":
        return p2_worker_branch(worker, shard, of)
    return push_to


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one P2 shard.")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--p1-done", default="data/batches/done")
    parser.add_argument("--out", default="data/batches/p2")
    parser.add_argument("--traj-out", default="data/batches/p2_traj",
                        help="repository-relative directory for canonical P2 "
                             "trajectory artifacts (data/batches/p2_traj/"
                             "<batch_id>.npz); newly executed P2 results "
                             "are bound to these artifacts")
    parser.add_argument("--shard", type=int, default=0)
    parser.add_argument("--of", type=int, default=1)
    parser.add_argument("--device", default="auto",
                        help="auto|cpu|cuda (auto = cuda if available)")
    parser.add_argument("--worker", default="worker")
    parser.add_argument(
        "--batch-id",
        default="",
        help="production target: process exactly this batch ID; "
             "when omitted, run the selected shard",
    )
    parser.add_argument("--retry-errors", action="store_true",
                        help="recompute batches with ERROR records (default: skip)")
    parser.add_argument("--equil-steps", type=int, default=0,
                        help="override protocol equil_steps (0 = config default)")
    parser.add_argument("--prod-steps", type=int, default=0,
                        help="override the adaptive final-tier production limit "
                             "(0 = config default 8000); earlier tiers below "
                             "the limit still apply, a limit below the first "
                             "tier collapses to one final evaluation")
    parser.add_argument("--sample-interval", type=int, default=0,
                        help="override protocol sample_interval_steps (0 = default)")
    parser.add_argument("--git-commit", action="store_true",
                        help="commit ONLY p2 outputs after the run (aborts if "
                             "unrelated files are staged)")
    parser.add_argument("--push-to", default="",
                        help="push HEAD to this worker branch (never main; "
                             "'auto' derives worker/p2/<worker>-s<shard>-of<of>); "
                             "auth comes from the environment (Kaggle "
                             "GITHUB_PAT secret)")
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
    parser.add_argument("--p2-stall-diagnostic", action="store_true",
                        help="run a bounded, instrumented single-candidate MD "
                             "diagnostic instead of the campaign (no P2 verdicts, "
                             "no production writes)")
    parser.add_argument("--p2-production-diagnostic", action="store_true",
                        help="run a bounded single-candidate diagnostic through "
                             "the exact production run_nvt path with "
                             "high-resolution loop timing (no P2 verdicts, "
                             "no production writes)")
    parser.add_argument("--p2-force-benchmark", action="store_true",
                        help="run a bounded force-only MACE benchmark on one "
                             "candidate (no MD, no P2 verdicts, "
                             "no production writes)")
    parser.add_argument("--p2-state-diagnostic", action="store_true",
                        help="run a bounded single-candidate diagnostic through "
                             "the production run_nvt path with CUDA-synced "
                             "force timing, per-window stats and GPU "
                             "telemetry (no P2 verdicts, no production "
                             "writes)")
    parser.add_argument("--p2-stall-profile", action="store_true",
                        help="run the exact production-path MD setup for one "
                             "candidate (full equil + 1000 production steps, "
                             "one trajectory) and print a 100-step checkpoint "
                             "table of wall/force timing plus physical state "
                             "(diagnostic only: no P2 verdicts, no files, "
                             "no commits)")
    parser.add_argument("--n-warmup", type=int, default=10,
                        help="warmup evaluations for --p2-force-benchmark "
                             "(excluded from statistics)")
    parser.add_argument("--n-evals", type=int, default=300,
                        help="timed force evaluations for --p2-force-benchmark")
    parser.add_argument("--probe-window", type=int, default=100,
                        help="window size in steps/evals for per-window "
                             "timing statistics")
    parser.add_argument("--max-steps", type=int, default=1200,
                        help="total MD steps for --p2-stall-diagnostic "
                             "(equil first, then production)")
    parser.add_argument("--heartbeat-steps", type=int, default=100,
                        help="heartbeat cadence in MD steps")
    parser.add_argument("--stall-timeout-s", type=float, default=300.0,
                        help="single-step wall-time threshold marking "
                             "STALL_SUSPECTED (diagnostic only)")
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
    print(f"p2 trajectory: equil={protocol['equil_steps']} "
          f"tiers={effective_production_tiers(protocol)} "
          f"policy={protocol.get('trajectory_policy')} "
          f"version={protocol.get('p2_protocol_version')}")

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

    if args.p2_stall_diagnostic:
        from rudeus.mlip.gpu_diagnostic import resolve_diagnostic_candidate
        from rudeus.mlip.p2 import p2_job_seed
        from rudeus.mlip.stall_diagnostic import run_stall_diagnostic
        if not args.batch_id:
            print("STOP: --p2-stall-diagnostic requires --batch-id <id>")
            raise SystemExit(2)
        try:
            candidate = resolve_diagnostic_candidate(
                args.p1_done, args.batch_id)
        except (FileNotFoundError, ValueError) as e:
            print(f"STOP: {e}")
            raise SystemExit(2)
        model_path = ensure_checkpoint(mcfg["checkpoint_url"],
                                       default_model_path(),
                                       mcfg["checkpoint_sha256"])
        calc = load_calculator(model_path, device=device,
                               dtype=cfg.get("p2", {}).get("dtype", "float32"))
        seed = p2_job_seed(int(protocol.get("base_seed", 550)), args.batch_id)
        record = run_stall_diagnostic(
            candidate=candidate, calc=calc, protocol=protocol, seed=seed,
            max_steps=args.max_steps, heartbeat_steps=args.heartbeat_steps,
            stall_timeout_s=args.stall_timeout_s,
            worker_info={"session": args.worker, "device": device},
            device_info={"requested": args.device, "resolved": device})
        import json as _json2
        print(_json2.dumps({"outcome": record["outcome"],
                            "termination": record["termination"],
                            "record": record["record_file"]}, indent=1))
        return

    if args.p2_production_diagnostic:
        from rudeus.mlip.gpu_diagnostic import resolve_diagnostic_candidate
        from rudeus.mlip.p2 import p2_job_seed
        from rudeus.mlip.production_diagnostic import (
            run_production_diagnostic,
        )
        if not args.batch_id:
            print("STOP: --p2-production-diagnostic requires --batch-id <id>")
            raise SystemExit(2)
        try:
            candidate = resolve_diagnostic_candidate(
                args.p1_done, args.batch_id)
        except (FileNotFoundError, ValueError) as e:
            print(f"STOP: {e}")
            raise SystemExit(2)
        # Identical checkpoint verification + calculator construction as
        # the production path below (same checkpoint, dtype, device).
        model_path = ensure_checkpoint(mcfg["checkpoint_url"],
                                       default_model_path(),
                                       mcfg["checkpoint_sha256"])
        calc = load_calculator(model_path, device=device,
                               dtype=cfg.get("p2", {}).get("dtype", "float32"))
        seed = p2_job_seed(int(protocol.get("base_seed", 550)), args.batch_id)
        payload = run_production_diagnostic(
            candidate=candidate, calc=calc, protocol=protocol, seed=seed,
            checkpoint_id=mcfg["primary_checkpoint"],
            checkpoint_sha256=mcfg["checkpoint_sha256"],
            max_steps=args.max_steps, heartbeat_steps=args.heartbeat_steps,
            worker_info={"session": args.worker, "device": device},
            device_info={"requested": args.device, "resolved": device})
        import json as _json3
        print(_json3.dumps(
            {"termination_reason": payload["termination_reason"],
             "termination": payload["termination"],
             "timing_breakdown": payload["timing_breakdown"],
             "record": payload["record_file"]}, indent=1, default=str))
        return

    if args.p2_force_benchmark:
        from rudeus.mlip.cuda_force_diagnostic import run_force_benchmark
        from rudeus.mlip.gpu_diagnostic import resolve_diagnostic_candidate
        if not args.batch_id:
            print("STOP: --p2-force-benchmark requires --batch-id <id>")
            raise SystemExit(2)
        try:
            candidate = resolve_diagnostic_candidate(
                args.p1_done, args.batch_id)
        except (FileNotFoundError, ValueError) as e:
            print(f"STOP: {e}")
            raise SystemExit(2)
        # Identical checkpoint verification + calculator construction as
        # the production path below (same checkpoint, dtype, device).
        model_path = ensure_checkpoint(mcfg["checkpoint_url"],
                                       default_model_path(),
                                       mcfg["checkpoint_sha256"])
        calc = load_calculator(model_path, device=device,
                               dtype=cfg.get("p2", {}).get("dtype", "float32"))
        payload = run_force_benchmark(
            candidate=candidate, calc=calc, device=device,
            n_warmup=args.n_warmup, n_evals=args.n_evals,
            window=args.probe_window,
            checkpoint_id=mcfg["primary_checkpoint"],
            checkpoint_sha256=mcfg["checkpoint_sha256"],
            worker_info={"session": args.worker, "device": device})
        import json as _json4
        print(_json4.dumps(
            {"force_summary": payload["force_summary"],
             "first_window_median_s": payload["first_window_median_s"],
             "middle_window_median_s": payload["middle_window_median_s"],
             "last_window_median_s": payload["last_window_median_s"],
             "telemetry_summary": payload["telemetry_summary"],
             "record": payload["record_file"]}, indent=1, default=str))
        return

    if args.p2_state_diagnostic:
        from rudeus.mlip.cuda_force_diagnostic import run_state_diagnostic
        from rudeus.mlip.gpu_diagnostic import resolve_diagnostic_candidate
        from rudeus.mlip.p2 import p2_job_seed
        if not args.batch_id:
            print("STOP: --p2-state-diagnostic requires --batch-id <id>")
            raise SystemExit(2)
        try:
            candidate = resolve_diagnostic_candidate(
                args.p1_done, args.batch_id)
        except (FileNotFoundError, ValueError) as e:
            print(f"STOP: {e}")
            raise SystemExit(2)
        # Identical checkpoint verification + calculator construction as
        # the production path below (same checkpoint, dtype, device).
        model_path = ensure_checkpoint(mcfg["checkpoint_url"],
                                       default_model_path(),
                                       mcfg["checkpoint_sha256"])
        calc = load_calculator(model_path, device=device,
                               dtype=cfg.get("p2", {}).get("dtype", "float32"))
        seed = p2_job_seed(int(protocol.get("base_seed", 550)), args.batch_id)
        payload = run_state_diagnostic(
            candidate=candidate, calc=calc, protocol=protocol, seed=seed,
            device=device,
            checkpoint_id=mcfg["primary_checkpoint"],
            checkpoint_sha256=mcfg["checkpoint_sha256"],
            max_steps=args.max_steps, heartbeat_steps=args.heartbeat_steps,
            window=args.probe_window,
            worker_info={"session": args.worker, "device": device},
            device_info={"requested": args.device, "resolved": device})
        import json as _json5
        print(_json5.dumps(
            {"outcome": payload["outcome"],
             "termination": payload["termination"],
             "force_summary": payload["force_summary"],
             "first_window_median_s": payload["first_window_median_s"],
             "middle_window_median_s": payload["middle_window_median_s"],
             "last_window_median_s": payload["last_window_median_s"],
             "telemetry_summary": payload["telemetry_summary"],
             "record": payload["record_file"]}, indent=1, default=str))
        return

    if args.p2_stall_profile:
        from rudeus.mlip.gpu_diagnostic import resolve_diagnostic_candidate
        from rudeus.mlip.p2 import p2_job_seed
        from rudeus.mlip.stall_profile_diagnostic import (
            run_stall_profile_diagnostic,
        )
        if not args.batch_id:
            print("STOP: --p2-stall-profile requires --batch-id <id>")
            raise SystemExit(2)
        try:
            candidate = resolve_diagnostic_candidate(
                args.p1_done, args.batch_id)
        except (FileNotFoundError, ValueError) as e:
            print(f"STOP: {e}")
            raise SystemExit(2)
        if str(device).startswith("cuda"):
            try:
                import torch as _torch_cuda

                _cuda_ok = bool(_torch_cuda.cuda.is_available())
            except Exception:
                _cuda_ok = False
            if not _cuda_ok:
                print("STOP: --p2-stall-profile requested CUDA but no CUDA "
                      "device is available; refusing to substitute CPU")
                raise SystemExit(2)
        # Identical checkpoint verification + calculator construction as
        # the production path below (same checkpoint, dtype, device).
        model_path = ensure_checkpoint(mcfg["checkpoint_url"],
                                       default_model_path(),
                                       mcfg["checkpoint_sha256"])
        calc = load_calculator(model_path, device=device,
                               dtype=cfg.get("p2", {}).get("dtype", "float32"))
        seed = p2_job_seed(int(protocol.get("base_seed", 550)), args.batch_id)
        # Table prints inside; no files, no production writes, no commits.
        run_stall_profile_diagnostic(
            candidate=candidate, calc=calc, protocol=protocol, seed=seed,
            checkpoint_id=mcfg["primary_checkpoint"],
            checkpoint_sha256=mcfg["checkpoint_sha256"],
            device=device, dtype=cfg.get("p2", {}).get("dtype", "float32"),
            worker_info={"session": args.worker, "device": device},
            device_info={"requested": args.device, "resolved": device})
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
                               {"session": args.worker, "device": device},
                               traj_dir=args.traj_out)

    target_batch_id = args.batch_id.strip() or None

    if target_batch_id is not None:
        print(f"single-candidate production mode: {target_batch_id}",
              flush=True)

        if target_batch_id not in allowlist:
            print(
                f"STOP: batch {target_batch_id} is not present in the "
                f"AUTHORIZED manifest",
                flush=True,
            )
            raise SystemExit(1)

    summary = run_p2_batches(
        args.p1_done,
        args.out,
        args.shard,
        args.of,
        md_runner,
        protocol,
        {"session": args.worker, "device": device},
        retry_errors=args.retry_errors,
        allowlist=allowlist,
        target_batch_id=target_batch_id,
    )
    print(f"p2 shard {args.shard}/{args.of}: {summary}")

    if args.git_commit:
        msg = (f"p2 {args.worker} shard {args.shard}/{args.of}: "
               f"{summary.get('processed', 0)} processed, "
               f"{summary.get('errored', 0)} errored")
        wrote = summary.get("wrote", [])
        if wrote:
            try:
                info = persist_p2_results(".", args.out, wrote, msg,
                                          traj_dir=args.traj_out)
            except GitSafetyError as e:
                print(f"STOP: p2 commit failed ({e}); local results "
                      f"preserved in {args.out}, nothing staged/committed "
                      f"beyond the aborted attempt")
                raise SystemExit(1)
            print(f"committed {len(info['files'])} p2 files as {info['commit']}")
        else:
            # Idempotent rerun (resume skipped everything valid): no new
            # files, hence no commit. Never fall back to committing the
            # whole p2 directory (other workers' results live there).
            print("no new P2 results written by this invocation; "
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
            print(f"STOP: p2 push to {branch} failed ({e}); local results "
                  f"in {args.out} and the local commit are preserved for "
                  f"later retry; do NOT retry with force")
            raise SystemExit(1)
        print(f"pushed to {pushed['remote']}/{pushed['branch']}")


if __name__ == "__main__":
    main()
