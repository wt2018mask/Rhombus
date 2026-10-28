"""Analytic/synthetic reference problems; never material calibration receipts."""
import json
import sys
from urllib.error import URLError
import numpy as np
import pytest
from rhombus.transport.bvse_percolation import SiteEnergyEvaluator,percolation_thresholds
from rhombus.transport.neb_pathway import ClimbingImageMEPSolver
from rhombus.transport.arrhenius_ensemble import quantify_arrhenius,KB_EV
from rhombus.qualification.cross_falsifier import compare_evaluators
from rhombus.pipeline import RhombusDiscoveryFunnel


def test_voxel_thresholds_detect_independent_periodic_directions():
    field=np.full((4,4,4),5.);field[:,:,0]=1.;field[:,0,0]=0.
    result=percolation_thresholds(field)
    assert result['barriers_eV']=={'1D':0.,'2D':1.,'3D':5.}
    assert result['qualification']=='ABSTAIN'
    for rank,cycles in result['percolating_cycles'].items():
        assert np.linalg.matrix_rank([c['winding_vector'] for c in cycles])==int(rank[0])
        for cycle in cycles:
            path=np.array(cycle['fractional_path'])
            assert np.max(np.abs(np.diff(path,axis=0)))<=.25+1e-12
            assert path[-1]-path[0]==pytest.approx(cycle['winding_vector'])
            assert cycle['maximum_energy_eV']<=result['barriers_eV'][rank]
    with pytest.raises(ValueError):percolation_thresholds(np.full((3,3,3),np.nan))


def test_voxel_witness_clearance_requires_explicit_host_radii():
    from pymatgen.core import Lattice
    result=percolation_thresholds(np.zeros((3,3,3)),lattice=Lattice.cubic(6),
                                  host_fractional=[[.5,.5,.5]],host_radii_A=[1.])
    assert result['bottleneck_status']=='VOXEL_WITNESS_CLEARANCE'
    assert np.isfinite(result['bottleneck_radius_A'])
    assert result['qualification']=='ABSTAIN'
    with pytest.raises(ValueError):percolation_thresholds(np.zeros((3,3,3)),host_radii_A=[1.])


def test_site_energy_gradient_and_periodic_identity():
    from pymatgen.core import Structure,Lattice
    structure=Structure(Lattice.cubic(7),['Li','O','Al'],[[.1,.1,.1],[.7,.4,.4],[.5,.7,.5]])
    with pytest.raises(ValueError,match='missing'):SiteEnergyEvaluator(structure,anions={},cations={})
    potential=SiteEnergyEvaluator(structure,anions={'O':(2.,.4,.3)},cations={'Al':(3.,1.,1.)})
    x=np.array([[1.,1.7,2.1]]);energy,force=potential(x)
    for axis in range(3):
        delta=np.zeros_like(x);delta[0,axis]=1e-5
        derivative=(potential(x+delta)[0]-potential(x-delta)[0])/(2e-5)
        assert force[0,axis]==pytest.approx(-derivative[0],rel=1e-5,abs=1e-6)
    assert potential(x+np.array([7.,0,0]))[0]==pytest.approx(energy)
    assert potential.grid(min_dimension=3,max_dimension=4).shape==(4,4,4)


@pytest.mark.parametrize('cod',['1008166','9009060'])
def test_real_pilot_crystals_cannot_inherit_invented_bvse_calibration(cod):
    from pathlib import Path
    from pymatgen.core import Structure
    path=Path(__file__).resolve().parents[1]/'data/benchmarks/known_material/structures/cod'/f'{cod}-latest-freeze-v1.cif'
    structure=Structure.from_file(path)
    assert 'Li' in [site.specie.symbol for site in structure]
    with pytest.raises(ValueError,match='missing explicit host parameters'):
        SiteEnergyEvaluator(structure,anions={},cations={})


@pytest.mark.parametrize('height',[.1,1.])
def test_climbing_band_double_well(height):
    def evaluator(points):
        x,y,z=points.T
        return height*(x*x-1)**2+y*y+z*z,np.column_stack((-4*height*x*(x*x-1),-2*y,-2*z))
    result=ClimbingImageMEPSolver().solve([-1,0,0],[1,0,0],evaluator)
    assert result['converged'] and result['barrier_ev']==pytest.approx(height)
    assert result['reverse_barrier_ev']==pytest.approx(height)
    assert result['qualification']=='ABSTAIN'


def test_steric_initialization_and_unconverged_evaluator():
    def evaluator(x):return np.sum(x*x,axis=1),-2*x
    result=ClimbingImageMEPSolver().solve([-2,0,0],[2,0,0],evaluator,host_positions=[[0,0,0]],max_steps=1)
    assert result['min_host_clearance_angstrom']>=.5
    assert not result['converged']
    with pytest.raises(ValueError):ClimbingImageMEPSolver().solve([0,0,0],[1,0,0],lambda x:(np.zeros(len(x)),np.full_like(x,np.nan)))


def test_curved_band_requires_actual_force_optimization():
    def evaluator(points):
        x,y,z=points.T
        delta=y-.3*(1-x*x)
        energy=.2*(x*x-1)**2+delta*delta+z*z
        force=np.column_stack((-.8*x*(x*x-1)-1.2*x*delta,-2*delta,-2*z))
        return energy,force
    result=ClimbingImageMEPSolver().solve([-1,0,0],[1,0,0],evaluator,max_steps=2000)
    assert result['converged'] and result['iterations']>1
    assert result['barrier_ev']==pytest.approx(.2,abs=.001)
    assert np.max(np.array(result['positions_A'])[:,1])>.25


def test_optional_ase_adapter_never_evaluates_without_host_permission():
    from ase import Atoms
    from rhombus.transport.neb_pathway import ASEMobileIonEvaluator
    evaluator=ASEMobileIonEvaluator(Atoms('Li',positions=[[0,0,0]]),0,None)
    with pytest.raises(PermissionError):evaluator([[0,0,0]])


def records(temperatures=(400.,500.,600.,700.)):
    return [dict(temperature_K=t,diffusivity_m2_s=1e-6*np.exp(-.25/(KB_EV*t)),
                 diffusivity_variance=(1e-6*np.exp(-.25/(KB_EV*t))*.03)**2,
                 seed=seed,p2_verdict='PASS',regime='DIFFUSIVE_FICKIAN') for t in temperatures for seed in (1,2)]


def test_arrhenius_recovers_conditional_activation_and_units():
    result=quantify_arrhenius(records(),carrier_count=4,volume_A3=1000)
    assert result['activation_energy_ev']==pytest.approx(.25,abs=1e-9)
    assert result['arrhenius_r2']==pytest.approx(1.)
    assert result['sigma_95_ci_s_cm'][0]<result['extrapolated_sigma_298k_s_cm']<result['sigma_95_ci_s_cm'][1]
    half=quantify_arrhenius(records(),carrier_count=4,volume_A3=1000,haven_ratio=2.)
    assert half['extrapolated_sigma_298k_s_cm']==pytest.approx(result['extrapolated_sigma_298k_s_cm']/2)
    assert result['qualification']=='ABSTAIN'
    assert quantify_arrhenius(records((500.,550.)),carrier_count=4,volume_A3=1000)['p3_verdict']=='INSUFFICIENT_TEMPERATURE_LEVER_ARM'
    bad=records();bad[0]['regime']='SUBDIFFUSIVE_TRANSIENT'
    with pytest.raises(ValueError):quantify_arrhenius(bad,carrier_count=4,volume_A3=1000)


def test_cross_model_disagreement_is_not_independence_proof():
    a={'model_id':'a','volume_A3':100.,'barrier_eV':.1,'fast_diffusion':True}
    b={'model_id':'b','volume_A3':110.,'barrier_eV':.4}
    result=compare_evaluators(a,b,host_rmsd_A=1.,host_limit_A=.5)
    assert len(result['reasons'])==3 and result['verdict']=='MODEL_DISAGREEMENT_OOD'
    assert compare_evaluators(a,a,host_rmsd_A=0,host_limit_A=.5)['verdict']=='INDEPENDENCE_NOT_ESTABLISHED'
    assert 'FRAMEWORK_MELTING_ARTIFACT' in compare_evaluators(a,a,host_rmsd_A=1,host_limit_A=.5)['reasons']


@pytest.mark.parametrize('domain',['O_ONLY','S_ONLY','HALIDE'])
def test_funnel_early_exit_hash_and_full_diagnostic_flow(domain):
    from rhombus.pipeline.funnel import STAGES
    calls=[]
    def reject(context):calls.append('reject');return {'decision':'REJECT','reason':'synthetic high barrier'}
    def forbidden(context):raise AssertionError('downstream calculation executed')
    candidate={'candidate_id':'synthetic','domain':domain}
    funnel=RhombusDiscoveryFunnel({'G_P0':lambda c:{'decision':'CONTINUE'},'P0_5':reject,'P2':forbidden})
    first=funnel.run(candidate);second=funnel.run(candidate)
    assert first['dossier_sha256']==second['dossier_sha256']
    assert first['compute_saved_stages']==['P2_MD','P3_ARRHENIUS']
    assert not first['scientific_GO']
    full=RhombusDiscoveryFunnel({stage:lambda c:{'decision':'CONTINUE'} for stage in STAGES}).run(candidate)
    assert len(full['observations'])==8 and full['qualification']=='ABSTAIN'


@pytest.mark.parametrize('module_name', ['original_bulk_grain_routes_0170','original_cross_paper_transfer_0169'])
def test_pr_timeout_runs_real_offline_regressions_and_manual_remains_strict(tmp_path,monkeypatch,module_name):
    import importlib
    module=importlib.import_module('scripts.science.'+module_name)
    def timeout():raise URLError(TimeoutError('synthetic timeout'))
    monkeypatch.setattr(module,'run_original',timeout)
    target=tmp_path/'pr'
    monkeypatch.setattr(sys,'argv',['tool','--live-original','--allow-source-timeout','--output-dir',str(target)])
    module.main()
    receipt=json.loads((target/'source-unavailable.json').read_text())
    assert receipt['offline_regression_status']=='VERIFIED' and receipt['sha256'] is None
    monkeypatch.setattr(sys,'argv',['tool','--live-original','--require-live-network','--output-dir',str(tmp_path/'strict')])
    with pytest.raises(URLError):module.main()
    def mismatch():raise ValueError('checksum mismatch')
    monkeypatch.setattr(module,'run_original',mismatch)
    monkeypatch.setattr(sys,'argv',['tool','--live-original','--allow-source-timeout','--output-dir',str(tmp_path/'bad')])
    with pytest.raises(ValueError,match='checksum'):module.main()
