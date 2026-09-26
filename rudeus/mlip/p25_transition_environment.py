"""Frozen execution-environment contract for canonical P2.5 transition."""

from __future__ import annotations

import importlib.metadata as md
import json
import platform
import sys
from pathlib import Path
from typing import Any, Dict

import numpy as np
import torch
import ase
import mace

from rudeus.mlip.sharding import write_json_atomic

ENV_CONTRACT_VERSION = "p25-transition-execution-environment-v1"

REQUIRED_FIELDS = (
    "python",
    "torch",
    "cuda_runtime",
    "numpy",
    "ase",
    "mace",
    "pymatgen",
    "pymatgen_core",
    "cudnn",
    "gpu_model",
)


def _pkg_version(name: str) -> str:
    try:
        return md.version(name)
    except Exception:
        return "UNKNOWN"


def collect_transition_environment() -> Dict[str, Any]:
    if not torch.cuda.is_available():
        gpu_model = "NO_CUDA"
    else:
        names = {torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())}
        gpu_model = next(iter(names)) if len(names) == 1 else sorted(names)

    return {
        "environment_contract_version": ENV_CONTRACT_VERSION,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "torch": torch.__version__,
        "cuda_runtime": torch.version.cuda,
        "numpy": np.__version__,
        "ase": ase.__version__,
        "mace": mace.__version__,
        "pymatgen": _pkg_version("pymatgen"),
        "pymatgen_core": _pkg_version("pymatgen-core"),
        "cudnn": torch.backends.cudnn.version(),
        "gpu_model": gpu_model,
    }


def write_transition_environment(path: str | Path) -> Dict[str, Any]:
    payload = collect_transition_environment()
    write_json_atomic(Path(path), payload)
    return payload


def load_transition_environment(path: str | Path) -> Dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("environment_contract_version") != ENV_CONTRACT_VERSION:
        raise ValueError("unsupported P2.5 transition environment contract")
    for key in REQUIRED_FIELDS:
        if key not in payload:
            raise ValueError(f"environment contract missing required field: {key}")
    return payload


def validate_transition_environment(path: str | Path) -> Dict[str, Any]:
    frozen = load_transition_environment(path)
    actual = collect_transition_environment()
    mismatches = {
        key: {"expected": frozen.get(key), "actual": actual.get(key)}
        for key in REQUIRED_FIELDS
        if frozen.get(key) != actual.get(key)
    }
    if mismatches:
        raise RuntimeError(
            "canonical P2.5 transition environment mismatch: "
            + json.dumps(mismatches, sort_keys=True)
        )
    return frozen
