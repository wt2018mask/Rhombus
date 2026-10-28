"""Canonical SoftBV is a provisional screen; no benchmark label is fitted."""
import pytest
from rhombus.pipeline.funnel import RhombusDiscoveryFunnel
from rhombus.transport.static_assessment import barrier_scale_diagnostics


def context(channel, combined, *, negative_void=True, converged=True):
    delta=-.669471 if negative_void else .1
    return {'P0':{'gate_verdict':'PASS_ELECTRONIC_INSULATOR'},
            'P1':{'energy_above_hull_meV_atom':0.},
            'P0_5':{'host_channel_barrier_3d_ev':channel,
                    'effective_activation_barrier_ev':combined,
                    'mep':{'converged':converged,'endpoints_stationary':True,
                           'dense_path_barrier_ev':combined},
                    'frenkel':{'required':True,'site_energy_difference_eV':delta,
                               'raw_interstitial_minus_occupied_ev':delta,
                               'sub_occupied_void_detected':negative_void,
                               'stationary':True}}}


def test_negative_host_only_void_cannot_override_high_3d_channel():
    verdict=RhombusDiscoveryFunnel._static_verdict
    assert verdict(context(1.1790,1.5392))=='FALSIFIED_STATIC_P0_5_HIGH_BARRIER'
    assert verdict(context(1.1790,.7696))=='FALSIFIED_STATIC_P0_5_HIGH_BARRIER'


def test_unconverged_mep_never_gets_high_barrier_verdict():
    verdict=RhombusDiscoveryFunnel._static_verdict
    assert verdict(context(1.1790,1.5392,converged=False))=='STATIC_SCREENING_INCONCLUSIVE'
    assert verdict(context(.5895,.7696))=='STATIC_SCREENING_INCONCLUSIVE'


def test_output_only_normalization_preserves_raw_barriers():
    r=barrier_scale_diagnostics(1.1790,.3602,1.5392,factor=.5)
    assert r['raw_barriers_ev']==pytest.approx({'channel_3d':1.1790,'hop':.3602,'combined':1.5392})
    assert r['valence_normalized_barriers_ev']==pytest.approx({'channel_3d':.5895,'hop':.1801,'combined':.7696})
    assert r['barrier_normalization']['scope']=='OUTPUT_ONLY_NO_REOPTIMIZATION'
    assert r['barrier_normalization']['neb_convergence_retested'] is False
    for factor in (0.,-1.,float('nan')):
        with pytest.raises(ValueError):barrier_scale_diagnostics(1.,2.,3.,factor=factor)
