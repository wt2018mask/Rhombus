import importlib.util
from pathlib import Path
import numpy as np
import pytest
from pymatgen.core import Lattice
from scipy.special import logsumexp
from rhombus.transport.periodic_clearance import complete_images,periodic_clearance,sampled_lipschitz_bound
from rhombus.transport.soft_clearance import soft_clearance


def test_bcc_tie_tangent_and_gradient():
    q=np.array([[1.5,1.5,0.]]);sites=np.array([[0,0,0],[2,2,2],[2,2,-2.]])
    d=np.linalg.norm(q-sites,axis=1);np.testing.assert_allclose(d,1.5*np.sqrt(2),atol=1e-12)
    avg=np.mean((q-sites)/d[:,None],axis=0);np.testing.assert_allclose(avg,[1/(9*np.sqrt(2)),1/(9*np.sqrt(2)),0],atol=1e-12)
    _,g=soft_clearance(q,sites,np.ones(3)*1.2,30);assert g[0]@np.array([-1,1,0])==pytest.approx(0,abs=1e-12)
    h=1e-5;num=(soft_clearance(q+[[h,0,0]],sites,np.ones(3)*1.2,30)[0]-soft_clearance(q-[[h,0,0]],sites,np.ones(3)*1.2,30)[0])/(2*h);assert num[0]==pytest.approx(g[0,0],abs=1e-8)


def test_skew_image_exclusion_and_lipschitz():
    lat=Lattice([[4,0,0],[3.7,1,0],[2.9,.4,2]])
    frac=np.array([[.1,.2,.3],[.6,.4,.8]]);r=np.array([1.,1.3]);img,rad,meta=complete_images(lat,frac,r,margin_A=.025);assert meta['periodic_image_completeness_verified']
    points=lat.get_cartesian_coords([[.01,.93,.25],[.87,.04,.75]])
    value=periodic_clearance(points,lat,img,rad);shell=np.array(np.meshgrid(*([np.arange(-12,13)]*3),indexing='ij')).reshape(3,-1).T;candidate=lat.get_cartesian_coords((frac[None]+shell[:,None]).reshape(-1,3));reference=(np.linalg.norm(points[:,None]-candidate,axis=2)-np.tile(r,len(shell))).min(axis=1);np.testing.assert_allclose(value,reference,atol=1e-10)
    bounds=sampled_lipschitz_bound(points,lat,img,rad,max_spacing_A=.025);dense=points[0]+np.linspace(0,1,5001)[:,None]*(points[1]-points[0]);actual=periodic_clearance(dense,lat,img,rad).min();assert bounds['lower_bound_A']<=actual+1e-10


def test_logsumexp_normalization_sampling_is_not_invariant():
    tau=.1;e=np.array([0.,1.]);other=np.array([0.,1.,1.]);raw=lambda x:tau*logsumexp(x/tau);norm=lambda x:raw(x)-tau*np.log(len(x));assert norm(e)!=pytest.approx(norm(other));assert (raw(e)-norm(e))==pytest.approx(tau*np.log(len(e)))
    # Duplicate every bead equally: normalized value is unchanged only in this special case.
    assert norm(e)==pytest.approx(norm(np.repeat(e,2)))


def test_sc_exact_cavity_and_face():
    lat=Lattice.cubic(4);img,rad,meta=complete_images(lat,[[0,0,0]],[1.2]);pts=np.array([[2,2,2],[0,2,2]])
    np.testing.assert_allclose(periodic_clearance(pts,lat,img,rad),[2*np.sqrt(3)-1.2,2*np.sqrt(2)-1.2],atol=1e-12)


def test_actual_graph_cosine_and_sc_analytical_references():
    from rhombus.transport.segment_percolation import segment_percolation
    n=4;u=np.stack(np.meshgrid(*([np.arange(n)/n]*3),indexing='ij'),axis=-1).reshape(-1,3)
    lat=Lattice.cubic(5);amps=np.array([.2,.35,.5])
    def cos(x):
        t=2*np.pi*x/5;return ((1-np.cos(t))*amps).sum(axis=1),-(2*np.pi/5)*np.sin(t)*amps
    f=cos(lat.get_cartesian_coords(u))[0].reshape((n,n,n));g=segment_percolation(f,lat,cos,origin=np.zeros(3),max_spacing_A=.15)
    assert g['barrier_3d_eV']==pytest.approx(1.,abs=1e-12)
    sc=Lattice.cubic(4);images,radii,meta=complete_images(sc,[[0,0,0]],[1.2])
    def negative(x):return -periodic_clearance(x,sc,images,radii),np.zeros_like(x)
    field=negative(sc.get_cartesian_coords(u))[0].reshape((n,n,n));graph=segment_percolation(field,sc,negative,origin=np.zeros(3),max_spacing_A=.15)
    assert -graph['thresholds_eV']['3D']==pytest.approx(2*np.sqrt(2)-1.2,abs=1e-12)


def test_actual_joint_reports_stationarity_and_sampling():
    path=Path(__file__).parents[1]/'scripts/diagnostics/priority7_joint.py';spec=importlib.util.spec_from_file_location('r1_joint',path);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    p=np.array([[0.,0,0],[.5,.2,0],[1.,0,0]])
    def host(x):return x[:,1]**2,np.column_stack((np.zeros(len(x)),-2*x[:,1],np.zeros(len(x))))
    final,meta=mod.joint_relax([p],host,max_iterations=3)
    assert meta['smoothmax_raw_eV']-meta['smoothmax_normalized_eV']==pytest.approx(.05*np.log(len(final[0])))
    assert meta['final_max_perp_force_ev_per_A'] is not None
    d=mod.sampling_diagnostic(final[0],host);assert d['uniform_2N']['n']==2*d['uniform_N']['n']


def test_lipschitz_remains_valid_at_host_center():
    lattice=Lattice.cubic(4);images,r,meta=complete_images(lattice,[[0,0,0]],[1.2]);points=np.array([[0.,0,0],[2.,0,0]])
    measured=sampled_lipschitz_bound(points,lattice,images,r,max_spacing_A=.025)
    assert measured['lower_bound_A']<=-1.2 and measured['sampled_min_clearance_A']==pytest.approx(-1.2)


def test_bcc_tetrahedral_vertex_exact_clearance():
    lattice=Lattice.cubic(4);images,radii,metadata=complete_images(lattice,[[0,0,0],[.5,.5,.5]],[1.2,1.2]);assert metadata['periodic_image_completeness_verified']
    assert periodic_clearance(np.array([[2.,1.,0.]]),lattice,images,radii)[0]==pytest.approx(np.sqrt(5)-1.2,abs=1e-12)


def test_summary_requires_measured_topology_and_stationarity():
    path=Path(__file__).parents[1]/'scripts/diagnostics/priority7_summary.py';spec=importlib.util.spec_from_file_location('r1_summary',path);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    good={'topology_valid':True,'final_max_segment_length_A':.1,'adaptive_post_recheck':'PASSED','convergence_classification':'LOCALLY_STATIONARY_ON_FIXED_BEADS'}
    assert mod.qualifies(good,.02)
    assert not mod.qualifies(good,.021)
    assert not mod.qualifies({**good,'topology_valid':False},.01)
    assert not mod.qualifies({},None)


def test_final_accepted_refinement_retained_on_actual_witness():
    import json
    path=Path(__file__).parents[1]/'data/benchmarks/v3_static/priority7_li2s_n16_o0_joint_r1_v4.json'
    data=json.loads(path.read_text())
    assert data['termination_reason']=='FINAL_REFINEMENT_ACCEPTED_NO_POLISH_BUDGET'
    added=sum(sum(r['additional_insertions']) for r in data['rounds'])
    assert sum(len(p) for p in data['final_points_cartesian'])==data['initial_beads']+added
    assert data['convergence_classification']=='FEASIBLE_WITNESS_NON_STATIONARY'
    assert data['joint_optimizer']['final_max_perp_force_ev_per_A']>0
