import numpy as np
from pymatgen.core import Lattice, Structure
from rhombus.transport.cohort_audit import accessible_basin_fraction


def test_fixed_windows_do_not_depend_on_percolation_saddle():
    structure = Structure(Lattice.cubic(6), ['Li', 'O'], [[.5, .5, .5], [0, 0, 0]])
    field = np.full((6, 6, 6), 10.)
    field[2, 2, 0] = .4
    field[4, 0, 2] = .6
    host = lambda x: (np.zeros(len(x)), np.zeros_like(x))
    low = {'minimum_energy_eV': 0., 'barriers_eV': {'3D': .5}}
    high = {'minimum_energy_eV': 0., 'barriers_eV': {'3D': 2.}}
    a = accessible_basin_fraction(structure, host, field, low)
    b = accessible_basin_fraction(structure, host, field, high)
    assert a['fixed_window_counts'] == {'0.3': 0, '0.5': 1, '0.75': 2}
    assert a['fixed_window_fractions'] == b['fixed_window_fractions']
    assert a['x_vac_basin'] != b['x_vac_basin']
    assert a['qualification'] == 'ABSTAIN'
