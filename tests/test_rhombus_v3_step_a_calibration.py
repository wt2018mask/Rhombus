"""Step A numerical falsification; never force a desired material ordering."""
import numpy as np
import pytest
from pymatgen.core import Structure, Lattice, Composition

from rhombus.domain.archetypes import ARCHETYPES,load_archetype
from rhombus.transport.bvse_parameters import build_site_evaluator
from rhombus.transport.bvse_percolation import SiteEnergyEvaluator,SpectatorSiteEnergyEvaluator,refine_channel_barrier
from rhombus.transport.neb_pathway import initialize_pathway_from_voxel_grid,refine_path_saddle
from rhombus.transport.static_assessment import assess_caged_transport
from rhombus.atomistics.phase_stability_p1 import assess_phase_stability
from rhombus.qualification.electrochemical_window import assess_electrochemical_window
from rhombus.qualification.reference_phases import DEFAULT_THERMOCHEMICAL_REFERENCES_V3,REFERENCE_MODEL_ID,default_phase_inputs
from rhombus.pipeline import RhombusDiscoveryFunnel


def test_periodic_sum_is_supercell_invariant_and_force_is_continuous():
    s=load_archetype('Li2S')['structure'];large=s.copy();large.make_supercell([2,2,2])
    a=build_site_evaluator(s,periodic_cutoff_A=8);b=build_site_evaluator(large,periodic_cutoff_A=8)
    x=np.array([[1.1,1.7,2.2],[2.854,1.3,1.9]])
    assert a(x)[0]==pytest.approx(b(x)[0],abs=1e-10)
    assert a(x)[1]==pytest.approx(b(x)[1],abs=1e-9)
    for axis in range(3):
        dx=np.zeros_like(x);dx[:,axis]=1e-5
        numeric=-(a(x+dx)[0]-a(x-dx)[0])/(2e-5)
        assert a(x)[1][:,axis]==pytest.approx(numeric,abs=2e-6)
    assert a(x+s.lattice.matrix[0])[0]==pytest.approx(a(x)[0],abs=1e-10)


def test_shell_adiabatic_gradient_and_energy_lowering_are_not_fitted_offsets():
    s=Structure(Lattice.cubic(8),['Li','S'],[[.7,.7,.7],[.5,.5,.5]])
    fixed=SiteEnergyEvaluator(s,anions={'S':(2.44,.44,.82)},cations={})
    soft=SiteEnergyEvaluator(s,anions={'S':(2.44,.44,.82)},cations={},shell_stiffness={'S':8},shell_max_A=.15)
    x=np.array([[5.9,4.,4.]])
    assert soft(x)[0][0]<fixed(x)[0][0]
    dx=np.array([[1e-5,0,0]])
    assert soft(x)[1][0,0]==pytest.approx(-(soft(x+dx)[0][0]-soft(x-dx)[0][0])/(2e-5),rel=1e-6)
    with pytest.raises(ValueError):
        SiteEnergyEvaluator(s,anions={'S':(2.44,.44,.82)},cations={},shell_stiffness={'S':-1})


def test_spectators_are_n_minus_one_and_vacancy_is_not_stripped_away():
    s=load_archetype('Li2S')['structure'];active=1
    bare=build_site_evaluator(s,periodic_cutoff_A=8)
    pristine=SpectatorSiteEnergyEvaluator(s,active,bare,periodic_cutoff_A=8)
    assert len(pristine.spectators)==7
    child=s.copy();target=child[0].coords.copy();child.remove_sites([0])
    vacancy=SpectatorSiteEnergyEvaluator(child,0,build_site_evaluator(child,periodic_cutoff_A=8),periodic_cutoff_A=8)
    assert len(vacancy.spectators)==6
    assert pristine([target])[0][0]>vacancy([target])[0][0]+1e6
    point=[[1.4,1.5,1.6]]
    assert bare(point)[0]==pytest.approx(build_site_evaluator(child,periodic_cutoff_A=8)(point)[0])


def test_voxel_dijkstra_curves_around_a_high_energy_straight_line():
    lattice=Lattice.cubic(8)
    grid=np.stack(np.meshgrid(*[np.arange(16)/2]*3,indexing='ij'),axis=-1)
    field=20*np.exp(-np.sum((grid-[4,4,4])**2,axis=3)/.4)
    path=initialize_pathway_from_voxel_grid(field,lattice,[1,4,4],[7,4,4],images=17)
    points=np.array(path['images_A'])
    assert points[0]==pytest.approx([1,4,4]) and points[-1]==pytest.approx([7,4,4])
    assert np.max(np.linalg.norm(points[:,1:]-4,axis=1))>1
    assert path['minimax_peak_energy_eV']<1
    def quadratic(x):
        x=np.array(x);return 1-(x[:,0]-.123)**2,np.column_stack((2*(x[:,0]-.123),np.zeros((len(x),2))))
    saddle=refine_path_saddle([[-1,0,0],[1,0,0]],quadratic)
    assert saddle['peak_energy_eV']==pytest.approx(1,abs=1e-8)
    assert saddle['position_A'][0]==pytest.approx(.123,abs=1e-5)


def test_curved_spectator_neb_removes_li2s_spike_without_forcing_point65_ev():
    s=load_archetype('Li2S')['structure']
    pristine=assess_caged_transport(s,grid_dimension=16,mep_steps=1000)
    child=s.copy();target=child[0].frac_coords.tolist();child.remove_sites([0])
    defective=assess_caged_transport(child,vacancy_targets=[target],grid_dimension=16,mep_steps=1000)
    assert pristine['mep']['converged'] and defective['mep']['converged']
    assert .65<defective['spectator_caged_hop_barrier_ev']<1.0
    assert defective['spectator_caged_hop_barrier_ev']<pristine['spectator_caged_hop_barrier_ev']<1.1
    assert pristine['defect_generation_penalty_ev']>0 and defective['defect_generation_penalty_ev']==0
    assert pristine['effective_activation_barrier_ev']>defective['effective_activation_barrier_ev']
    assert 'NOT_FRENKEL_FORMATION_ENERGY' in pristine['defect_generation_scope']
    assert defective['mep']['maximum_step_A']==.05
    with pytest.raises(ValueError,match='occupied'):
        assess_caged_transport(s,vacancy_targets=[s[0].frac_coords],grid_dimension=8)


def test_gamma_analytic_subvoxel_refinement_measures_grid_difference_below_point03():
    s=load_archetype('gamma_LiAlO2')['structure'];e=build_site_evaluator(s,periodic_cutoff_A=8)
    results=[refine_channel_barrier(e.grid(min_dimension=n,max_dimension=n),s.lattice,e,max_steps=1000) for n in (24,32)]
    assert all(r['converged'] for r in results)
    assert abs(results[0]['refined_channel_barrier_3d_ev']-results[1]['refined_channel_barrier_3d_ev'])<.03
    assert all(r['qualification']=='ABSTAIN' for r in results)


def test_thermochemical_prior_has_35_compounds_and_14_elements_and_correct_units():
    table=DEFAULT_THERMOCHEMICAL_REFERENCES_V3
    assert len(table)==49 and sum(len(Composition(f).elements)==1 for f in table)==14
    row,refs,meta=default_phase_inputs({'composition':'Li2S'})
    assert row['energy_eV']==pytest.approx(-1.510*3)
    assert meta['actual_source']=='OWNER_SUPPLIED_VALUES_NOT_INDEPENDENTLY_AUTHENTICATED'
    assert assess_phase_stability({'composition':'Li2S'})['energy_above_hull_meV_atom']==0
    assert assess_electrochemical_window({'composition':'Li2S'})['voltage_window_V']==pytest.approx([0,2.265])
    with pytest.raises(ValueError,match='foreign'):
        assess_phase_stability({'composition':'Li2S','energy_eV':-10,'energy_model_id':'MACE_ABSOLUTE'})
    with pytest.raises(ValueError,match='gauge'):
        assess_phase_stability({'composition':'Li2S','energy_eV':-10})
    with pytest.raises(ValueError,match='Ewald'):
        default_phase_inputs({'composition':'Li2S'},defect_energy_eV=-100,defect_energy_model_id='RAW_EWALD')


def test_unstable_phase_has_empty_window_not_fabricated_numeric_endpoints():
    result=assess_electrochemical_window({'composition':'Li6PS5Cl'})
    assert assess_phase_stability({'composition':'Li6PS5Cl'})['energy_above_hull_meV_atom']==pytest.approx(15.76923076923)
    assert result['voltage_window_V']==[] and result['stability_interval_status']=='EMPTY_UNSTABLE_PHASE'
    row,_,meta=default_phase_inputs({'composition':'Li2.5Y0.5Zr0.5Cl6'})
    assert meta['candidate_energy_basis']=='LOWEST_ENDMEMBER_MIXTURE_PRIOR_NOT_STABILITY_EVIDENCE'
    assert row['energy_model_id']==REFERENCE_MODEL_ID


@pytest.mark.parametrize('name',ARCHETYPES)
def test_source_archetypes_preserve_missing_and_processed_coordinate_identity(name):
    info=load_archetype(name)
    if name in ('Li3YCl6','Li2_5Y0_5Zr0_5Cl6','LiCoO2'):
        assert info['structure'] is None and info['coordinate_status']=='SOURCE_COORDINATES_UNAVAILABLE'
    else:
        s=info['structure'];assert s.is_ordered
        if name in ('cubic_Ta_LLZO','argyrodite_Li6PS5Cl'):
            assert abs(s.charge)<1e-8 and 'NOT_EXPERIMENTAL_ORIGINAL' in info['coordinate_status']
            assert info['defect']['vacant_fractional_targets']


def test_static_tier_does_not_turn_priors_into_material_qualification():
    assert RhombusDiscoveryFunnel._static_verdict({'P0':{'gate_verdict':'FALSIFIED_MIEC_ELECTRONIC_LEAKAGE'}})=='FALSIFIED_STATIC_P0_ELECTRONIC_LEAKAGE'
    assert RhombusDiscoveryFunnel._static_verdict({'P1':{'energy_above_hull_meV_atom':101}})=='FALSIFIED_STATIC_P1_UNSTABLE_HULL'
    assert RhombusDiscoveryFunnel._static_verdict({'P0_5':{'effective_activation_barrier_ev':1,'mep':{'converged':True}}})=='FALSIFIED_STATIC_P0_5_HIGH_BARRIER'
    assert RhombusDiscoveryFunnel._static_verdict({'P0_5':{'effective_activation_barrier_ev':10,'mep':{'converged':False}}})=='STATIC_SCREENING_INCONCLUSIVE'
    context={'P0':{'gate_verdict':'PASS_ELECTRONIC_INSULATOR'},'P1':{'energy_above_hull_meV_atom':0},
             'P0_5':{'effective_activation_barrier_ev':.4,'mep':{'converged':True,'barrier_ev':.4,'endpoints_stationary':True}}}
    assert RhombusDiscoveryFunnel._static_verdict(context)=='PROVISIONAL_STATIC_TIER1_CANDIDATE'
    candidate={'candidate_id':'synthetic','domain':'O_ONLY'}
    dossier=RhombusDiscoveryFunnel({}).run(candidate)
    assert dossier['final_qualification_verdict']=='ABSTAIN' and not dossier['scientific_GO']
