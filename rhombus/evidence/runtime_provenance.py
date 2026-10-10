"""Record observed runtime identity without inferring reproducibility.

No environment dump, credential files, package source URLs, remote hardware
probe or scientific computation. Hash only the local artifacts explicitly
provided by the caller. Never use a version inventory as lineage attestation.
"""
from __future__ import annotations

import hashlib
from importlib import metadata
from numbers import Integral
import os
from pathlib import Path
import platform
import subprocess
import sys
from typing import Mapping


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_runtime_provenance(
    source_root: Path, *, random_seed: int | None = None,
    artifact_paths: Mapping[str, Path] | None = None,
) -> dict:
    """Collect actual versions, local Git identity and explicit artifact bytes.

    A missing seed remains unknown/not applicable; no default seed is invented.
    Model/data labels in artifact_paths are caller supplied, not an assertion
    about checkpoint-selected training lineage or dataset completeness.
    """
    if random_seed is not None and (
        isinstance(random_seed, bool) or not isinstance(random_seed, Integral) or random_seed < 0
    ):
        raise ValueError("random_seed must be a non-negative integer or None")
    commit = subprocess.check_output(
        ["git", "-C", str(source_root), "rev-parse", "--verify", "HEAD^{commit}"], text=True,
    ).strip()
    dirty = bool(subprocess.check_output(
        ["git", "-C", str(source_root), "status", "--porcelain", "--untracked-files=no"],
    ))
    packages = {
        distribution.metadata["Name"]: distribution.version
        for distribution in metadata.distributions() if distribution.metadata.get("Name")
    }
    constraint_path = source_root / "scripts/ci/constraints.txt"
    return {
        "schema_version": "rhombus-observed-runtime-provenance-v1",
        "source_commit": commit,
        "tracked_source_dirty": dirty,
        "python": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "packages": dict(sorted(packages.items())),
        "constraints_sha256": _sha256(constraint_path) if constraint_path.is_file() else None,
        "hardware": {
            "os": platform.system(), "machine": platform.machine(),
            "cpu_description": platform.processor() or "UNKNOWN",
            "logical_cpu_count": os.cpu_count(), "gpu_observation": "NOT_PROBED",
        },
        "precision": {"python_float_mantissa_bits": sys.float_info.mant_dig,
                      "model_dtype": "NOT_OBSERVED", "blas_runtime": "NOT_OBSERVED"},
        "random_seed": int(random_seed) if random_seed is not None else None,
        "artifact_sha256": {label: _sha256(Path(path)) for label, path in (artifact_paths or {}).items()},
        "bitwise_reproducibility_verified": False,
        "independent_reproduction_verified": False,
    }
