"""Replay-verified immutable closure for the frozen S2 v2 qualification."""
from __future__ import annotations

import json
from pathlib import Path

from rudeus.execution.contracts import ExecutionError
from rudeus.science.calibration_s2v2_qualification import (
    NOT_QUALIFIED,
    QUALIFICATION_DIR,
    QUALIFICATION_FORMAT,
    QUALIFIED,
    verify_qualification_record,
)
from rudeus.science.contracts import canonical_bytes, digest, require_hash
from rudeus.science.evidence import append_file, inside
from rudeus.science.run_s2v2_heldout import EVALUATION_DIR

CLOSURE_FORMAT = "s2v2-scientific-closure-v1"
CLOSURE_DIR = "s2v2_scientific_closure"
SCIENTIFIC_SCOPE = (
    "S2 v2 frozen in-scope isotropic Brownian validation contract"
)
_OPEN_DIR = "heldout_open"
_EXPECTED_EVALUATION_COUNT = 379


def _fail(message):
    raise ExecutionError(message, "INTEGRITY")


def _namespace(root, relative):
    root = Path(root).resolve()
    candidate = root / relative
    if candidate.is_symlink():
        _fail(f"closure namespace cannot be a symlink: {relative}")
    return inside(root, relative)


def _read_canonical_record(path, *, expected_hash, label):
    try:
        data = path.read_bytes()
        record = json.loads(data)
    except (OSError, ValueError) as exc:
        _fail(f"{label} is unreadable: {exc}")
    if (not isinstance(record, dict) or data != canonical_bytes(record)
            or digest(record) != expected_hash):
        _fail(f"{label} is not canonical or its content hash is invalid")
    return record


def _read_qualification(artifact_root, qualification_hash):
    try:
        require_hash(qualification_hash)
    except (TypeError, ValueError) as exc:
        _fail(f"qualification hash is malformed: {exc}")
    root = Path(artifact_root).resolve()
    directory = _namespace(root, QUALIFICATION_DIR)
    if not directory.is_dir():
        _fail("qualification record is missing")
    entries = sorted(directory.iterdir())
    if (len(entries) != 1 or entries[0].is_symlink()
            or not entries[0].is_file() or entries[0].suffix != ".json"
            or entries[0].name != f"{qualification_hash}.json"):
        _fail("qualification artifact is missing, duplicate, or ambiguous")
    path = inside(root, f"{QUALIFICATION_DIR}/{qualification_hash}.json")
    qualification = _read_canonical_record(
        path, expected_hash=qualification_hash, label="qualification record")
    if qualification.get("format") != QUALIFICATION_FORMAT:
        _fail("qualification record format is unsupported")
    return qualification


def _read_evaluations_for_replay(artifact_root, qualification):
    """Load only the exact canonical evaluation inventory bound by the record."""
    hashes = qualification.get("ordered_evaluation_hashes")
    if (not isinstance(hashes, list) or len(hashes) != _EXPECTED_EVALUATION_COUNT
            or any(not isinstance(value, str) for value in hashes)
            or len(set(hashes)) != len(hashes)):
        _fail("qualification evaluation hash inventory is malformed")
    try:
        for value in hashes:
            require_hash(value)
    except (TypeError, ValueError) as exc:
        _fail(f"qualification evaluation hash inventory is malformed: {exc}")

    root = Path(artifact_root).resolve()
    directory = _namespace(root, EVALUATION_DIR)
    if not directory.is_dir():
        _fail("qualification source evaluation namespace is missing")
    entries = sorted(directory.iterdir())
    if (len(entries) != _EXPECTED_EVALUATION_COUNT
            or any(path.is_symlink() or not path.is_file()
                   or path.suffix != ".json" for path in entries)
            or {path.stem for path in entries} != set(hashes)):
        _fail("qualification source evaluation inventory is missing, duplicate, or foreign")
    records = []
    for entry in entries:
        path = inside(root, f"{EVALUATION_DIR}/{entry.name}")
        records.append(_read_canonical_record(
            path, expected_hash=entry.stem, label="qualification source evaluation"))

    # The qualification replay checks all statistical summaries and the
    # ordered hashes. It does not itself verify the HELDOUT-open record, so
    # verify that content-addressed provenance link against the summary here.
    marker_hash = qualification.get("heldout_open_marker_hash")
    try:
        require_hash(marker_hash)
    except (TypeError, ValueError) as exc:
        _fail(f"qualification open-marker hash is malformed: {exc}")
    marker_dir = _namespace(root, _OPEN_DIR)
    if not marker_dir.is_dir():
        _fail("qualification open-marker namespace is missing")
    marker_entries = list(marker_dir.iterdir())
    if (len(marker_entries) != 1 or marker_entries[0].is_symlink()
            or not marker_entries[0].is_file()
            or marker_entries[0].name != f"{marker_hash}.json"):
        _fail("qualification open-marker artifact is missing or ambiguous")
    marker_path = inside(root, f"{_OPEN_DIR}/{marker_hash}.json")
    marker = _read_canonical_record(
        marker_path, expected_hash=marker_hash, label="HELDOUT-open marker")
    expected_marker_bindings = {
        "format": "s2v2-heldout-open-v1",
        "transition": "OPEN",
        "previous_status": "UNOPENED",
        "heldout_status": "OPENED",
        "pre_heldout_acknowledgment_hash":
            qualification.get("pre_heldout_acknowledgment_hash"),
        "method_hash": qualification.get("method_hash"),
        "criterion_hash": qualification.get("criterion_hash"),
        "heldout_population_hash": qualification.get("heldout_population_hash"),
        "calibration_package_hash": qualification.get("calibration_package_hash"),
        "q_hat": qualification.get("q_hat"),
        "heldout_execution_code_revision":
            qualification.get("heldout_execution_code_revision"),
    }
    if any(marker.get(key) != value
           for key, value in expected_marker_bindings.items()):
        _fail("qualification open-marker provenance does not match")
    return records


def _replay_qualification(artifact_root, qualification_hash):
    qualification = _read_qualification(artifact_root, qualification_hash)
    evaluation_records = _read_evaluations_for_replay(
        artifact_root, qualification)
    # Method, criterion, and population use the existing verifier's frozen
    # defaults. Other bindings are compared against the exact evaluations.
    replayed = verify_qualification_record(
        artifact_root=artifact_root,
        evaluation_records=evaluation_records,
        pre_heldout_acknowledgment_hash=
            qualification.get("pre_heldout_acknowledgment_hash"),
        heldout_open_marker_hash=qualification.get("heldout_open_marker_hash"),
        calibration_package_hash=qualification.get("calibration_package_hash"),
        q_hat=qualification.get("q_hat"),
        execution_code_revision=
            qualification.get("heldout_execution_code_revision"),
    )
    if replayed != qualification:
        _fail("qualification replay differs from the retained record")
    return replayed


def build_s2v2_closure_record(verified_qualification_record,
                              qualification_hash, closure_code_revision):
    """Pure builder; source record must already have passed strict replay."""
    try:
        require_hash(qualification_hash)
    except (TypeError, ValueError) as exc:
        _fail(f"qualification hash is malformed: {exc}")
    if (not isinstance(verified_qualification_record, dict)
            or digest(verified_qualification_record) != qualification_hash):
        _fail("verified qualification record/hash binding mismatch")
    if verified_qualification_record.get("format") != QUALIFICATION_FORMAT:
        _fail("qualification record format is unsupported")
    if verified_qualification_record.get("final_qualification_state") != QUALIFIED:
        raise ExecutionError(
            "only a replay-verified QUALIFIED result can be scientifically closed",
            "UNSUPPORTED_INPUT")
    if (verified_qualification_record.get("coverage_criterion_result") != "PASS"
            or verified_qualification_record.get("bias_criterion_result") != "PASS"):
        _fail("QUALIFIED record does not have both required criterion results")
    if (not isinstance(closure_code_revision, str)
            or not closure_code_revision):
        _fail("closure code revision is missing")

    source = verified_qualification_record
    return {
        "format": CLOSURE_FORMAT,
        "phase": "CLOSED",
        "scientific_status": QUALIFIED,
        "scientific_scope": SCIENTIFIC_SCOPE,
        "qualification_record_hash": qualification_hash,
        "method_hash": source["method_hash"],
        "criterion_hash": source["criterion_hash"],
        "heldout_population_hash": source["heldout_population_hash"],
        "calibration_package_hash": source["calibration_package_hash"],
        "pre_heldout_acknowledgment_hash":
            source["pre_heldout_acknowledgment_hash"],
        "heldout_open_marker_hash": source["heldout_open_marker_hash"],
        "heldout_execution_code_revision":
            source["heldout_execution_code_revision"],
        "q_hat": source["q_hat"],
        "n_attempted": source["n_attempted"],
        "n_valid": source["n_valid"],
        "n_covered": source["n_covered"],
        "n_missed": source["n_missed"],
        "coverage": source["coverage"],
        "coverage_lcb_95": source["coverage_lcb_95"],
        "coverage_criterion_result": source["coverage_criterion_result"],
        "mean_signed_error": source["mean_signed_error"],
        "abs_mean_signed_error": source["abs_mean_signed_error"],
        "mean_absolute_error": source["mean_absolute_error"],
        "bias_criterion_result": source["bias_criterion_result"],
        "final_qualification_state": source["final_qualification_state"],
        "closure_code_revision": closure_code_revision,
    }


def _scan_closure_namespace(artifact_root):
    root = Path(artifact_root).resolve()
    directory = _namespace(root, CLOSURE_DIR)
    if not directory.is_dir():
        return directory, []
    entries = sorted(directory.iterdir())
    decoded = []
    for entry in entries:
        if entry.is_symlink() or not entry.is_file() or entry.suffix != ".json":
            _fail("scientific-closure namespace contains an unexpected entry")
        path = inside(root, f"{CLOSURE_DIR}/{entry.name}")
        record = _read_canonical_record(
            path, expected_hash=entry.stem, label="scientific closure record")
        if (record.get("format") != CLOSURE_FORMAT
                or not isinstance(record.get("qualification_record_hash"), str)):
            _fail("scientific-closure record has an unsupported identity")
        decoded.append((entry.name, path, record))
    return directory, decoded


def persist_s2v2_closure_record(*, artifact_root, record):
    """Append a closure, idempotently accepting only identical prior bytes."""
    if not isinstance(record, dict) or record.get("format") != CLOSURE_FORMAT:
        _fail("scientific-closure record is malformed")
    try:
        require_hash(record.get("qualification_record_hash"))
    except (TypeError, ValueError) as exc:
        _fail(f"scientific-closure qualification binding is malformed: {exc}")
    qualification_hash = record["qualification_record_hash"]
    qualification = _replay_qualification(artifact_root, qualification_hash)
    expected = build_s2v2_closure_record(
        qualification, qualification_hash, record.get("closure_code_revision"))
    if record != expected:
        _fail("scientific-closure record does not match qualification replay")
    identity = digest(record)
    data = canonical_bytes(record)
    _, existing = _scan_closure_namespace(artifact_root)
    same_qualification = [
        (name, path, value) for name, path, value in existing
        if value.get("qualification_record_hash")
        == record["qualification_record_hash"]
    ]
    if len(same_qualification) > 1:
        _fail("conflicting closures exist for this qualification identity")
    if same_qualification:
        name, path, prior = same_qualification[0]
        if name != f"{identity}.json" or prior != record or path.read_bytes() != data:
            _fail("conflicting closure exists for this qualification identity")
        return {"closure_hash": identity, "closure_record": record}

    root = Path(artifact_root).resolve()
    path = inside(root, f"{CLOSURE_DIR}/{identity}.json")
    append_file(path, data)
    try:
        stored = path.read_bytes()
        decoded = json.loads(stored)
    except (OSError, ValueError) as exc:
        _fail(f"scientific-closure persistence re-read failed: {exc}")
    if stored != data or decoded != record or digest(decoded) != identity:
        _fail("scientific-closure persistence mismatch")
    return {"closure_hash": identity, "closure_record": record}


def create_s2v2_scientific_closure(*, artifact_root, qualification_hash,
                                   closure_code_revision):
    """Replay the exact qualification before creating one immutable closure."""
    qualification = _replay_qualification(artifact_root, qualification_hash)
    record = build_s2v2_closure_record(
        qualification, qualification_hash, closure_code_revision)
    persisted = persist_s2v2_closure_record(
        artifact_root=artifact_root, record=record)
    replayed = verify_s2v2_scientific_closure(
        artifact_root=artifact_root, closure_hash=persisted["closure_hash"])
    if replayed != record:
        _fail("scientific-closure replay differs from the created record")
    return {**persisted, "replayed": "VERIFIED"}


def verify_s2v2_scientific_closure(*, artifact_root, closure_hash):
    """Re-read closure and qualification, replay, rebuild, and compare."""
    try:
        require_hash(closure_hash)
    except (TypeError, ValueError) as exc:
        _fail(f"scientific-closure hash is malformed: {exc}")
    directory, records = _scan_closure_namespace(artifact_root)
    if not directory.is_dir():
        _fail("scientific-closure record is missing")
    matches = [(name, path, record) for name, path, record in records
               if name == f"{closure_hash}.json"]
    if len(matches) != 1:
        _fail("scientific-closure record is missing or ambiguous")
    _, path, stored = matches[0]
    qualification_hash = stored.get("qualification_record_hash")
    qualification = _replay_qualification(artifact_root, qualification_hash)
    expected = build_s2v2_closure_record(
        qualification, qualification_hash, stored.get("closure_code_revision"))
    data = path.read_bytes()
    if (stored != expected or data != canonical_bytes(expected)
            or digest(stored) != closure_hash):
        _fail("scientific-closure record does not match qualification replay")
    same_qualification = [
        record for _, _, record in records
        if record.get("qualification_record_hash") == qualification_hash
    ]
    if len(same_qualification) != 1:
        _fail("scientific-closure identity is duplicate or conflicting")
    return expected
