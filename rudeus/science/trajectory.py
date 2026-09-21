"""P3-only trajectory checks. No changes to historical P2 serialization or MD."""
import numpy as np

from rudeus.mlip.p2 import unwrap_trajectory


def recorded_times(frame_steps, timestep_fs, *, n_frames):
    steps = np.asarray(frame_steps)
    if (steps.shape != (n_frames,) or steps.dtype.kind not in "iu"
            or any(isinstance(value, (bool, np.bool_)) for value in frame_steps)
            or np.any(steps < 0) or any(int(b) <= int(a) for a, b in zip(steps, steps[1:]))):
        raise ValueError("frame steps must be strictly increasing nonnegative integers")
    if (not isinstance(timestep_fs, (int, float, np.integer, np.floating))
            or isinstance(timestep_fs, (bool, np.bool_)) or not np.isfinite(timestep_fs) or timestep_fs <= 0):
        raise ValueError("MD integration timestep must be positive and finite")
    differences = [int(b) - int(a) for a, b in zip(steps, steps[1:])]
    if differences and any(value != differences[0] for value in differences):
        raise ValueError("irregular cadence or missing frames: unsupported lag-pair policy")
    return steps, differences[0] if differences else None


def validate_schedule(artifact, p2):
    """Validate the complete production sampling schedule, including both ends."""
    steps, spacing = recorded_times(artifact["frame_steps"], artifact["timestep_fs"],
                                    n_frames=artifact["n_production_frames"])
    for key in ("sample_interval_steps", "equil_steps", "production_steps_completed"):
        value = artifact[key]
        if type(value) is not int or value < (1 if key == "sample_interval_steps" else 0):
            raise ValueError(f"invalid declared schedule: {key}")
    interval = artifact["sample_interval_steps"]
    equil, completed = artifact["equil_steps"], artifact["production_steps_completed"]
    first = interval - equil % interval
    count = max(0, (completed - first) // interval + 1)
    if (len(steps) != count or (len(steps) and (int(steps[0]) != first or
            int(steps[-1]) != first + (count - 1) * interval)) or
            (spacing is not None and spacing != interval)):
        raise ValueError("recorded frames differ from declared production/sampling schedule")
    for source in (p2, p2.get("p2_protocol", {})):
        for key in ("timestep_fs", "sample_interval_steps", "equil_steps", "production_steps_completed"):
            if key in source and source[key] != artifact[key]:
                raise ValueError(f"P2 and trajectory schedule disagree: {key}")
    return {"integration_timestep_fs": artifact["timestep_fs"],
            "saved_frame_spacing_steps": interval,
            "saved_frame_spacing_ps": interval * artifact["timestep_fs"] / 1000,
            "production_steps_completed": completed,
            "saved_span_ps": (int(steps[-1]) - int(steps[0])) * artifact["timestep_fs"] / 1000
                              if len(steps) else 0.0}


def reconstruct_fixed_cell(artifact, declaration):
    """Apply the existing fractional-rounding algorithm only in explicit scope.

    Coordinate checks do NOT prove an image history. Sparse whole-cell crossings
    are unidentifiable from these samples and always remain a qualification blocker.
    """
    if declaration is None:
        raise ValueError("reconstruction declaration unavailable")
    if set(declaration) != {"coordinate_convention", "periodic_directions", "cell_origin_A"}:
        raise ValueError("explicit coordinate convention, periodic directions and cell origin required")
    if declaration["coordinate_convention"] != "wrapped_cartesian_primary_cell":
        raise ValueError("unsupported coordinate convention; no automatic wrapping or relabeling")
    periodic = tuple(declaration["periodic_directions"])
    if len(periodic) != 3 or any(type(value) is not bool or not value for value in periodic):
        raise ValueError("only explicitly three-dimensional periodic trajectories are supported")
    cell = np.asarray(artifact["cell"], dtype=float)
    if artifact["cell_mode"] != "fixed" or cell.shape != (3, 3):
        raise ValueError("variable-cell/NPT trajectories are unsupported")
    if not np.isfinite(cell).all():
        raise ValueError("fixed cell must be finite")
    sign, logdet = np.linalg.slogdet(cell)
    if sign == 0 or not np.isfinite(logdet):
        raise ValueError("fixed cell must be nonsingular")
    gram = cell @ cell.T
    # Floating-point roundoff bound for three-term dot products, NOT a physical
    # tolerance or a calibrated allowance for skew. Arbitrary skew is unsupported.
    eps = np.finfo(float).eps
    roundoff = (3 * eps / (1 - 3 * eps)) * np.outer(np.linalg.norm(cell, axis=1),
                                                  np.linalg.norm(cell, axis=1))
    if not np.isfinite(gram).all() or np.any(np.abs(gram - np.diag(np.diag(gram))) > roundoff):
        raise ValueError("skew cell unsupported by this fractional-rounding reconstruction scope")
    origin = np.asarray(declaration["cell_origin_A"], dtype=float)
    pos = np.asarray(artifact["positions"], dtype=float)
    species = artifact["species"]
    if (origin.shape != (3,) or not np.isfinite(origin).all() or
            pos.shape != (artifact["n_production_frames"], len(species), 3) or not np.isfinite(pos).all()):
        raise ValueError("invalid coordinate shape, cell origin or nonfinite positions")
    if not len(pos):
        raise ValueError("no coordinates to reconstruct")
    relative = pos - origin
    inverse = np.linalg.inv(cell)
    frac = relative @ inverse
    # Domain validation allows only arithmetic roundoff at the cell faces.
    error = (3 * eps / (1 - 3 * eps)) * (np.abs(relative) @ np.abs(inverse))
    if np.any(frac < -error) or np.any(frac > 1 + error):
        raise ValueError("coordinates contradict declared wrapped primary cell")
    delta = np.diff(frac, axis=0)
    mic = delta - np.round(delta)
    tie_error = error[1:] + error[:-1] + eps * np.abs(delta)
    if np.any(np.abs(np.abs(mic) - 0.5) <= tie_error):
        raise ValueError("ambiguous half-cell crossing; image cannot be selected")
    reconstructed = unwrap_trajectory(relative, cell) + origin
    return reconstructed, {
        "data_contract_version": "p3-fixed-cell-data-v1-unqualified",
        "algorithm": "p2_fractional_rounding_accumulation",
        "coordinate_convention": declaration["coordinate_convention"],
        "periodic_directions": list(periodic), "cell_origin_A": origin.tolist(),
        "cell_scope": "fixed_orthogonal", "coordinate_domain_check": "VALID",
        "image_history": "UNAVAILABLE", "sampling_aliasing": "UNKNOWN",
        "applicability": "UNKNOWN / NEEDS EVIDENCE",
        "unresolved_requirements": ["unobserved_whole_cell_crossings_not_excluded",
                                    "drift_applicability_unqualified"],
        "drift_subtraction": False, "recentering": False, "time_dependent_rotation": False,
    }
