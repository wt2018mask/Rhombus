"""Design contract for an observational mobile-ion displacement cohort diagnostic."""

import json

import pytest
from pymatgen.core import Lattice, Structure

from rudeus.filters.p0 import evaluate_p0
from rudeus.generation.generator import ParentRecord
from rudeus.generation.scheduler import (
    derive_candidate_supply_v2_operator_rng_identity,
)


def _parent(parent_id, species, coords, family, lattice_a=4.6):
    structure = Structure(Lattice.cubic(lattice_a), species, coords)
    return ParentRecord(
        parent_id=parent_id,
        source_dataset="fixture",
        source_ref=parent_id,
        composition=str(structure.composition.reduced_formula),
        structure=structure,
        structure_sha256="fixture",
        conductivity=None,
        chemical_family=family,
        perturbable=True,
        provenance={"source": "synthetic-diagnostic-fixture"},
    )


def _ordered_parents():
    return [
        _parent(
            "fixture:blocked", ["Li", "O"],
            [[0, 0, 0], [0.5, 0.5, 0.5]], "oxide",
        ),
        _parent(
            "fixture:halide", ["Li", "Cl"],
            [[0, 0, 0], [0.5, 0.5, 0.5]], "halide", lattice_a=4.0,
        ),
        _parent(
            "fixture:no-li", ["Na", "Cl"],
            [[0, 0, 0], [0.5, 0.5, 0.5]], "halide", lattice_a=4.0,
        ),
        _parent(
            "fixture:three-sites", ["Li", "Li", "O"],
            [[0, 0, 0], [0.5, 0.5, 0], [0.5, 0, 0.5]], "oxide",
        ),
    ]


def _diagnose(parents, mobile_ion="Li", base_seed=41):
    # The standalone module/function is intentionally absent until the
    # diagnostic harness is implemented; these tests specify its interface.
    from rudeus.generation.mobile_ion_diagnostic import (
        diagnose_mobile_ion_displacement_cohort,
    )

    return diagnose_mobile_ion_displacement_cohort(
        parents,
        mobile_ion=mobile_ion,
        sigma_A_provisional=0.10,
        base_seed=base_seed,
        diagnostic_config_hash="fixture-config-v1",
    )


def test_mobile_ion_cohort_diagnostic_preserves_guard_and_raw_rows():
    parents = _ordered_parents()
    parent_p0 = evaluate_p0(
        str(parents[0].structure.composition.reduced_formula),
        structure=parents[0].structure,
    )
    assert parent_p0.neutrality_ok is False
    assert evaluate_p0(
        str(parents[1].structure.composition.reduced_formula),
        structure=parents[1].structure,
    ).neutrality_ok is True

    report = _diagnose(parents)
    rows = report["rows"]
    assert [row["parent_id"] for row in rows] == [
        parent.parent_id for parent in parents
    ]
    assert len(rows) == len(parents)

    blocked, halide, inapplicable, three_sites = rows
    assert blocked["parent_guard_state"] == "BLOCKED_BY_PARENT_P0"
    assert blocked["parent_p0_neutrality_ok"] is False
    assert blocked["child_material_id"] is None
    assert blocked["p0_state"] is None
    assert blocked["novelty_tag"] is None

    assert inapplicable["parent_guard_state"] == "INAPPLICABLE"
    assert inapplicable["target_species"] == "Li"
    assert inapplicable["target_site_count"] == 0
    assert inapplicable["child_material_id"] is None
    assert inapplicable["p0_state"] is None  # no failed material was created

    for parent, row in (
        (parents[1], halide),
        (parents[3], three_sites),
    ):
        identity = derive_candidate_supply_v2_operator_rng_identity(
            parent_id=parent.parent_id,
            seed=41,
            operator_name="mobile-ion-displace",
            operator_version="mobile-ion-displace-v2",
        )
        assert row["parent_guard_state"] == "ELIGIBLE"
        assert row["parent_chemical_family"] == parent.chemical_family
        assert row["target_species"] == "Li"
        assert row["sigma_A_provisional"] == pytest.approx(0.10)
        assert row["diagnostic_config_hash"] == "fixture-config-v1"
        assert row["operator_name"] == "mobile-ion-displace"
        assert row["operator_version"] == "mobile-ion-displace-v2"
        assert row["base_seed"] == 41
        assert row["operator_rng_identity"] == identity
        assert row["operator_rng_seed"] == (
            int(identity[:16], 16) & ((1 << 63) - 1)
        )
        assert row["child_material_id"]
        child_structure = Structure.from_dict(row["child_structure_dict"])
        child_p0 = evaluate_p0(
            str(child_structure.composition.reduced_formula),
            structure=child_structure,
        )
        assert row["p0_neutrality_ok"] == child_p0.neutrality_ok
        assert row["p0_pauling_ok"] == child_p0.pauling_ok
        assert row["p0_geometry_ok"] == child_p0.geometry_ok
        assert row["p0_state"] == child_p0.existence_state.value
        assert row["site_count"] == len(parent.structure)
        assert row["target_site_count"] == sum(
            "Li" in {element.symbol for element in site.species.elements}
            for site in parent.structure
        )
        assert row["p0_neutrality_ok"] in (True, False, None)
        assert row["p0_pauling_ok"] in (True, False, None)
        assert row["p0_geometry_ok"] in (True, False, None)
        assert row["p0_state"] in ("PLAUSIBLE", "FAIL", "UNKNOWN")
        assert row["novelty_tag"] in ("novel", "rediscovery")
        assert row["novelty_matched"] in (None, "parent")
        assert row["novelty_matcher_version"] == "novelty-matcher-v2-same-cell"


def test_mobile_ion_cohort_diagnostic_reconciles_counts_and_is_deterministic():
    parents = _ordered_parents()
    report = _diagnose(parents)
    repeated = _diagnose(parents)
    assert report["summary"] == repeated["summary"]
    for row, repeated_row in zip(report["rows"], repeated["rows"]):
        for key in (
            "parent_id", "base_seed", "operator_rng_identity",
            "operator_rng_seed", "child_material_id", "child_structure_dict",
            "p0_state", "novelty_tag", "novelty_matcher_version",
        ):
            assert row[key] == repeated_row[key]

    rows = report["rows"]
    summary = report["summary"]

    def counts(group):
        generated = [row for row in group if row["child_material_id"] is not None]
        return {
            "requested_parents": len(group),
            "blocked_parents": sum(
                row["parent_guard_state"] == "BLOCKED_BY_PARENT_P0"
                for row in group
            ),
            "inapplicable_parents": sum(
                row["parent_guard_state"] == "INAPPLICABLE" for row in group
            ),
            "generated_children": len(generated),
            "novel": sum(row["novelty_tag"] == "novel" for row in generated),
            "rediscovery": sum(
                row["novelty_tag"] == "rediscovery" for row in generated
            ),
            "p0_plausible": sum(
                row["p0_state"] == "PLAUSIBLE" for row in generated
            ),
            "geometry_failures": sum(
                row["p0_geometry_ok"] is False for row in generated
            ),
            "useful_diagnostic_yield": sum(
                row["novelty_tag"] == "novel"
                and row["p0_state"] == "PLAUSIBLE"
                for row in generated
            ),
        }

    assert {key: summary[key] for key in counts(rows)} == counts(rows)
    assert summary["requested_parents"] == 4
    assert summary["blocked_parents"] == 1
    assert summary["inapplicable_parents"] == 1
    assert summary["generated_children"] == 2
    assert summary["novel"] + summary["rediscovery"] == 2

    for family in {parent.chemical_family for parent in parents}:
        family_rows = [
            row for row in rows if row["parent_chemical_family"] == family
        ]
        assert summary["by_chemical_family"][family] == counts(family_rows)

    for site_count in {len(parent.structure) for parent in parents}:
        size_rows = [row for row in rows if row["site_count"] == site_count]
        assert summary["by_site_count"][str(site_count)] == counts(size_rows)

    for key in counts(rows):
        assert sum(
            family_counts[key]
            for family_counts in summary["by_chemical_family"].values()
        ) == summary[key]
        assert sum(
            size_counts[key]
            for size_counts in summary["by_site_count"].values()
        ) == summary[key]

    assert "activation_decision" not in report
    assert "activation_decision" not in summary


def test_mobile_ion_cohort_diagnostic_target_is_configured():
    report = _diagnose(_ordered_parents(), mobile_ion="Na")
    rows = report["rows"]
    assert [row["parent_id"] for row in rows] == [
        "fixture:blocked", "fixture:halide", "fixture:no-li",
        "fixture:three-sites",
    ]
    assert all(row["target_species"] == "Na" for row in rows)
    assert rows[1]["parent_guard_state"] == "INAPPLICABLE"
    assert rows[1]["p0_state"] is None
    assert rows[2]["parent_guard_state"] == "ELIGIBLE"
    assert rows[2]["child_material_id"] is not None
    assert report["summary"]["generated_children"] == 1


def test_mobile_ion_cohort_diagnostic_rng_does_not_depend_on_previous_parent():
    blocked, halide, _, _ = _ordered_parents()
    another_executable = _parent(
        "fixture:earlier-executable", ["Li", "F"],
        [[0, 0, 0], [0.5, 0.5, 0.5]], "halide", lattice_a=4.0,
    )

    after_blocked = _diagnose([blocked, halide])["rows"][1]
    after_executable = _diagnose([another_executable, halide])["rows"][1]
    assert after_blocked["base_seed"] == after_executable["base_seed"]
    assert (
        after_blocked["operator_rng_identity"]
        == after_executable["operator_rng_identity"]
    )
    assert after_blocked["operator_rng_seed"] == after_executable["operator_rng_seed"]
    assert after_blocked["child_material_id"] == after_executable["child_material_id"]
    assert after_blocked["child_structure_dict"] == after_executable[
        "child_structure_dict"
    ]


def _treatment_by_parent(report):
    return {
        row["parent_id"]: (
            row["operator_rng_identity"],
            row["operator_rng_seed"],
            row["child_material_id"],
            row["child_structure_dict"],
        )
        for row in report["rows"]
    }


def _three_applicable_parents():
    _, halide, _, oxide = _ordered_parents()
    fluoride = _parent(
        "fixture:fluoride", ["Li", "F"],
        [[0, 0, 0], [0.5, 0.5, 0.5]], "halide", lattice_a=4.0,
    )
    return halide, oxide, fluoride


def test_mobile_ion_cohort_treatment_is_invariant_to_parent_order():
    parents = _three_applicable_parents()
    forward = _diagnose(parents, base_seed=71)
    reordered = _diagnose([parents[2], parents[0], parents[1]], base_seed=71)

    assert [row["parent_id"] for row in forward["rows"]] == [
        parent.parent_id for parent in parents
    ]
    assert [row["parent_id"] for row in reordered["rows"]] == [
        parents[2].parent_id,
        parents[0].parent_id,
        parents[1].parent_id,
    ]
    forward_by_parent = _treatment_by_parent(forward)
    reordered_by_parent = _treatment_by_parent(reordered)
    for parent in parents:
        assert reordered_by_parent[parent.parent_id] == forward_by_parent[
            parent.parent_id
        ]


def test_mobile_ion_cohort_treatment_is_invariant_to_parent_subset():
    parents = _three_applicable_parents()
    full_cohort = _treatment_by_parent(_diagnose(parents, base_seed=83))
    singleton = _treatment_by_parent(_diagnose([parents[1]], base_seed=83))

    assert singleton[parents[1].parent_id] == full_cohort[parents[1].parent_id]


@pytest.mark.parametrize(
    "preceding_parent",
    [
        _ordered_parents()[0],  # parent P0 neutrality blocked
        _ordered_parents()[2],  # no configured Li sites
    ],
    ids=["blocked-neighbor", "inapplicable-neighbor"],
)
def test_mobile_ion_blocked_or_inapplicable_neighbor_does_not_change_stream(
    preceding_parent,
):
    target_parent = _three_applicable_parents()[0]
    alone = _treatment_by_parent(_diagnose([target_parent], base_seed=97))
    preceded = _treatment_by_parent(
        _diagnose([preceding_parent, target_parent], base_seed=97)
    )

    assert preceded[target_parent.parent_id] == alone[target_parent.parent_id]
    output = _diagnose(
        [preceding_parent, target_parent], base_seed=97
    )["rows"]
    assert [row["parent_id"] for row in output] == [
        preceding_parent.parent_id,
        target_parent.parent_id,
    ]


def _build_panel(parents, *, sigmas=(0.10, 0.20), seeds=(11, 12)):
    from rudeus.generation.mobile_ion_diagnostic import (
        build_mobile_ion_displacement_diagnostic_panel,
    )

    return build_mobile_ion_displacement_diagnostic_panel(
        parents,
        mobile_ion="Li",
        sigma_values_A_provisional=list(sigmas),
        base_seeds=list(seeds),
        diagnostic_config_hash="fixture-panel-config-v1",
        persistent_useful_threshold=0.75,
    )


def test_mobile_ion_diagnostic_panel_preserves_cartesian_runs_and_raw_rows(
    tmp_path,
):
    from rudeus.generation.mobile_ion_diagnostic import (
        write_mobile_ion_displacement_diagnostic_panel,
    )

    parents = _ordered_parents()
    payload = _build_panel(parents)
    output_path = tmp_path / "nested" / "panel.json"
    written_payload = write_mobile_ion_displacement_diagnostic_panel(
        output_path, parents,
        mobile_ion="Li",
        sigma_values_A_provisional=[0.10, 0.20],
        base_seeds=[11, 12],
        diagnostic_config_hash="fixture-panel-config-v1",
        persistent_useful_threshold=0.75,
    )

    assert payload == written_payload
    assert json.loads(output_path.read_text(encoding="utf-8")) == payload
    assert payload["artifact_type"] == "OBSERVATIONAL_DIAGNOSTIC"
    assert payload["activation_authorized"] is False
    assert payload["p1_eligibility_authorized"] is False
    assert payload["downstream_scientific_claims_authorized"] is False
    assert payload["metadata"]["operator_name"] == "mobile-ion-displace"
    assert payload["metadata"]["operator_version"] == "mobile-ion-displace-v2"
    assert payload["metadata"]["novelty_matcher_version"] == (
        "novelty-matcher-v2-same-cell"
    )
    assert payload["metadata"]["target_species"] == "Li"
    assert payload["metadata"]["sigma_values_A_provisional"] == [0.10, 0.20]
    assert payload["metadata"]["base_seeds"] == [11, 12]
    assert payload["metadata"]["ordered_parent_ids"] == [
        parent.parent_id for parent in parents
    ]
    assert payload["metadata"]["diagnostic_config_hash"] == (
        "fixture-panel-config-v1"
    )
    assert len(payload["runs"]) == 4
    assert len(payload["rows"]) == 4 * len(parents)

    required_row_fields = {
        "parent_id", "parent_chemical_family", "target_species",
        "sigma_A_provisional", "base_seed", "operator_name",
        "operator_version", "novelty_matcher_version", "diagnostic_state",
        "parent_guard_state", "site_count", "target_site_count",
        "operator_rng_identity", "operator_rng_seed", "child_material_id",
        "novelty_tag", "p0_state", "p0_neutrality_ok", "p0_pauling_ok",
        "p0_geometry_ok",
    }
    assert all(required_row_fields <= row.keys() for row in payload["rows"])
    assert [
        (row["sigma_A_provisional"], row["base_seed"])
        for row in payload["rows"][: len(parents)]
    ] == [(0.10, 11)] * len(parents)

    # Every run aggregate is reconstructed directly from that run's persisted rows.
    for run in payload["runs"]:
        run_rows = [
            row for row in payload["rows"]
            if row["sigma_A_provisional"] == run["sigma_A_provisional"]
            and row["base_seed"] == run["base_seed"]
        ]
        assert run["summary"] == _diagnose_summary_from_rows(run_rows)

    summary = payload["summary"]
    assert summary["per_sigma"]
    assert summary["per_parent_useful_frequency"]
    assert summary["per_parent_geometry_failure_frequency"]
    assert summary["persistent_useful_threshold"] == 0.75
    assert summary["by_chemical_family"]
    assert summary["by_site_count_bin"]
    assert sum(
        item["generated_children"]
        for item in summary["by_chemical_family"].values()
    ) == sum(row["diagnostic_state"] == "GENERATED" for row in payload["rows"])


def _diagnose_summary_from_rows(rows):
    generated = [row for row in rows if row["diagnostic_state"] == "GENERATED"]
    return {
        "requested_parents": len(rows),
        "blocked_parents": sum(
            row["diagnostic_state"] == "BLOCKED_BY_PARENT_P0" for row in rows
        ),
        "inapplicable_parents": sum(
            row["diagnostic_state"] == "INAPPLICABLE" for row in rows
        ),
        "generated_children": len(generated),
        "novel": sum(row["novelty_tag"] == "novel" for row in generated),
        "rediscovery": sum(
            row["novelty_tag"] == "rediscovery" for row in generated
        ),
        "p0_plausible": sum(row["p0_state"] == "PLAUSIBLE" for row in generated),
        "geometry_failures": sum(
            row["p0_geometry_ok"] is False for row in generated
        ),
        "useful_diagnostic_yield": sum(
            row["novelty_tag"] == "novel" and row["p0_state"] == "PLAUSIBLE"
            for row in generated
        ),
    }


def test_mobile_ion_diagnostic_panel_summaries_and_persistence_are_reproducible(
    tmp_path,
):
    from rudeus.generation.mobile_ion_diagnostic import (
        write_mobile_ion_displacement_diagnostic_panel,
    )

    parents = _ordered_parents()
    kwargs = {
        "mobile_ion": "Li",
        "sigma_values_A_provisional": [0.10, 0.20],
        "base_seeds": [11, 12],
        "diagnostic_config_hash": "fixture-panel-config-v1",
        "persistent_useful_threshold": 0.75,
    }
    first_path = tmp_path / "first.json"
    second_path = tmp_path / "second.json"
    first = write_mobile_ion_displacement_diagnostic_panel(
        first_path, parents, **kwargs
    )
    second = write_mobile_ion_displacement_diagnostic_panel(
        second_path, parents, **kwargs
    )

    assert first_path.read_bytes() == second_path.read_bytes()
    assert first == second
    assert len(first["runs"]) == len(kwargs["sigma_values_A_provisional"]) * len(
        kwargs["base_seeds"]
    )
    for sigma in kwargs["sigma_values_A_provisional"]:
        sigma_runs = [
            run for run in first["runs"]
            if run["sigma_A_provisional"] == sigma
        ]
        for metric in ("novel", "geometry_failures", "useful_diagnostic_yield"):
            values = [run["summary"][metric] for run in sigma_runs]
            assert first["summary"]["per_sigma"][str(sigma)][metric] == {
                "mean": pytest.approx(sum(values) / len(values)),
                "min": min(values),
                "max": max(values),
            }

    per_parent = first["summary"]["per_parent_useful_frequency"]
    per_parent_geometry = first["summary"][
        "per_parent_geometry_failure_frequency"
    ]
    for parent in parents:
        rows = [row for row in first["rows"] if row["parent_id"] == parent.parent_id]
        useful_n = sum(
            row["novelty_tag"] == "novel" and row["p0_state"] == "PLAUSIBLE"
            for row in rows
        )
        geometry_n = sum(row["p0_geometry_ok"] is False for row in rows)
        assert per_parent[parent.parent_id]["useful_count"] == useful_n
        assert per_parent[parent.parent_id]["useful_frequency"] == pytest.approx(
            useful_n / len(kwargs["base_seeds"])
        )
        assert per_parent_geometry[parent.parent_id]["geometry_fail_count"] == (
            geometry_n
        )
        assert per_parent_geometry[parent.parent_id]["geometry_fail_frequency"] == (
            pytest.approx(geometry_n / len(kwargs["base_seeds"]))
        )

    reordered = _build_panel(list(reversed(parents)), sigmas=(0.10,), seeds=(11,))
    original = _build_panel(parents, sigmas=(0.10,), seeds=(11,))
    assert reordered["metadata"]["ordered_parent_ids"] == [
        parent.parent_id for parent in reversed(parents)
    ]
    assert [row["parent_id"] for row in reordered["rows"]] == [
        parent.parent_id for parent in reversed(parents)
    ]
    original_by_parent = {row["parent_id"]: row for row in original["rows"]}
    reordered_by_parent = {row["parent_id"]: row for row in reordered["rows"]}
    for parent in parents:
        assert reordered_by_parent[parent.parent_id]["operator_rng_identity"] == (
            original_by_parent[parent.parent_id]["operator_rng_identity"]
        )
        assert reordered_by_parent[parent.parent_id]["operator_rng_seed"] == (
            original_by_parent[parent.parent_id]["operator_rng_seed"]
        )


def test_mobile_ion_panel_global_frequencies_use_generated_observation_denominator(
    monkeypatch,
):
    import rudeus.generation.mobile_ion_diagnostic as diagnostic

    generated_parent = _parent(
        "fixture:generated", ["Li", "F"],
        [[0, 0, 0], [0.5, 0.5, 0.5]], "halide", lattice_a=4.0,
    )
    blocked_parent, _, inapplicable_parent, _ = _ordered_parents()

    # Across 2 sigmas x 2 seeds, this parent has exactly four generated
    # observations: three useful, with one geometry failure among them.
    outcomes = {
        (0.1, 1): (True, False),
        (0.1, 2): (True, False),
        (0.2, 1): (True, True),
        (0.2, 2): (False, False),
    }

    def fake_diagnose(parents, *, mobile_ion, sigma_A_provisional,
                      base_seed, diagnostic_config_hash, matcher=None):
        rows = []
        for parent in parents:
            common = {
                "parent_id": parent.parent_id,
                "parent_chemical_family": parent.chemical_family,
                "target_species": mobile_ion,
                "sigma_A_provisional": sigma_A_provisional,
                "base_seed": base_seed,
                "diagnostic_config_hash": diagnostic_config_hash,
                "operator_name": "mobile-ion-displace",
                "operator_version": "mobile-ion-displace-v2",
                "novelty_matcher_version": "novelty-matcher-v2-same-cell",
                "site_count": len(parent.structure),
                "target_site_count": 1,
                "operator_rng_identity": "fixture-rng-id",
                "operator_rng_seed": 123,
                "child_material_id": None,
                "diagnostic_state": "INAPPLICABLE",
                "parent_guard_state": "INAPPLICABLE",
                "novelty_tag": None,
                "p0_state": None,
                "p0_geometry_ok": None,
            }
            if parent.parent_id == blocked_parent.parent_id:
                common.update(
                    diagnostic_state="BLOCKED_BY_PARENT_P0",
                    parent_guard_state="BLOCKED_BY_PARENT_P0",
                )
            elif parent.parent_id == inapplicable_parent.parent_id:
                pass
            else:
                useful, geometry_fail = outcomes[
                    (sigma_A_provisional, base_seed)
                ]
                common.update(
                    diagnostic_state="GENERATED",
                    parent_guard_state="ELIGIBLE",
                    child_material_id=f"child-{sigma_A_provisional}-{base_seed}",
                    novelty_tag="novel" if useful else "rediscovery",
                    p0_state="PLAUSIBLE" if useful else "FAIL",
                    p0_geometry_ok=not geometry_fail,
                )
            rows.append(common)
        return {"rows": rows, "summary": {}}

    monkeypatch.setattr(
        diagnostic, "diagnose_mobile_ion_displacement_cohort", fake_diagnose
    )
    payload = diagnostic.build_mobile_ion_displacement_diagnostic_panel(
        [generated_parent, blocked_parent, inapplicable_parent],
        mobile_ion="Li",
        sigma_values_A_provisional=[0.1, 0.2],
        base_seeds=[1, 2],
        diagnostic_config_hash="synthetic-frequency-config",
        persistent_useful_threshold=0.75,
    )

    global_useful = payload["summary"]["per_parent_useful_frequency"][
        generated_parent.parent_id
    ]
    global_geometry = payload["summary"][
        "per_parent_geometry_failure_frequency"
    ][generated_parent.parent_id]
    assert global_useful["useful_count"] == 3
    assert global_useful["useful_frequency"] == pytest.approx(0.75)
    assert global_geometry["geometry_fail_count"] == 1
    assert global_geometry["geometry_fail_frequency"] == pytest.approx(0.25)
    assert global_useful["observations_count"] == 4
    assert global_geometry["observations_count"] == 4

    for parent_id, values in payload["summary"][
        "per_parent_useful_frequency"
    ].items():
        assert 0.0 <= values["useful_frequency"] <= 1.0
        if parent_id != generated_parent.parent_id:
            assert values["observations_count"] == 0
            assert values["useful_frequency"] == 0.0
    for values in payload["summary"][
        "per_parent_geometry_failure_frequency"
    ].values():
        assert 0.0 <= values["geometry_fail_frequency"] <= 1.0

    # Per-sigma persistence keeps a distinct denominator: generated observations
    # within that sigma, not the panel's pooled sigma x seed observations.
    for sigma in (0.1, 0.2):
        persisted = payload["summary"]["parent_persistence_by_sigma"][str(sigma)][
            generated_parent.parent_id
        ]
        assert persisted["generated_count"] == 2
        assert persisted["useful_frequency"] == pytest.approx(
            persisted["useful_count"] / persisted["generated_count"]
        )

    blocked_global = payload["summary"]["per_parent_useful_frequency"][
        blocked_parent.parent_id
    ]
    inapplicable_global = payload["summary"]["per_parent_useful_frequency"][
        inapplicable_parent.parent_id
    ]
    assert blocked_global["observations_count"] == 0
    assert inapplicable_global["observations_count"] == 0
