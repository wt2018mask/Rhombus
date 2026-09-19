"""Unit tests for fixed-position local force replay metrics."""
import numpy as np


def test_local_replay_force_delta_is_deterministic():
    f32 = np.array([[1.0, 0.0, 0.0], [0.0, 2.0, 0.0]])
    f64 = np.array([[1.1, 0.0, 0.0], [0.0, 2.5, 0.0]])
    delta = f64 - f32
    mags = np.sqrt((delta ** 2).sum(axis=1))
    assert int(mags.argmax()) == 1
    assert float(mags.max()) == 0.5
