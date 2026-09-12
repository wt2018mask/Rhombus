"""LiIon room-temperature sulfide cross-validation for bench scoring functions.

Purpose:
    Independently check whether the OBELiX sulfide signal (notably the F2 BVSE
    within-sulfide AUC ~0.77, PROVISIONAL) replicates on a disjoint experimental
    source: the temperature-resolved LiIon conductivity dataset, restricted to
    its room-temperature sulfide slice.

HARD INVARIANTS (AGENTS.md §6 -- enforced by construction, not just comments):
    1. LiIon rows are NEVER merged into OBELiX rows. This module only reads the
       two tables side by side; no concat/merge/join of row data occurs.
    2. Temperature is NEVER averaged away. Every LiIon row is scored as its own
       observation (repeated measurements of one composition at different
       temperatures stay as separate rows). There is no groupby on composition.

Structure problem and honest workaround:
    LiIon ships compositions + conductivities but NO crystal structures, while
    F2 BVSE requires a structure. For each LiIon RT sulfide row whose composition
    parses to a normalized formula exactly matching an OBELiX CIF-linked entry,
    the OBELiX structure is borrowed *as a scoring handle only*. Rows with
    glass/mixture notations (e.g. "(Li2S)0.3...") or compositions with no CIF
    counterpart are left unscored by BVSE. Coverage (n_matched / n_total) and
    the polymorph caveat (same formula != same structure) are always reported
    alongside the metric so a small matched subset can never masquerade as a
    full replication.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from rudeus.bench.harness import (
    composition_baseline_scorer,
    f2_bvse_probation_scorer,
)
from rudeus.bench.metrics import compute_roc_auc
from rudeus.empirical.liion import LiIonDataset
from rudeus.empirical.obelix import OBELiXDataset, normalize_formula


@dataclass(frozen=True)
class LiIonCrossCheckResult:
    """Outcome of scoring the LiIon RT sulfide slice with bench filters.

    Attributes:
        n_rt_sulfide_rows:      LiIon rows with 18<=T<=32 °C and 'sulph' family.
        n_unique_compositions:  Distinct composition strings in that slice.
        n_superionic:           Slice rows with target >= cutoff (PROVISIONAL).
        superionic_cutoff_provisional: Conductivity cutoff used for labels.
        baseline_auc / baseline_spearman_rho / baseline_spearman_p:
                                composition_baseline on ALL slice rows.
        n_bvse_matched:         Slice rows matched to an OBELiX CIF structure.
        n_bvse_formulas:        Distinct matched formulas (polymorph caveat scope).
        bvse_auc / bvse_spearman_rho / bvse_spearman_p:
                                f2_bvse_probation on the matched subset only
                                (NaN fields are None when subset is degenerate).
        readout:                Honest human-readable interpretation, including
                                whether the OBELiX sulfide signal replicates.
    """

    n_rt_sulfide_rows: int
    n_unique_compositions: int
    n_superionic: int
    superionic_cutoff_provisional: float
    baseline_auc: float
    baseline_spearman_rho: float
    baseline_spearman_p: float
    n_bvse_matched: int
    n_bvse_formulas: int
    bvse_auc: Optional[float]
    bvse_spearman_rho: Optional[float]
    bvse_spearman_p: Optional[float]
    readout: str


def _spearman_guarded(scores: np.ndarray, log_target: np.ndarray) -> tuple:
    """Spearman rho/p with the same NaN guard convention as metrics.py."""
    rho, p_val = spearmanr(scores, log_target)
    rho_out = float(rho) if not np.isnan(rho) else 0.0
    p_out = float(p_val) if not np.isnan(p_val) else 1.0
    return rho_out, p_out


def _build_formula_structure_map(obelix: OBELiXDataset) -> Dict[str, str]:
    """Map normalized formula -> one OBELiX entry ID that has a CIF.

    Deterministic: for formulas with several CIF-linked entries (polymorphs /
    duplicates), the lexicographically smallest ID wins. Only the ID is
    borrowed (as a structure handle for BVSE scoring) -- no OBELiX row data
    is copied into any LiIon table.
    """
    cif_ids = {p.stem for p in obelix.cif_dir.glob("*.cif")} if obelix.cif_dir.exists() else set()
    formula_map: Dict[str, str] = {}
    for _, row in obelix.df.iterrows():
        entry_id = str(row["ID"])
        if entry_id not in cif_ids:
            continue
        try:
            key = normalize_formula(str(row["Composition"]))
        except Exception:
            continue
        if key not in formula_map or entry_id < formula_map[key]:
            formula_map[key] = entry_id
    return formula_map


def run_liion_sulfide_rt_crosscheck(
    obelix: OBELiXDataset,
    liion: LiIonDataset,
    superionic_cutoff_provisional: float = 1e-3,
) -> LiIonCrossCheckResult:
    """Score the LiIon RT sulfide slice with composition_baseline + F2 BVSE.

    Each LiIon row is one observation (temperature-resolved, never averaged).
    BVSE is evaluated only on the formula-matched subset; the composition
    baseline is evaluated on the full slice since it needs no structure.
    """
    rt_sulf = liion.sulfide_rt_slice()
    n_rows = len(rt_sulf)
    if n_rows == 0:
        return LiIonCrossCheckResult(
            n_rt_sulfide_rows=0,
            n_unique_compositions=0,
            n_superionic=0,
            superionic_cutoff_provisional=superionic_cutoff_provisional,
            baseline_auc=0.5,
            baseline_spearman_rho=0.0,
            baseline_spearman_p=1.0,
            n_bvse_matched=0,
            n_bvse_formulas=0,
            bvse_auc=None,
            bvse_spearman_rho=None,
            bvse_spearman_p=None,
            readout="Empty LiIon RT sulfide slice -- no cross-validation possible.",
        )

    targets = rt_sulf["target"].to_numpy(dtype=float)
    y_true = (targets >= superionic_cutoff_provisional).astype(int)
    log_target = np.log10(np.maximum(targets, 1e-15))

    # --- Composition baseline on the FULL slice (no structure needed) ---
    base_scores: List[float] = []
    for _, row in rt_sulf.iterrows():
        adapter = pd.Series({"ID": str(row["ID"]), "Composition": str(row["composition"])})
        try:
            base_scores.append(float(composition_baseline_scorer(adapter, obelix)))
        except Exception:
            base_scores.append(0.0)
    base_scores_arr = np.array(base_scores, dtype=float)
    baseline_auc = compute_roc_auc(y_true, base_scores_arr)
    baseline_rho, baseline_p = _spearman_guarded(base_scores_arr, log_target)

    # --- F2 BVSE on the formula-matched subset only ---
    formula_map = _build_formula_structure_map(obelix)
    matched_idx: List[int] = []
    bvse_scores: List[float] = []
    matched_formulas: set = set()
    for pos, (_, row) in enumerate(rt_sulf.iterrows()):
        try:
            key = normalize_formula(str(row["composition"]))
        except Exception:
            continue
        obelix_id = formula_map.get(key)
        if obelix_id is None:
            continue
        adapter = pd.Series({"ID": obelix_id, "Composition": str(row["composition"])})
        try:
            bvse_scores.append(float(f2_bvse_probation_scorer(adapter, obelix)))
        except Exception:
            bvse_scores.append(0.0)
        matched_idx.append(pos)
        matched_formulas.add(key)

    if matched_idx:
        m_true = y_true[np.array(matched_idx)]
        m_scores = np.array(bvse_scores, dtype=float)
        m_logt = log_target[np.array(matched_idx)]
        if len(np.unique(m_true)) == 2:
            bvse_auc: Optional[float] = compute_roc_auc(m_true, m_scores)
        else:
            bvse_auc = None  # Single class in matched subset -- AUC undefined.
        bvse_rho, bvse_p = _spearman_guarded(m_scores, m_logt)
        bvse_rho_out: Optional[float] = bvse_rho
        bvse_p_out: Optional[float] = bvse_p
    else:
        bvse_auc = None
        bvse_rho_out = None
        bvse_p_out = None

    n_superionic = int(y_true.sum())
    n_unique = int(rt_sulf["composition"].nunique())

    # --- Honest readout ---
    coverage = len(matched_idx) / n_rows if n_rows else 0.0
    if bvse_auc is None:
        verdict = (
            "F2 BVSE cross-validation INCONCLUSIVE on LiIon RT sulfides "
            f"(matched subset n={len(matched_idx)} has a single conductivity class; "
            "AUC undefined)."
        )
    elif len(matched_idx) < 15:
        verdict = (
            f"F2 BVSE cross-validation INCONCLUSIVE (matched n={len(matched_idx)} "
            f"of {n_rows} RT sulfide rows, coverage {coverage:.0%}; below any "
            "reasonable minimum for an AUC claim -- small-sample noise dominates)."
        )
    elif bvse_auc >= 0.65:
        verdict = (
            f"F2 BVSE sulfide signal REPLICATES on LiIon RT sulfides "
            f"(matched-subset AUC={bvse_auc:.3f}, n={len(matched_idx)}; "
            "still PROVISIONAL -- structure borrowing by formula carries a "
            "polymorph caveat)."
        )
    else:
        verdict = (
            f"F2 BVSE sulfide signal DOES NOT replicate on LiIon RT sulfides "
            f"(matched-subset AUC={bvse_auc:.3f}, n={len(matched_idx)}; "
            "OBELiX within-sulfide AUC ~0.77 looks consistent with small-sample "
            "noise or population shift, NOT a confirmed effect)."
        )
    readout = (
        f"LiIon RT sulfide slice: n={n_rows} rows ({n_unique} unique compositions), "
        f"{n_superionic} superionic at PROVISIONAL cutoff {superionic_cutoff_provisional} S/cm. "
        f"composition_baseline on full slice: AUC={baseline_auc:.3f}, "
        f"Spearman rho={baseline_rho:.3f} (p={baseline_p:.3g}). "
        f"F2 BVSE matched {len(matched_idx)}/{n_rows} rows "
        f"({len(matched_formulas)} formulas, coverage {coverage:.0%})"
        + (f": AUC={bvse_auc:.3f}, Spearman rho={bvse_rho_out:.3f} (p={bvse_p_out:.3g}). " if bvse_auc is not None else ". ")
        + verdict
        + " Tables kept separate; temperature never averaged (one row = one observation)."
    )

    return LiIonCrossCheckResult(
        n_rt_sulfide_rows=n_rows,
        n_unique_compositions=n_unique,
        n_superionic=n_superionic,
        superionic_cutoff_provisional=superionic_cutoff_provisional,
        baseline_auc=baseline_auc,
        baseline_spearman_rho=baseline_rho,
        baseline_spearman_p=baseline_p,
        n_bvse_matched=len(matched_idx),
        n_bvse_formulas=len(matched_formulas),
        bvse_auc=bvse_auc,
        bvse_spearman_rho=bvse_rho_out,
        bvse_spearman_p=bvse_p_out,
        readout=readout,
    )
