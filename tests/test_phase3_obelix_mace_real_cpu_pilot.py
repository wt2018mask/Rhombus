"""Real inference 0145: fixture geometry and fake MACE prove fail-closed routing.

Fake calculator here is NOT real model inference; only 0145 GitHub real-source
workflow downloads pinned model and source and produces genuine CPU energies.
"""
import hashlib
import json
import math
import sys
import types

import numpy as np
import pytest
from pymatgen.core import Lattice, Structure
from ase.calculators.calculator import Calculator, all_changes

from scripts.science.obelix_mace_real_cpu_pilot import (
    EXPECTED, SCHEMA, _geometry, inspect_original_train_cifs,
    run_original_train_mace_cpu,
)
from tests.test_phase3_obelix_benchmark_intake import checkout


def fixture_source(tmp_path):
    structure = Structure(
        Lattice.cubic(6.0), ["Li", "O"], [[0, 0, 0], [0.5, 0.5, 0.5]]
    )
    data = structure.to(fmt="cif").encode()
    return checkout(tmp_path, cifs={"a.cif": data, "c.cif": b"not parsed test"})


def test_real_pymatgen_cif_parse_fixture_and_official_test_geometry_reserved(tmp_path):
    root, commit = fixture_source(tmp_path)
    report, rows = inspect_original_train_cifs(
        root, expected_commit=commit, require_official=False
    )
    assert report["all_source_records"] == 4
    assert report["official_train_records"] == 3
    assert report["official_test_reserved_without_geometry_inference"] == 1
    assert report["train_geometry_eligibility_counts"]["ELIGIBLE"] == 1
    assert report["train_geometry_eligibility_counts"]["NOT_EXACT_MATCH"] == 2
    assert report["train_geometry_eligibility_counts"]["OFFICIAL_TEST_RESERVED_UNPARSED"] == 1
    assert [(i, sid) for i, sid, _, s in rows] == [(2, "a")]
    assert EXPECTED == (599, 478, 121, 321)


def test_exact_test_cif_is_never_parsed_even_if_broken_or_malicious(tmp_path):
    root, commit = fixture_source(tmp_path)
    r, _ = inspect_original_train_cifs(
        root, expected_commit=commit, require_official=False)
    assert r["official_test_reserved_without_geometry_inference"] == 1


def test_no_official_claim_for_synthetic_checkout(tmp_path):
    root, commit = fixture_source(tmp_path)
    with pytest.raises(ValueError):
        inspect_original_train_cifs(root)
    with pytest.raises(ValueError):
        inspect_original_train_cifs(root, expected_commit=commit, require_official=True)


def test_geometry_rejects_mismatch_and_missing_structures(tmp_path):
    root, commit = fixture_source(tmp_path)
    from rhombus.qualification.obelix_benchmark_intake import build_obelix_benchmark_intake
    rows, _ = build_obelix_benchmark_intake(root, expected_commit=commit)
    matched = rows[0].copy()
    wrong = matched.copy()
    wrong["cif_content_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="digest"):
        _geometry(root, wrong)
    wrong = matched.copy()
    wrong["official_split"] = "TEST"
    with pytest.raises(ValueError, match="official TEST"):
        _geometry(root, wrong)
    wrong = matched.copy()
    wrong["cif_relative_path"] = "../../secrets.txt"
    with pytest.raises(ValueError, match="relative CIF"):
        _geometry(root, wrong)


def test_disordered_occupancies_are_not_inference_input(tmp_path):
    root, commit = fixture_source(tmp_path)
    from rhombus.qualification.obelix_benchmark_intake import build_obelix_benchmark_intake
    rows, _ = build_obelix_benchmark_intake(root, expected_commit=commit)
    from unittest.mock import patch
    disorder = Structure(Lattice.cubic(6), [{"Li": 0.6, "Na": 0.4}, "O"], [[0,0,0],[0.5,0.5,0.5]])
    with patch("pymatgen.core.Structure.from_str", return_value=disorder):
        status, structure = _geometry(root, rows[0])
    assert status == "DISORDERED_PARTIAL_OCCUPANCY"
    assert structure is None


class StubPotential(Calculator):
    implemented_properties = ["energy", "forces"]
    def __init__(self, **kwargs):
        super().__init__()
    def calculate(self, atoms=None, properties=("energy", "forces"),
                  system_changes=all_changes):
        super().calculate(atoms, properties, system_changes)
        self.results = {
            "energy": -float(len(atoms)),
            "forces": np.zeros((len(atoms), 3)),
        }


def test_end_to_end_source_bound_fake_calculator_unit_is_not_science(tmp_path, monkeypatch):
    root, commit = fixture_source(tmp_path)
    import scripts.science.obelix_mace_real_cpu_pilot as mod
    monkeypatch.setattr(mod, "observe_mpa0_official_release_file",
                        lambda x: {"observed_full_file_sha256": mod.PUBLIC_SHA256,
                                   "source_release_asset_id": 213937064})
    parent = types.ModuleType("mace")
    calcmod = types.ModuleType("mace.calculators")
    calcmod.MACECalculator = StubPotential
    monkeypatch.setitem(sys.modules, "mace", parent)
    monkeypatch.setitem(sys.modules, "mace.calculators", calcmod)
    (tmp_path / "test-only-model").write_bytes(b"TEST_ONLY_NOT_MODEL")
    out = tmp_path / "new-output"
    r = run_original_train_mace_cpu(
        root, tmp_path / "test-only-model", out,
        expected_commit=commit, require_official=False
    )
    assert r["scope"] == "SYNTHETIC_SOURCE_WITH_REAL_MODEL_TEST"
    assert r["actual_successful_model_singlepoint_structures"] == 1
    assert r["selected_original_train_records"] == 1
    assert r["records"][0]["energy_eV"] == -2.0
    assert r["records"][0]["max_force_eV_per_A"] == 0
    assert r["experimental_conductivity_prediction_count"] == 0
    assert r["experimentally_scored_materials"] == 0
    assert r["independent_physical_materials_authenticated"] is None
    assert not r["scientific_qualification_authorized"]
    assert (r["P0_01_status"], r["P0_02_status"], r["P0_03_status"]) == (
        "BLOCKED", "BLOCKED", "BLOCKED",
    )
    assert json.loads((out/"real_mace_train_pilot.json").read_text()) == r
    with pytest.raises(ValueError, match="new"):
        run_original_train_mace_cpu(
            root, tmp_path / "test-only-model", out,
            expected_commit=commit, require_official=False
        )


def test_bad_source_or_model_not_written(tmp_path, monkeypatch):
    root, commit = fixture_source(tmp_path)
    import scripts.science.obelix_mace_real_cpu_pilot as mod
    monkeypatch.setattr(mod, "observe_mpa0_official_release_file",
                        lambda x: {"observed_full_file_sha256": "bad"})
    with pytest.raises(ValueError, match="wrong published"):
        run_original_train_mace_cpu(
            root, tmp_path/"bad", tmp_path/"out",
            expected_commit=commit, require_official=False
        )
    assert not (tmp_path/"out").exists()


@pytest.mark.parametrize("limit", [0, 4, True, "3"])
def test_invalid_budget_rejected(tmp_path, limit):
    root, commit = fixture_source(tmp_path)
    with pytest.raises(ValueError, match="pilot limit"):
        run_original_train_mace_cpu(
            root, tmp_path/"model", tmp_path/"out",
            expected_commit=commit, require_official=False,
            max_selected=limit
        )
