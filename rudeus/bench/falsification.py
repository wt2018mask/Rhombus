"""Falsification / negative-control gate for rudeus bench.

Gate logic:
  - Negative controls are Li-rich structures measured to be ionic insulators
    (conductivity <= 1e-8 S/cm, Li-fraction >= 20%) sourced from OBELiX itself.
    These are empirically validated real structures, NOT invented.
  - Scoring functions should NOT rank these insulators highly.
  - PASS condition: <= 25% of negatives land in top-20% of the combined ranking.
    (PROVISIONAL threshold -- requires calibration against additional insulator
     sets once available, e.g. from Materials Project.)
  - Result is a distinct field "falsification_gate" in filter_verdict.json
    and is NEVER folded into the AUC-based verdict logic.

Source note:
  Negatives sourced from OBELiX itself (subset with conductivity <= 1e-8 S/cm and
  Li-fraction >= 20%), NOT from Materials Project.  Using the officially published
  structures here respects the empirical anchor constraint of AGENTS.md §6.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from pymatgen.core import Composition, Structure

from rudeus.empirical.obelix import OBELiXDataset
from rudeus.filters.bvse import evaluate_f2_bvse


# ---------------------------------------------------------------------------
# Negative-control set -- OBELiX IDs with Li-fraction >= 20% AND
# measured conductivity <= 1e-8 S/cm (empirically confirmed insulators).
# ---------------------------------------------------------------------------
NEGATIVE_CONTROL_IDS: List[str] = [
    "ro9", "47i", "clt", "bq9", "skm", "y2l", "cfy", "pe2", "n27", "ecp",
    "me3", "1xt", "5zv", "uu4", "tws", "t0h", "4kt", "uox", "mq1", "ssv",
    "h6c", "bsa", "1e9", "an2", "cdk", "5z0", "472", "9zk", "w7d", "gxz",
    "tbu", "uxo", "dku", "ndx", "m0j", "9lo", "dth", "45e", "qa9", "d7f",
    "sg0", "97b", "2ro", "dc8", "jy6", "kkn",
]

# PROVISIONAL -- fraction threshold for the falsification gate
_FALSIFICATION_TOP20_THRESHOLD_PROVISIONAL: float = 0.25


# ---------------------------------------------------------------------------
# Scoring-function type
# ---------------------------------------------------------------------------
ScoringFunction = Callable[[pd.Series, OBELiXDataset], float]


@dataclass(frozen=True)
class FalsificationResult:
    """Outcome of running a scoring function against the negative-control set.

    Attributes:
        filter_name:          Name of the filter being evaluated.
        n_negatives_loaded:   Number of negative controls that had CIF + row in dataset.
        n_negatives_scored:   Number of negative controls that returned a real score.
        n_positives_scored:   Number of OBELiX test-set positives included in ranking.
        fraction_neg_top10:   Fraction of negatives landing in top 10% of combined ranking.
        fraction_neg_top20:   Fraction of negatives landing in top 20% of combined ranking.
        gate_threshold_provisional: The fraction threshold used for PASS/FAIL (PROVISIONAL).
        gate_result:          "PASS" or "FAIL".
        rationale:            Human-readable explanation.
    """
    filter_name: str
    n_negatives_loaded: int
    n_negatives_scored: int
    n_positives_scored: int
    fraction_neg_top10: float
    fraction_neg_top20: float
    gate_threshold_provisional: float
    gate_result: str
    rationale: str


def _composition_score(row: pd.Series, dataset: OBELiXDataset) -> float:
    """Composition-only baseline: sulfide-flag + Li-fraction."""
    comp_str = str(row.get("Composition", "") or "")
    try:
        comp = Composition(comp_str)
        elements = set(el.symbol for el in comp.elements)
        has_chalcogen = any(e in elements for e in ["S", "Se", "Te"])
        total = sum(comp.values())
        li_frac = float(comp["Li"] / total) if "Li" in comp and total > 0 else 0.0
        return (1.0 if has_chalcogen else 0.0) + li_frac
    except Exception:
        return 0.0


def _bvse_score(row: pd.Series, dataset: OBELiXDataset) -> float:
    """F2 BVSE percolation score; 0.50 neutral fallback if no CIF."""
    entry_id = str(row.get("ID", ""))
    struct = dataset.get_structure(entry_id)
    if struct is not None:
        result = evaluate_f2_bvse(struct, mobile_ion="Li")
        return float(result.score)
    return 0.50


def _make_negative_control_df(dataset: OBELiXDataset) -> pd.DataFrame:
    """Build a DataFrame row for each negative-control ID that has a CIF.

    Returns a DataFrame with columns: ID, Composition, is_negative_control.
    Conductivity is filled with 0 (below any superionic threshold) so these
    entries are always labelled as non-superionic when merged into rankings.
    """
    cif_dir = dataset.cif_dir
    full_df = dataset.df  # includes both train and test rows

    rows = []
    for entry_id in NEGATIVE_CONTROL_IDS:
        # Must have a CIF (we don't want to evaluate blind)
        cif_path = cif_dir / f"{entry_id}.cif"
        if not cif_path.exists():
            continue
        # Find the metadata row (for Composition etc.)
        match = full_df[full_df["ID"] == entry_id]
        if match.empty:
            continue
        r = match.iloc[0].copy()
        r["is_negative_control"] = True
        rows.append(r)

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def run_falsification_gate(
    filter_name: str,
    scorer: ScoringFunction,
    dataset: OBELiXDataset,
    top_k_fractions: Tuple[float, float] = (0.10, 0.20),
    gate_threshold_provisional: float = _FALSIFICATION_TOP20_THRESHOLD_PROVISIONAL,
) -> FalsificationResult:
    """Run the falsification gate for one scoring function.

    Procedure:
    1. Load all negative-control entries that have CIFs.
    2. Score them with the provided scorer.
    3. Mix with OBELiX test-set entries (real evaluation population).
    4. Rank all together and check what fraction of negatives land in top-10%/20%.
    5. FAIL if fraction-in-top-20% > gate_threshold_provisional.

    Args:
        filter_name:  Human-readable name of the filter.
        scorer:       Function (row, dataset) -> float score (higher = more promising).
        dataset:      Loaded OBELiXDataset.
        top_k_fractions:  (top-10%, top-20%) to check (default: (0.10, 0.20)).
        gate_threshold_provisional:
                      Maximum allowed fraction of negatives in top-20% to PASS.
                      PROVISIONAL -- must be calibrated against broader neg-control set.

    Returns:
        FalsificationResult with gate_result "PASS" or "FAIL".
    """
    # --- Build negative-control DataFrame ---
    neg_df = _make_negative_control_df(dataset)
    if neg_df.empty:
        return FalsificationResult(
            filter_name=filter_name,
            n_negatives_loaded=0,
            n_negatives_scored=0,
            n_positives_scored=len(dataset.test_df),
            fraction_neg_top10=float("nan"),
            fraction_neg_top20=float("nan"),
            gate_threshold_provisional=gate_threshold_provisional,
            gate_result="FAIL",
            rationale="No negative controls could be loaded (no CIF matches). Gate fails by default.",
        )

    # --- Score negative controls ---
    neg_scores: List[float] = []
    for _, row in neg_df.iterrows():
        try:
            s = scorer(row, dataset)
        except Exception:
            s = 0.0
        neg_scores.append(s)

    neg_df = neg_df.copy()
    neg_df["score"] = neg_scores
    neg_df["is_negative_control"] = True

    # --- Score OBELiX test set positives ---
    test_df = dataset.test_df.copy()
    pos_scores: List[float] = []
    for _, row in test_df.iterrows():
        try:
            s = scorer(row, dataset)
        except Exception:
            s = 0.0
        pos_scores.append(s)
    test_df["score"] = pos_scores
    test_df["is_negative_control"] = False

    # --- Merge and rank (descending: higher score = higher rank) ---
    combined_cols = ["ID", "score", "is_negative_control"]
    combined = pd.concat(
        [
            neg_df[combined_cols],
            test_df[combined_cols],
        ],
        ignore_index=True,
    )
    combined = combined.sort_values("score", ascending=False).reset_index(drop=True)
    n_total = len(combined)

    top10_frac, top20_frac = top_k_fractions
    top10_k = max(1, int(np.ceil(n_total * top10_frac)))
    top20_k = max(1, int(np.ceil(n_total * top20_frac)))

    top10_ids = set(combined.iloc[:top10_k]["ID"].astype(str))
    top20_ids = set(combined.iloc[:top20_k]["ID"].astype(str))

    neg_ids_loaded = set(neg_df["ID"].astype(str))
    neg_in_top10 = len(neg_ids_loaded & top10_ids)
    neg_in_top20 = len(neg_ids_loaded & top20_ids)

    n_neg = len(neg_df)
    frac_top10 = neg_in_top10 / n_neg if n_neg > 0 else float("nan")
    frac_top20 = neg_in_top20 / n_neg if n_neg > 0 else float("nan")

    # --- Gate decision ---
    gate_result = "PASS" if frac_top20 <= gate_threshold_provisional else "FAIL"
    rationale = (
        f"{filter_name}: {n_neg} negative controls scored; "
        f"{neg_in_top10}/{n_neg} ({frac_top10:.1%}) in top 10%, "
        f"{neg_in_top20}/{n_neg} ({frac_top20:.1%}) in top 20% "
        f"(PROVISIONAL threshold: <={gate_threshold_provisional:.0%} for PASS). "
        f"Gate: {gate_result}."
    )

    return FalsificationResult(
        filter_name=filter_name,
        n_negatives_loaded=n_neg,
        n_negatives_scored=n_neg,
        n_positives_scored=len(test_df),
        fraction_neg_top10=frac_top10,
        fraction_neg_top20=frac_top20,
        gate_threshold_provisional=gate_threshold_provisional,
        gate_result=gate_result,
        rationale=rationale,
    )


def run_all_falsification_gates(
    dataset: OBELiXDataset,
    scorers: Optional[Dict[str, ScoringFunction]] = None,
) -> Dict[str, FalsificationResult]:
    """Run falsification gates for all named scorers.

    If scorers is None, defaults to both built-in scorers:
    - composition_baseline
    - f2_bvse_probation
    """
    if scorers is None:
        scorers = {
            "composition_baseline": _composition_score,
            "f2_bvse_probation": _bvse_score,
        }

    results: Dict[str, FalsificationResult] = {}
    for name, fn in scorers.items():
        results[name] = run_falsification_gate(
            filter_name=name,
            scorer=fn,
            dataset=dataset,
        )
    return results
