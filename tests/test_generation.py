"""Tests for rudeus.generation (G1 perturbation + G2 substitution, small fixtures)."""

from pathlib import Path

import numpy as np
import pytest
from pymatgen.core import Lattice, Structure

import rudeus.generation
from rudeus.filters.p0 import evaluate_p0
from rudeus.generation import (
    ParentRecord,
    generate_children,
    op_displace,
    op_interstitial,
    op_strain,
    op_substitute,
    op_vacancy,
    retrieve_liion_parents,
    retrieve_obelix_parents,
)
from rudeus.schema import ExistenceState


def _licl():
    lattice = Lattice.cubic(4.0)
    return Structure(lattice, ["Li", "Cl"], [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]])


def _parent(struct=None):
    s = struct or _licl()
    return ParentRecord(
        parent_id="test:licl", source_dataset="test", source_ref="licl",
        composition="LiCl", structure=s, structure_sha256="abc",
        conductivity=None, chemical_family="halide", perturbable=True,
        provenance={"source": "test"},
    )


def test_generation_module_namespace():
    """Verify generation package is importable and has docstring."""
    assert rudeus.generation.__doc__ is not None
    assert "G1 Generation" in rudeus.generation.__doc__
    assert "G2 Generation" in rudeus.generation.__doc__


def _structures_equal(a, b):
    import json
    return (json.dumps(a.as_dict(), sort_keys=True, default=str)
            == json.dumps(b.as_dict(), sort_keys=True, default=str))


def test_operators_deterministic_given_seed():
    """Same seed -> bit-identical children.

    Different seeds must differ for continuous operators (displace/strain/
    interstitial). Vacancy is a discrete single-site choice that may coincide
    legitimately, so only same-seed equality is asserted for it.
    """
    for op, kwargs, must_differ in [
        (op_displace, {"sigma_A_provisional": 0.05}, True),
        (op_strain, {"strain_max_fraction_provisional": 0.02}, True),
        (op_vacancy, {}, False),
        (op_interstitial, {}, True),
    ]:
        a, _ = op(_licl(), np.random.default_rng(7), **kwargs)
        b, _ = op(_licl(), np.random.default_rng(7), **kwargs)
        c, _ = op(_licl(), np.random.default_rng(8), **kwargs)
        assert _structures_equal(a, b)
        if must_differ:
            assert not _structures_equal(a, c)


def test_operator_effects_on_composition_and_lattice():
    """Each operator does what its name claims."""
    base = _licl()
    rng = np.random.default_rng(0)

    strained, _ = op_strain(base, rng, 0.02)
    assert not np.allclose(strained.lattice.matrix, base.lattice.matrix)
    assert strained.composition.reduced_formula == "LiCl"

    vac, params = op_vacancy(base, rng)
    assert len(vac) == len(base) - 1
    assert params["removed_species"] == "Li"

    inter, _ = op_interstitial(base, rng)
    assert len(inter) == len(base) + 1
    assert inter.composition["Li"] == base.composition["Li"] + 1

    sub, params = op_substitute(base, rng, {"Li": ["Na"]})
    assert "Na" in {el.symbol for el in sub.composition.elements}
    assert "Li" not in {el.symbol for el in sub.composition.elements}
    assert params["old_element"] == "Li" and params["new_element"] == "Na"
    assert isinstance(params["smact_neutral"], bool)

    with pytest.raises(ValueError):
        op_vacancy(base, rng, mobile_ion="Mg")  # no Mg site to vacate


def test_absurd_displacement_trips_p0_clash():
    """Heavily perturbed structure must FAIL P0 on geometry, not pass silently.

    A 2-atom cell can dodge a clash by luck, so the test forces one overlap
    deterministically after a heavy operator-path displacement.
    """
    rng = np.random.default_rng(1)
    wrecked, _ = op_displace(_licl(), rng, sigma_A_provisional=2.5)
    wrecked.translate_sites(0, wrecked[1].coords - wrecked[0].coords,
                            frac_coords=False)  # site 0 lands on site 1
    res = evaluate_p0("LiCl", structure=wrecked)
    assert res.geometry_ok is False
    assert res.passed is False
    assert res.existence_state == ExistenceState.FAIL
    assert res.details["geometry"].get("clash_detected") is True


def test_near_zero_perturbation_tags_rediscovery():
    """Near-zero displacement must match the parent (rediscovery, not novel)."""
    kids = generate_children(
        _parent(), operators=["displace"], children_per_parent=2, seed=0,
        displacement_sigma_A_provisional=1e-6,
    )
    assert len(kids) == 2
    for kid in kids:
        assert kid.metadata["novelty_tag"] == "rediscovery"
        assert kid.metadata["novelty_matched"] == "parent"


def _li2o():
    """3-site fixture where Li vacancy breaks neutrality (Li2O -> LiO)."""
    lattice = Lattice.cubic(4.6)
    return Structure(lattice, ["Li", "Li", "O"],
                     [[0.0, 0.0, 0.0], [0.5, 0.5, 0.0], [0.5, 0.0, 0.5]])


def test_vacancy_child_tags_novel_and_runs_p0_at_birth():
    """A composition-changing child is novel and always carries a P0 verdict."""
    kids = generate_children(
        _parent(_li2o()), operators=["vacancy"], children_per_parent=1, seed=0)
    assert len(kids) == 1
    kid = kids[0]
    assert kid.metadata["novelty_tag"] == "novel"
    assert kid.metadata["p0_passed"] is False  # Li2O minus Li -> LiO: not neutral
    assert kid.existence_state == ExistenceState.FAIL
    assert "p0_rejection" in kid.metadata  # FAIL kept with reason, not dropped
    assert len(kid.evidence_log) == 1 and kid.evidence_log[0].level == "P0"


def test_liion_structureless_parent_not_perturbable(tmp_path):
    """LiIon rows without a matchable structure are retrievable, not perturbable."""
    if not Path("data/obelix").exists():
        pytest.skip("data/obelix repository not found locally")
    csv = tmp_path / "li.csv"
    csv.write_text(
        "ID,composition,source,temperature,target,log_target,family,ChemicalFamily\n"
        "1,UnobtaniumX2,doi:10.1/x,25.0,1e-4,-4.0,x,Oxides\n"
    )
    parents = retrieve_liion_parents(str(csv), "data/obelix")
    assert len(parents) == 1
    assert parents[0].structure is None
    assert parents[0].perturbable is False
    assert generate_children(parents[0], ["displace"], 2, seed=0) == []


def test_obelix_parent_retrieval_provenance():
    """OBELiX parents carry dataset + ID + sha256 provenance."""
    if not Path("data/obelix").exists():
        pytest.skip("data/obelix repository not found locally")
    parents = retrieve_obelix_parents("data/obelix")
    assert len(parents) > 300  # all CIF-linked entries, train AND test
    for p in parents[:5]:
        assert p.parent_id.startswith("obelix:")
        assert p.source_dataset == "obelix"
        assert len(p.structure_sha256) == 64
        assert "structure_sha256" in p.provenance
