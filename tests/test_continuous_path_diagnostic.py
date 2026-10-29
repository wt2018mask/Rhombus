import numpy as np
import pytest
from rhombus.transport.continuous_path_diagnostic import relax_witness_path


def test_relaxes_whole_path_keeps_winding_and_does_not_increase_sampled_max():
    path = np.array([[0., 0., 0.], [.25, 1., 0.], [.5, 1., 0.], [.75, 1., 0.], [1., 0., 0.]])
    energy = lambda points: points[:, 1]**2
    result = relax_witness_path(path, energy, subdivisions=4, smoothing_ev=.1,
                                displacement_bound_A=1.1, max_iterations=100)
    assert result['after_sampled_max'] < result['before_sampled_max']
    assert result['winding_displacement_cartesian'] == [1., 0., 0.]
    assert result['path_cartesian'][0] == path[0].tolist()
    assert result['path_cartesian'][-1] == path[-1].tolist()
    assert result['qualification'] == 'ABSTAIN'


def test_invalid_inputs_and_evaluator_rejected():
    path = [[0, 0, 0], [.5, 0, 0], [1, 0, 0]]
    with pytest.raises(ValueError):
        relax_witness_path(path, lambda p: np.ones(len(p)), subdivisions=0,
                           smoothing_ev=.1, displacement_bound_A=1, max_iterations=1)
    with pytest.raises(ValueError):
        relax_witness_path(path, lambda p: np.array([np.nan]), subdivisions=2,
                           smoothing_ev=.1, displacement_bound_A=1, max_iterations=1)
