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


def test_f2_bvse_disordered_partial_occupancy():
    """REGRESSION: disordered (partial-occupancy) sites must score, not crash.

    Newer pymatgen removed ``PeriodicSite.specie`` (AttributeError on disordered
    sites); the majority of OBELiX CIFs are disordered, so a crash here silently
    zeroes most BVSE scores downstream via try/except fallbacks.
    """
    lattice = Lattice.cubic(5.0)
    struct = Structure(
        lattice,
        [{"Li": 0.5, "Na": 0.5}, "S"],
        [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]],
    )
    assert not struct.is_ordered

    result = evaluate_f2_bvse(struct, mobile_ion="Li")

    assert result.status == "PROBATION"
    assert 0.0 < result.score <= 1.0
    assert result.percolation_barrier_ev > 0.0


def _disordered_li_structure():
    """Shared disordered fixture: partial-occupancy Li/Na site, no clashes.

    Composition Li0.5Na0.5Cl (neutral: +0.5 +0.5 -1 = 0).
    """
    lattice = Lattice.cubic(5.0)
    return Structure(
        lattice,
        [{"Li": 0.5, "Na": 0.5}, "Cl"],
        [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]],
    )


def test_p0_geometry_disordered_partial_occupancy():
    """REGRESSION (STEP 1): P0 geometry must handle disordered sites, not fail-closed.

    Same removed ``PeriodicSite.specie`` API as the bvse.py bug. A sane
    disordered structure must not be misreported as a geometry FAIL.
    """
    from rudeus.filters.p0 import check_geometry_clash

    struct = _disordered_li_structure()
    assert not struct.is_ordered

    passed, details = check_geometry_clash(struct)
    assert "error" not in details, f"geometry check errored instead of scoring: {details}"
    assert passed is True


def test_p0_evaluate_disordered_partial_occupancy():
    """REGRESSION (STEP 1): evaluate_p0 on a sane disordered structure."""
    from rudeus.filters.p0 import evaluate_p0

    res = evaluate_p0("LiNaCl2", structure=_disordered_li_structure())
    assert res.geometry_ok is True
    assert res.passed is True
    assert res.existence_state == ExistenceState.PLAUSIBLE


# ---------------------------------------------------------------------------
# B1 regression tests: insufficient transport data must not become NONDIFFUSIVE
# ---------------------------------------------------------------------------

def test_fit_log_log_slope_insufficient_data_returns_none():
    """Test that fit_log_log_slope returns None (not 0.0 sentinel) for insufficient data."""
    # 1. Empty input
    assert fit_log_log_slope(np.array([]), np.array([])) is None
    assert fit_log_log_slope(np.array([1, 2]), np.array([])) is None

    # 2. Single valid point (Muse reproducer)
    assert fit_log_log_slope(np.array([1]), np.array([0.5])) is None

    # 3. Two valid points (< 3 required)
    assert fit_log_log_slope(np.array([1, 2]), np.array([0.5, 0.6])) is None

    # 4. All-filtered / no usable observations (MSD <= 1e-12 or NaN/inf)
    assert fit_log_log_slope(np.array([1, 2, 3, 4]), np.array([0.0, 0.0, 0.0, 0.0])) is None
    assert fit_log_log_slope(np.array([1, 2, 3, 4]), np.array([1e-13, -1.0, 0.0, np.nan])) is None

    # 5. Insufficient points in selected fit window (< 2 points)
    # 5 valid points, but window (0.9, 0.95) slices to < 2 points
    lags = np.arange(1, 6)
    msd = lags * 0.1
    assert fit_log_log_slope(lags, msd, fit_window_fraction=(0.9, 0.95)) is None

    # 6. Sufficient valid data produces a real float slope
    lags_ok = np.arange(1, 20)
    msd_ok = (lags_ok ** 1.0) * 0.2
    slope = fit_log_log_slope(lags_ok, msd_ok)
    assert slope is not None
    assert isinstance(slope, float)
    assert pytest.approx(slope, rel=1e-2) == 1.0


def test_validate_diffusive_regime_insufficient_data_yields_indeterminate():
    """Verify that any insufficient data case yields INDETERMINATE, never NONDIFFUSIVE."""
    species_li = ["Li", "Li"]

    # 1. Empty / 0-frame trajectory
    res_empty = validate_diffusive_regime(np.zeros((0, 2, 3)), species_li)
    assert res_empty.transport_state == TransportState.INDETERMINATE
    assert res_empty.is_diffusive is False
    assert res_empty.log_slope is None

    # 2. Trajectory too short to support a valid displacement (1 frame)
    res_1frame = validate_diffusive_regime(np.zeros((1, 2, 3)), species_li)
    assert res_1frame.transport_state == TransportState.INDETERMINATE
    assert res_1frame.is_diffusive is False
    assert res_1frame.log_slope is None

    # 3. 2-frame trajectory (only 1 lag point; Muse reproducer)
    traj_2frame = np.zeros((2, 2, 3))
    traj_2frame[1] = traj_2frame[0] + 0.5
    res_2frame = validate_diffusive_regime(traj_2frame, species_li)
    assert res_2frame.transport_state == TransportState.INDETERMINATE
    assert res_2frame.is_diffusive is False
    assert res_2frame.log_slope is None

    # 4. 3-frame trajectory (at most 1 lag point with n_frames // 2 = 1)
    traj_3frame = np.zeros((3, 2, 3))
    traj_3frame[1] = traj_3frame[0] + 0.5
    traj_3frame[2] = traj_3frame[1] + 0.5
    res_3frame = validate_diffusive_regime(traj_3frame, species_li)
    assert res_3frame.transport_state == TransportState.INDETERMINATE
    assert res_3frame.is_diffusive is False
    assert res_3frame.log_slope is None

    # 5. Zero target/mobile ions (e.g. oxygen only, evaluating Li)
    traj_no_target = np.zeros((50, 2, 3))
    traj_no_target[1:] = np.cumsum(np.random.normal(0, 0.1, size=(49, 2, 3)), axis=0)
    res_no_target = validate_diffusive_regime(traj_no_target, ["O", "O"], target_species="Li")
    assert res_no_target.transport_state == TransportState.INDETERMINATE
    assert res_no_target.is_diffusive is False
    assert res_no_target.n_mobile_ions == 0
    assert res_no_target.log_slope is None
    assert res_no_target.diagnostics.get("error") == "no_target_ions_found"

    # 6. All-filtered / no usable MSD observations (static trajectory, MSD == 0)
    traj_static = np.ones((50, 2, 3)) * 2.5
    res_static = validate_diffusive_regime(traj_static, species_li)
    assert res_static.transport_state == TransportState.INDETERMINATE
    assert res_static.is_diffusive is False
    assert res_static.log_slope is None

    # 7. Insufficient fit-window points (< 2 points in window)
    # 6-frame trajectory -> 3 lags, but window (0.9, 0.95) leaves < 2 points
    traj_short = np.zeros((6, 2, 3))
    for t in range(1, 6):
        traj_short[t] = traj_short[t - 1] + 0.2
    res_short_win = validate_diffusive_regime(traj_short, species_li, fit_window_fraction=(0.9, 0.95))
    assert res_short_win.transport_state == TransportState.INDETERMINATE
    assert res_short_win.is_diffusive is False
    assert res_short_win.log_slope is None


def test_validate_diffusive_regime_genuinely_nondiffusive_remains_nondiffusive():
    """Verify that a genuinely non-diffusive trajectory (caged vibration plateau) remains NONDIFFUSIVE."""
    np.random.seed(42)
    n_frames = 200
    n_atoms = 4
    species = ["Li"] * n_atoms
    # Caged harmonic motion: atoms oscillate around fixed sites with thermal noise sigma=0.05
    base_sites = np.array([[1.0, 1.0, 1.0], [3.0, 1.0, 1.0], [1.0, 3.0, 1.0], [3.0, 3.0, 1.0]])
    traj = np.zeros((n_frames, n_atoms, 3))
    for t in range(n_frames):
        traj[t] = base_sites + np.random.normal(0, 0.05, size=(n_atoms, 3))

    res = validate_diffusive_regime(traj, species, target_species="Li")
    assert res.transport_state == TransportState.NONDIFFUSIVE
    assert res.is_diffusive is False
    assert res.n_mobile_ions == 4
    assert res.log_slope is not None
    assert res.log_slope < 0.4, f"Caged plateau slope should be < 0.4, got {res.log_slope}"


def test_validate_diffusive_regime_genuinely_diffusive_remains_diffusive():
    """Verify that a genuinely diffusive Brownian walk remains DIFFUSIVE."""
    np.random.seed(42)
    n_frames = 250
    n_atoms = 4
    species = ["Li"] * n_atoms
    traj = np.zeros((n_frames, n_atoms, 3))
    traj[1:] = np.cumsum(np.random.normal(0, 0.3, size=(n_frames - 1, n_atoms, 3)), axis=0)

    res = validate_diffusive_regime(traj, species, target_species="Li")
    assert res.transport_state == TransportState.DIFFUSIVE
    assert res.is_diffusive is True
    assert res.n_mobile_ions == 4
    assert res.log_slope is not None
    assert 0.75 <= res.log_slope <= 1.30
    assert res.alpha2 is not None and res.alpha2 <= 0.35
