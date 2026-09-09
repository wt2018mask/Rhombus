"""Tests for rudeus.filters: F3 diffusive-regime validator, P0 static filters, and F2 BVSE."""

import numpy as np
import pytest
from pymatgen.core import Lattice, Structure

from rudeus.filters import (
    DiffusiveValidationResult,
    compute_msd_curve,
    compute_non_gaussian_alpha2,
    compute_species_resolved_msd,
    evaluate_f2_bvse,
    evaluate_p0,
    fit_log_log_slope,
    validate_diffusive_regime,
)
from rudeus.schema import CandidateMaterial, ExistenceState, TransportState


def test_regression_li_only_vs_all_atom_msd():
    """REGRESSION TEST: All-atom MSD masks true diffusive behavior with framework vibration noise.

    Construct a synthetic trajectory with:
    - 8 static/vibrating framework atoms ('S' and 'P') that oscillate around fixed positions.
    - 2 mobile 'Li' ions that undergo an active Brownian random walk (true diffusion).

    Assert that:
    1. Li-only MSD grows linearly with lag time (diffusive scaling).
    2. All-atom MSD is heavily diluted and dominated by framework vibration plateau.
    3. The two curves differ materially at long lag times.
    4. validate_diffusive_regime correctly identifies Li diffusion as DIFFUSIVE.
    """
    np.random.seed(42)
    n_frames = 150
    n_framework = 8
    n_mobile = 2
    n_atoms = n_framework + n_mobile

    species = ["S"] * 6 + ["P"] * 2 + ["Li"] * 2

    # Framework base positions
    framework_base = np.random.uniform(0.0, 10.0, size=(n_framework, 3))
    # Mobile initial positions
    mobile_base = np.random.uniform(0.0, 10.0, size=(n_mobile, 3))

    trajectory = np.zeros((n_frames, n_atoms, 3))

    # Framework vibrates with zero net displacement (thermal noise)
    framework_noise = np.random.normal(0.0, 0.08, size=(n_frames, n_framework, 3))
    for t in range(n_frames):
        trajectory[t, :n_framework, :] = framework_base + framework_noise[t]

    # Mobile Li ions perform continuous Brownian walk (step ~ N(0, 0.25))
    li_positions = np.zeros((n_frames, n_mobile, 3))
    li_positions[0] = mobile_base
    for t in range(1, n_frames):
        step = np.random.normal(0.0, 0.25, size=(n_mobile, 3))
        li_positions[t] = li_positions[t - 1] + step

    trajectory[:, n_framework:, :] = li_positions

    # Compute all-atom MSD vs Li-only MSD
    lags, all_atom_msd, _ = compute_species_resolved_msd(
        trajectory, species, target_species=None
    )
    _, li_msd, li_alpha2 = compute_species_resolved_msd(
        trajectory, species, target_species="Li"
    )

    # 1. Li MSD at long lags must be substantially larger than all-atom MSD (material divergence)
    assert li_msd[-1] > 3.0 * all_atom_msd[-1], (
        f"Li MSD ({li_msd[-1]:.3f}) should strongly exceed diluted all-atom MSD ({all_atom_msd[-1]:.3f})"
    )

    # 2. Li log-log slope should indicate diffusion (~1.0), whereas all-atom slope is depressed
    li_slope = fit_log_log_slope(lags, li_msd)
    all_atom_slope = fit_log_log_slope(lags, all_atom_msd)

    assert li_slope >= 0.70, f"Li-only slope should be diffusive (>=0.70), got {li_slope:.3f}"
    assert li_slope > all_atom_slope, (
        f"Li-only slope ({li_slope:.3f}) must be steeper than all-atom slope ({all_atom_slope:.3f})"
    )

    # 3. F3 validator must declare Li sublattice as DIFFUSIVE
    val_result = validate_diffusive_regime(trajectory, species, target_species="Li")
    assert val_result.is_diffusive is True
    assert val_result.transport_state == TransportState.DIFFUSIVE
    assert val_result.n_mobile_ions == 2


def test_f3_alpha2_non_gaussian_caging_rejection():
    """Verify that anomalous non-Gaussian parameter (e.g. trapped/caged hopping) prevents false-positive DIFFUSIVE verdict."""
    np.random.seed(123)
    n_frames = 120
    n_atoms = 4
    species = ["Li"] * n_atoms

    # Simulate localized caging: atoms jump between two sites back and forth (highly non-Gaussian)
    trajectory = np.zeros((n_frames, n_atoms, 3))
    site_a = np.array([1.0, 1.0, 1.0])
    site_b = np.array([3.5, 1.0, 1.0])

    for t in range(n_frames):
        for i in range(n_atoms):
            site = site_a if (t // 5) % 2 == 0 else site_b
            trajectory[t, i] = site + np.random.normal(0.0, 0.05, size=3)

    _, alpha2 = compute_non_gaussian_alpha2(trajectory)
    # The non-Gaussian parameter should be elevated due to bimodal cage jump
    max_alpha2 = float(np.max(alpha2))
    assert max_alpha2 > 0.30

    # Validator with strict alpha_2 cutoff must NOT classify this trapped trajectory as DIFFUSIVE
    val_result = validate_diffusive_regime(
        trajectory, species, target_species="Li", max_alpha2_provisional=0.20
    )
    assert val_result.is_diffusive is False
    assert val_result.transport_state in (TransportState.NONDIFFUSIVE, TransportState.INDETERMINATE)


def test_p0_filters_smact_and_geometry():
    """Verify P0 static filters: neutrality, electronegativity, and geometry checks."""
    # 1. Known stable electrolyte composition should pass P0
    p0_pass = evaluate_p0("Li2O")
    assert p0_pass.passed is True
    assert p0_pass.neutrality_ok is True
    assert p0_pass.existence_state == ExistenceState.PLAUSIBLE

    # 2. Charge-unbalanced composition should fail P0
    p0_fail = evaluate_p0("Li3O")
    assert p0_fail.passed is False
    assert p0_fail.neutrality_ok is False
    assert p0_fail.existence_state == ExistenceState.FAIL

    # 3. Create a valid crystal structure for geometry test
    lattice = Lattice.cubic(4.0)
    struct = Structure(lattice, ["Li", "Cl"], [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]])
    res_struct = evaluate_p0("LiCl", structure=struct)
    assert res_struct.passed is True
    assert res_struct.geometry_ok is True

    # 4. Create an overlapping clashing structure
    clash_struct = Structure(lattice, ["Li", "Cl"], [[0.0, 0.0, 0.0], [0.01, 0.01, 0.01]])
    res_clash = evaluate_p0("LiCl", structure=clash_struct)
    assert res_clash.passed is False
    assert res_clash.geometry_ok is False
    assert res_clash.existence_state == ExistenceState.FAIL


def test_f2_bvse_probationary_wiring():
    """Verify F2 BVSE percolation scoring returns PROBATION status and never sets SUPPORTED."""
    lattice = Lattice.cubic(5.0)
    # Simple Li-S test structure
    struct = Structure(
        lattice,
        ["Li", "Li", "S"],
        [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5], [0.25, 0.25, 0.25]],
    )

    result = evaluate_f2_bvse(struct, mobile_ion="Li")

    # Critical assertions
    assert result.status == "PROBATION", "F2 BVSE must be strictly locked to PROBATION"
    assert result.evidence_event.level == "F2_PROBATION"
    assert 0.0 < result.score <= 1.0
    assert result.percolation_barrier_ev > 0.0

    # Ensure adding F2 evidence to a candidate does not set existence_state to SUPPORTED
    candidate = CandidateMaterial(material_id="test_mat_01", formula="Li2S")
    candidate.add_evidence(result.evidence_event)
    # existence_state remains UNKNOWN (or PLAUSIBLE if P0 was run); never SUPPORTED by F2 alone
    assert candidate.existence_state != ExistenceState.SUPPORTED
