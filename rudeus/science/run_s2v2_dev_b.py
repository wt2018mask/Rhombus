"""S2 v2 DEV-B runner: frozen-input verification + fresh-root preflight ONLY.

Answers two questions and nothing more: are the frozen DEV-A calibration
inputs exactly valid, and is the requested DEV-B target root clean enough
for a first execution? No plan/dataset creation, no materialization, no
estimation, no evaluation, no summary, no owner acknowledgment, no
HELD_OUT access. Importing this module executes nothing; use ``main()``
or the ``__main__`` guard (``--preflight-only`` is the sole permitted
operational behavior).

Frozen pins below (package hash, identity hash, q_hat) are the audited
real-DEV-A outputs, recorded here as resolution targets -- never learned,
never recomputed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from rudeus.execution.contracts import ExecutionError
from rudeus.science.calibration_s2v2 import (
    S2V2_CRITERION_HASH,
    S2V2_METHOD,
    S2V2_METHOD_HASH,
    assert_frozen_v2_policy,
)
from rudeus.science.calibration_s2v2_populations import (
    S2V2_DEV_A_HASH,
    S2V2_DEV_B_HASH,
    S2V2_DEV_B_SEEDS,
    S2V2_HELDOUT_HASH,
    S2V2_POPULATIONS_HASH,
    assert_frozen_v2_populations,
)
from rudeus.science.calibration_s2v2_stageb import PACKAGE_STATUS
from rudeus.science.contracts import digest, require_hash

# Audited real-DEV-A outputs (C:\s2v2-dev-a-v3 completeness audit): pinned
# as resolution targets so future runs resolve exactly this evidence. ----
S2V2_FROZEN_PACKAGE_HASH = (
    "a79fe85256a34317b7512f1a51d627653b5b9c530b5b75b0914102b1cc067a30"
)
S2V2_FROZEN_IDENTITY_HASH = (
    "1947732e97cf14659b3d2c100ba2ce8c1905aa9998ce69f95e9c466529494dba"
)
S2V2_FROZEN_Q_HAT = 7.195845360795594e-10

# DEV-A artifact namespaces (mirror the DEV-A runner layout; literals keep
# this module free of execution-pipeline imports).
DEV_A_PACKAGE_DIR = "calibration_packages"
DEV_A_IDENTITY_DIR = "pre_heldout_identities"

# DEV-B target-root namespaces scanned by preflight. ------------------------
DEV_B_EVALUATION_DIR = "dev_b_evaluations"
DEV_B_SUMMARY_DIR = "dev_b_summaries"


def _fail(message):
    raise ExecutionError(message, "INTEGRITY")


def _read_json(path):
    try:
        return json.loads(Path(path).read_bytes())
    except (OSError, ValueError) as exc:
        _fail(f"unreadable evidence file {Path(path).name}: {exc}")


def resolve_s2v2_calibration_package(*, dev_a_artifact_root,
                                     package_hash=S2V2_FROZEN_PACKAGE_HASH):
    """Resolve and verify a DEV-A calibration package (read-only).

    Opens artifacts/calibration_packages/<hash>.json, requires digest
    equality, then enforces the frozen package contract: method, criterion,
    and DEV-A population bindings; n == 99; k == 90; target 0.90; exact
    frozen q_hat. The default hash pins the audited real package; callers
    may supply an explicit hash (validated identically) for testing. No
    writes. q_hat is consumed, never derived.
    """
    record = _read_json(
        Path(dev_a_artifact_root) / DEV_A_PACKAGE_DIR / f"{package_hash}.json")
    if not isinstance(record, dict) or digest(record) != package_hash:
        _fail("calibration package content does not match its content hash")
    if record.get("method_hash") != S2V2_METHOD_HASH:
        _fail("calibration package binds a foreign method")
    if record.get("criterion_hash") != S2V2_CRITERION_HASH:
        _fail("calibration package binds a foreign criterion")
    if record.get("dev_a_population_hash") != S2V2_DEV_A_HASH:
        _fail("calibration package binds a foreign population")
    if record.get("n") != 99:
        _fail("calibration package replicate count is not frozen DEV-A")
    if record.get("k") != 90:
        _fail("calibration package conformal rank is not frozen")
    if record.get("target_coverage") != 0.90:
        _fail("calibration package target coverage is not frozen")
    if record.get("q_hat") != S2V2_FROZEN_Q_HAT:
        _fail("calibration package q_hat is not the frozen value")
    if record.get("package_status") != PACKAGE_STATUS:
        _fail("calibration package status is not frozen non-qualification")
    estimator = record.get("estimator")
    expected_estimator = S2V2_METHOD.get("estimator", {})
    if not isinstance(estimator, dict) or any(
            estimator.get(key) != expected_estimator.get(key)
            for key in ("name", "module", "config_hash")):
        _fail("calibration package estimator binding disagrees with method")
    for key in ("truth", "scope", "generator_protocol"):
        if record.get(key) != S2V2_METHOD.get(key):
            _fail(f"calibration package {key} binding disagrees with method")
    revision = record.get("code_revision")
    if not isinstance(revision, str) or not revision:
        _fail("calibration package code revision is not valid provenance")
    return record


def resolve_s2v2_pre_heldout_identity(*, dev_a_artifact_root,
                                      identity_hash=S2V2_FROZEN_IDENTITY_HASH):
    """Resolve and verify a pre-HELDOUT identity record (read-only).

    Requires digest equality, all six frozen population/method/criterion/
    package bindings, and phase {frozen, not-evaluated, unopened}. The
    default hash pins the audited real identity; explicit hashes are
    validated identically. No mutation, no writes.
    """
    record = _read_json(
        Path(dev_a_artifact_root) / DEV_A_IDENTITY_DIR / f"{identity_hash}.json")
    if not isinstance(record, dict) or digest(record) != identity_hash:
        _fail("pre-HELDOUT identity content does not match its content hash")
    for key, expected in (
            ("method_hash", S2V2_METHOD_HASH),
            ("criterion_hash", S2V2_CRITERION_HASH),
            ("dev_a_population_hash", S2V2_DEV_A_HASH),
            ("dev_b_population_hash", S2V2_DEV_B_HASH),
            ("heldout_population_hash", S2V2_HELDOUT_HASH)):
        if record.get(key) != expected:
            _fail(f"pre-HELDOUT identity binding mismatch: {key}")
    # The calibration_package_hash binding is verified by
    # verify_s2v2_devb_inputs against the resolved package itself, not here.
    try:
        require_hash(record.get("calibration_package_hash"))
    except (ValueError, TypeError, AttributeError) as exc:
        _fail(f"pre-HELDOUT identity package binding malformed: {exc}")
    if record.get("populations_hash") != S2V2_POPULATIONS_HASH:
        _fail("pre-HELDOUT identity combined population binding mismatch")
    revision = record.get("code_revision")
    if not isinstance(revision, str) or not revision:
        _fail("pre-HELDOUT identity code revision is not valid provenance")
    phase = record.get("phase")
    if not isinstance(phase, dict) or phase.get("calibration") != "frozen" \
            or phase.get("dev_b") != "not-evaluated" \
            or phase.get("heldout") != "unopened":
        _fail("pre-HELDOUT identity phase is not frozen pre-DEV-B state")
    return record


def verify_s2v2_devb_inputs(package, identity):
    """Cross-verify resolved package and identity (pure, read-only).

    Requires identity.calibration_package_hash == digest(package) with all
    frozen bindings agreeing. Returns a small immutable summary for the
    future runner; it is not scientific evidence and not a verdict.
    """
    package_hash = digest(package)
    if identity.get("calibration_package_hash") != package_hash:
        _fail("pre-HELDOUT identity does not bind the resolved package")
    for key, expected in (
            ("method_hash", S2V2_METHOD_HASH),
            ("criterion_hash", S2V2_CRITERION_HASH),
            ("dev_a_population_hash", S2V2_DEV_A_HASH)):
        if package.get(key) != expected or identity.get(key) != expected:
            _fail(f"package/identity binding mismatch: {key}")
    if package.get("q_hat") != S2V2_FROZEN_Q_HAT:
        _fail("resolved package q_hat is not the frozen value")
    if identity.get("code_revision") != package.get("code_revision"):
        _fail("pre-HELDOUT identity revision does not match package revision")
    return {
        "package_hash": package_hash,
        "identity_hash": digest(identity),
        "q_hat": package["q_hat"],
        "dev_b_population_hash": S2V2_DEV_B_HASH,
        "frozen_dev_a_code_revision": package.get("code_revision"),
        "preflight": "INPUTS-VERIFIED",
    }


def check_devb_target_root_empty(*, store_root, artifact_root):
    """Fresh-root exclusivity guard for DEV-B (read-only, no writes).

    Conservative policy for greenfield DEV-B roots: ANY *.json file under
    the scanned evidence namespaces refuses (replicate manifests, estimator
    results, DEV-B evaluations/summaries, calibration packages, pre-HELDOUT
    identities), as does any unreadable file there (absence unprovable).
    Absent roots and genuinely empty directories pass. No resume, no
    skip-complete, no overwrite, no cleanup, no directory creation.
    """
    store = Path(store_root)
    root = Path(artifact_root)
    for dirname in ("calibration_replicates",):
        directory = store / dirname
        if directory.is_dir() and any(directory.glob("*.json")):
            _fail(f"target root already holds evidence: store/{dirname}")
    for dirname in ("estimator_results", DEV_B_EVALUATION_DIR,
                    DEV_B_SUMMARY_DIR, DEV_A_PACKAGE_DIR, DEV_A_IDENTITY_DIR):
        directory = root / dirname
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.json")):
            _read_json(path)  # fail-closed on unreadable content
            _fail(f"target root already holds evidence: {dirname}/{path.name}")


def preflight_s2v2_dev_b(*, dev_a_artifact_root, store_root, artifact_root,
                         code_revision):
    """DEV-B preflight orchestration (read-only; zero scientific writes)."""
    assert_frozen_v2_policy()
    assert_frozen_v2_populations()
    if not isinstance(code_revision, str) or not code_revision:
        _fail("code revision must be explicit")
    package = resolve_s2v2_calibration_package(
        dev_a_artifact_root=dev_a_artifact_root,
        package_hash=S2V2_FROZEN_PACKAGE_HASH)
    identity = resolve_s2v2_pre_heldout_identity(
        dev_a_artifact_root=dev_a_artifact_root,
        identity_hash=S2V2_FROZEN_IDENTITY_HASH)
    verified = verify_s2v2_devb_inputs(package, identity)
    check_devb_target_root_empty(store_root=store_root, artifact_root=artifact_root)
    return {**verified,
            "dev_b_replicates": len(S2V2_DEV_B_SEEDS),
            "code_revision": code_revision,
            "preflight": "PASS"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dev-a-artifact-root", required=True)
    parser.add_argument("--store-root", required=True)
    parser.add_argument("--artifact-root", required=True)
    parser.add_argument("--code-revision", required=True)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args(argv)
    if not args.preflight_only:
        parser.error("only --preflight-only is implemented in this slice")
    preflight_s2v2_dev_b(dev_a_artifact_root=args.dev_a_artifact_root,
                         store_root=args.store_root,
                         artifact_root=args.artifact_root,
                         code_revision=args.code_revision)


if __name__ == "__main__":
    main()
