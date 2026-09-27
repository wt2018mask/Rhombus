"""Design contract for an observational mobile-ion displacement cohort diagnostic."""

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

    for parent, row, parent_index in (
        (parents[1], halide, 1),
        (parents[3], three_sites, 3),
    ):
        seed = 41 + parent_index
        identity = derive_candidate_supply_v2_operator_rng_identity(
            parent_id=parent.parent_id,
            seed=seed,
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
        assert row["parent_seed"] == seed
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
            "parent_id", "parent_seed", "operator_rng_identity",
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
    assert after_blocked["parent_seed"] == after_executable["parent_seed"]
    assert (
        after_blocked["operator_rng_identity"]
        == after_executable["operator_rng_identity"]
    )
    assert after_blocked["operator_rng_seed"] == after_executable["operator_rng_seed"]
    assert after_blocked["child_material_id"] == after_executable["child_material_id"]
    assert after_blocked["child_structure_dict"] == after_executable[
        "child_structure_dict"
    ]
