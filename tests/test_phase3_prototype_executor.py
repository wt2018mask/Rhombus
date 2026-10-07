from __future__ import annotations

from pymatgen.core import Lattice, Structure

from rhombus.domain import matbench_prototype_group


def test_frozen_prototype_executor_matches_matbench_nacl_label() -> None:
    nacl = Structure(
        lattice=[[2, 2, 0], [0, 2, 2], [2, 0, 2]],
        species=["Na", "Cl"],
        coords=[[0, 0, 0], [0.5, 0.5, 0.5]],
    )

    assert matbench_prototype_group(nacl) == "AB_cF8_225_a_b:Cl-Na"


def test_frozen_prototype_executor_matches_matbench_perovskite_label() -> None:
    perovskite = Structure(
        lattice=Lattice.cubic(3.9),
        species=["Sr", "Ti", "O", "O", "O"],
        coords=[
            [0, 0, 0],
            [0.5, 0.5, 0.5],
            [0.5, 0.5, 0],
            [0.5, 0, 0.5],
            [0, 0.5, 0.5],
        ],
    )

    assert matbench_prototype_group(perovskite) == "A3BC_cP5_221_c_a_b:O-Sr-Ti"
