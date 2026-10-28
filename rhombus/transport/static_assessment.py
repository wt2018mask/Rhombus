"""Reproducible static diagnostics on actual coordinates, with explicit limits."""
import hashlib
import json
import math
import numpy as np
from .bvse_parameters import build_site_evaluator, host_radii, parameter_identity
from .bvse_percolation import percolation_thresholds
from .neb_pathway import ClimbingImageMEPSolver


def assess_static_transport(structure, *, grid_dimension=24, screening_factor=1.,
                            effective_charge_scale=1., max_barrier_eV=1., run_mep=True,
                            vacancy_fractional_target=None, mep_steps=200):
    if not 4 <= grid_dimension <= 40 or not math.isfinite(max_barrier_eV) or max_barrier_eV <= 0:
        raise ValueError('bounded grid and explicit positive barrier policy required')
    evaluator = build_site_evaluator(structure, screening_factor=screening_factor,
                                     effective_charge_scale=effective_charge_scale)
    field = evaluator.grid(min_dimension=grid_dimension, max_dimension=grid_dimension)
    result = percolation_thresholds(field, lattice=structure.lattice,
                                    host_fractional=[s.frac_coords for s in evaluator.sites],
                                    host_radii_A=host_radii(structure))
    barrier = result['barriers_eV']['3D']
    rejected = barrier is not None and barrier > max_barrier_eV
    result.update(decision='REJECT' if rejected else 'CONTINUE',
                  gate_verdict='FALSIFIED_HIGH_STATIC_BARRIER' if rejected else 'PASS_P0_5',
                  gate_scope='PROVISIONAL_OWNER_MODEL_POLICY_NOT_MATERIAL_CALIBRATION',
                  threshold_eV=max_barrier_eV, parameter_identity=parameter_identity(),
                  screening_factor=screening_factor, effective_charge_scale=effective_charge_scale,
                  structure_sha256=hashlib.sha256(json.dumps(structure.as_dict(), sort_keys=True).encode()).hexdigest())
    result['mep'] = None
    if run_mep:
        mobile = [s for s in structure if s.specie.symbol == 'Li']
        if len(mobile) < 2 and vacancy_fractional_target is None:
            raise ValueError('two mobile sites or an explicit vacancy target required')
        if vacancy_fractional_target is not None:
            target = np.asarray(vacancy_fractional_target, float)
            if target.shape != (3,) or not np.isfinite(target).all():
                raise ValueError('finite fractional vacancy target required')
            start = min(mobile, key=lambda s: structure.lattice.get_distance_and_image(s.frac_coords, target)[0])
            _, image = structure.lattice.get_distance_and_image(start.frac_coords, target)
            end = structure.lattice.get_cartesian_coords(target+image)
        else:
            distance, i, j, image = min((
                (lambda d: (d[0], i, j, d[1]))(structure.lattice.get_distance_and_image(a.frac_coords, b.frac_coords))
                for i, a in enumerate(mobile) for j, b in enumerate(mobile) if j > i), key=lambda p: p[:3])
            start = mobile[i]
            end = structure.lattice.get_cartesian_coords(mobile[j].frac_coords+image)
        mep = ClimbingImageMEPSolver().solve(start.coords, end, evaluator, max_steps=mep_steps,
                                             step_size=.005, force_tolerance=.05)
        mep['scope'] = 'FIXED_HOST_TEST_ION_MORSE_MODEL_NO_MANY_ION_EXCLUSION_OR_MLIP'
        result['mep'] = mep
    return result
