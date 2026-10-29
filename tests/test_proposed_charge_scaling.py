import pytest
from pymatgen.core import Lattice, Species, Structure
from rhombus.transport.bvse_parameters import proposed_occupancy_weighted_charges


def test_charge_scaling_uses_occupancies_and_is_supercell_invariant():
    structure = Structure(Lattice.cubic(5), [Species('Li', 1), Species('O', -2)], [[0, 0, 0], [.5, .5, .5]])
    charges = proposed_occupancy_weighted_charges(structure)
    assert charges['Li+'] == pytest.approx(4**.25 / 2**.5)
    assert charges['O2-'] == pytest.approx(-2 / 2**.5 / 4**.25)
    structure.make_supercell([2, 2, 2])
    assert proposed_occupancy_weighted_charges(structure) == pytest.approx(charges)


def test_missing_oxidation_states_are_rejected():
    structure = Structure(Lattice.cubic(5), ['Li', 'O'], [[0, 0, 0], [.5, .5, .5]])
    with pytest.raises(ValueError, match='oxidation'):
        proposed_occupancy_weighted_charges(structure)


def test_scaled_host_uses_charge_product_and_freezes_reference():
    import numpy as np
    from scipy.special import erfc
    from rhombus.transport.bvse_parameters import build_charge_scaled_evaluator
    structure = Structure(Lattice.cubic(30), [Species('Li', 1), Species('Al', 3), Species('O', -2)],
                          [[.1,.1,.1], [.5,.5,.5], [.8,.8,.8]])
    host = build_charge_scaled_evaluator(structure, periodic_cutoff_A=None)
    charges = host.charge_metadata['effective_charges']
    params = next(p for kind, p in host.parameters if kind == 'repulsion')
    assert params[0] == pytest.approx(charges['Li+']*charges['Al3+'])
    assert params[1] == pytest.approx(.74*(.76+.535))
    energy, derivative = host._pair('repulsion',params,np.array([2.]),'Al')
    assert energy[0] == pytest.approx(14.3996454784255*params[0]*erfc(2/params[1])/2)
    delta=1e-5
    plus=host._pair('repulsion',params,np.array([2+delta]),'Al')[0]
    minus=host._pair('repulsion',params,np.array([2-delta]),'Al')[0]
    assert derivative[0] == pytest.approx((plus-minus)[0]/(2*delta),rel=1e-6)
    probe=structure.copy();probe.remove_sites([0])
    assert build_charge_scaled_evaluator(probe,charge_reference=structure,periodic_cutoff_A=None).charge_metadata == host.charge_metadata


def test_scaled_model_rejects_mixed_valence_symbol_kernel():
    from rhombus.transport.bvse_parameters import build_charge_scaled_evaluator
    structure = Structure(Lattice.cubic(9), [Species('Li',1), Species('Fe',2), Species('Fe',3), Species('O',-2)],
                          [[0,0,0],[.2,.2,.2],[.5,.5,.5],[.8,.8,.8]])
    with pytest.raises(ValueError):
        build_charge_scaled_evaluator(structure)


def test_spectator_charge_scales_coulomb_for_periodic_and_nonperiodic():
    import numpy as np
    from rhombus.transport.bvse_percolation import SpectatorSiteEnergyEvaluator
    structure = Structure(Lattice.cubic(30), ['Li','Li'], [[0,0,0],[.1,0,0]])
    def zero(points):
        return np.zeros(len(points)),np.zeros((len(points),3))
    for cutoff in (None, 8.):
        a=SpectatorSiteEnergyEvaluator(structure,0,zero,periodic_cutoff_A=cutoff,charge_product=1.)
        b=SpectatorSiteEnergyEvaluator(structure,0,zero,periodic_cutoff_A=cutoff,charge_product=.5)
        ea,fa=a([[0,0,0]]);eb,fb=b([[0,0,0]])
        assert ea[0]>eb[0] and np.linalg.norm(fa)>np.linalg.norm(fb)
