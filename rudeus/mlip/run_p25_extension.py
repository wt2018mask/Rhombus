"""GPU runner for P2.5 transport-evidence extension.

Re-runs only an exactly authorized P2.5-INDETERMINATE cohort from the
original P1 relaxed structures. Uses the same 550 K/FixCom P2 dynamics and
seed, but ignores early PASS decisions so transport evidence can accumulate
to 8000 production steps. Explicit structural FAIL/abort remains terminal.
Outputs live in separate directories and never overwrite frozen P2/P2.5 data.
"""

from __future__ import annotations

import argparse
import yaml

from rudeus.mlip.calibration import make_md_runner
from rudeus.mlip.gpu_diagnostic import resolve_device
from rudeus.mlip.p2 import P2_PROTOCOL_DEFAULTS, run_p2_batches
from rudeus.mlip.p25_extension import load_extension_manifest
from rudeus.mlip.relax import default_model_path, ensure_checkpoint, load_calculator
from rudeus.mlip.validation import collect_backend_versions

EXTENSION_PROTOCOL_VERSION = (
    "p2-transport-extension-v1-fixcom-constraint-provisional"
)
EXTENSION_POLICY = "transport-extension-1000-3000-8000-v1-provisional"


def build_extension_protocol(cfg):
    protocol = dict(P2_PROTOCOL_DEFAULTS)
    protocol.update(cfg.get("p2", {}))
    protocol["p2_protocol_version"] = EXTENSION_PROTOCOL_VERSION
    protocol["trajectory_policy"] = EXTENSION_POLICY
    protocol["production_tier_schedule_provisional"] = [1000, 3000, 8000]
    protocol["production_steps"] = 8000
    protocol["force_full_production_for_transport"] = True
    return protocol


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--p1-done", required=True)
    ap.add_argument("--source-p2", required=True)
    ap.add_argument("--source-p25", required=True)
    ap.add_argument("--authorized-manifest", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--traj-out", required=True)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--worker", required=True)
    args = ap.parse_args()

    with open(args.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    protocol = build_extension_protocol(cfg)

    allowlist = load_extension_manifest(
        args.authorized_manifest,
        args.p1_done,
        args.source_p2,
        args.source_p25,
    )
    print(f"authorized extension candidates: {len(allowlist)}")
    print(
        "extension protocol:",
        protocol["p2_protocol_version"],
        protocol["trajectory_policy"],
        protocol["production_tier_schedule_provisional"],
    )

    device = resolve_device(args.device)
    mcfg = cfg["mlip"]
    model_path = ensure_checkpoint(
        mcfg["checkpoint_url"],
        default_model_path(),
        mcfg["checkpoint_sha256"],
    )
    print(f"checkpoint verified: {model_path}")
    calc = load_calculator(
        model_path,
        device=device,
        dtype=cfg.get("p2", {}).get("dtype", "float32"),
    )
    print(f"calculator on {device}")

    calc_info = {
        "checkpoint_name": mcfg["primary_checkpoint"],
        "mace_version": __import__("mace").__version__,
        "url": mcfg["checkpoint_url"],
        "sha256": mcfg["checkpoint_sha256"],
        "device": device,
        "dtype": cfg.get("p2", {}).get("dtype", "float32"),
    }
    calc_info.update({
        k: v for k, v in collect_backend_versions().items()
        if k not in calc_info
    })

    md_runner = make_md_runner(
        calc,
        calc_info,
        {"session": args.worker, "device": device},
        traj_dir=args.traj_out,
    )
    summary = run_p2_batches(
        args.p1_done,
        args.out,
        0,
        1,
        md_runner,
        protocol,
        {"session": args.worker, "device": device},
        retry_errors=False,
        allowlist=allowlist,
    )
    print(f"p25 extension shard 0/1: {summary}")


if __name__ == "__main__":
    main()
