import pytest
from rhombus.qualification.opinion_synthesizer import synthesize_scientific_opinion


def test_preserves_abort_and_abstains_without_inventing_values():
    record = {'formula': 'Li2S', 'relaxed_sha256': 'abc',
              'relaxed': {'host_channel_barrier_3d_ev': 1.2, 'x_vac': None},
              'p2_records': [{'termination': {'completed': False, 'note': 'explosive-step'}}]}
    result = synthesize_scientific_opinion(record)
    assert result['section_4_thermochemical_and_dynamic_linkage']['p2_records'][0]['termination']['completed'] is False
    assert result['section_4_thermochemical_and_dynamic_linkage']['p2_summary'][0]['status'] == 'UNFINISHED_EXPLOSIVE_STEP'
    assert result['section_2_electronic_and_composition_gate']['x_vac'] is None
    assert result['section_5_scientific_verdict_and_limitations']['qualification'] == 'ABSTAIN'
    assert result == synthesize_scientific_opinion(record)


def test_rejects_nonfinite_and_invalid_input():
    with pytest.raises(TypeError): synthesize_scientific_opinion([])
    with pytest.raises(ValueError): synthesize_scientific_opinion({'value': float('nan')})


def test_completed_displacement_is_retained():
    result = synthesize_scientific_opinion({'p2_records': [{'temperature_K': 550,
        'termination': {'completed': True}, 'mobile_ion_metrics': {'mobile_mean_displacement_A': 0.8}}]})
    summary = result['section_4_thermochemical_and_dynamic_linkage']['p2_summary'][0]
    assert summary['status'] == 'COMPLETED'
    assert summary['mean_li_displacement_A'] == 0.8


def test_collision_warning_remains_a_diagnostic():
    result = synthesize_scientific_opinion({'relaxed': {'host_min_distance_A': 1.2,
        'host_steric_collision_warning': True, 'basin_diagnostic': {'x_vac_basin': .2}}})
    assert result['section_3_geometric_and_static_percolation']['host_steric_collision_warning'] is True
    assert result['section_5_scientific_verdict_and_limitations']['qualification'] == 'ABSTAIN'
    result = synthesize_scientific_opinion({'host_min_distance_A': 1.1,
        'host_steric_collision_warning': True, 'basin': {'x_vac_basin': .3}})
    assert result['section_3_geometric_and_static_percolation']['basin_diagnostic']['x_vac_basin'] == .3
