"""Immutable provenance marker for the explicit S2 v2 HELDOUT opening.

The marker records authorization and target identity only. It is not a
scientific result or an execution attestation.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from rudeus.execution.contracts import ExecutionError
from rudeus.science.contracts import canonical_bytes, digest, require_hash
from rudeus.science.evidence import append_file, inside

FORMAT = "s2v2-heldout-open-v1"
OPEN_DIR = "heldout_open"
ROOT_IDENTITY_FORMAT = "s2v2-heldout-execution-root-v1"


def _fail(message):
    raise ExecutionError(message, "INTEGRITY")


def execution_root_identity(*, store_root, artifact_root):
    """Hash normalized configured roots without persisting host paths."""
    def normalized(path):
        return os.path.normcase(str(Path(path).expanduser().resolve()))

    return digest({
        "format": ROOT_IDENTITY_FORMAT,
        "store_root": normalized(store_root),
        "artifact_root": normalized(artifact_root),
    })


def build_heldout_open_marker(*, context, code_revision, root_identity):
    """Pure deterministic record builder from strict gate context."""
    try:
        require_hash(root_identity)
        if not isinstance(code_revision, str) or not code_revision:
            _fail("HELDOUT execution code revision is missing")
        for key in (
            "acknowledgment_hash", "method_hash", "criterion_hash",
            "heldout_population_hash", "populations_hash",
            "calibration_package_hash", "dev_b_summary_hash",
        ):
            require_hash(context[key])
        if (not isinstance(context["dev_b_summary_code_revision"], str)
                or not context["dev_b_summary_code_revision"]):
            _fail("verified acknowledgment DEV-B revision is malformed")
        q_hat = context["q_hat"]
        if isinstance(q_hat, bool) or not isinstance(q_hat, (int, float)):
            _fail("verified acknowledgment q_hat is malformed")
    except (KeyError, TypeError, ValueError) as exc:
        _fail(f"HELDOUT-open marker binding is malformed: {exc}")
    return {
        "format": FORMAT,
        "transition": "OPEN",
        "previous_status": "UNOPENED",
        "heldout_status": "OPENED",
        "pre_heldout_acknowledgment_hash": context["acknowledgment_hash"],
        "method_hash": context["method_hash"],
        "criterion_hash": context["criterion_hash"],
        "heldout_population_hash": context["heldout_population_hash"],
        "populations_hash": context["populations_hash"],
        "calibration_package_hash": context["calibration_package_hash"],
        "q_hat": q_hat,
        "dev_b_summary_hash": context["dev_b_summary_hash"],
        "dev_b_summary_code_revision": context["dev_b_summary_code_revision"],
        "heldout_execution_code_revision": code_revision,
        "execution_root_identity": root_identity,
    }


def _marker_directory(artifact_root):
    root = Path(artifact_root).resolve()
    candidate = root / OPEN_DIR
    if candidate.is_symlink():
        _fail("HELDOUT-open marker namespace cannot be a symlink")
    return inside(root, OPEN_DIR)


def _persist_heldout_open_marker(*, artifact_root, context, code_revision,
                                 root_identity):
    """Append exactly one marker and verify the exact persisted bytes.

    This low-level writer is called only after the runner's strict
    acknowledgment replay and target-freshness checks.
    """
    directory = _marker_directory(artifact_root)
    if directory.exists() or directory.is_symlink():
        _fail("HELDOUT-open marker already exists or conflicts")
    record = build_heldout_open_marker(
        context=context, code_revision=code_revision,
        root_identity=root_identity)
    marker_hash = digest(record)
    data = canonical_bytes(record)
    path = inside(Path(artifact_root).resolve(), f"{OPEN_DIR}/{marker_hash}.json")
    append_file(path, data)
    try:
        stored = path.read_bytes()
        decoded = json.loads(stored)
    except (OSError, ValueError) as exc:
        _fail(f"HELDOUT-open marker re-read failed: {exc}")
    if stored != data or decoded != record or digest(decoded) != marker_hash:
        _fail("HELDOUT-open marker persistence mismatch")
    return {"marker_hash": marker_hash, "marker": record}


def _verify_heldout_open_marker(*, artifact_root, context, code_revision,
                                root_identity):
    """Verify the sole canonical marker against independently checked inputs."""
    directory = _marker_directory(artifact_root)
    if not directory.is_dir() or directory.is_symlink():
        _fail("HELDOUT-open marker is missing or invalid")
    entries = sorted(directory.iterdir())
    if (len(entries) != 1 or entries[0].is_symlink()
            or not entries[0].is_file() or entries[0].suffix != ".json"):
        _fail("HELDOUT-open marker namespace is missing, duplicate, or conflicting")
    path = inside(Path(artifact_root).resolve(), f"{OPEN_DIR}/{entries[0].name}")
    try:
        data = path.read_bytes()
        record = json.loads(data)
    except (OSError, ValueError) as exc:
        _fail(f"HELDOUT-open marker is unreadable: {exc}")
    expected = build_heldout_open_marker(
        context=context, code_revision=code_revision,
        root_identity=root_identity)
    marker_hash = digest(expected)
    if (not isinstance(record, dict) or entries[0].name != f"{marker_hash}.json"
            or data != canonical_bytes(record) or digest(record) != marker_hash
            or record != expected):
        _fail("HELDOUT-open marker does not match verified authorization and execution target")
    return {"marker_hash": marker_hash, "marker": record}
