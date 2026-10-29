"""Bounded, unqualified whole-witness path optimization for periodic fields.

This does not certify 3D connectivity: separately relaxed winding cycles can
become disconnected, and finitely sampled line segments can miss extrema.
"""
import numpy as np
from scipy.optimize import minimize
from scipy.special import logsumexp


def _samples(path, subdivisions):
    fractions = np.arange(subdivisions, dtype=float) / subdivisions
    return np.concatenate([a + fractions[:, None] * (b-a)
                           for a, b in zip(path[:-1], path[1:])] + [path[-1:]])


def relax_witness_path(path_cartesian, evaluate, *, subdivisions, smoothing_ev,
                       displacement_bound_A, max_iterations):
    """Optimize all interior vertices of a fixed-endpoint unwrapped witness.

    ``evaluate`` maps Cartesian (n, 3) points to energies (n,). Its periodicity
    is the caller's responsibility. Limits and smoothing must be explicit.
    Endpoints, and therefore the supplied winding displacement, stay fixed.
    The smooth-max objective has no claim to a global minimax optimum.
    """
    path = np.asarray(path_cartesian, dtype=float)
    if path.ndim != 2 or path.shape[1] != 3 or len(path) < 3 or not np.isfinite(path).all():
        raise ValueError('finite path of at least three 3D points required')
    if (not isinstance(subdivisions, int) or subdivisions < 1 or
        not np.isfinite(smoothing_ev) or smoothing_ev <= 0 or
        not np.isfinite(displacement_bound_A) or displacement_bound_A <= 0 or
        not isinstance(max_iterations, int) or max_iterations < 1):
        raise ValueError('explicit positive bounds, sampling, smoothing and iterations required')
    original = path.copy()

    def energies(candidate):
        values = np.asarray(evaluate(_samples(candidate, subdivisions)), dtype=float)
        if values.shape != ((len(candidate)-1)*subdivisions+1,) or not np.isfinite(values).all():
            raise ValueError('evaluator must return one finite energy per sample')
        return values

    def candidate(x):
        result = original.copy()
        result[1:-1] = x.reshape(-1, 3)
        return result

    def objective(x):
        return float(smoothing_ev * logsumexp(energies(candidate(x)) / smoothing_ev))

    baseline = float(energies(original).max())
    x0 = original[1:-1].ravel()
    bounds = [(x-displacement_bound_A, x+displacement_bound_A) for x in x0]
    result = minimize(objective, x0, method='L-BFGS-B', bounds=bounds,
                      options={'maxiter': max_iterations})
    proposed = candidate(result.x)
    proposed_max = float(energies(proposed).max())
    accepted = proposed_max <= baseline
    retained = proposed if accepted else original
    return {'path_cartesian': retained.tolist(), 'before_sampled_max': baseline,
            'after_sampled_max': proposed_max if accepted else baseline,
            'proposed_sampled_max': proposed_max, 'accepted': bool(accepted),
            'optimizer_converged': bool(result.success), 'optimizer_message': str(result.message),
            'winding_displacement_cartesian': (original[-1]-original[0]).tolist(),
            'subdivisions': subdivisions, 'smoothing_ev': smoothing_ev,
            'displacement_bound_A': displacement_bound_A,
            'scope': 'FINITE_SAMPLED_LOCAL_WITNESS_NOT_GLOBAL_OR_3D_CONNECTIVITY',
            'qualification': 'ABSTAIN'}
