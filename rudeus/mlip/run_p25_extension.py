"""Canonical GPU runner for the P2.5 evidence-sufficiency transition.

This is a pipeline transition, not a hand-picked candidate rescue.  The
authorization manifest is re-derived from frozen P1/P2/P2.5 sources before
calculator initialization.  The exact transition protocol is code-versioned
and embedded in the manifest.  Existing P2/P2.5 records are never overwritten.
"""

from __future__ import annotations

import argparse
import yaml

from rudeus.mlip.calibration import make_md_runner
from rudeus.mlip.gpu_diagnostic import resolve_device
from rudeus.mlip.p2 import run_p2_batches
from rudeus.mlip.p25_extension import (
    build_extension_protocol,
    validated_manifest,
)
from rudeus.mlip.p25_transition_environment import (
    validate_transition_environment,
)
from rudeus.mlip.relax import default_model_path, ensure_checkpoint, load_calculator
from rudeus.mlip.validation import collect_backend_versions


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--p1-done", required=True)
    ap.add_argument("--source-p2", required=True)
    ap.add_argument("--source-p25", required=True)
    ap.add_argument("--authorized-manifest", required=True)
    ap.add_argument("--environment-manifest", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--traj-out", required=True)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--worker", required=True)
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--of", type=int, default=1)
    args = ap.parse_args()

    if args.of < 1 or not (0 <= args.shard < args.of):
        raise SystemExit("STOP: require 0 <= --shard < --of and --of >= 1")

    # Admission + source binding is validated before any checkpoint download or
    # calculator initialization (fail closed, cheap first).
    manifest = validated_manifest(
        args.authorized_manifest,
        args.p1_done,
        args.source_p2,
        args.source_p25,
    )
    environment = validate_transition_environment(args.environment_manifest)
    allowlist = {r["batch_id"] for r in manifest["candidates"]}
    protocol = build_extension_protocol()

    with open(args.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    mcfg = cfg["mlip"]

    source_checkpoint_shas = {
        r["source_p2_checkpoint_sha256"] for r in manifest["candidates"]
    }
    if len(source_checkpoint_shas) != 1:
        raise SystemExit(
            "STOP: canonical transition source cohort uses multiple P2 "
            "checkpoint hashes"
        )
    expected_checkpoint_sha = next(iter(source_checkpoint_shas))
    if mcfg["checkpoint_sha256"] != expected_checkpoint_sha:
        raise SystemExit(
            "STOP: config checkpoint SHA differs from the checkpoint bound "
            "to the source P2 cohort"
        )

    source_dtypes = {r["source_p2_calc_dtype"] for r in manifest["candidates"]}
    if len(source_dtypes) != 1:
        raise SystemExit(
            "STOP: canonical transition source cohort uses multiple calculator dtypes"
        )
    expected_dtype = next(iter(source_dtypes))
    runtime_dtype = cfg.get("p2", {}).get("dtype", "float32")
    if runtime_dtype != expected_dtype:
        raise SystemExit(
            "STOP: config calculator dtype differs from the dtype bound "
            "to the source P2 cohort"
        )

    print(f"canonical transition candidates: {len(allowlist)}")
    print(f"cohort identity: {manifest['cohort_identity']}")
    print(f"transition version: {manifest['transition_version']}")
    print(f"admission policy: {manifest['admission_policy']}")
    print(f"protocol hash: {manifest['transition_protocol_hash']}")
    print(f"checkpoint sha256: {expected_checkpoint_sha}")
    print(f"calculator dtype: {expected_dtype}")
    print(
        "execution environment:",
        environment["python"],
        environment["torch"],
        environment["mace"],
        environment["ase"],
        environment["gpu_model"],
    )

    device = resolve_device(args.device)
    model_path = ensure_checkpoint(
        mcfg["checkpoint_url"],
        default_model_path(),
        expected_checkpoint_sha,
    )
    print(f"checkpoint verified: {model_path}")
    calc = load_calculator(
        model_path,
        device=device,
        dtype=expected_dtype,
    )
    print(f"calculator on {device}")

    calc_info = {
        "checkpoint_name": mcfg["primary_checkpoint"],
        "mace_version": __import__("mace").__version__,
        "url": mcfg["checkpoint_url"],
        "sha256": expected_checkpoint_sha,
        "device": device,
        "dtype": expected_dtype,
        "p25_transition_version": manifest["transition_version"],
        "p25_transition_cohort_identity": manifest["cohort_identity"],
        "p25_transition_protocol_hash": manifest["transition_protocol_hash"],
    }
    calc_info.update({
        k: v for k, v in collect_backend_versions().items()
        if k not in calc_info
    })

    md_runner_base = make_md_runner(
        calc,
        calc_info,
        {"session": args.worker, "device": device},
        traj_dir=args.traj_out,
    )

    rows = {r["batch_id"]: r for r in manifest["candidates"]}

    def md_runner(job):
        result = md_runner_base(job)
        row = rows[job["batch_id"]]
        result["p25_evidence_transition"] = {
            "transition_version": manifest["transition_version"],
            "admission_policy": manifest["admission_policy"],
            "admission_basis": row["admission_basis"],
            "source_p2_trajectory_sha256":
                row["source_p2_trajectory_sha256"],
            "source_p25_config_hash": row["source_p25_config_hash"],
            "cohort_identity": manifest["cohort_identity"],
            "transition_protocol_hash": manifest["transition_protocol_hash"],
            "one_shot": True,
        }
        return result

    summary = run_p2_batches(
        args.p1_done,
        args.out,
        args.shard,
        args.of,
        md_runner,
        protocol,
        {"session": args.worker, "device": device},
        retry_errors=False,
        allowlist=allowlist,
    )
    print(
        f"canonical p25 evidence transition shard "
        f"{args.shard}/{args.of}: {summary}"
    )


if __name__ == "__main__":
    main()
