import math
import numpy as np
import pytest
from pymatgen.core import Lattice,Species,Structure
from rhombus.transport.bvse_parameters import build_charge_scaled_evaluator,coordination_summary


def _structure(n):
    lattice=Lattice.cubic(30);center=np.array([15.,15.,15.]);directions=np.vstack((np.eye(3),-np.eye(3)))
    coords=[lattice.get_fractional_coords(center+2.0*v) for v in directions[:n]]
    return Structure(lattice,[Species('Li',1),Species('Al',3)]+[Species('O',-2)]*n,
                     [lattice.get_fractional_coords(center),[.2,.2,.2]]+coords)


def test_fixed_radius_coordination_count_and_supercell_invariance():
    for n in (4,6):
        structure=_structure(n);r=coordination_summary(structure)
        assert r['raw_mean']==n and r['effective']==n and r['counts']==[n]
        structure.make_supercell([2,1,1]);r=coordination_summary(structure)
        assert r['raw_mean']==n and r['effective']==n


def test_n4_is_half_host_potential_and_n6_shifts_pair_minimum():
    s=_structure(4);original=build_charge_scaled_evaluator(s,periodic_cutoff_A=None)
    scaled=build_charge_scaled_evaluator(s,periodic_cutoff_A=None,coordination=4.)
    points=np.array([[15.1,14.8,15.2],[14.,14.1,15.4]])
    e0,f0=original(points);e,f=scaled(points)
    assert e==pytest.approx(e0*.5) and f==pytest.approx(f0*.5)
    six=build_charge_scaled_evaluator(s,periodic_cutoff_A=None,coordination=6.)
    kind,params=next(p for p in six.parameters if p[0]=='morse')
    assert params[0]==pytest.approx(1.96+.39*math.log(1.5))
    assert params[2]==pytest.approx(.985/3)
    for axis in range(3):
        step=np.eye(3)[axis]*1e-5
        assert six(points)[1][:,axis]==pytest.approx(-(six(points+step)[0]-six(points-step)[0])/(2e-5),rel=1e-5,abs=1e-5)


def test_coordination_model_validates_parameters_and_preserves_legacy():
    s=_structure(4)
    with pytest.raises(ValueError):build_charge_scaled_evaluator(s,coordination=3.)
    with pytest.raises(ValueError):build_charge_scaled_evaluator(s,valence_sum=True,coordination=4.)
    assert build_charge_scaled_evaluator(s).charge_metadata['anion_model']=='PAIRWISE_MORSE'
