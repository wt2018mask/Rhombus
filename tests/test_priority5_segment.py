import numpy as np
import pytest
from pymatgen.core import Lattice, Structure
from rhombus.transport.segment_percolation import segment_percolation
from rhombus.transport.bvse_percolation import percolation_thresholds, SiteEnergyEvaluator


def test_segment_graph_preserves_periodic_cycles_and_detects_edges():
    lattice=Lattice.cubic(4);n=4
    def energy(x):
        d=np.sin(np.pi*(x-np.array([.5,.5,0]))/4)
        return np.exp(-np.sum(d*d,axis=1)/.02),np.zeros_like(x)
    xyz=np.stack(np.meshgrid(*([np.arange(n)/n]*3),indexing='ij'),axis=-1)
    field=energy(lattice.get_cartesian_coords(xyz.reshape(-1,3)))[0].reshape((n,n,n))
    graph=segment_percolation(field,lattice,energy,max_spacing_A=.1)
    assert graph['barrier_3d_eV'] >= percolation_thresholds(field)['barriers_eV']['3D']-1e-12
    assert len(graph['cycles_3d'])==3
    for c in graph['cycles_3d']:
        assert np.allclose(np.subtract(c['fractional_path'][-1],c['fractional_path'][0]),c['winding_vector'])
    assert graph['qualification']=='ABSTAIN'


def test_multi_image_gradient_periodicity_and_supercell():
    s=Structure(Lattice.cubic(6),['Li','O'],[[.25,.25,.25],[0,0,0]])
    args={'anions':{'O':(2.,.4,1.)},'cations':{},'pauli':False,'periodic_cutoff_A':8.}
    a=SiteEnergyEvaluator(s,**args);t=s.copy();t.make_supercell([2,2,2]);b=SiteEnergyEvaluator(t,**args)
    points=np.array([[3.-1e-5,.4,.5],[3.+1e-5,.4,.5],[7.5,0,0]])
    ea,fa=a(points);eb,fb=b(points)
    np.testing.assert_allclose(ea,eb,rtol=1e-11,atol=1e-11);np.testing.assert_allclose(fa,fb,rtol=1e-11,atol=1e-11)
    np.testing.assert_allclose(a(points+np.array([6.,0,0]))[0],ea,atol=1e-11)
    h=1e-5;grad=(a(points+np.array([h,0,0]))[0]-a(points-np.array([h,0,0]))[0])/(2*h)
    np.testing.assert_allclose(grad,-fa[:,0],rtol=1e-5,atol=1e-7)
    assert abs(fa[0,0]-fa[1,0])<1e-3


def test_string_force_projection_and_endpoint_constraints():
    from rhombus.transport.periodic_string import relax_periodic_string
    p=np.array([[0.,0.,0.],[.25,.5,0.],[.5,.5,0.],[.75,.5,0.],[1.,0.,0.]])
    def potential(x):return x[:,1]**2,np.column_stack([np.zeros(len(x)),-2*x[:,1],np.zeros(len(x))])
    result=relax_periodic_string(p,potential,max_iterations=200,force_tolerance_eV_A=.001,step_scale=.2,max_step_A=.05)
    assert result['converged'] and result['max_perpendicular_force_eV_A']<=.001
    np.testing.assert_allclose(result['points_cartesian'][0],p[0]);np.testing.assert_allclose(result['points_cartesian'][-1],p[-1])
    assert result['qualification']=='ABSTAIN'


@pytest.mark.parametrize('radius',[7.,7.5,8.])
def test_quintic_switch_force_gradient_at_boundary(radius):
    s=Structure(Lattice.cubic(30),['Li','O'],[[.2,.2,.2],[0,0,0]])
    ev=SiteEnergyEvaluator(s,anions={'O':(2.,.4,1.)},cations={},pauli=False,periodic_cutoff_A=8.)
    p=np.array([[radius,0.,0.]]);h=1e-5;e,f=ev(p)
    derivative=(ev(p+np.array([h,0,0]))[0]-ev(p-np.array([h,0,0]))[0])/(2*h)
    assert derivative[0] == pytest.approx(-f[0,0],abs=1e-7)
    assert abs(ev(p+np.array([h,0,0]))[0][0]-ev(p-np.array([h,0,0]))[0][0]) < 1e-8


def test_interior_energy_changes_graph_threshold_before_witness_selection():
    lattice=Lattice.cubic(4); n=4
    def field(x):return 1.+np.sin(np.pi*x[:,0]),np.zeros_like(x)
    frac=np.stack(np.meshgrid(*([np.arange(n)/n]*3),indexing='ij'),axis=-1)
    vertices=field(lattice.get_cartesian_coords(frac.reshape(-1,3)))[0].reshape((n,)*3)
    old=percolation_thresholds(vertices)['barriers_eV']['3D']
    new=segment_percolation(vertices,lattice,field,max_spacing_A=.05)['barrier_3d_eV']
    assert old < 1e-10 and new > .99


def test_steric_cohort_subset_and_p0_bond_separation():
    import json
    from pathlib import Path
    path=Path(__file__).parents[1]/'data/benchmarks/v3_static/priority5_steric_v1.json'
    result=json.loads(path.read_text());assert len(result['rows'])==72
    assert result['summary']['OS']['COMPLETED']['n']==3
    assert result['summary']['OS']['EXPLOSIVE']['n']==28
    for row in result['rows']:
        if row['anion_min_pair'] is not None:
            assert set(row['anion_min_pair']) <= set(result['anion_symbols'])
    assert result['qualification']=='ABSTAIN'
