import numpy as np
import pytest
from pymatgen.core import Lattice
from rhombus.transport.path_numerical_audit import inspect_witness
from rhombus.transport.bvse_percolation import percolation_thresholds


def test_diagonal_edge_has_unseen_obstacle_and_energy_spike():
    lattice=Lattice.cubic(4)
    def potential(x):
        d=np.sin(np.pi*(x-np.array([1.,1.,0.]))/4); return np.exp(-np.sum(d*d,axis=1)/.02),np.zeros_like(x)
    result=inspect_witness([[0,0,0],[.5,.5,0],[1,1,0]], [1,1,0], lattice, potential,
                           [[.25,.25,0]], [.3], max_spacing_A=.025)
    assert result['winding_matches']
    assert result['missed_barrier_eV']>.99
    assert result['steric_overlap_sampled']


def test_neighborhood_threshold_monotonic_and_winding():
    rng=np.random.default_rng(5);field=rng.normal(size=(4,4,4))
    graphs=[percolation_thresholds(field,neighborhood=n) for n in (6,18,26)]
    assert graphs[0]['barriers_eV']['3D'] >= graphs[1]['barriers_eV']['3D'] >= graphs[2]['barriers_eV']['3D']
    for g in graphs:
        for cycle in g['percolating_cycles']['3D']:
            assert np.allclose(np.subtract(cycle['fractional_path'][-1],cycle['fractional_path'][0]),cycle['winding_vector'])
    with pytest.raises(ValueError):percolation_thresholds(field,neighborhood=7)


def test_nonorthogonal_cartesian_path_and_origin_shift():
    lattice=Lattice([[4,0,0],[1,4,0],[.2,.3,4]])
    eval_zero=lambda p:(np.zeros(len(p)),np.zeros_like(p))
    path=np.array([[.1,.2,.3],[.6,.2,.3],[1.1,.2,.3]])
    x=inspect_witness(path,[1,0,0],lattice,eval_zero,[[0,0,0]],[.2],max_spacing_A=.05)
    y=inspect_witness(path+1,[1,0,0],lattice,eval_zero,[[0,0,0]],[.2],max_spacing_A=.05)
    assert x['winding_matches'] and x['sampled_min_clearance_A']==pytest.approx(y['sampled_min_clearance_A'])


def test_half_voxel_origin_changes_analytic_grid_samples():
    n=8
    zero=np.arange(n)/n
    shifted=(np.arange(n)+.5)/n
    field=lambda x:np.cos(2*np.pi*x)
    assert np.max(field(zero)) == pytest.approx(1.)
    assert np.max(field(shifted)) < 1.
    assert field(0.1) == pytest.approx(field(1.1))
