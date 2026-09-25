"""Fail-closed S2 v2 HELDOUT qualification."""
from __future__ import annotations
import json, math
from pathlib import Path
from rudeus.execution.contracts import ExecutionError
from rudeus.science.calibration_s2v2 import S2V2_BIAS_TOLERANCE_M2_PER_S, S2V2_CRITERION_HASH, S2V2_HELDOUT_CONFIDENCE, S2V2_METHOD_HASH, S2V2_MINIMUM_COVERAGE, assert_frozen_v2_policy, exact_one_sided_lcb
from rudeus.science.calibration_s2v2_populations import S2V2_HELDOUT_COUNT, S2V2_HELDOUT_HASH, S2V2_HELDOUT_SEEDS, assert_frozen_v2_populations
from rudeus.science.contracts import canonical_bytes, digest
from rudeus.science.evidence import append_file, inside
QUALIFICATION_FORMAT = "s2v2-heldout-qualification-v1"
QUALIFICATION_DIR = "heldout_qualification"
QUALIFIED = "QUALIFIED"
NOT_QUALIFIED = "NOT-QUALIFIED"
INTEGRITY_HOLD = "INDETERMINATE / INTEGRITY-HOLD"
def _fail(message): raise ExecutionError(message, "INTEGRITY")
def _finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value): _fail(f"qualification {name} must be finite numeric")
def classify_qualification(coverage_lcb_95, abs_mean_signed_error):
    """Apply only the two frozen criteria, including exact boundaries."""
    _finite(coverage_lcb_95, "coverage LCB"); _finite(abs_mean_signed_error, "absolute mean signed error")
    coverage_pass = coverage_lcb_95 >= S2V2_MINIMUM_COVERAGE
    bias_pass = abs_mean_signed_error <= S2V2_BIAS_TOLERANCE_M2_PER_S
    return coverage_pass, bias_pass, (QUALIFIED if coverage_pass and bias_pass else NOT_QUALIFIED)

def build_qualification_record(*, evaluation_records, method_hash=S2V2_METHOD_HASH, criterion_hash=S2V2_CRITERION_HASH, population_hash=S2V2_HELDOUT_HASH, pre_heldout_acknowledgment_hash, heldout_open_marker_hash, calibration_package_hash, q_hat, execution_code_revision):
    assert_frozen_v2_policy(); assert_frozen_v2_populations()
    if method_hash != S2V2_METHOD_HASH or criterion_hash != S2V2_CRITERION_HASH or population_hash != S2V2_HELDOUT_HASH: _fail("qualification frozen binding mismatch")
    for value in (pre_heldout_acknowledgment_hash, heldout_open_marker_hash, calibration_package_hash):
        if not isinstance(value, str) or len(value) != 64: _fail("qualification provenance hash malformed")
    if not isinstance(execution_code_revision, str) or not execution_code_revision: _fail("qualification execution code revision is missing")
    _finite(q_hat, "q_hat")
    if q_hat < 0: _fail("qualification q_hat must be nonnegative")
    records = list(evaluation_records)
    if len(records) != S2V2_HELDOUT_COUNT: _fail("qualification requires exactly 379 evaluations")
    ids = [r.get("replicate_id") if isinstance(r, dict) else None for r in records]
    if any(not isinstance(r, dict) for r in records) or len(set(ids)) != len(ids) or set(ids) != set(S2V2_HELDOUT_SEEDS): _fail("qualification evaluations are missing, duplicated, or foreign")
    for r in records:
        if (r.get("format") != "s2v2-heldout-evaluation-v2" or r.get("method_hash") != method_hash or r.get("population_hash") != population_hash or r.get("pre_heldout_acknowledgment_hash") != pre_heldout_acknowledgment_hash or r.get("calibration_package_hash") != calibration_package_hash or r.get("q_hat") != q_hat or r.get("code_revision") != execution_code_revision): _fail("qualification evaluation provenance binding is invalid")
        _finite(r.get("signed_error"), "signed_error"); _finite(r.get("absolute_error"), "absolute_error")
        if r.get("absolute_error") != abs(r["signed_error"]) or not isinstance(r.get("covered"), bool): _fail("qualification evaluation derived values are malformed")
    ordered = sorted(records, key=lambda r: r["replicate_id"]); n = len(ordered); covered = sum(r["covered"] for r in ordered)
    signed = [float(r["signed_error"]) for r in ordered]; absolute = [float(r["absolute_error"]) for r in ordered]; mean = sum(signed) / n
    lcb = exact_one_sided_lcb(covered, n, S2V2_HELDOUT_CONFIDENCE); cp, bp, state = classify_qualification(lcb, abs(mean))
    return {"format": QUALIFICATION_FORMAT, "method_hash": method_hash, "criterion_hash": criterion_hash, "heldout_population_hash": population_hash, "pre_heldout_acknowledgment_hash": pre_heldout_acknowledgment_hash, "heldout_open_marker_hash": heldout_open_marker_hash, "calibration_package_hash": calibration_package_hash, "q_hat": float(q_hat), "heldout_execution_code_revision": execution_code_revision, "ordered_evaluation_hashes": [digest(r) for r in ordered], "n_attempted": n, "n_valid": n, "n_covered": covered, "n_missed": n - covered, "coverage": covered / n, "coverage_lcb_95": float(lcb), "mean_signed_error": float(mean), "abs_mean_signed_error": float(abs(mean)), "mean_absolute_error": float(sum(absolute) / n), "coverage_criterion_result": "PASS" if cp else "FAIL", "bias_criterion_result": "PASS" if bp else "FAIL", "final_qualification_state": state}
def persist_qualification_record(*, artifact_root, record):
    directory = inside(Path(artifact_root).resolve(), QUALIFICATION_DIR)
    if directory.exists():
        entries = list(directory.iterdir())
        if len(entries) != 1 or entries[0].suffix != ".json" or not entries[0].is_file() or entries[0].stem != digest(record): _fail("qualification namespace is not exactly one matching record")
    identity = digest(record); data = canonical_bytes(record); path = inside(Path(artifact_root).resolve(), f"{QUALIFICATION_DIR}/{identity}.json")
    append_file(path, data); stored = path.read_bytes()
    if stored != data or json.loads(stored) != record or digest(json.loads(stored)) != identity: _fail("qualification persistence mismatch")
    return {"qualification_hash": identity, "qualification_record": record}
def verify_qualification_record(*, artifact_root, evaluation_records, method_hash=S2V2_METHOD_HASH, criterion_hash=S2V2_CRITERION_HASH, population_hash=S2V2_HELDOUT_HASH, pre_heldout_acknowledgment_hash, heldout_open_marker_hash, calibration_package_hash, q_hat, execution_code_revision):
    """Read once, rebuild from verified evaluations, and compare exact bytes."""
    expected = build_qualification_record(evaluation_records=evaluation_records, method_hash=method_hash, criterion_hash=criterion_hash, population_hash=population_hash, pre_heldout_acknowledgment_hash=pre_heldout_acknowledgment_hash, heldout_open_marker_hash=heldout_open_marker_hash, calibration_package_hash=calibration_package_hash, q_hat=q_hat, execution_code_revision=execution_code_revision)
    directory = inside(Path(artifact_root).resolve(), QUALIFICATION_DIR); entries = list(directory.iterdir()) if directory.is_dir() else []
    if len(entries) != 1 or entries[0].suffix != ".json" or not entries[0].is_file(): _fail("qualification record missing or duplicated")
    data = entries[0].read_bytes()
    try: decoded = json.loads(data)
    except ValueError as exc: _fail(f"qualification record unreadable: {exc}")
    if decoded != expected or canonical_bytes(decoded) != data or digest(decoded) != entries[0].stem: _fail("qualification record does not match verified replay")
    return decoded
