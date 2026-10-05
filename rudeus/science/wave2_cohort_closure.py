"""Append-only, candidate-free closure of the historical P2.5 transition.

Historical Git bytes are verified against the frozen checkpoint. They are not
assigned synthetic TaskSpecs, attempts, or canonical ingestion receipts.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

from rudeus.execution.contracts import ExecutionError
from rudeus.science.contracts import canonical_bytes, digest
from rudeus.science.downstream import CLAIM_IDS, make_out
from rudeus.science.evidence import append_file, inside
from rudeus.science.pipeline_release import ReleaseRecord, RunIdentity


CHECKPOINT = "8c89d1127075e0347daacb8a8e333e13812e7473"
AUTH_PATH = "data/batches/audit/p25_ordered_expansion_wave1_v1_canonical_transition_v1.json"
AUTH_RAW_SHA256 = "d35a9c349497daf26fc3dbd58436d454e70f25b88ad1b2dedf5f093815fff24e"
AUTH_GIT_SHA256 = "05fe1938da2ec7ed55090378a7f2aca8a01cd41470da1dc30b5136070c0ca6f2"
COHORT_ID = "f8fba8e61b232eaa66b8f1475cb02851c2afce9ed1caed8052475b480c2692e1"
PROTOCOL_HASH = "f691326014cdb510"
OUT_DIR = "data/batches/audit/wave2_no_candidate_closure"
FORMAT = "wave2-historical-no-candidate-closure-v1"
NONDIFFUSIVE = frozenset((
    "03bc47ef27166988", "245ce322c5ff3994", "71137be4704df025",
    "9437c63d0446ae9d", "9f7812a466402dd8",
))
P2_FAIL = frozenset(("518ff3ccd9252e6f", "a08649ae5622454d", "f0db485b49bce2f3"))
P2_INDETERMINATE = frozenset(("5369d16d453bfc74",))
EXPECTED_IDS = NONDIFFUSIVE | P2_FAIL | P2_INDETERMINATE
SOURCE_DIRS = {
    "p1": "done_ordered_expansion_wave1_v1",
    "p2": "p2_ordered_expansion_wave1_v1",
    "trajectory": "p2_traj_ordered_expansion_wave1_v1",
    "p25": "p25_ordered_expansion_wave1_v1",
}
TRANSITION_DIRS = {
    "p2": "p2_ordered_expansion_wave1_v1_canonical_transition_v1",
    "trajectory": "p2_traj_ordered_expansion_wave1_v1_canonical_transition_v1",
    "p25": "p25_ordered_expansion_wave1_v1_canonical_transition_v1",
}


def _fail(message):
    raise ExecutionError(message, "INTEGRITY")


def _raw_hash(data):
    return hashlib.sha256(data).hexdigest()


def _read_git_bound(root: Path, relative: str) -> bytes:
    path = inside(root, relative)
    if path.is_symlink() or not path.is_file():
        _fail(f"historical artifact is missing or redirected: {relative}")
    local = path.read_bytes()
    result = subprocess.run(
        ["git", "-C", str(root), "show", f"HEAD:{relative}"],
        capture_output=True, check=False,
    )
    # Windows text checkouts may contain CRLF while Git stores LF. Verify the
    # exact checkout normalization; NPZ and all other binary bytes must match.
    committed_equivalent = local.replace(b"\r\n", b"\n") if path.suffix in (".json", ".py") else local
    if result.returncode or result.stdout != committed_equivalent:
        _fail(f"historical bytes differ from the checkpoint: {relative}")
    return result.stdout


def _record(root: Path, relative: str):
    data = _read_git_bound(root, relative)
    try:
        value = json.loads(data)
    except (UnicodeError, ValueError) as exc:
        _fail(f"historical JSON is unreadable: {relative}: {exc}")
    if not isinstance(value, dict):
        _fail(f"historical JSON is not a record: {relative}")
    return value, {"path": relative, "raw_sha256": _raw_hash(data),
                   "logical_sha256": digest(value), "size_bytes": len(data),
                   "retention": "GIT_COMMITTED_AT_CHECKPOINT",
                   "canonical_ingestion": "VERIFIED_BUT_NOT_CANONICALLY_INGESTED"}


def _trajectory_verifier(root: Path):
    # Import the existing persistence verifier without importing the MLIP
    # package initializer, which loads scientific execution dependencies.
    _read_git_bound(root, "rudeus/mlip/p2_traj.py")
    source = root / "rudeus/mlip/p2_traj.py"
    spec = importlib.util.spec_from_file_location("_wave2_p2_traj_verifier", source)
    if spec is None or spec.loader is None:
        _fail("P2 trajectory verifier is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.verify_traj_artifact


def _trajectory(root: Path, relative: str, expected_logical: str, verify):
    data = _read_git_bound(root, relative)
    try:
        verify(inside(root, relative), expected_logical)
    except Exception as exc:
        _fail(f"trajectory logical hash/structure failed: {relative}: {exc}")
    return {"path": relative, "raw_sha256": _raw_hash(data),
            "logical_sha256": expected_logical, "size_bytes": len(data),
            "retention": "GIT_COMMITTED_AT_CHECKPOINT",
            "canonical_ingestion": "VERIFIED_BUT_NOT_CANONICALLY_INGESTED"}


def _config_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()[:16]


def _path(directory: str, batch_id: str, suffix="json"):
    return f"data/batches/{directory}/{batch_id}.{suffix}"


def build_closure(root: Path):
    """Replay the frozen cohort from committed source bytes; perform no science."""
    root = Path(root).resolve()
    head = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=True).stdout.strip()
    if head != CHECKPOINT and not (root / OUT_DIR / "closure").is_dir():
        _fail("closure outside the checkpoint requires a persisted reference record")
    checkpoint_ref = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "refs/remotes/origin/checkpoint/wave2-software-closed"],
        capture_output=True, text=True, check=False,
    )
    if not checkpoint_ref.returncode and checkpoint_ref.stdout.strip() != CHECKPOINT:
        _fail("software checkpoint ref differs from the required revision")
    auth, auth_ref = _record(root, AUTH_PATH)
    observed_authorization = _raw_hash(inside(root, AUTH_PATH).read_bytes())
    if (auth_ref["raw_sha256"] != AUTH_GIT_SHA256
            or observed_authorization not in (AUTH_RAW_SHA256, AUTH_GIT_SHA256)
            or auth.get("one_shot") is not True
            or auth.get("cohort_identity") != COHORT_ID
            or auth.get("transition_protocol_hash") != PROTOCOL_HASH
            or auth.get("transition_version") != "p25-evidence-sufficiency-transition-v1"
            or auth.get("n_authorized") != 9):
        _fail("frozen transition authorization differs")
    authorized = auth.get("candidates")
    if (not isinstance(authorized, list)
            or [r.get("batch_id") for r in authorized] != sorted(EXPECTED_IDS)
            or _raw_hash(json.dumps(authorized, sort_keys=True, separators=(",", ":")).encode()) != COHORT_ID
            or _config_hash(auth.get("transition_protocol")) != PROTOCOL_HASH):
        _fail("authorization cohort or protocol identity differs")
    if (root / "data/batches/evidence").exists():
        _fail("canonical evidence store exists; audit its receipts before historical closure")
    p25_dir = root / "data/batches" / TRANSITION_DIRS["p25"]
    actual_p25 = {p.stem for p in p25_dir.glob("*.json")}
    if actual_p25 != NONDIFFUSIVE:
        _fail("canonical transition P2.5 inventory differs")
    verify_traj = _trajectory_verifier(root)
    dispositions = []
    for authorized_row in authorized:
        batch_id = authorized_row["batch_id"]
        source, source_refs = {}, {}
        for name in ("p1", "p2", "p25"):
            source[name], source_refs[name] = _record(root, _path(SOURCE_DIRS[name], batch_id))
        transition, transition_refs = {}, {}
        transition["p2"], transition_refs["p2"] = _record(root, _path(TRANSITION_DIRS["p2"], batch_id))
        p1, p2, p25, transitioned = (source["p1"], source["p2"], source["p25"], transition["p2"])
        r1, r2, r25, rt = (p1.get("result") or {}, p2.get("result") or {},
                             p25.get("result") or {}, transitioned.get("result") or {})
        metadata = rt.get("p25_evidence_transition") or {}
        calc = (rt.get("provenance") or {}).get("calc") or {}
        source_calc = (r2.get("provenance") or {}).get("calc") or {}
        seed = (550 + int(batch_id[:8], 16)) % (2 ** 32)
        if (any(v.get("batch_id") != batch_id for v in (p1, p2, p25, transitioned))
                or r1.get("p1_verdict") != "KEEP_FOR_P2"
                or r2.get("p2_verdict") != "PASS"
                or r25.get("transport_state") != "INDETERMINATE"
                or authorized_row.get("relaxed_structure_sha256") != r1.get("relaxed_structure_sha256")
                or r1.get("relaxed_structure_sha256") != r2.get("p2_input_relaxed_sha256")
                or r1.get("relaxed_structure_sha256") != rt.get("p2_input_relaxed_sha256")
                or authorized_row.get("source_p2_trajectory_sha256") != r2.get("trajectory_artifact", {}).get("sha256")
                or authorized_row.get("source_p2_trajectory_sha256") != r25.get("provenance", {}).get("trajectory_artifact_sha256")
                or authorized_row.get("source_p2_trajectory_sha256") != metadata.get("source_p2_trajectory_sha256")
                or authorized_row.get("source_p2_config_hash") != r2.get("p2_config_hash")
                or authorized_row.get("source_p2_protocol_version") != r2.get("p2_protocol_version")
                or authorized_row.get("source_p25_config_hash") != r25.get("provenance", {}).get("p25_config_hash")
                or authorized_row.get("source_p25_config_hash") != _config_hash(p25.get("p25_config"))
                or authorized_row.get("source_p25_config_hash") != metadata.get("source_p25_config_hash")
                or authorized_row.get("source_p2_seed") != seed
                or r2.get("seed") != seed or rt.get("seed") != seed
                or authorized_row.get("source_p2_checkpoint_sha256") != source_calc.get("sha256")
                or source_calc.get("sha256") != calc.get("sha256")
                or authorized_row.get("source_p2_calc_dtype") != source_calc.get("dtype")
                or source_calc.get("dtype") != calc.get("dtype")
                or r2.get("provenance", {}).get("trajectory_sha256") != r2.get("trajectory_artifact", {}).get("sha256")
                or rt.get("provenance", {}).get("trajectory_sha256") != rt.get("trajectory_artifact", {}).get("sha256")
                or rt.get("p2_protocol") != auth.get("transition_protocol")
                or rt.get("p2_config_hash") != PROTOCOL_HASH
                or rt.get("p2_protocol_version") != auth.get("transition_protocol_version")
                or rt.get("p2_verdict") != rt.get("dynamic_state")
                or metadata.get("transition_version") != auth.get("transition_version")
                or metadata.get("cohort_identity") != COHORT_ID
                or metadata.get("transition_protocol_hash") != PROTOCOL_HASH
                or metadata.get("admission_policy") != auth.get("admission_policy")
                or metadata.get("admission_basis") != authorized_row.get("admission_basis")
                or metadata.get("one_shot") is not True
                or calc.get("p25_transition_cohort_identity") != COHORT_ID
                or calc.get("p25_transition_protocol_hash") != PROTOCOL_HASH
                or calc.get("p25_transition_version") != auth.get("transition_version")):
            _fail(f"source or transition provenance mismatch: {batch_id}")
        for name, record, dirs, refs in (
            ("source", r2, SOURCE_DIRS, source_refs),
            ("transition", rt, TRANSITION_DIRS, transition_refs),
        ):
            binding = record.get("trajectory_artifact") or {}
            relative = _path(dirs["trajectory"], batch_id, "npz")
            if binding.get("path") != relative or binding.get("format_version") != "p2-traj-v1":
                _fail(f"{name} trajectory binding differs: {batch_id}")
            refs["trajectory"] = _trajectory(root, relative, binding.get("sha256"), verify_traj)
        state = rt.get("p2_verdict")
        if batch_id in NONDIFFUSIVE:
            if state != "PASS":
                _fail(f"P2.5 terminal member lacks P2 PASS: {batch_id}")
            transition["p25"], transition_refs["p25"] = _record(root, _path(TRANSITION_DIRS["p25"], batch_id))
            result = transition["p25"].get("result") or {}
            provenance = result.get("provenance") or {}
            if (transition["p25"].get("batch_id") != batch_id
                    or result.get("p2_verdict") != "PASS"
                    or result.get("p25_verdict") != "NONDIFFUSIVE"
                    or result.get("transport_state") != "NONDIFFUSIVE"
                    or provenance.get("p25_evidence_transition") != metadata
                    or provenance.get("trajectory_artifact_sha256") != rt["trajectory_artifact"]["sha256"]
                    or provenance.get("p2_config_hash") != PROTOCOL_HASH
                    or provenance.get("p2_seed") != seed
                    or provenance.get("p25_config_hash") != _config_hash(transition["p25"].get("p25_config"))):
                _fail(f"P2.5 result lineage differs: {batch_id}")
            p25_state, terminal, reasons = "NONDIFFUSIVE", True, ["P25_NONDIFFUSIVE_TERMINAL"]
        elif batch_id in P2_FAIL:
            if state != "FAIL" or rt.get("early_stop_reason") != "explosive_termination":
                _fail(f"P2 FAIL disposition differs: {batch_id}")
            p25_state, terminal, reasons = "NOT_RUN", True, ["P2_FAIL_TERMINAL", "EXPLOSIVE_TERMINATION"]
        else:
            if state != "INDETERMINATE" or rt.get("early_stop_reason") != "completed_final_tier":
                _fail(f"P2 INDETERMINATE disposition differs: {batch_id}")
            p25_state, terminal, reasons = "NOT_RUN", False, ["P2_INDETERMINATE", "P25_REQUIRES_P2_PASS"]
        dispositions.append({
            "batch_id": batch_id, "authorization": "AUTHORIZED_ONE_SHOT",
            "execution": "HISTORICAL_EXTENSION_RETAINED", "p2_state": state,
            "p25_state": p25_state, "terminal": terminal,
            "p3_admissible": False, "reason_codes": reasons,
            "source_artifacts": source_refs, "transition_artifacts": transition_refs,
        })
    if len(dispositions) != 9 or {r["batch_id"] for r in dispositions} != EXPECTED_IDS:
        _fail("cohort disposition is incomplete")
    closure = {
        "format": FORMAT, "scientific_status": "NO_P3_QUALIFYING_CANDIDATE",
        "candidate_id": None, "authorization": auth_ref,
        "authorization_prior_checkout_raw_sha256": AUTH_RAW_SHA256,
        "cohort_identity": COHORT_ID, "transition_protocol_hash": PROTOCOL_HASH,
        "transition_protocol_full_hash": digest(auth["transition_protocol"]),
        "source_code_checkpoint": CHECKPOINT,
        "closure_builder_source_sha256": _raw_hash(Path(__file__).read_bytes().replace(b"\r\n", b"\n")),
        "historical_evidence_retention": "GIT_COMMITTED_AT_CHECKPOINT",
        "canonical_ingestion": "VERIFIED_BUT_NOT_CANONICALLY_INGESTED",
        "new_canonical_provider_execution": False,
        "dispositions": dispositions,
        "p3_admissible_count": 0,
        "downstream": {key: "UNKNOWN" for key in ("X", "N", "S", "APPLICATION")},
        "software_qualification": {
            "classification": "SOFTWARE_ONLY",
            "synthetic_e2e_run_id": "37241191846",
            "full_regression_run_id": "37242957977",
            "integrated_head": CHECKPOINT,
            "checkpoint_ref": "checkpoint/wave2-software-closed",
        },
        "limitations": [
            "NO_P3_QUALIFYING_CANDIDATE",
            "HISTORICAL_SCIENCE_NOT_NEW_CANONICAL_REMOTE_E2E",
            "CANONICAL_INGESTION_RECEIPTS_UNAVAILABLE",
            "X_N_S_APPLICATION_EVIDENCE_UNAVAILABLE",
            "REAL_REMOTE_E2E_PASS_NOT_CLAIMED",
        ],
    }
    if head != CHECKPOINT:
        reference = root / OUT_DIR / "closure" / f"{digest(closure)}.json"
        if not reference.is_file() or reference.read_bytes().replace(b"\r\n", b"\n") != canonical_bytes(closure):
            _fail("replayed closure differs from the committed reference record")
    return closure


def assemble_closure_release(closure):
    """Use existing immutable OUT/release types without invented stage receipts."""
    if (closure.get("format") != FORMAT or closure.get("cohort_identity") != COHORT_ID
            or closure.get("scientific_status") != "NO_P3_QUALIFYING_CANDIDATE"
            or closure.get("p3_admissible_count") != 0
            or len(closure.get("dispositions", ())) != 9
            or closure.get("canonical_ingestion") != "VERIFIED_BUT_NOT_CANONICALLY_INGESTED"
            or closure.get("new_canonical_provider_execution") is not False):
        _fail("closure is not a verified no-candidate disposition")
    closure_hash = digest(closure)
    all_logical = tuple(sorted({ref["logical_sha256"] for row in closure["dispositions"]
                            for group in (row["source_artifacts"], row["transition_artifacts"])
                            for ref in group.values()} | {closure["authorization"]["logical_sha256"]}))
    limitations = tuple(sorted(closure["limitations"]))
    out = make_out(
        candidate_id=None, claims={}, stages={}, applicability={},
        protocol_hashes={"transition": closure["transition_protocol_full_hash"]},
        config_hashes={"authorization": closure["authorization"]["logical_sha256"]},
        input_artifact_hashes=all_logical, output_artifact_hashes=(),
        execution_references=(), provenance_references=(closure_hash,),
        scientific_limitations=limitations,
    )
    if (out.final_assessment != "UNKNOWN" or set(out.claim_vector) != set(CLAIM_IDS)
            or any(value != "UNKNOWN" for value in out.claim_vector.values())
            or out.candidate_id is not None):
        _fail("candidate-free OUT promoted an unsupported claim")
    software = closure["software_qualification"]
    record = ReleaseRecord(
        run=RunIdentity(candidate_id=f"cohort:{COHORT_ID}",
                        source_hash=AUTH_GIT_SHA256,
                        pipeline_protocol_hash=closure["transition_protocol_full_hash"],
                        code_revision=CHECKPOINT),
        stage_receipts={}, code_revisions={}, claim_assessment_hashes=(),
        followup_hashes=(), downstream=out.stage_assessments,
        p3_series_hash=None, p3_series_receipt=None, evidence_index={},
        release_evidence={
            "historical_science": (closure_hash,),
            "software_regression": (digest({"scope": "SOFTWARE_ONLY", "run_id": software["full_regression_run_id"], "head": CHECKPOINT}),),
            "synthetic_e2e": (digest({"scope": "SOFTWARE_ONLY", "run_id": software["synthetic_e2e_run_id"], "head": CHECKPOINT}),),
            "production_science": (),
        },
        limitations=limitations, out_hash=out.content_hash,
        qualification={
            "software_regression_reference_present": True,
            "canonical_synthetic_e2e_reference_present": True,
            "historical_science_reference_present": True,
            "production_scientific_reference_present": False,
            "provenance_complete": False,
            "durable_artifacts_complete": False,
            "downstream_complete": False,
            "known_limitations_frozen": True,
            "out_available": True,
            "real_remote_e2e_pass": False,
        },
    )
    return out, record


def persist_closure(root: Path):
    """Verify first; append content-addressed closure, OUT, then release."""
    root = Path(root).resolve()
    closure = build_closure(root)
    out, release = assemble_closure_release(closure)
    closure_dir = root / OUT_DIR / "closure"
    if closure_dir.exists():
        existing = list(closure_dir.iterdir())
        if (closure_dir.is_symlink() or any(path.is_symlink() or not path.is_file()
                or path.name != f"{digest(closure)}.json" for path in existing)):
            _fail("conflicting historical cohort closure already exists")
    items = (("closure", closure), ("out", out.to_dict()),
             ("release", release.to_dict()))
    written = {}
    for kind, value in items:
        identity = digest(value)
        relative = f"{OUT_DIR}/{kind}/{identity}.json"
        data = canonical_bytes(value)
        append_file(inside(root, relative), data)
        if inside(root, relative).read_bytes() != data:
            _fail(f"persisted {kind} bytes differ")
        written[kind] = {"path": relative, "sha256": identity}
    if written["release"]["sha256"] != release.content_hash or written["out"]["sha256"] != out.content_hash:
        _fail("release or OUT content identity differs")
    return written


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--write", action="store_true", help="append verified closure files")
    args = parser.parse_args()
    if args.write:
        print(json.dumps(persist_closure(args.root), sort_keys=True))
    else:
        closure = build_closure(args.root)
        out, release = assemble_closure_release(closure)
        print(json.dumps({"closure": digest(closure), "out": out.content_hash,
                          "release": release.content_hash}, sort_keys=True))


if __name__ == "__main__":
    main()
