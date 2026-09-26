"""P2.5 transport-evidence worker: verified artifact -> unwrap -> F3 -> verdict.

P2.5 is the FIRST stage allowed to produce transport evidence
(`transport_state`), and the ONLY thing it produces: never existence,
never dynamic stability, never experimental conductivity, never D_self
or sigma_NE production claims (both explicitly deferred).

Pipeline position: consumes bound P2 results
(`data/batches/p2/<batch_id>.json` + `data/batches/p2_traj/<batch_id>.npz`),
writes atomic `data/batches/p25/<batch_id>.json`. Stateless,
restartable, Git-as-DB; mirrors the proven P2 batch/resume/persist
philosophy. No locks, no queue, no daemon, no database.

Scientific core (UNMODIFIED, owned by `rudeus.filters.f3_diffusive`):
  provisional gate 0.75 <= log_slope <= 1.30 AND tail_alpha2 <= 0.35,
  max_lag = n_frames // 2, fit window (0.3, 0.9), multi-origin MSD,
  standard 3D alpha2, slope < 0.4 -> NONDIFFUSIVE, else INDETERMINATE,
  zero target ions / insufficient data -> INDETERMINATE. P2.5 never retunes these.

Calibration-driven additions (methodology only, no new science):
  - Canonical unwrapping with the existing `p2.unwrap_trajectory`
    (wrapped input to F3 is a measured false negative; P2.5 makes it
    structurally impossible by unwrapping inside the loader path).
  - Block bootstrap over time origins for slope/alpha2 uncertainty.
    Naive iid-origin bootstrap is PROHIBITED (measured ~35x too narrow);
    this module implements only the block variant.
  - Conservative sufficiency: N=1 can never yield DIFFUSIVE; degenerate
    lag support, missing frames, or indefensible uncertainty yield
    INDETERMINATE, never a forced verdict.
  - Uncertainty veto: a DIFFUSIVE point claim whose 68% block CI leaves
    the provisional gate is held INDETERMINATE (edge-margin protection).
    Every claim is additionally marked transport_claim_status=provisional.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

from rudeus.filters.f3_diffusive import (
    compute_species_resolved_msd,
    fit_log_log_slope,
    validate_diffusive_regime,
)
from rudeus.mlip.p2 import unwrap_trajectory
from rudeus.mlip.p2_traj import (
    P2_TRAJ_FORMAT_VERSION,
    verify_traj_artifact,
)
from rudeus.mlip.sharding import assign_shard, write_json_atomic
from rudeus.schema import EvidenceEvent, TransportState

#: P2.5 code/config version recorded in every result (reproducibility).
P25_VERSION = "p25-f3-v1-provisional"

#: Evidence method label (F3 analysis + block uncertainty, no new science).
P25_TRANSPORT_METHOD = "f3_mobile_ion_msd_alpha2_block_bootstrap"

#: Provisional F3 gate mirrors. These MUST equal the defaults of
#: `validate_diffusive_regime`; they are used ONLY for the uncertainty
#: veto (CI-overlap check), never to re-derive the point verdict (which
#: comes straight from F3). A test locks this equality; do NOT retune.
P25_SLOPE_MIN_PROVISIONAL = 0.75
P25_SLOPE_MAX_PROVISIONAL = 1.30
P25_ALPHA2_MAX_PROVISIONAL = 0.35

#: Default methodological parameters (provisional; part of config hash).
#: block_origins ~ tens-of-origins scale per the calibration audit.
P25_DEFAULTS: Dict[str, Any] = {
    "p25_version": P25_VERSION,
    "target_species": "Li",
    "fit_window_fraction": [0.3, 0.9],
    "block_origins": 20,
    "n_bootstrap": 200,
    "ci_level": 0.68,
    "min_mobile_ions": 2,  # evidence sufficiency rule: N=1 never DIFFUSIVE
    "min_blocks": 4,  # bootstrap degeneracy floor (methodological, not frames)
    "uncertainty_veto": True,
}

#: Bootstrap seed salt: keeps P2.5 resampling streams distinct from P2 MD.
P25_BOOTSTRAP_SALT = 2505


class P25Error(RuntimeError):
    """Raised when a P2.5 analysis cannot be performed (fail closed).

    The batch runner converts this into a structured ERROR result (same
    convention as P2): attempted and failed, retryable, never a verdict.
    """


def p25_config_hash(config: Dict[str, Any]) -> str:
    """Deterministic hash of the method-defining P2.5 configuration."""
    payload = json.dumps(config, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def resolve_artifact_path(binding_path: Union[str, Path]) -> Path:
    """Resolve a recorded artifact path to a filesystem path.

    Bindings are recorded CWD-relative at P2 time (workers run with the
    repo root as CWD); absolute paths pass through unchanged.
    """
    p = Path(binding_path)
    if p.is_absolute():
        return p
    return Path(os.getcwd()) / p


# ---------------------------------------------------------------------------
# Artifact loading (verified, production-only, fail closed).
# ---------------------------------------------------------------------------

def load_verified_artifact(p2_payload: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Load the trajectory artifact bound to a P2 result payload.

    Returns (artifact_payload, binding_info). Verifies: binding presence,
    format/version (inside `verify_traj_artifact`), SHA256 match, shape
    consistency (species count, cell, finite values, strictly increasing
    production frame steps). Raises P25Error on any defect; never analyzes
    an unverified artifact.
    """
    batch_id = p2_payload.get("batch_id", "?")
    result = p2_payload.get("result")
    if not isinstance(result, dict):
        raise P25Error(f"p25 {batch_id}: P2 payload has no result mapping")
    binding = result.get("trajectory_artifact")
    if not isinstance(binding, dict):
        raise P25Error(
            f"p25 {batch_id}: P2 result carries no trajectory_artifact "
            "binding (legacy result without persisted trajectory)")
    for key in ("path", "sha256", "format_version"):
        if not isinstance(binding.get(key), str) or not binding[key]:
            raise P25Error(
                f"p25 {batch_id}: malformed trajectory_artifact binding")
    if binding["format_version"] != P2_TRAJ_FORMAT_VERSION:
        raise P25Error(
            f"p25 {batch_id}: unsupported artifact format "
            f"{binding['format_version']!r}")
    path = resolve_artifact_path(binding["path"])
    try:
        payload = verify_traj_artifact(path, binding["sha256"])
    except Exception as e:
        raise P25Error(
            f"p25 {batch_id}: artifact verification failed "
            f"({type(e).__name__}: {e})")
    # Defense-in-depth structural checks (hash already covers content).
    n_atoms = int(payload.get("n_atoms", -1))
    species = list(payload.get("species", []))
    cell = np.asarray(payload.get("cell", np.zeros((0, 0))))
    positions = np.asarray(payload.get("positions", np.zeros((0, 0, 0))))
    steps = np.asarray(payload.get("frame_steps", np.zeros(0)))
    if len(species) != n_atoms or positions.shape[1:] != (n_atoms, 3):
        raise P25Error(f"p25 {batch_id}: species/atom-count mismatch")
    if cell.shape != (3, 3) or not np.all(np.isfinite(cell)):
        raise P25Error(f"p25 {batch_id}: invalid cell matrix")
    if positions.shape[0] != len(steps) or (
            len(steps) and bool((np.diff(steps) <= 0).any())):
        raise P25Error(f"p25 {batch_id}: production frame ordering defect")
    if positions.size and not np.all(np.isfinite(positions)):
        raise P25Error(f"p25 {batch_id}: non-finite positions in artifact")
    return payload, {"path": str(binding["path"]), "sha256": binding["sha256"],
                     "format_version": binding["format_version"]}


# ---------------------------------------------------------------------------
# Block bootstrap over time origins (iid-origin resampling prohibited).
# ---------------------------------------------------------------------------

def block_bootstrap_uncertainty(
    mobile_unwrapped: np.ndarray,
    fit_window_fraction: Tuple[float, float],
    block_origins: int,
    n_bootstrap: int,
    ci_level: float,
    seed: int,
    min_blocks: int = 4,
) -> Dict[str, Any]:
    """Block-bootstrap CIs for log_slope and tail_alpha2.

    Origin pool: the first (n_frames - max_lag) time origins, IDENTICAL
    across lags, partitioned into contiguous blocks of `block_origins`.
    Each replicate resamples blocks with replacement and recomputes the
    MSD/alpha2 curves with the exact F3 moment definitions, then the F3
    slope fit and tail average. Percentile CIs at `ci_level`.

    Fewer than `min_blocks` complete blocks cannot support a defensible
    estimate (measured collapse: 2 blocks gave 0.006 vs 0.193 replicate
    std on hopping L=100) -> status insufficient with reason, no CIs,
    never zero-filled. Deterministic in `seed`.
    """
    n_frames, n_ions, _ = mobile_unwrapped.shape
    max_lag = min(max(1, n_frames // 2), n_frames - 1) if n_frames >= 2 else 0
    base: Dict[str, Any] = {
        "method": "block_bootstrap_origins",
        "block_length_origins": int(block_origins),
        "n_bootstrap": int(n_bootstrap),
        "ci_level": float(ci_level),
        "status": "insufficient",
        "reason": "not_evaluated",
    }
    if n_frames < 2 or max_lag < 1 or block_origins < 1 or n_bootstrap < 1:
        base["reason"] = "degenerate_trajectory_or_parameters"
        return base
    n_orig = n_frames - max_lag
    n_blocks = n_orig // int(block_origins)
    base["n_origins"] = int(n_orig)
    base["n_blocks"] = int(n_blocks)
    if n_blocks < 1:
        base["reason"] = "no_complete_block"
        return base
    if n_blocks < int(min_blocks):
        base["reason"] = "fewer_blocks_than_minimum"
        return base
    rng = np.random.default_rng(int(seed) % (2 ** 32))
    lags = np.arange(1, max_lag + 1)
    slopes: List[float] = []
    a2tails: List[float] = []
    for _ in range(int(n_bootstrap)):
        picks = rng.integers(0, n_blocks, size=n_blocks)
        rows = np.concatenate(
            [np.arange(i * block_origins, (i + 1) * block_origins)
             for i in picks])
        msd = np.zeros(len(lags))
        a2 = np.zeros(len(lags))
        for idx, lag in enumerate(lags):
            d = mobile_unwrapped[lag:] - mobile_unwrapped[:-lag]
            # rows indexes time origins; every lag carries >= n_orig rows
            # since lag <= max_lag  =>  n_frames - lag >= n_orig.
            sq = np.sum(d ** 2, axis=-1)[rows]
            r2 = sq.reshape(-1)
            r4 = r2 ** 2
            m2 = float(r2.mean())
            m4 = float(r4.mean())
            msd[idx] = m2
            if m2 > 1e-12:
                a2[idx] = (3.0 * m4) / (5.0 * (m2 ** 2)) - 1.0
            else:
                a2[idx] = 0.0
        s = fit_log_log_slope(lags, msd, fit_window_fraction=fit_window_fraction)
        if s is None or not np.isfinite(s):
            base["status"] = "insufficient"
            base["reason"] = "insufficient_bootstrap_slope_data"
            return base
        mid = len(a2) // 2
        tail = float(np.mean(a2[mid:]))
        if not np.isfinite(tail):
            base["status"] = "insufficient"
            base["reason"] = "insufficient_bootstrap_alpha2_data"
            return base
        slopes.append(s)
        a2tails.append(tail)
    lo_q = (1.0 - float(ci_level)) / 2.0
    out = dict(base)
    out.update({
        "status": "sufficient",
        "reason": None,
        "log_slope_ci": [float(np.quantile(slopes, lo_q)),
                         float(np.quantile(slopes, 1.0 - lo_q))],
        "tail_alpha2_ci": [float(np.quantile(a2tails, lo_q)),
                           float(np.quantile(a2tails, 1.0 - lo_q))],
        "log_slope_bootstrap_mean": float(np.mean(slopes)),
        "tail_alpha2_bootstrap_mean": float(np.mean(a2tails)),
    })
    return out


# ---------------------------------------------------------------------------
# Full P2.5 analysis: unwrap -> extract -> F3 -> uncertainty -> verdict.
# ---------------------------------------------------------------------------

def analyze_p25(p2_payload: Dict[str, Any],
                config: Dict[str, Any],
                worker_info: Optional[Dict[str, Any]] = None,
                p2_result_path: str = "") -> Dict[str, Any]:
    """Analyze one bound P2 result; return the P2.5 result mapping.

    Raises P25Error when analysis is impossible (missing/tampered
    artifact, missing thermal provenance). Thin but analyzable evidence
    yields INDETERMINATE verdicts, never exceptions.
    """
    batch_id = p2_payload.get("batch_id", "?")
    p2res = p2_payload.get("result", {})
    cfg_hash = p25_config_hash(config)
    target_species = str(config.get("target_species", "Li"))
    window = tuple(config.get("fit_window_fraction", [0.3, 0.9]))
    block_origins = int(config.get("block_origins", 20))
    n_bootstrap = int(config.get("n_bootstrap", 200))
    ci_level = float(config.get("ci_level", 0.68))
    min_mobile = int(config.get("min_mobile_ions", 2))
    min_blocks = int(config.get("min_blocks", 4))
    use_veto = bool(config.get("uncertainty_veto", True))

    # Thermal + identity provenance from the existing P2 contract
    # (never hard-coded; P2.5 reads what P2 recorded).
    temperature: Optional[float] = None
    temp_source = None
    if isinstance(p2res.get("temperature_K"), (int, float)):
        temperature = float(p2res["temperature_K"])
        temp_source = "p2_result"
    elif isinstance((p2res.get("p2_protocol") or {}).get("temperature_K"),
                    (int, float)):
        temperature = float(p2res["p2_protocol"]["temperature_K"])
        temp_source = "p2_protocol"
    if temperature is None or not np.isfinite(temperature):
        raise P25Error(f"p25 {batch_id}: no finite temperature_K in P2 result")

    artifact, binding = load_verified_artifact(p2_payload)
    species_all: List[str] = [str(s) for s in artifact["species"]]
    cell = np.asarray(artifact["cell"], dtype=float)
    wrapped = np.asarray(artifact["positions"], dtype=float)
    dt_ps = float(artifact["timestep_fs"]) / 1000.0 * float(
        artifact["sample_interval_steps"])
    n_frames = int(artifact["n_production_frames"])

    # Canonical unwrapping (single call site; F3 never sees wrapped data).
    unwrapped = unwrap_trajectory(wrapped, cell) if n_frames else wrapped.copy()

    # Explicit mobile-ion extraction (exact match, order preserved).
    mobile_idx = [i for i, s in enumerate(species_all) if s == target_species]
    n_mobile = len(mobile_idx)

    reasons: List[str] = []
    point_state = TransportState.INDETERMINATE
    log_slope: Optional[float] = None
    tail_a2: Optional[float] = None
    lags = np.zeros(0, dtype=int)
    msd = np.zeros(0)
    a2curve = np.zeros(0)
    n_valid = 0

    if n_frames == 0:
        reasons.append("no_production_frames: artifact carries no "
                       "production trajectory")
    elif n_frames < 2:
        reasons.append("insufficient_frames: trajectory has fewer than 2 frames")
    elif n_mobile == 0:
        res0 = validate_diffusive_regime(unwrapped, species_all,
                                         target_species=target_species)
        point_state = res0.transport_state  # INDETERMINATE
        log_slope, tail_a2 = res0.log_slope, res0.alpha2
        reasons.append("no_target_ions_found: transport_state INDETERMINATE "
                       "per F3 absent-sublattice semantics")
    else:
        res = validate_diffusive_regime(unwrapped, species_all,
                                        target_species=target_species,
                                        fit_window_fraction=window)
        point_state = res.transport_state
        log_slope, tail_a2 = res.log_slope, res.alpha2
        lags, msd, a2curve = compute_species_resolved_msd(
            unwrapped, species_all, target_species=target_species)
        n_valid = int(((lags > 0) & (msd > 1e-12) & np.isfinite(lags) & np.isfinite(msd)).sum())
        if n_valid < 3:
            reasons.append("insufficient_lag_points: fewer than 3 valid "
                           "lag points for the F3 slope fit")
        elif log_slope is None:
            reasons.append("insufficient_fit_window_points: fewer than 2 points "
                           "in the selected fit window for the F3 slope fit")

    # Block uncertainty (mobile-only unwrapped input; same-lag blocks).
    uncertainty: Dict[str, Any] = {
        "method": "block_bootstrap_origins",
        "block_length_origins": int(block_origins),
        "n_bootstrap": int(n_bootstrap),
        "ci_level": float(ci_level),
        "status": "insufficient",
        "reason": "not_estimated",
    }
    if n_frames >= 2 and n_mobile > 0:
        boot_seed = (int(p2res.get("seed", 0)) + P25_BOOTSTRAP_SALT) % (2 ** 32)
        uncertainty = block_bootstrap_uncertainty(
            unwrapped[:, mobile_idx, :], window, block_origins,
            n_bootstrap, ci_level, boot_seed, min_blocks=min_blocks)

    # Final verdict: point classification, then conservative escalation.
    # Only DIFFUSIVE claims require positive support; NONDIFFUSIVE and
    # INDETERMINATE points stand (with uncertainty reported as available).
    # n_frames == 0 already leaves point INDETERMINATE above.
    final_state = point_state
    if n_frames > 0 and n_mobile > 0 and (n_valid < 3 or log_slope is None):
        final_state = TransportState.INDETERMINATE
    if final_state == TransportState.DIFFUSIVE:
        if n_mobile < min_mobile:
            final_state = TransportState.INDETERMINATE
            reasons.append("insufficient_mobile_ions: single-ion point "
                           "estimates cannot support a DIFFUSIVE claim")
        elif uncertainty.get("status") != "sufficient":
            final_state = TransportState.INDETERMINATE
            reasons.append("insufficient_uncertainty_blocks: too few "
                           "origin blocks for a defensible DIFFUSIVE claim")
        elif use_veto:
            slo, shi = uncertainty["log_slope_ci"]
            ahi = uncertainty["tail_alpha2_ci"][1]
            if (slo < P25_SLOPE_MIN_PROVISIONAL
                    or shi > P25_SLOPE_MAX_PROVISIONAL
                    or ahi > P25_ALPHA2_MAX_PROVISIONAL):
                final_state = TransportState.INDETERMINATE
                reasons.append("uncertainty_overlaps_gate: 68pct block CI "
                               "leaves the provisional F3 gate")

    calc = (p2res.get("provenance") or {}).get("calc") or {}
    event = EvidenceEvent(
        level="P2.5",
        method=P25_TRANSPORT_METHOD,
        conditions={"temperature_K": temperature,
                    "temperature_source": temp_source,
                    "target_species": target_species,
                    "n_mobile_ions": n_mobile,
                    "n_production_frames": n_frames,
                    "n_valid_lags": n_valid,
                    "fit_window_fraction": list(window),
                    "uncertainty_method": uncertainty.get("method"),
                    "block_length_origins": uncertainty.get(
                        "block_length_origins"),
                    "n_bootstrap": uncertainty.get("n_bootstrap"),
                    "ci_level": uncertainty.get("ci_level"),
                    "log_slope_ci": uncertainty.get("log_slope_ci"),
                    "tail_alpha2_ci": uncertainty.get("tail_alpha2_ci"),
                    "p25_config_hash": cfg_hash,
                    "p25_version": P25_VERSION,
                    "trajectory_frames": n_frames},
        uncertainty=None,  # intervals live in conditions (float field
        # cannot hold a CI); never zero-filled (absent when insufficient).
        source=str((worker_info or {}).get("session", "")),
        artifact_hash=binding["sha256"],
        model_or_data_version=str(calc.get("checkpoint_name", "")),
    )
    lag_time_ps = (lags.astype(float) * dt_ps).tolist() if len(lags) else []
    return {
        "candidate_material_id": p2res.get("candidate_material_id"),
        "batch_id": p2_payload.get("batch_id"),
        "parent_id": p2res.get("parent_id"),
        "p2_dynamic_state": p2res.get("dynamic_state"),
        "p2_verdict": p2res.get("p2_verdict"),
        "temperature_K": temperature,
        "temperature_source": temp_source,
        "target_species": target_species,
        "transport_state": final_state.value,
        "p25_verdict": final_state.value,  # alias for worker-side filtering
        "transport_claim_status": "provisional",  # gates are provisional;
        # uncertainty does not (yet) redefine the scientific gate.
        "point_transport_state": point_state.value,
        "provenance": {
            "p2_result_path": p2_result_path,
            "trajectory_artifact_path": binding["path"],
            "trajectory_artifact_sha256": binding["sha256"],
            "artifact_format_version": binding["format_version"],
            "p2_config_hash": p2res.get("p2_config_hash"),
            "p2_protocol_version": p2res.get("p2_protocol_version"),
            "p2_seed": p2res.get("seed"),
            "p25_config_hash": cfg_hash,
            "p25_version": P25_VERSION,
        },
        "transport": {
            "n_mobile_ions": n_mobile,
            "n_frames": n_frames,
            "lag_time_ps": lag_time_ps,
            "msd_A2": [float(v) for v in msd] if len(msd) else [],
            "alpha2_curve": [float(v) for v in a2curve] if len(a2curve) else [],
            "log_slope": float(log_slope) if log_slope is not None else None,
            "tail_alpha2": float(tail_a2) if tail_a2 is not None else None,
            "fit_window": list(window),
            "max_lag_frames": int(len(lags)),
            "dt_ps_per_lag_step": float(dt_ps),
            "uncertainty": uncertainty,
        },
        "sufficiency": {
            "n_mobile_ions": n_mobile,
            "min_mobile_ions": int(min_mobile),
            "n_production_frames": n_frames,
            "n_valid_lags": n_valid,
            "n_origin_blocks": int(uncertainty.get("n_blocks", 0)),
            "min_blocks": int(min_blocks),
        },
        "diagnostics": {
            "unwrapped": True,
            "unwrap_method": "p2.unwrap_trajectory",
            "point_transport_state": point_state.value,
            "reasons": reasons,
        },
        "error_info": None,
        "evidence_events": [event.to_dict()],
    }


# ---------------------------------------------------------------------------
# Batch runner (mirrors run_p2_batches resume philosophy).
# ---------------------------------------------------------------------------

def _p25_eligible(p2_payload: Dict[str, Any]) -> Optional[str]:
    """Eligibility gate: P2 PASS with a bound trajectory artifact.

    Returns None when eligible, else an ineligibility reason. P2 FAIL /
    legacy-unbound results are skipped (not errors): transport analysis
    on a collapsed framework is meaningless, and legacy results have no
    verifiable trajectory to analyze.
    """
    res = p2_payload.get("result")
    if not isinstance(res, dict):
        return "no P2 result mapping"
    if res.get("p2_verdict") != "PASS":
        return f"P2 verdict {res.get('p2_verdict')!r} is not PASS"
    binding = res.get("trajectory_artifact")
    if not isinstance(binding, dict):
        return "legacy P2 result without trajectory_artifact binding"
    return None


def run_p25_batches(
    p2_dir: Union[str, Path],
    p25_dir: Union[str, Path],
    shard_index: int,
    n_shards: int,
    config: Dict[str, Any],
    worker_info: Optional[Dict[str, Any]] = None,
    retry_errors: bool = False,
) -> Dict[str, Any]:
    """Run one P2.5 shard over bound P2 PASS results. No locks, no queue."""
    p2_dir, p25_dir = Path(p2_dir), Path(p25_dir)
    cfg_hash = p25_config_hash(config)
    counts: Dict[str, Any] = {"processed": 0, "errored": 0, "skipped_done": 0,
                              "skipped_shard": 0, "skipped_ineligible": 0,
                              "stale_recomputed": 0, "retried_errors": 0,
                              # Batch IDs whose result file THIS invocation
                              # wrote (processed + errored + stale
                              # recomputes). Consumed by run_p25
                              # --git-commit so only this worker's files are
                              # ever staged. Skipped (resume) IDs never
                              # appear here.
                              "wrote": []}
    for p2_file in sorted(Path(p2_dir).glob("*.json")):
        batch_id = p2_file.stem
        if not assign_shard(batch_id, shard_index, n_shards):
            counts["skipped_shard"] += 1
            continue
        try:
            with open(p2_file, encoding="utf-8") as f:
                p2_payload = json.load(f)
            inelig = _p25_eligible(p2_payload)
            if inelig is not None:
                raise _Ineligible(inelig)
            p2res = p2_payload["result"]
            need_sha = p2res["trajectory_artifact"]["sha256"]
        except _Ineligible as e:
            counts["skipped_ineligible"] += 1
            continue
        except Exception:
            counts["skipped_ineligible"] += 1
            continue
        out_file = p25_dir / f"{batch_id}.json"
        if out_file.exists():
            try:
                with open(out_file, encoding="utf-8") as f:
                    prior = json.load(f)
                prior_res = prior.get("result") or {}
                same_input = (prior_res.get("provenance", {}).get(
                    "trajectory_artifact_sha256") == need_sha)
                same_cfg = (prior_res.get("provenance", {}).get(
                    "p25_config_hash") == cfg_hash)
                prior_verdict = prior_res.get("p25_verdict")
            except Exception:
                same_input, same_cfg, prior_verdict = False, False, None
            if not (same_input and same_cfg) or prior_verdict == "ERROR":
                if prior_verdict == "ERROR" and not retry_errors:
                    counts["skipped_done"] += 1
                    continue
                counts["stale_recomputed"] += 1
                if prior_verdict == "ERROR":
                    counts["retried_errors"] += 1
                # fall through: recompute
            else:
                counts["skipped_done"] += 1
                continue
        try:
            result = analyze_p25(p2_payload, config, worker_info,
                                 p2_result_path=str(p2_file))
        except Exception as e:
            result = {"p25_verdict": "ERROR",
                      "transport_state": TransportState.NOT_RUN.value,
                      "error_type": type(e).__name__,
                      "error_message": str(e)[:500],
                      "p2_trajectory_sha256": need_sha,
                      "p25_config_hash": cfg_hash}
            counts["errored"] += 1
        else:
            counts["processed"] += 1
        payload = {"batch_id": batch_id, "p25_config": config,
                   "result": result, "worker": worker_info or {}}
        write_json_atomic(out_file, payload)
        # Read-back validation (same contract as P2): the file must parse
        # before it counts as written; failure is loud, file preserved.
        try:
            with open(out_file, encoding="utf-8") as f:
                json.load(f)
        except Exception as e:
            raise IOError(f"p25 result not readable after atomic write: "
                          f"{out_file}: {e}")
        counts["wrote"].append(batch_id)
    counts["wrote"] = sorted(counts["wrote"])
    return counts


class _Ineligible(Exception):
    """Internal control flow: batch skipped as ineligible (not an error)."""
