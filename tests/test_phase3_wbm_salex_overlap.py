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

    with WBMStreamingOverlapAuditor(target_db) as auditor:
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


def test_production_request_is_pilot_only_and_fail_closed() -> None:
    root = Path(__file__).resolve().parents[1]
    request = json.loads(
        (root / "data/development/phase3_salex_production_request_v1.json")
        .read_text(encoding="utf-8")
    )

    assert request["enabled"] is True
    assert request["mode"] == "pilot"
    assert request["pilot"]["max_records"] == 10000
    assert request["pilot"]["authoritative"] is False
    assert request["frozen_sources"]["salex"]["expected_records"] == 10447765
    assert request["authorization"]["run_real_source_pilot"] is True
    assert request["authorization"]["full_run_authorized"] is False
    assert request["authorization"]["execute_full_salex_wbm_overlap_audit"] is False
    assert request["authorization"]["unseen_generalization_claim"] is False
