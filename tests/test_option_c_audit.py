import numpy as np
from pathlib import Path
import importlib.util

def test_bcc_active_weights_correct_external_audit():
    point=np.array([1.5,1.5,0]);hosts=np.array([[0,0,0],[2,2,2],[2,2,-2]])
    vectors=point-hosts;vectors/=np.linalg.norm(vectors,axis=1)[:,None]
    assert np.linalg.norm(np.array([.2,.4,.4])@vectors)>.06
    np.testing.assert_allclose(np.array([.25,.375,.375])@vectors,0,atol=1e-14)

def test_unweighted_polish_reduces_normal_force():
    from rhombus.transport.periodic_string import relax_periodic_string
    p=np.array([[0.,0,0],[.25,.4,0],[.5,.4,0],[.75,.4,0],[1.,0,0]])
    def field(x):return x[:,1]**2,np.column_stack((np.zeros(len(x)),-2*x[:,1],np.zeros(len(x))))
    result=relax_periodic_string(p,field,max_iterations=15,force_tolerance_eV_A=.05,step_scale=.1,max_step_A=.05)
    assert result['max_perpendicular_force_eV_A']<.8
    np.testing.assert_allclose(result['points_cartesian'][0],p[0])
    np.testing.assert_allclose(result['points_cartesian'][-1],p[-1])
