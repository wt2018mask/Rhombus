"""Design contract for persisting existing P0 detail payloads in panels.

P0FilterResult.details currently contains neutrality, Pauling, geometry,
coordination, and provisional_clash_ratio values. Geometry details may carry
raw clash measurements (distance/min_allowed) or coordination fields
(coordination_number/all_sites_sane); these tests preserve their values and
do not translate them into new scientific diagnoses.
"""

from __future__ import annotations

import copy
import json
from types import SimpleNamespace

from pymatgen.core import Lattice, Structure

from rudeus.generation.generator import ParentRecord


_PLAUSIBLE_DETAILS = {
    "neutrality": {"neutral_found": True, "elements": ["Li", "O"]},
    "pauling": {"pauling_test": True, "electronegativities": [0.98, 3.44]},
    "geometry": {"clash_detected": False},
    "coordination": {"mean_coordination": 4.0, "all_sites_sane": True},
    "provisional_clash_ratio": 0.6,
}
_GEOMETRY_FAIL_DETAILS = {
    "neutrality": {"neutral_found": True, "elements": ["Li", "O"]},
    "pauling": {"pauling_test": True, "electronegativities": [0.98, 3.44]},
    "geometry": {
        "clash_detected": True,
        "atom_i": "Li",
        "atom_j": "O",
        "distance": 0.8,
        "min_allowed": 1.1,
    },
    "coordination": {"mean_coordination": 3.0, "all_sites_sane": True},
    "provisional_clash_ratio": 0.6,
}
_NON_GEOMETRY_FAIL_DETAILS = {
    "neutrality": {"neutral_found": False, "elements": ["Li", "O"]},
    "pauling": {"pauling_test": True, "electronegativities": [0.98, 3.44]},
    "geometry": {"clash_detected": False},
    "coordination": {"mean_coordination": 4.0, "all_sites_sane": True},
    "provisional_clash_ratio": 0.6,
}


def _parent(parent_id, species=("Li", "O")):
    structure = Structure(
        Lattice.cubic(4.5), list(species),
        [[0, 0, 0], [0.5, 0.5, 0.5]],
    )
    return ParentRecord(
        parent_id=parent_id,
        source_dataset="fixture",
        source_ref=parent_id,
        composition=str(structure.composition.reduced_formula),
        structure=structure,
        structure_sha256="fixture-sha",
        conductivity=None,
        chemical_family="synthetic",
        perturbable=True,
        provenance={"source": "p0-detail-fixture"},
    )


def _install_fake_p0(monkeypatch):
    from rudeus.generation import mobile_ion_diagnostic as diagnostic

    parents = [
        _parent("fixture:plausible"),
        _parent("fixture:geometry-fail"),
        _parent("fixture:non-geometry-fail"),
        _parent("fixture:blocked"),
        _parent("fixture:inapplicable", ("Na", "Cl")),
    ]
    parent_by_structure = {id(parent.structure): parent for parent in parents}
    child_results = [
        ("PLAUSIBLE", True, True, True, _PLAUSIBLE_DETAILS),
        ("FAIL", True, True, False, _GEOMETRY_FAIL_DETAILS),
        ("FAIL", False, True, True, _NON_GEOMETRY_FAIL_DETAILS),
    ]
    child_index = 0

    def fake_evaluate_p0(formula, *, structure):
        nonlocal child_index
        parent = parent_by_structure.get(id(structure))
        if parent is not None:
            if parent.parent_id == "fixture:plausible":
                child_index = 0
            if parent.parent_id == "fixture:blocked":
                state, neutrality, pauling, geometry, details = (
                    "FAIL", False, True, True, _NON_GEOMETRY_FAIL_DETAILS
                )
            else:
                state, neutrality, pauling, geometry, details = (
                    "PLAUSIBLE", True, True, True, _PLAUSIBLE_DETAILS
                )
        else:
            state, neutrality, pauling, geometry, details = child_results[child_index]
            child_index += 1
        return SimpleNamespace(
            existence_state=SimpleNamespace(value=state),
            neutrality_ok=neutrality,
            pauling_ok=pauling,
            geometry_ok=geometry,
            details=copy.deepcopy(details),
        )

    def fake_operator(structure, rng, **kwargs):
        return structure.copy(), {
            "operator_name": "mobile-ion-displace",
            "operator_version": "mobile-ion-displace-v2",
            "mobile_ion": kwargs["mobile_ion"],
            "sigma_A_provisional": kwargs["sigma_A_provisional"],
            "operator_rng_identity": kwargs["operator_rng_identity"],
        }

    monkeypatch.setattr(diagnostic, "evaluate_p0", fake_evaluate_p0)
    monkeypatch.setattr(diagnostic, "op_mobile_ion_displace_v2", fake_operator)
    monkeypatch.setattr(
        diagnostic,
        "classify_candidate_supply_v2_novelty",
        lambda *args, **kwargs: {
            "novelty_tag": "rediscovery",
            "novelty_matched": "parent",
            "novelty_matcher_version": "novelty-matcher-v2-same-cell",
        },
    )
    return diagnostic, parents


def _run_report(diagnostic, parents):
    return diagnostic.diagnose_mobile_ion_displacement_cohort(
        parents,
        mobile_ion="Li",
        sigma_A_provisional=0.1,
        base_seed=23,
        diagnostic_config_hash="p0-details-config-v1",
    )


def _strings_and_keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _strings_and_keys(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _strings_and_keys(item)
    elif isinstance(value, str):
        yield value


def test_generated_rows_preserve_exact_p0_details_and_guard_rows_have_none(monkeypatch):
    diagnostic, parents = _install_fake_p0(monkeypatch)
    report = _run_report(diagnostic, parents)
    rows = {row["parent_id"]: row for row in report["rows"]}

    expected = {
        "fixture:plausible": ("PLAUSIBLE", _PLAUSIBLE_DETAILS, True),
        "fixture:geometry-fail": ("FAIL", _GEOMETRY_FAIL_DETAILS, False),
        "fixture:non-geometry-fail": ("FAIL", _NON_GEOMETRY_FAIL_DETAILS, True),
    }
    for parent_id, (state, details, geometry_ok) in expected.items():
        row = rows[parent_id]
        assert row["diagnostic_state"] == "GENERATED"
        assert row["p0_state"] == state
        assert row["p0_details"] == details
        assert row["p0_neutrality_ok"] == details["neutrality"]["neutral_found"]
        assert row["p0_pauling_ok"] == details["pauling"]["pauling_test"]
        assert row["p0_geometry_ok"] is geometry_ok
        forbidden_diagnoses = {
            "CLASH", "COORDINATION_COLLAPSE", "BOND_BREAK", "LOCAL_ENVIRONMENT_FAILURE"
        }
        assert forbidden_diagnoses.isdisjoint(_strings_and_keys(row))

    for parent_id in ("fixture:blocked", "fixture:inapplicable"):
        row = rows[parent_id]
        assert row["diagnostic_state"] in {"BLOCKED_BY_PARENT_P0", "INAPPLICABLE"}
        assert row["p0_details"] is None

    assert len(report["rows"]) == 5
    assert report["summary"]["generated_children"] == 3
    assert report["summary"]["p0_plausible"] == 1
    assert report["summary"]["geometry_failures"] == 1


def test_identical_p0_results_produce_identical_json_ready_rows(monkeypatch):
    diagnostic, parents = _install_fake_p0(monkeypatch)
    first = _run_report(diagnostic, parents)
    second = _run_report(diagnostic, parents)
    assert json.dumps(first["rows"], sort_keys=True) == json.dumps(
        second["rows"], sort_keys=True
    )
    for row in first["rows"]:
        if row["diagnostic_state"] == "GENERATED":
            details_json = json.dumps(row["p0_details"], sort_keys=True)
            assert json.loads(details_json) == row["p0_details"]
    assert first["summary"] == second["summary"]


def test_new_panel_schema_and_writer_retain_details_and_provenance(monkeypatch, tmp_path):
    diagnostic, parents = _install_fake_p0(monkeypatch)
    report = _run_report(diagnostic, parents)
    monkeypatch.setattr(
        diagnostic, "diagnose_mobile_ion_displacement_cohort", lambda *a, **k: report
    )

    kwargs = {
        "mobile_ion": "Li",
        "sigma_values_A_provisional": [0.1],
        "base_seeds": [23],
        "diagnostic_config_hash": "p0-details-config-v1",
    }
    payload = diagnostic.build_mobile_ion_displacement_diagnostic_panel(parents, **kwargs)
    assert payload["schema_version"] == "mobile-ion-displacement-diagnostic-panel-v2"
    assert payload["authorization"]["scheduler_activation"] is False
    assert payload["authorization"]["p1_eligibility"] is False
    assert payload["authorization"]["downstream_scientific_superiority_claim"] is False
    for row in payload["rows"]:
        if row["diagnostic_state"] == "GENERATED":
            assert row["p0_details"] is not None
            assert row["operator_rng_identity"]
            assert isinstance(row["operator_rng_seed"], int)
            assert row["novelty_matcher_version"] == "novelty-matcher-v2-same-cell"
        else:
            assert row["p0_details"] is None

    path = tmp_path / "audit" / "panel.json"
    first = diagnostic.write_mobile_ion_displacement_diagnostic_panel(path, parents, **kwargs)
    first_bytes = path.read_bytes()
    second = diagnostic.write_mobile_ion_displacement_diagnostic_panel(path, parents, **kwargs)
    assert path.read_bytes() == first_bytes
    assert json.loads(path.read_text(encoding="utf-8")) == second
    assert first == second
    assert json.loads(path.read_text(encoding="utf-8"))["rows"] == payload["rows"]


def test_historical_v1_panel_without_details_remains_readable_by_analysis_modules():
    from rudeus.generation.mobile_ion_geometry_taxonomy import (
        build_mobile_ion_geometry_failure_taxonomy,
    )
    from rudeus.generation.mobile_ion_parent_atlas import (
        build_mobile_ion_parent_diagnostic_atlas,
    )

    panel = {
        "schema_version": "mobile-ion-displacement-diagnostic-panel-v1",
        "artifact_type": "OBSERVATIONAL_DIAGNOSTIC",
        "metadata": {
            "operator_name": "mobile-ion-displace",
            "operator_version": "mobile-ion-displace-v2",
            "novelty_matcher_version": "novelty-matcher-v2-same-cell",
            "target_species": "Mg",
            "sigma_values_A_provisional": [0.1],
            "base_seeds": [5],
            "ordered_parent_ids": ["fixture:old"],
            "ordered_cohort_identity": "old-cohort",
            "diagnostic_config_hash": "old-config",
            "persistent_useful_threshold": 0.75,
        },
        "rows": [{
            "parent_id": "fixture:old",
            "parent_chemical_family": "synthetic",
            "site_count": 4,
            "target_site_count": 1,
            "target_species": "Mg",
            "sigma_A_provisional": 0.1,
            "base_seed": 5,
            "diagnostic_state": "GENERATED",
            "novelty_tag": "rediscovery",
            "p0_state": "FAIL",
            "p0_neutrality_ok": True,
            "p0_pauling_ok": True,
            "p0_geometry_ok": False,
        }],
    }
    original = copy.deepcopy(panel)
    atlas = build_mobile_ion_parent_diagnostic_atlas(panel)
    taxonomy = build_mobile_ion_geometry_failure_taxonomy(panel)
    assert panel == original
    assert atlas["source"]["schema_version"].endswith("-v1")
    assert atlas["parents"][0]["geometry_fail_count"] == 1
    assert taxonomy["source"]["schema_version"].endswith("-v1")
    assert taxonomy["rows"][0]["evidence_category"] == "GEOMETRY_FAIL_UNSPECIFIED"
    assert "p0_details" not in taxonomy["rows"][0]
