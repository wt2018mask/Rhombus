"""Lightweight contract tests for P2 center-of-mass handling."""

from ase import Atoms
from ase.constraints import FixCom

from rudeus.mlip.p2 import (
    P2_PROTOCOL_DEFAULTS,
    P2_PROTOCOL_VERSION,
    _configure_center_of_mass_constraint,
)


def test_p2_protocol_version_records_explicit_fixcom_contract():
    assert P2_PROTOCOL_VERSION == "p2-adaptive-v2-fixcom-constraint-provisional"
    assert P2_PROTOCOL_DEFAULTS["p2_protocol_version"] == P2_PROTOCOL_VERSION
    assert P2_PROTOCOL_DEFAULTS["fix_center_of_mass"] is True


def test_fixcom_constraint_applied_once_when_enabled():
    atoms = Atoms("Li2", positions=[[0, 0, 0], [1, 0, 0]])

    assert _configure_center_of_mass_constraint(atoms, True) is True
    assert sum(isinstance(c, FixCom) for c in atoms.constraints) == 1

    assert _configure_center_of_mass_constraint(atoms, True) is True
    assert sum(isinstance(c, FixCom) for c in atoms.constraints) == 1


def test_fixcom_constraint_not_applied_when_disabled():
    atoms = Atoms("Li", positions=[[0, 0, 0]])

    assert _configure_center_of_mass_constraint(atoms, False) is False
    assert not atoms.constraints
