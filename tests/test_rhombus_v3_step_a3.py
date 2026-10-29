"""A3 physics contracts: analytic forces, separate basins, and explicit priors."""
import hashlib
import subprocess
from pathlib import Path
import numpy as np
import pytest
from pymatgen.core import Structure,Lattice
from rhombus.transport.bvse_percolation import build_softbv_evaluator
from rhombus.transport.neb_pathway import relax_endpoint_local_basin,initialize_relaxed_pathway
from rhombus.transport.static_assessment import assess_host_frenkel_proxy,assess_vacancy_transport_a3
from rhombus.transport.bvse_percolation import percolation_thresholds
from rhombus.domain.archetypes import ARCHETYPES,build_archetype_a3
from rhombus.qualification.electrochemical_window import assess_electrochemical_window


def test_morse_minimum_is_not_shifted_by_duplicate_born_mayer():
    s=Structure(Lattice.cubic(30),['Li','O'],[[0,0,0],[.5,.5,.5]])
    evaluator=build_softbv_evaluator(s)
    point=np.array([15+1.96,15,15])
    energy,force=evaluator([point])
    assert energy[0]==pytest.approx(-.985,abs=1e-10)
    assert force[0]==pytest.approx([0,0,0],abs=1e-10)
    for axis in range(3):
        d=np.eye(3)[axis]*1e-5
        assert force[0,axis]==pytest.approx(-(evaluator([point+d])[0][0]-evaluator([point-d])[0][0])/2e-5,abs=1e-7)


def test_soft_boundary_never_mislabels_restrained_force_as_stationary():
    def outside(p):
        d=np.array(p)-[1.,0,0];return (d*d).sum(axis=1),-2*d
    r=relax_endpoint_local_basin([0,0,0],outside,radius_A=.65,boundary='soft')
    assert r['displacement_A']>.65 and not r['stationary'] and r['force_norm_eV_A']>.1


def test_periodic_same_basin_cannot_be_called_a_distinct_hop():
    def potential(p):
        p=np.array(p);return np.zeros(len(p)),np.zeros_like(p)
    with pytest.raises(ValueError,match='nominal endpoints'):
        initialize_relaxed_pathway(np.zeros((8,8,8)),Lattice.cubic(5),[0,0,0],[5,0,0],potential,separation_range_A=(2,4.2))


@pytest.mark.parametrize('name',ARCHETYPES)
def test_a3_structures_remain_explicit_and_overlap_free(name):
    info=build_archetype_a3(name,allow_idealized_completion=True);s=info['structure']
    assert s.is_ordered
    li=[i for i,a in enumerate(s) if a.specie.symbol=='Li']
    assert (s.distance_matrix[np.ix_(li,li)]+np.eye(len(li))*100).min()>=1.95
    if name=='argyrodite_Li6PS5Cl':
        d=info['defect']
        assert d['raw_crystallographic_site_count']==48
        assert d['maximum_occupiable_sites']==48 and d['stoichiometric_vacancy_fraction']==.5
        assert len(d['vacant_fractional_targets'])==24
        assert 'NOT_EXPERIMENTAL' in info['coordinate_status']
    if name=='LiCoO2':
        assert s.composition.element_composition.as_dict()=={'Li':3.,'Co':3.,'O':6.}
        for element,expected in [('Li',2.0932373),('Co',1.9210207)]:
            a=[i for i,v in enumerate(s) if v.specie.symbol==element];b=[i for i,v in enumerate(s) if v.specie.symbol=='O']
            assert s.distance_matrix[np.ix_(a,b)].min()==pytest.approx(expected,abs=1e-6)


def test_dilute_parent_window_keeps_strict_tieline_and_does_not_map_dopants():
    r=assess_electrochemical_window({'composition':'Li1.96875S'},reference_revision='A2',include_intrinsic=True,dilute_parent_limit=True)
    assert r['intrinsic_esw_volts']==pytest.approx([0,2.265])
    assert r['off_stoichiometric_tieline_window_volts']==pytest.approx([2.265,2.265])
    assert r['equilibrium_esw_volts']==pytest.approx([2.265,2.265])
    assert r['esw_evaluation_basis']=='PARENT_PHASE_DILUTE_DEFECT_LIMIT'
    for formula in ('Li1.8S','Li1.96875S0.96875Cl0.03125'):
        q=assess_electrochemical_window({'composition':formula},reference_revision='A2',include_intrinsic=True,dilute_parent_limit=True)
        assert 'parent_reference_id' not in q
    with pytest.raises(ValueError,match='requires intrinsic'):
        assess_electrochemical_window({'composition':'Li2S'},dilute_parent_limit=True)


def test_host_frenkel_proxy_preserves_raw_sign_and_excludes_spectators():
    s=build_archetype_a3('gamma_LiAlO2')['structure'];e=build_softbv_evaluator(s)
    field=e.grid(min_dimension=12,max_dimension=12)
    r=assess_host_frenkel_proxy(s,e,field,percolation_thresholds(field))
    assert r['site_energy_difference_eV']==pytest.approx(r['interstitial_energy_eV']-r['initial']['energy_eV'])
    assert r['binding_correction_eV']==0 and not r['negative_energy_clipped']
    assert r['hamiltonian']=='HOST_ONLY_PURE_MORSE_SCREENED_CATION_A3'


def test_current_ase_time_units_and_historical_v2_are_separate_contracts():
    from ase import units
    from rudeus.mlip.p2 import P2_PROTOCOL_VERSION,_ase_langevin_native_units
    dt,friction,fs=_ase_langevin_native_units(1.,.02)
    assert P2_PROTOCOL_VERSION=='p2-adaptive-v3-ase-units-fixcom-provisional'
    assert dt==pytest.approx(units.fs) and friction==pytest.approx(.02/units.fs)
    assert dt*friction==pytest.approx(.02) and fs==units.fs
    root=Path(__file__).resolve().parents[1]
    old=subprocess.check_output(['git','show','5bd77a241e72e9b52a97a86cafe96f78ddb11112:rudeus/mlip/p2.py'],cwd=root)
    assert hashlib.sha256(old).hexdigest()=='63d577fafd22238ef245d2988e87bc079b3b33b0905d5220e90804f4b0af471c'
    assert b'p2-adaptive-v2-fixcom-constraint-provisional' in old
    frozen=root/'data/batches/audit/p2_ordered_expansion_wave1_v1_authorized.json'
    assert hashlib.sha256(frozen.read_bytes()).hexdigest()=='bb6bf2050150146c2409738e5846d2eb32c3de5bca226b347623b31f39959010'


@pytest.mark.parametrize('name',['argyrodite_Li6PS5Cl','LiCoO2'])
def test_distinct_actual_hop_uses_stationary_endpoints_and_retains_cell_expansion(name):
    i=build_archetype_a3(name,allow_idealized_completion=True)
    r=assess_vacancy_transport_a3(i['structure'],defect=i['defect'],grid_dimension=24,mep_steps=1200)
    assert r['schema_version']=='rhombus-vacancy-transport-a3'
    assert 2<=r['initialization']['nominal_mic_distance_A']<=4.2
    assert 2<=r['initialization']['relaxed_mic_distance_A']<=4.2
    assert r['vacancy_migration_barrier_ev']>0
    assert r['mep']['endpoint_stationary']
    assert all(e['force_norm_eV_A']<=1e-3 for e in r['mep']['endpoint_relaxations'])
    assert r['model_parameters']['anion_born_mayer_scale']==0
    if name=='LiCoO2':assert r['periodic_probe_expansion']==[2,2,1]
