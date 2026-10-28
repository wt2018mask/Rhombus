"""The owner-proposed valence-sum Hamiltonian is an uncalibrated hypothesis."""
import math
import numpy as np
import pytest
from pymatgen.core import Lattice,Species,Structure
from rhombus.transport.bvse_parameters import build_charge_scaled_evaluator


def test_coordination_invariance_at_equal_bond_valence_sum():
    lattice=Lattice.cubic(30);center=np.array([15.,15.,15.]);r0=1.96;b=.390
    directions=np.vstack((np.eye(3),-np.eye(3)))
    for n in (4,6):
        radius=r0+b*math.log(n/4)
        coordinates=[lattice.get_fractional_coords(center+radius*v) for v in directions[:n]]
        structure=Structure(lattice,[Species('Li',1)]+[Species('O',-2)]*n,[[0,0,0]]+coordinates)
        e=build_charge_scaled_evaluator(structure,valence_sum=True)
        assert e([center])[0][0]==pytest.approx(-.985,abs=1e-9)


def test_valence_sum_forces_match_finite_differences_for_mixed_anions_and_cutoff():
    s=Structure(Lattice.cubic(25),[Species('Li',1),Species('Al',3),Species('O',-2),Species('Cl',-1)],
                [[.1,.1,.1],[.51,.5,.5],[.58,.52,.5],[.72,.52,.5]])
    e=build_charge_scaled_evaluator(s,valence_sum=True)
    points=np.array([[12.5,12.5,12.5],[12.1,12.7,12.3]])
    energy,forces=e(points)
    for axis in range(3):
        shift=np.eye(3)[axis]*1e-5
        numeric=-(e(points+shift)[0]-e(points-shift)[0])/(2e-5)
        assert forces[:,axis]==pytest.approx(numeric,rel=1e-5,abs=1e-6)
    assert e(points+np.array([25,0,0]))[0]==pytest.approx(energy,abs=1e-9)
    assert e(points+np.array([25,0,0]))[1]==pytest.approx(forces,abs=1e-9)


def test_valence_sum_preserves_old_model_and_requires_periodic_cutoff():
    s=Structure(Lattice.cubic(20),[Species('Li',1),Species('O',-2)],[[0,0,0],[.5,.5,.5]])
    assert build_charge_scaled_evaluator(s).charge_metadata['anion_model']=='PAIRWISE_MORSE'
    with pytest.raises(ValueError,match='periodic cutoff'):
        build_charge_scaled_evaluator(s,valence_sum=True,periodic_cutoff_A=None)
