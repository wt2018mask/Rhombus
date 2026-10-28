"""A2 numerical contracts, including explicit rejection of desired-label fitting."""
import numpy as np
import pytest
from pymatgen.core import Structure,Lattice,Species
from rhombus.generation.defect_engine import mobile_site_capacity,order_mobile_sites,order_fractional
from rhombus.transport.neb_pathway import relax_endpoint_local_basin,initialize_relaxed_pathway
from rhombus.transport.bvse_percolation import SiteEnergyEvaluator
from rhombus.transport.static_assessment import assess_vacancy_transport_a2
from rhombus.domain.archetypes import ARCHETYPES,build_archetype_a2,audit_prompt_coordinates
from rhombus.qualification.reference_phases import DEFAULT_THERMOCHEMICAL_REFERENCES_V3,DEFAULT_THERMOCHEMICAL_REFERENCES_A2
from rhombus.qualification.electrochemical_window import assess_electrochemical_window
from rhombus.atomistics.phase_stability_p1 import assess_phase_stability


def test_split_cluster_chain_is_not_incorrectly_collapsed_to_one_site():
    lattice=Lattice.cubic(10);sites=[[0,0,0],[.1,0,0],[.2,0,0]]
    r=mobile_site_capacity(lattice,sites)
    assert r['maximum_occupiable_sites']==2 and r['capacity_certified']
    assert len(r['split_clusters'])==1 and len(r['split_clusters'][0])==3
    s=Structure(lattice,[{Species('Li',1):2/3}]*3+[Species('O',-2)],sites+[[.5,.5,.5]])
    ordered=order_mobile_sites(s)
    assert ordered['maximum_occupiable_sites']==2 and ordered['stoichiometric_vacancy_fraction']==0
    assert ordered['minimum_li_li_distance_A']>=1.95
    assert ordered['raw_crystallographic_site_count']==3
    assert order_fractional(s,max_configurations=1)[0]['minimum_li_li_distance_A']>=1.95


def test_ordering_rejects_infeasible_population_instead_of_deleting_li():
    s=Structure(Lattice.cubic(8),[Species('Li',1),Species('Li',1),Species('O',-2)],[[0,0,0],[.1,0,0],[.5,.5,.5]])
    with pytest.raises(ValueError,match='capacity'):
        order_mobile_sites(s)


def test_endpoint_basin_relaxation_uses_physical_force_and_reports_boundary_failure():
    def potential(points):
        delta=np.asarray(points)-[.2,.1,0]
        return np.sum(delta*delta,axis=1),-2*delta
    result=relax_endpoint_local_basin([0,0,0],potential)
    assert result['stationary'] and result['force_norm_eV_A']<=1e-3
    assert result['position_A']==pytest.approx([.2,.1,0],abs=1e-4)
    assert result['displacement_A']<=.45
    def outside(points):
        delta=np.asarray(points)-[1.,0,0]
        return np.sum(delta*delta,axis=1),-2*delta
    result=relax_endpoint_local_basin([0,0,0],outside)
    assert not result['stationary'] and result['status']=='BASIN_BOUNDARY_NONSTATIONARY'
    assert result['displacement_A']==pytest.approx(.45)


def test_born_mayer_and_unscreened_contact_forces_match_energy_derivatives():
    s=Structure(Lattice.cubic(8),['Li','O','Al'],[[.1,.1,.1],[.5,.5,.5],[.8,.5,.5]])
    e=SiteEnergyEvaluator(s,anions={'O':(1.96,.39,.985)},cations={'Al':(3,1.295,.535)},
                         born_mayer={'O':(1,2.16,.29),'Al':(1,1.295,.29)},
                         unscreened_contacts={'Al':1.295},shell_stiffness={'O':20},periodic_cutoff_A=8)
    points=np.array([[5.8,4.1,4.],[5.4,4.2,4.1]])
    for axis in range(3):
        step=np.zeros_like(points);step[:,axis]=1e-5
        force=-(e(points+step)[0]-e(points-step)[0])/(2e-5)
        assert e(points)[1][:,axis]==pytest.approx(force,rel=2e-5,abs=2e-4)


@pytest.mark.parametrize('name',['cubic_Ta_LLZO','argyrodite_Li6PS5Cl'])
def test_pauli_ordered_models_have_certified_capacity_and_no_short_li_pairs(name):
    info=build_archetype_a2(name,allow_idealized_completion=True)
    d=info['defect'];s=info['structure']
    assert d['minimum_li_li_distance_A']>=1.95
    assert d['capacity_certified'] and abs(s.charge)<1e-8
    count=sum(a.specie.symbol=='Li' for a in s)
    assert d['stoichiometric_vacancy_fraction']==pytest.approx((d['maximum_occupiable_sites']-count)/d['maximum_occupiable_sites'])
    assert 'NOT_EXPERIMENTAL' in info['coordinate_status']


def test_supplied_partial_tables_are_audited_instead_of_called_published_exact():
    audit=audit_prompt_coordinates()
    assert audit['argyrodite_nearest_P_S_A']>4
    assert sum(audit['halide_supplied_Cl_orbit_multiplicities'])!=18
    for name in ('Li3YCl6','argyrodite_Li6PS5Cl','cubic_Ta_LLZO'):
        with pytest.raises(ValueError,match='experimental table'):
            build_archetype_a2(name)
    cobalt=build_archetype_a2('LiCoO2')
    assert cobalt['structure'].composition.element_composition.reduced_formula=='LiCoO2'
    assert len(cobalt['structure'])==12
    assert 'NOT_INDEPENDENTLY_AUTHENTICATED' in cobalt['coordinate_status']


@pytest.mark.parametrize('name',ARCHETYPES)
def test_all_ten_model_structures_are_explicit_and_charge_accounted(name):
    info=build_archetype_a2(name,allow_idealized_completion=True)
    assert info['structure'] is not None and info['structure'].is_ordered
    if name=='Li2S_vacancy':assert info['defect']['formal_charge_e']==-1
    elif name in ('LiCoO2','cubic_Ta_LLZO','argyrodite_Li6PS5Cl','Li3YCl6','Li2_5Y0_5Zr0_5Cl6'):
        assert abs(info['structure'].charge)<1e-8


def test_revised_energy_is_versioned_and_result_window_is_not_forced_to_prompt():
    assert DEFAULT_THERMOCHEMICAL_REFERENCES_V3['Li6PS5Cl']==-1.365
    assert DEFAULT_THERMOCHEMICAL_REFERENCES_A2['Li6PS5Cl']==-1.468
    r=assess_electrochemical_window({'composition':'Li6PS5Cl'},reference_revision='A2',include_intrinsic=True)
    assert r['equilibrium_esw_volts']==pytest.approx([1.5572,2.6858])
    assert r['intrinsic_esw_volts']==pytest.approx(r['equilibrium_esw_volts'])
    assert 'NOT_INDEPENDENT_CALIBRATION' in r['revision_basis']
    assert assess_phase_stability({'composition':'Li6PS5Cl'},reference_revision='A2')['energy_above_hull_meV_atom']==0


def test_hull_projection_does_not_invent_nonzero_width_at_an_interior_tie_line():
    r=assess_electrochemical_window({'composition':'Li1.96875S'},include_intrinsic=True,reference_revision='A2')
    assert r['intrinsic_esw_volts']==pytest.approx([2.265,2.265])
    assert r['intrinsic_status']=='ZERO_WIDTH_HULL_FACET'
    changed=assess_electrochemical_window({'composition':'Li1.96875S'},include_intrinsic=True,
                                         reference_revision='A2',projection_offset_eV_atom=.001)
    assert changed['intrinsic_esw_volts'][1]>changed['intrinsic_esw_volts'][0]
    assert changed['projection_offset_eV_atom']==.001 and changed['qualification']=='ABSTAIN'


def test_relaxed_true_lattice_to_lattice_probe_separates_frenkel_hamiltonian():
    import json
    from rhombus.pipeline import RhombusDiscoveryFunnel
    intrinsic=build_archetype_a2('gamma_LiAlO2')
    r=assess_vacancy_transport_a2(intrinsic['structure'],grid_dimension=12,mep_steps=600)
    assert r['migration_probe_mobile_count']==3 and r['spectator_count']==2
    assert r['frenkel']['required'] and r['frenkel']['binding_correction_eV']<=0
    assert r['mechanism']=='TEMPORARY_VACANCY_HOP_PLUS_SEPARATE_FRENKEL_PROXY'
    assert r['mep']['endpoint_stationary']
    assert all(e['force_norm_eV_A']<=1e-3 for e in r['mep']['endpoint_relaxations'])
    # Uncalibrated Hamiltonian cannot be repaired by asserting the desired >1 eV.
    assert r['model_applicability']=='UNQUALIFIED' and r['qualification']=='ABSTAIN'
    json.dumps(r,allow_nan=False)
    if r['frenkel']['site_energy_difference_eV']<0:
        assert RhombusDiscoveryFunnel._static_verdict({'P0_5':r})=='STATIC_MODEL_INAPPLICABLE_NEGATIVE_FRENKEL_ENERGY'
    ext=build_archetype_a2('Li2S_vacancy')
    q=assess_vacancy_transport_a2(ext['structure'],defect=ext['defect'],grid_dimension=12,mep_steps=600)
    assert not q['frenkel']['required'] and q['defect_generation_penalty_ev']==0
    assert q['mep']['endpoint_stationary']
