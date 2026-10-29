import numpy as np
from pymatgen.core import Lattice, Structure
from rhombus.transport.cohort_audit import geometric_percolation_radius


def test_geometric_radius_is_deterministic_and_declares_limits():
    structure = Structure(Lattice.cubic(5), ['Li', 'O'], [[.5, .5, .5], [0, 0, 0]])
    result = geometric_percolation_radius(structure, spacing_A=1., min_dimension=5, max_dimension=5)
    assert np.isfinite(result['radius_A'])
    assert result == geometric_percolation_radius(structure, spacing_A=1., min_dimension=5, max_dimension=5)
    assert result['qualification'] == 'ABSTAIN'
    assert result['scope'] == 'VOXEL_GRAPH_MAXIMIN_NOT_CONTINUUM_CONVERGENCE'
