"""S2 v2 pre-HELDOUT owner no-change gate (procedural freeze, no science).

Proves the owner reviewed the frozen DEV-A calibration evidence and the
completed DEV-B descriptive evidence and froze the S2 v2 method with no
post-DEV-B tuning, while HELD_OUT remains unopened. The persisted record
means only NO-CHANGE / UNOPENED / FORBIDDEN-tuning; it is never a
qualification verdict and never authorizes HELD_OUT execution.

Separation: this gate consumes the DEV-B runner's read-only resolvers but
never drives estimation, never opens HELD_OUT, and stops after
acknowledgment persistence. Importing this module executes nothing; use
``main()`` or the ``__main__`` guard with ``--acknowledge-no-change``.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from rudeus.execution.contracts import ExecutionError
from rudeus.science.calibration_s2v2 import (
    S2V2_CRITERION_HASH,
    S2V2_METHOD_HASH,
)
from rudeus.science.calibration_s2v2_devb import (
    Q_HAT_UNITS,
    SUMMARY_FORMAT,
    SUMMARY_STATUS,
)
from rudeus.science.calibration_s2v2_populations import (
    S2V2_DEV_A_HASH,
    S2V2_DEV_B_HASH,
    S2V2_HELDOUT_HASH,
    S2V2_HELDOUT_RECORD,
    S2V2_POPULATIONS_HASH,
)
from rudeus.science.contracts import canonical_bytes, digest, require_hash
from rudeus.science.evidence import append_file, inside
from rudeus.science.run_s2v2_dev_b import (
    DEV_B_SUMMARY_DIR,
    S2V2_FROZEN_IDENTITY_HASH,
    S2V2_FROZEN_PACKAGE_HASH,
    S2V2_FROZEN_Q_HAT,
    resolve_s2v2_calibration_package,
    resolve_s2v2_pre_heldout_identity,
)

NO_CHANGE_FORMAT = "s2v2-pre-heldout-no-change-v1"
NO_CHANGE_DIR = "pre_heldout_no_change"

# Audited real DEV-B descriptive summary and the committed producer revision.
# These pins identify the reviewed evidence; summary statistics are not
# recomputed and are never interpreted as qualification.
S2V2_FROZEN_DEV_B_SUMMARY_HASH = (
    "f5a1b7d008773d3e40f94b0731d58225df0cd8793b45dd793672989e60534d63"
)
S2V2_FROZEN_DEV_B_CODE_REVISION = "be1285311f81b0c5c54903c19c1b91b35f1d6fd5"

DECISION_NO_CHANGE = "NO-CHANGE"
HELDOUT_STATUS_UNOPENED = "UNOPENED"
POST_DEV_B_TUNING_FORBIDDEN = "FORBIDDEN"

# DEV-B evidence is descriptive only; the gate binds the role, never a verdict.
DEV_B_ROLE = SUMMARY_STATUS

# Namespaces whose mere presence in the target evidence root proves HELD_OUT
# was already opened (no such runner exists yet; any such file refuses).
HELDOUT_EVIDENCE_DIRS = (
    "heldout_evaluations",
    "heldout_summaries",
    "heldout_results",
    "heldout_manifests",
    "qualification_records",
)


def _fail(message):
    raise ExecutionError(message, "INTEGRITY")


def _read_json(path):
    try:
        return json.loads(Path(path).read_bytes())
    except (OSError, ValueError) as exc:
        _fail(f"unreadable evidence file {Path(path).name}: {exc}")


def build_pre_heldout_no_change(*, method_hash, criterion_hash,
                                dev_a_population_hash, dev_b_population_hash,
                                heldout_population_hash, populations_hash,
                                calibration_package_hash,
                                pre_heldout_identity_hash, q_hat,
                                dev_b_summary_hash,
                                dev_b_summary_code_revision):
    """Build the deterministic no-change acknowledgment record (pure).

    All bindings are caller-supplied verified values; the frozen science
    bindings must equal the frozen v2 constants. The decision semantics are
    fixed constants, never caller parameters: there is no approved flag,
    no verdict, no threshold, no tuning allowance. No filesystem access.
    """
    if method_hash != S2V2_METHOD_HASH:
        _fail("no-change gate method hash is not the frozen v2 method")
    if criterion_hash != S2V2_CRITERION_HASH:
        _fail("no-change gate criterion hash is not the frozen criterion")
    if dev_a_population_hash != S2V2_DEV_A_HASH:
        _fail("no-change gate DEV-A population is not frozen")
    if dev_b_population_hash != S2V2_DEV_B_HASH:
        _fail("no-change gate DEV-B population is not frozen")
    if heldout_population_hash != S2V2_HELDOUT_HASH:
        _fail("no-change gate HELDOUT population is not frozen")
    if populations_hash != S2V2_POPULATIONS_HASH:
        _fail("no-change gate combined population binding is not frozen")
    if calibration_package_hash != S2V2_FROZEN_PACKAGE_HASH:
        _fail("no-change gate calibration package is not the frozen package")
    if pre_heldout_identity_hash != S2V2_FROZEN_IDENTITY_HASH:
        _fail("no-change gate identity is not the frozen pre-HELDOUT identity")
    if q_hat != S2V2_FROZEN_Q_HAT:
        _fail("no-change gate q_hat is not the frozen package value")
    if dev_b_summary_hash != S2V2_FROZEN_DEV_B_SUMMARY_HASH:
        _fail("no-change gate DEV-B summary is not the reviewed summary")
    if dev_b_summary_code_revision != S2V2_FROZEN_DEV_B_CODE_REVISION:
        _fail("no-change gate DEV-B summary revision is not the reviewed revision")
    for name, value in (
            ("calibration_package_hash", calibration_package_hash),
            ("pre_heldout_identity_hash", pre_heldout_identity_hash),
            ("dev_b_summary_hash", dev_b_summary_hash)):
        try:
            require_hash(value)
        except (ValueError, TypeError) as exc:
            _fail(f"no-change gate {name} is not a content hash: {exc}")
    if isinstance(q_hat, bool) or not isinstance(q_hat, (int, float)):
        _fail("no-change gate q_hat is not numeric")
    if not math.isfinite(q_hat) or q_hat < 0:
        _fail("no-change gate q_hat is not a finite nonnegative value")
    if not isinstance(dev_b_summary_code_revision, str) \
            or not dev_b_summary_code_revision:
        _fail("no-change gate DEV-B summary revision must be explicit")
    return {
        "format": NO_CHANGE_FORMAT,
        "decision": DECISION_NO_CHANGE,
        "heldout_status": HELDOUT_STATUS_UNOPENED,
        "post_dev_b_tuning": POST_DEV_B_TUNING_FORBIDDEN,
        "dev_b_role": DEV_B_ROLE,
        "method_hash": S2V2_METHOD_HASH,
        "criterion_hash": S2V2_CRITERION_HASH,
        "dev_a_population_hash": S2V2_DEV_A_HASH,
        "dev_b_population_hash": S2V2_DEV_B_HASH,
        "heldout_population_hash": S2V2_HELDOUT_HASH,
        "populations_hash": S2V2_POPULATIONS_HASH,
        "calibration_package_hash": calibration_package_hash,
        "pre_heldout_identity_hash": pre_heldout_identity_hash,
        "q_hat": float(q_hat),
        "q_hat_units": Q_HAT_UNITS,
        "dev_b_summary_hash": dev_b_summary_hash,
        "dev_b_summary_code_revision": dev_b_summary_code_revision,
    }


def check_heldout_unopened(*, artifact_root):
    """Refuse if any HELD_OUT evidence already exists (read-only, no writes).

    Any JSON file under the frozen HELDOUT-indicating namespaces proves the
    gate is late: HELD_OUT was opened before acknowledgment. Absent roots
    and empty directories pass. No resume, no overwrite, no cleanup.
    """
    root = Path(artifact_root).resolve()
    for dirname in HELDOUT_EVIDENCE_DIRS:
        directory = inside(root, dirname)
        if not directory.is_dir():
            continue
        try:
            entries = sorted(directory.rglob("*"))
        except OSError as exc:
            _fail(f"cannot inspect HELDOUT evidence namespace {dirname}: {exc}")
        for path in entries:
            if path.is_file() or path.is_symlink():
                if (dirname == "heldout_manifests" and path.parent == directory
                        and path.name == f"{S2V2_HELDOUT_HASH}.json"):
                    # The one permitted HELDOUT file is frozen contract
                    # metadata (population IDs/seeds), never an outcome.
                    metadata = _read_json(inside(
                        root, f"{dirname}/{path.name}"))
                    if canonical_bytes(metadata) == canonical_bytes(S2V2_HELDOUT_RECORD) \
                            and digest(metadata) == S2V2_HELDOUT_HASH:
                        continue
                    _fail("frozen HELDOUT inventory metadata is invalid")
                # Presence is sufficient to refuse. Never open an outcome.
                _fail(f"HELDOUT evidence already exists: {dirname}/{path.name}")


def resolve_verified_no_change_inputs(*, dev_a_artifact_root, artifact_root,
                                      package_hash=S2V2_FROZEN_PACKAGE_HASH,
                                      identity_hash=S2V2_FROZEN_IDENTITY_HASH,
                                      dev_b_summary_hash):
    """Verify all gate inputs by exact content hash (read-only, no writes).

    Resolves the frozen DEV-A package and pre-HELDOUT identity through the
    committed DEV-B resolvers, then the exact DEV-B summary by its content
    hash: digest equality plus semantic bindings (format, descriptive
    status, frozen population/method/criterion, package and identity
    bindings, package q_hat, exact 114 valid replicates). Refuses when
    HELD_OUT evidence already exists or an acknowledgment already exists.
    Descriptive summary numbers are bound by hash identity only, never
    recomputed and never converted into a verdict.
    """
    try:
        require_hash(dev_b_summary_hash)
    except (ValueError, TypeError) as exc:
        _fail(f"DEV-B summary hash is not a content hash: {exc}")
    if package_hash != S2V2_FROZEN_PACKAGE_HASH:
        _fail("no-change gate package argument is not the frozen package")
    if identity_hash != S2V2_FROZEN_IDENTITY_HASH:
        _fail("no-change gate identity argument is not the frozen identity")
    if dev_b_summary_hash != S2V2_FROZEN_DEV_B_SUMMARY_HASH:
        _fail("no-change gate summary argument is not the reviewed summary")
    package = resolve_s2v2_calibration_package(
        dev_a_artifact_root=dev_a_artifact_root, package_hash=package_hash)
    identity = resolve_s2v2_pre_heldout_identity(
        dev_a_artifact_root=dev_a_artifact_root, identity_hash=identity_hash)
    if identity.get("calibration_package_hash") != digest(package):
        _fail("pre-HELDOUT identity does not bind the resolved package")
    if package.get("q_hat") != S2V2_FROZEN_Q_HAT:
        _fail("resolved package q_hat is not the frozen value")
    root = Path(artifact_root).resolve()
    summary = _read_json(inside(
        root, f"{DEV_B_SUMMARY_DIR}/{dev_b_summary_hash}.json"))
    if not isinstance(summary, dict) or digest(summary) != dev_b_summary_hash:
        _fail("DEV-B summary content does not match its content hash")
    if summary.get("format") != SUMMARY_FORMAT:
        _fail("DEV-B summary format is not the frozen DEV-B summary")
    if summary.get("status") != SUMMARY_STATUS:
        _fail("DEV-B summary is not descriptive non-qualification evidence")
    for key, expected in (
            ("population_hash", S2V2_DEV_B_HASH),
            ("method_hash", S2V2_METHOD_HASH),
            ("criterion_hash", S2V2_CRITERION_HASH)):
        if summary.get(key) != expected:
            _fail(f"DEV-B summary binding mismatch: {key}")
    if summary.get("calibration_package_hash") != digest(package):
        _fail("DEV-B summary does not bind the resolved package")
    if summary.get("pre_heldout_identity_hash") != digest(identity):
        _fail("DEV-B summary does not bind the resolved identity")
    if summary.get("q_hat") != package.get("q_hat"):
        _fail("DEV-B summary q_hat does not match the frozen package q_hat")
    if summary.get("n_attempted") != 114 or summary.get("n_valid") != 114:
        _fail("DEV-B summary does not cover exactly 114 valid replicates")
    if len(summary.get("ordered_evaluation_hashes") or []) != 114:
        _fail("DEV-B summary replicate inventory is not exactly 114")
    revision = summary.get("code_revision")
    if revision != S2V2_FROZEN_DEV_B_CODE_REVISION:
        _fail("DEV-B summary code revision is not the reviewed producer revision")
    check_heldout_unopened(artifact_root=root)
    ack_dir = inside(root, NO_CHANGE_DIR)
    if ack_dir.is_dir() and any(ack_dir.iterdir()):
        _fail("a pre-HELDOUT no-change acknowledgment already exists")
    return build_pre_heldout_no_change(
        method_hash=S2V2_METHOD_HASH, criterion_hash=S2V2_CRITERION_HASH,
        dev_a_population_hash=S2V2_DEV_A_HASH,
        dev_b_population_hash=S2V2_DEV_B_HASH,
        heldout_population_hash=S2V2_HELDOUT_HASH,
        populations_hash=S2V2_POPULATIONS_HASH,
        calibration_package_hash=digest(package),
        pre_heldout_identity_hash=digest(identity),
        q_hat=package.get("q_hat"), dev_b_summary_hash=dev_b_summary_hash,
        dev_b_summary_code_revision=revision)


def persist_pre_heldout_no_change(*, dev_a_artifact_root, artifact_root,
                                  package_hash=S2V2_FROZEN_PACKAGE_HASH,
                                  identity_hash=S2V2_FROZEN_IDENTITY_HASH,
                                  dev_b_summary_hash):
    """Persist one content-addressed acknowledgment (fail-closed).

    Input evidence is resolved and verified before any write. The caller
    cannot supply or manufacture the acknowledgment record.

    Canonical serialization + append-only write + path confinement under
    ``pre_heldout_no_change/<content-hash>.json``, then exact re-read
    requiring digest equality and record equality. No mutable alias.
    """
    acknowledgment = resolve_verified_no_change_inputs(
        dev_a_artifact_root=dev_a_artifact_root, artifact_root=artifact_root,
        package_hash=package_hash, identity_hash=identity_hash,
        dev_b_summary_hash=dev_b_summary_hash)
    root = Path(artifact_root).resolve()
    ack_dir = inside(root, NO_CHANGE_DIR)
    if ack_dir.exists():
        _fail("a pre-HELDOUT no-change acknowledgment already exists")
    ack_hash = digest(acknowledgment)
    data = canonical_bytes(acknowledgment)
    try:
        # The exclusive namespace creation makes the one-ack rule atomic
        # across concurrent invocations; it is an append-only claim, not a
        # reusable lock or mutable alias.
        ack_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        _fail("a pre-HELDOUT no-change acknowledgment already exists")
    except OSError as exc:
        _fail(f"cannot claim no-change acknowledgment namespace: {exc}")
    append_file(inside(root, f"{NO_CHANGE_DIR}/{ack_hash}.json"), data)
    try:
        stored_bytes = inside(
            root, f"{NO_CHANGE_DIR}/{ack_hash}.json").read_bytes()
        persisted = json.loads(stored_bytes)
    except (OSError, ValueError) as exc:
        _fail(f"no-change acknowledgment re-read failed: {exc}")
    if not isinstance(persisted, dict) or digest(persisted) != ack_hash:
        _fail("no-change acknowledgment digest mismatch")
    if stored_bytes != data:
        _fail("no-change acknowledgment serialization mismatch")
    if persisted != acknowledgment:
        _fail("no-change acknowledgment content mismatch")
    return {"acknowledged": 1, "acknowledgment_hash": ack_hash}


def verify_pre_heldout_no_change_complete(*, dev_a_artifact_root,
                                          artifact_root,
                                          package_hash=S2V2_FROZEN_PACKAGE_HASH,
                                          identity_hash=S2V2_FROZEN_IDENTITY_HASH,
                                          dev_b_summary_hash):
    """Require exactly one replay-valid acknowledgment (fail-closed).

    The namespace must hold exactly one file whose name equals its
    canonical digest. Inputs are re-verified (including HELDOUT-unopened),
    the expected record is rebuilt with the pure builder, and required to
    match exactly: digest-valid forgeries with altered bindings or decision
    semantics refuse via replay mismatch. Never selects from multiples.
    """
    root = Path(artifact_root).resolve()
    ack_dir = inside(root, NO_CHANGE_DIR)
    entries = sorted(ack_dir.iterdir()) if ack_dir.is_dir() else []
    if len(entries) != 1 or not entries[0].is_file() or entries[0].suffix != ".json":
        _fail("no-change acknowledgment evidence is not exactly one record")
    paths = [inside(root, f"{NO_CHANGE_DIR}/{entries[0].name}")]
    record = _read_json(paths[0])
    if not isinstance(record, dict):
        _fail(f"no-change acknowledgment is not a record: {paths[0].name}")
    try:
        content_hash = digest(record)
    except ValueError:
        content_hash = None
    if content_hash != paths[0].stem:
        _fail(f"acknowledgment filename/hash mismatch: {paths[0].name}")
    # Replay uses the guard-free re-verification: the creation-time
    # acknowledgment-absence check must not run here, where exactly one
    # acknowledgment is expected to exist.
    inputs = _reverify_inputs_for_replay(
        dev_a_artifact_root=dev_a_artifact_root, artifact_root=root,
        package_hash=package_hash, identity_hash=identity_hash,
        dev_b_summary_hash=dev_b_summary_hash)
    replayed = build_pre_heldout_no_change(**inputs)
    if record != replayed:
        _fail("no-change acknowledgment replay mismatch")
    if digest(record) != digest(replayed):
        _fail("no-change acknowledgment replay digest mismatch")
    return {"acknowledged": 1, "acknowledgment_hash": paths[0].stem}


def _reverify_inputs_for_replay(*, dev_a_artifact_root, artifact_root,
                                package_hash, identity_hash,
                                dev_b_summary_hash):
    """Re-verify input bindings for replay without the ack-absence guard."""
    try:
        require_hash(dev_b_summary_hash)
    except (ValueError, TypeError) as exc:
        _fail(f"DEV-B summary hash is not a content hash: {exc}")
    if package_hash != S2V2_FROZEN_PACKAGE_HASH:
        _fail("no-change gate package argument is not the frozen package")
    if identity_hash != S2V2_FROZEN_IDENTITY_HASH:
        _fail("no-change gate identity argument is not the frozen identity")
    if dev_b_summary_hash != S2V2_FROZEN_DEV_B_SUMMARY_HASH:
        _fail("no-change gate summary argument is not the reviewed summary")
    package = resolve_s2v2_calibration_package(
        dev_a_artifact_root=dev_a_artifact_root, package_hash=package_hash)
    identity = resolve_s2v2_pre_heldout_identity(
        dev_a_artifact_root=dev_a_artifact_root, identity_hash=identity_hash)
    if identity.get("calibration_package_hash") != digest(package):
        _fail("pre-HELDOUT identity does not bind the resolved package")
    if package.get("q_hat") != S2V2_FROZEN_Q_HAT:
        _fail("resolved package q_hat is not the frozen value")
    root = Path(artifact_root).resolve()
    summary = _read_json(inside(
        root, f"{DEV_B_SUMMARY_DIR}/{dev_b_summary_hash}.json"))
    if not isinstance(summary, dict) or digest(summary) != dev_b_summary_hash:
        _fail("DEV-B summary content does not match its content hash")
    if summary.get("format") != SUMMARY_FORMAT:
        _fail("DEV-B summary format is not the frozen DEV-B summary")
    if summary.get("status") != SUMMARY_STATUS:
        _fail("DEV-B summary is not descriptive non-qualification evidence")
    for key, expected in (
            ("population_hash", S2V2_DEV_B_HASH),
            ("method_hash", S2V2_METHOD_HASH),
            ("criterion_hash", S2V2_CRITERION_HASH)):
        if summary.get(key) != expected:
            _fail(f"DEV-B summary binding mismatch: {key}")
    if summary.get("calibration_package_hash") != digest(package):
        _fail("DEV-B summary does not bind the resolved package")
    if summary.get("pre_heldout_identity_hash") != digest(identity):
        _fail("DEV-B summary does not bind the resolved identity")
    if summary.get("q_hat") != package.get("q_hat"):
        _fail("DEV-B summary q_hat does not match the frozen package q_hat")
    if summary.get("n_attempted") != 114 or summary.get("n_valid") != 114:
        _fail("DEV-B summary does not cover exactly 114 valid replicates")
    if len(summary.get("ordered_evaluation_hashes") or []) != 114:
        _fail("DEV-B summary replicate inventory is not exactly 114")
    revision = summary.get("code_revision")
    if revision != S2V2_FROZEN_DEV_B_CODE_REVISION:
        _fail("DEV-B summary code revision is not the reviewed producer revision")
    check_heldout_unopened(artifact_root=root)
    return {
        "method_hash": S2V2_METHOD_HASH,
        "criterion_hash": S2V2_CRITERION_HASH,
        "dev_a_population_hash": S2V2_DEV_A_HASH,
        "dev_b_population_hash": S2V2_DEV_B_HASH,
        "heldout_population_hash": S2V2_HELDOUT_HASH,
        "populations_hash": S2V2_POPULATIONS_HASH,
        "calibration_package_hash": digest(package),
        "pre_heldout_identity_hash": digest(identity),
        "q_hat": package.get("q_hat"),
        "dev_b_summary_hash": dev_b_summary_hash,
        "dev_b_summary_code_revision": revision,
    }


def acknowledge_pre_heldout_no_change(*, dev_a_artifact_root, artifact_root,
                                      package_hash=S2V2_FROZEN_PACKAGE_HASH,
                                      identity_hash=S2V2_FROZEN_IDENTITY_HASH,
                                      dev_b_summary_hash):
    """Verify inputs, persist the acknowledgment, replay-verify, then stop.

    Explicit owner action only; never automatic. Creates no HELDOUT
    evidence, launches nothing, calculates no qualification.
    """
    persisted = persist_pre_heldout_no_change(
        dev_a_artifact_root=dev_a_artifact_root, artifact_root=artifact_root,
        package_hash=package_hash, identity_hash=identity_hash,
        dev_b_summary_hash=dev_b_summary_hash)
    reverified = verify_pre_heldout_no_change_complete(
        dev_a_artifact_root=dev_a_artifact_root, artifact_root=artifact_root,
        package_hash=package_hash, identity_hash=identity_hash,
        dev_b_summary_hash=dev_b_summary_hash)
    if persisted["acknowledgment_hash"] != reverified["acknowledgment_hash"]:
        _fail("acknowledgment persistence/replay identity mismatch")
    summary = {
        "acknowledged": reverified["acknowledged"],
        "acknowledgment_hash": reverified["acknowledgment_hash"],
        "dev_b_summary_hash": dev_b_summary_hash,
        "failures": [],
    }
    print(f"acknowledged={summary['acknowledged']} "
          f"acknowledgment={summary['acknowledgment_hash'][:12]} failures=none")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dev-a-artifact-root", required=True)
    parser.add_argument("--artifact-root", required=True)
    parser.add_argument("--package-hash", default=S2V2_FROZEN_PACKAGE_HASH)
    parser.add_argument("--identity-hash", default=S2V2_FROZEN_IDENTITY_HASH)
    parser.add_argument("--dev-b-summary-hash", required=True)
    parser.add_argument("--acknowledge-no-change", action="store_true")
    args = parser.parse_args(argv)
    if not args.acknowledge_no_change:
        parser.error("--acknowledge-no-change is required; "
                     "acknowledgment is never automatic")
    acknowledge_pre_heldout_no_change(
        dev_a_artifact_root=args.dev_a_artifact_root,
        artifact_root=args.artifact_root, package_hash=args.package_hash,
        identity_hash=args.identity_hash,
        dev_b_summary_hash=args.dev_b_summary_hash)


if __name__ == "__main__":
    main()
