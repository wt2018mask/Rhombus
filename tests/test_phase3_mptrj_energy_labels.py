"""Phase 3 MPTrj energy-label semantics and MACE-MPA-0 non-attestation."""
from __future__ import annotations

import io
import json

import pytest
from pymatgen.core import Lattice, Structure

from rhombus.domain.mptrj import iter_mptrj_frames
from rhombus.domain.mptrj_energy_labels import (
    MPTrjEnergyLabelError,
    inspect_mptrj_frame_energy_labels,
    require_mace_mpa0_energy_training_label_provenance,
)


def _frame(*, raw=-30.1, corrected=-31.5, per_atom=-15.75):
    structure = Structure(Lattice.cubic(4), ["Li", "O"], [[0, 0, 0], [0.5, 0.5, 0.5]])
    return {
        "structure": structure.as_dict(),
        "uncorrected_total_energy": raw,
        "corrected_total_energy": corrected,
        "energy_per_atom": per_atom,
    }


def test_original_frame_raw_and_chgnet_corrected_labels_are_separate():
    evidence = inspect_mptrj_frame_energy_labels(_frame())
    assert evidence.raw_vasp_total_energy_ev == -30.1
    assert evidence.mp2020_corrected_total_energy_ev == -31.5
    assert evidence.chgnet_mp2020_corrected_energy_per_atom_ev == -15.75
    assert evidence.raw_and_corrected_total_energy_differ is True
    assert evidence.source_label_identity == "CHGNET_MPTRJ_ORIGINAL_JSON"
    assert evidence.model_training_label_identity == "MACE_MPA0_EXACT_LABEL_SELECTION_UNATTESTED"
    assert evidence.allows_energy_calibration_from_this_frame is False
    assert evidence.raw_label_can_be_assumed_mace_mpa0_training_target is False
    assert evidence.corrected_label_can_be_assumed_mace_mpa0_training_target is False


def test_absent_energies_are_missing_not_zero_and_cannot_authorize_calibration():
    evidence = inspect_mptrj_frame_energy_labels({"structure": _frame()["structure"]})
    assert evidence.raw_vasp_total_energy_ev is None
    assert evidence.mp2020_corrected_total_energy_ev is None
    assert evidence.chgnet_mp2020_corrected_energy_per_atom_ev is None
    assert evidence.raw_and_corrected_total_energy_differ is None
    assert evidence.allows_energy_calibration_from_this_frame is False


def test_identical_raw_and_corrected_labels_still_do_not_attest_training():
    evidence = inspect_mptrj_frame_energy_labels(_frame(raw=-30.1, corrected=-30.1))
    assert evidence.raw_and_corrected_total_energy_differ is False
    with pytest.raises(MPTrjEnergyLabelError, match="UNATTESTED"):
        require_mace_mpa0_energy_training_label_provenance(evidence)


@pytest.mark.parametrize("invalid", [True, False, "1.5", [], {}, float("nan"), float("inf"), -float("inf")])
def test_invalid_numeric_energies_fail_closed(invalid):
    with pytest.raises(MPTrjEnergyLabelError, match="finite numeric"):
        inspect_mptrj_frame_energy_labels({"energy_per_atom": invalid})


def test_streaming_mptrj_parser_preserves_label_identity_without_training_claim():
    payload = {"mp-1": {"task-0": _frame()}}
    data = io.BytesIO(json.dumps(payload).encode("utf-8"))
    row = next(iter_mptrj_frames(data))
    assert row.energy_provenance is not None
    assert row.energy_provenance.chgnet_mp2020_corrected_energy_per_atom_ev == -15.75
    assert row.energy_provenance.raw_vasp_total_energy_ev == -30.1
    assert row.energy_provenance.allows_energy_calibration_from_this_frame is False


def test_mptrj_original_label_semantics_evidence_and_scientific_gates():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    record = json.loads(
        (root / "data/development/phase3_mptrj_energy_label_lineage_evidence_v1.json")
        .read_text(encoding="utf-8")
    )
    assert record["original_mptrj"]["energy_per_atom"]["semantic"] == "CHGNET_MP2020_CORRECTED_EV_PER_ATOM"
    assert record["original_mptrj"]["uncorrected_total_energy"]["semantic"] == "VASP_RAW_DFT_TOTAL_ENERGY_EV"
    assert record["mace_public_documentation"]["mace_mp_raw_vasp_training_energy_claim"] is True
    assert record["mace_public_documentation"]["mace_mpa_0_exact_training_energy_label_attested"] is False
    assert record["authorization"]["mptrj_energy_as_mace_mpa0_training_reference"] is False
    assert record["authorization"]["unseen_generalization_claim"] is False
