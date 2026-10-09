from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

from ase import Atoms
from pymatgen.core import Lattice, Structure

from rhombus.domain import (
    MembershipIndexRecord,
    WBMStreamingOverlapAuditor,
    WBMTargetRecord,
    build_wbm_target_index,
    iter_wbm_initial_structure_jsonl,
    structure_candidate_fingerprint_sha256,
)


def _proto(structure: Structure) -> str:
    return f"fixture:{structure.composition.reduced_formula}"


def _nacl(a: float = 4.0) -> Structure:
    return Structure(
        Lattice.cubic(a),
        ["Na", "Cl"],
        [[0, 0, 0], [0.5, 0.5, 0.5]],
    )


def _li2o() -> Structure:
    return Structure(
        Lattice.cubic(4.2),
        ["Li", "Li", "O"],
        [[0, 0, 0], [0.5, 0.5, 0], [0.25, 0.25, 0.25]],
    )


def test_wbm_jsonl_parser_streams_canonical_columns(tmp_path: Path) -> None:
    path = tmp_path / "wbm.jsonl.gz"
    row = {
        "material_id": "wbm-1",
        "formula_from_cse": "NaCl",
        "initial_structure": _nacl().as_dict(),
    }
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")

    records = tuple(iter_wbm_initial_structure_jsonl(path))

    assert len(records) == 1
    assert records[0].material_id == "wbm-1"
    assert records[0].structure.composition.reduced_formula == "NaCl"


def test_one_pass_auditor_tracks_overlap_but_keeps_unseen_unresolved(
    tmp_path: Path,
) -> None:
    target_db = tmp_path / "targets.sqlite"
    source_sha = hashlib.sha256(b"wbm-source").hexdigest()
    targets = (
        WBMTargetRecord("wbm-nacl", _nacl()),
        WBMTargetRecord("wbm-li2o", _li2o()),
    )
    summary = build_wbm_target_index(
        targets,
        target_db,
        source_file_sha256=source_sha,
        fingerprint=structure_candidate_fingerprint_sha256,
        prototype_group=_proto,
        batch_size=1,
    )
    assert summary.row_count == 2

    exact_atoms = Atoms(
        "NaCl",
        scaled_positions=[[0, 0, 0], [0.5, 0.5, 0.5]],
        cell=[4.0, 4.0, 4.0],
        pbc=True,
    )
    exact_record = MembershipIndexRecord(
        dataset_id="sAlex",
        record_id="sAlex#0",
        source_locator="sAlex#0",
        composition_key="NaCl",
        site_count=2,
        structure_fingerprint_sha256=structure_candidate_fingerprint_sha256(
            _nacl()
        ),
        prototype_group=_proto(_nacl()),
    )
    prototype_only_record = MembershipIndexRecord(
        dataset_id="sAlex",
        record_id="sAlex#1",
        source_locator="sAlex#1",
        composition_key="KCl",
        site_count=2,
        structure_fingerprint_sha256=hashlib.sha256(b"no-candidate").hexdigest(),
        prototype_group=_proto(_li2o()),
    )

    with WBMStreamingOverlapAuditor(target_db, allow_custom_prototype_for_fixture=True) as auditor:
        auditor.observe(exact_record, exact_atoms)
        auditor.observe(prototype_only_record, exact_atoms)
        rows = {row.material_id: row for row in auditor.material_records()}
        audit_summary = auditor.summary()

    assert rows["wbm-nacl"].exact_training_match is True
    assert rows["wbm-nacl"].near_duplicate_match is True
    assert rows["wbm-nacl"].prototype_overlap is True
    assert rows["wbm-li2o"].exact_training_match is False
    assert rows["wbm-li2o"].prototype_overlap is True
    assert audit_summary.material_count == 2
    assert audit_summary.unseen_generalization_eligible_count == 0
    assert audit_summary.unresolved_count == 2


def test_target_index_fails_closed_on_duplicate_material_id(tmp_path: Path) -> None:
    target_db = tmp_path / "targets.sqlite"
    source_sha = hashlib.sha256(b"wbm-source").hexdigest()
    duplicate = (
        WBMTargetRecord("wbm-1", _nacl()),
        WBMTargetRecord("wbm-1", _li2o()),
    )

    try:
        build_wbm_target_index(
            duplicate,
            target_db,
            source_file_sha256=source_sha,
            fingerprint=structure_candidate_fingerprint_sha256,
            prototype_group=_proto,
            batch_size=1,
        )
    except Exception:
        pass
    else:
        raise AssertionError("duplicate material IDs must fail closed")

    assert target_db.exists() is False
    assert Path(f"{target_db}-wal").exists() is False
    assert Path(f"{target_db}-shm").exists() is False


def test_production_request_is_disabled_after_pilot_and_full_run_fail_closed() -> None:
    root = Path(__file__).resolve().parents[1]
    request = json.loads(
        (root / "data/development/phase3_salex_production_request_v1.json")
        .read_text(encoding="utf-8")
    )

    assert request["enabled"] is False
    assert request["mode"] == "pilot"
    assert request["pilot"]["max_records"] == 10000
    assert request["pilot"]["authoritative"] is False
    assert request["frozen_sources"]["salex"]["expected_records"] == 10447765
    assert request["authorization"]["run_real_source_pilot"] is False
    assert request["authorization"]["full_run_authorized"] is False
    assert request["authorization"]["execute_full_salex_wbm_overlap_audit"] is False
    assert request["authorization"]["unseen_generalization_claim"] is False


def test_captured_pilot_evidence_is_non_authoritative_and_selects_kaggle_cpu() -> None:
    root = Path(__file__).resolve().parents[1]
    evidence = json.loads(
        (root / "data/development/phase3_salex_throughput_pilot_evidence_v1.json")
        .read_text(encoding="utf-8")
    )

    assert evidence["status"] == "CAPTURED_NON_AUTHORITATIVE_PILOT"
    assert evidence["source"]["workflow_run_id"] == 37640287365
    assert evidence["source"]["head_sha"] == "93a2114d0d7be10a20c59303027a2f09a78b6ec6"
    assert evidence["measured"]["processed_records"] == 10000
    assert evidence["measured"]["elapsed_seconds"] == 16.87076601400001
    assert evidence["measured"]["records_per_second"] == 592.7413130916293
    assert evidence["measured"]["naive_full_stream_estimate_hours"] == 4.8961610745627455
    assert evidence["backend_decision"]["selected_full_run_backend"] == "KAGGLE_CPU"
    assert evidence["backend_decision"]["github_actions_full_run_selected"] is False
    assert evidence["authorization"]["full_run_authorized"] is False
    assert evidence["authorization"]["unseen_generalization_claim"] is False



def test_target_index_marks_fixture_callbacks_as_unattested(tmp_path):
    import sqlite3
    db = tmp_path / "custom-targets.sqlite"
    build_wbm_target_index(
        [WBMTargetRecord("wbm-fixture", _nacl())],
        db,
        source_file_sha256=hashlib.sha256(b"source").hexdigest(),
        fingerprint=structure_candidate_fingerprint_sha256,
        prototype_group=_proto,
    )
    with sqlite3.connect(db) as connection:
        metadata = dict(connection.execute("SELECT key, value FROM metadata"))
    assert metadata["candidate_fingerprint_protocol_id"] == (
        "rhombus-reduced-composition-candidate-fingerprint-v2"
    )
    assert metadata["prototype_group_protocol_id"] == "CUSTOM_UNATTESTED"


def test_empty_production_index_records_frozen_protocol_metadata(tmp_path):
    import sqlite3
    db = tmp_path / "frozen-protocols.sqlite"
    # The empty fixture is deliberate: it checks the production callback
    # binding without needing the separate frozen Matbench prototype runtime.
    build_wbm_target_index(
        [],
        db,
        source_file_sha256=hashlib.sha256(b"source").hexdigest(),
    )
    with sqlite3.connect(db) as connection:
        metadata = dict(connection.execute("SELECT key, value FROM metadata"))
    assert metadata["candidate_fingerprint_protocol_id"] == (
        "rhombus-reduced-composition-candidate-fingerprint-v2"
    )
    assert metadata["prototype_group_protocol_id"] == (
        "matbench-protostructure-label-v1"
    )



def _sample_source_only_jsonl():
    return b"".join(
        (json.dumps({
            "material_id": id_, "exact_training_match": e,
            "near_duplicate_match": n, "prototype_overlap": p,
            "audit_basis_ids": [],
        }, sort_keys=True) + "\n").encode()
        for id_, e, n, p in (
            ("wbm-1", True, True, False),
            ("wbm-2", False, True, True),
            ("wbm-3", False, False, False),
            ("wbm-4", False, False, True),
        )
    )


def test_preserved_salex_triage_source_only_union_and_intersections():
    import io
    from scripts.development.analyze_preserved_salex_wbm_overlap import analyze_rows
    raw = _sample_source_only_jsonl()
    got = analyze_rows(io.BytesIO(raw), expected_rows=4,
                       expected_raw_sha256=hashlib.sha256(raw).hexdigest())
    assert got["exact_source_matches"] == 1
    assert got["near_source_matches"] == 2
    assert got["prototype_source_matches"] == 2
    assert got["exact_and_near"] == 1
    assert got["near_and_prototype"] == 1
    assert got["positive_source_overlap_union"] == 3
    assert got["no_detected_salex_source_overlap_but_training_unresolved"] == 1


def test_preserved_salex_triage_fail_closed_on_duplicate_or_unsorted_materials():
    import io
    import pytest
    from scripts.development.analyze_preserved_salex_wbm_overlap import analyze_rows
    raw = _sample_source_only_jsonl()
    rows = raw.splitlines(keepends=True)
    altered = rows[1] + rows[0] + b"".join(rows[2:])
    with pytest.raises(ValueError, match="unordered"):
        analyze_rows(io.BytesIO(altered), expected_rows=4,
                     expected_raw_sha256=hashlib.sha256(altered).hexdigest())


def test_preserved_salex_triage_invalid_flag_and_incomplete_archive():
    import io
    import pytest
    from scripts.development.analyze_preserved_salex_wbm_overlap import analyze_rows
    raw = _sample_source_only_jsonl()
    with pytest.raises(ValueError, match="incomplete"):
        analyze_rows(io.BytesIO(raw), expected_rows=5,
                     expected_raw_sha256=hashlib.sha256(raw).hexdigest())
    invalid = raw.replace(b'"near_duplicate_match": true',
                          b'"near_duplicate_match": 1')
    with pytest.raises(ValueError, match="booleans"):
        analyze_rows(io.BytesIO(invalid), expected_rows=4,
                     expected_raw_sha256=hashlib.sha256(invalid).hexdigest())


def test_preserved_salex_triage_rejects_nonempty_model_audit_basis():
    import io
    import pytest
    from scripts.development.analyze_preserved_salex_wbm_overlap import analyze_rows
    raw = _sample_source_only_jsonl()
    invalid = raw.replace(b'"audit_basis_ids": []',
                          b'"audit_basis_ids": ["MACE-approved"]', 1)
    with pytest.raises(ValueError, match="unresolved"):
        analyze_rows(io.BytesIO(invalid), expected_rows=4,
                     expected_raw_sha256=hashlib.sha256(invalid).hexdigest())


def test_preserved_salex_triage_rejects_summary_promoted_to_unseen():
    import pytest
    from scripts.development.analyze_preserved_salex_wbm_overlap import (
        analyze_rows, validate_preserved_summary,
        EXPECTED_WBM_SOURCE_SHA256, EXPECTED_SALEX_SOURCE_SHA256,
    )
    import io
    raw = _sample_source_only_jsonl()
    analysis = analyze_rows(io.BytesIO(raw), expected_rows=4,
                            expected_raw_sha256=hashlib.sha256(raw).hexdigest())
    summary = {
        "schema_version": "rhombus-v2-salex-wbm-production-overlap-v1",
        "mode": "PRODUCTION_COMPLETE_SOURCE_STREAM",
        "wbm_target_count": 4, "wbm_source_sha256": EXPECTED_WBM_SOURCE_SHA256,
        "salex_source_sha256": EXPECTED_SALEX_SOURCE_SHA256,
        "salex_membership_row_count": 10447765,
        "overlap_jsonl_sha256": hashlib.sha256(raw).hexdigest(),
        "full_training_lineage_resolved": False,
        "unseen_generalization_claim_authorized": False,
        "remaining_blocker": "MPTRJ_TRAINING_REPRESENTATION_UNATTESTED",
        "audit_summary": {
            "material_count": 4, "exact_match_count": 1,
            "near_duplicate_count": 2, "prototype_overlap_count": 2,
            "unresolved_count": 4, "unseen_generalization_eligible_count": 0,
        }
    }
    validate_preserved_summary(summary, analysis)
    summary["unseen_generalization_claim_authorized"] = True
    with pytest.raises(ValueError, match="identity/scientific scope"):
        validate_preserved_summary(summary, analysis)


def test_preserved_salex_triage_rejects_wrong_raw_digest_and_duplicate_json_keys():
    import io
    import pytest
    from scripts.development.analyze_preserved_salex_wbm_overlap import analyze_rows
    raw = _sample_source_only_jsonl()
    with pytest.raises(ValueError, match="raw SHA256"):
        analyze_rows(io.BytesIO(raw), expected_rows=4,
                     expected_raw_sha256="0"*64)
    duplicate = raw.replace(b'"material_id": "wbm-1"',
                            b'"material_id": "wbm-1", "material_id": "wbm-1"',1)
    with pytest.raises(ValueError, match="duplicate JSON field"):
        analyze_rows(io.BytesIO(duplicate), expected_rows=4,
                     expected_raw_sha256=hashlib.sha256(duplicate).hexdigest())



def test_real_preserved_salex_wbm_union_evidence_is_source_only_and_arithmetic_frozen():
    root = Path(__file__).resolve().parents[1]
    data = json.loads(
        (root / "data/development/phase3_salex_preserved_source_overlap_union_observation_v1.json")
        .read_text(encoding="utf-8")
    )
    from scripts.development.analyze_preserved_salex_wbm_overlap import (
        EXPECTED_COMPRESSED_SHA256, EXPECTED_SUMMARY_SHA256, EXPECTED_RAW_SHA256,
        EXPECTED_WBM_ROWS, EXPECTED_SALEX_SOURCE_SHA256, EXPECTED_WBM_SOURCE_SHA256,
    )
    p = data["source_provenance"]
    c = data["wbms"]
    assert p["archive_sha256"] == EXPECTED_COMPRESSED_SHA256
    assert p["summary_sha256"] == EXPECTED_SUMMARY_SHA256
    assert p["decompressed_overlap_jsonl_sha256"] == EXPECTED_RAW_SHA256
    assert p["wbm_original_source_sha256"] == EXPECTED_WBM_SOURCE_SHA256
    assert p["salex_original_source_sha256"] == EXPECTED_SALEX_SOURCE_SHA256
    assert c["total"] == EXPECTED_WBM_ROWS
    assert c["exact"] == c["exact_only"] == 0
    assert c["near"] == c["near_only"] + c["near_and_prototype"]
    assert c["prototype"] == c["prototype_only"] + c["near_and_prototype"]
    assert c["near_and_prototype"] == 14
    assert c["distinct_positive_source_overlap_union"] == (
        c["near_only"] + c["prototype_only"] + c["near_and_prototype"]
    ) == 1946
    assert c["no_detected_salex_source_overlap_but_training_unresolved"] == (
        c["total"] - c["distinct_positive_source_overlap_union"]
    ) == 255017
    assert all(value is True for k, value in data["verification"].items()
               if k.endswith(("_matched", "_unique", "_boolean")) and isinstance(value, bool))
    assert all(value is False for value in data["scientific_authorization"].values()
               if isinstance(value, bool))



def test_wbm_target_v2_fingerprint_same_for_supercell_different_site_counts(tmp_path):
    import sqlite3
    base = _nacl()
    supercell = base.copy()
    supercell.make_supercell([2, 1, 1])
    db = tmp_path / "composition-v2-targets.sqlite"
    build_wbm_target_index(
        [WBMTargetRecord("wbm-one", base), WBMTargetRecord("wbm-two", supercell)],
        db, source_file_sha256="b"*64, prototype_group=_proto,
    )
    with sqlite3.connect(db) as c:
        records = c.execute(
            "SELECT site_count, candidate_fingerprint_sha256 FROM targets ORDER BY material_id"
        ).fetchall()
        metadata = dict(c.execute("SELECT key, value FROM metadata"))
    assert [x[0] for x in records] == [2, 4]
    assert records[0][1] == records[1][1]
    assert metadata["candidate_fingerprint_protocol_id"] == (
        "rhombus-reduced-composition-candidate-fingerprint-v2"
    )



def test_salex_auditor_refuses_stale_v1_index_before_source_consumption(tmp_path):
    import sqlite3
    import pytest
    db = tmp_path / "legacy-v1.sqlite"
    build_wbm_target_index(
        [WBMTargetRecord("wbm", _nacl())], db,
        source_file_sha256="c"*64, prototype_group=_proto,
    )
    with sqlite3.connect(db) as connection:
        connection.execute(
            "UPDATE metadata SET value = ? WHERE key = ?",
            ("rhombus-composition-site-count-candidate-fingerprint-v1",
             "candidate_fingerprint_protocol_id"),
        )
        connection.commit()
    with pytest.raises(ValueError, match="old v1"):
        WBMStreamingOverlapAuditor(
            db, allow_custom_prototype_for_fixture=True,
        )
