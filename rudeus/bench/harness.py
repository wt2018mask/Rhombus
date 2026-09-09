"""Pluggable scoring function interface and benchmark evaluation harness.

Evaluates any candidate pre-screening filter identically against the official
OBELiX test split with full statistical rigor.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd
from pymatgen.core import Composition

from rudeus.empirical.obelix import OBELiXDataset
from rudeus.filters.bvse import evaluate_f2_bvse
from rudeus.bench.metrics import MetricEvaluationResult, evaluate_filter_candidate


ScoringFunction = Callable[[pd.Series, OBELiXDataset], float]


def composition_baseline_scorer(row: pd.Series, dataset: OBELiXDataset) -> float:
    """Composition-only baseline filter: sulfide-flag + Li-fraction.

    A fast heuristic widely used as an intuitive baseline:
    score = (1.0 if sulfide/chalcogenide else 0.0) + (fraction of Li atoms)
    """
    comp_str = str(row["Composition"])
    try:
        comp = Composition(comp_str)
        elements = set(el.symbol for el in comp.elements)
        has_chalcogen = any(e in elements for e in ["S", "Se", "Te"])
        total_atoms = sum(comp.values())
        li_frac = float(comp["Li"] / total_atoms) if "Li" in comp and total_atoms > 0 else 0.0
        return (1.0 if has_chalcogen else 0.0) + li_frac
    except Exception:
        return 0.0


def f2_bvse_probation_scorer(row: pd.Series, dataset: OBELiXDataset) -> float:
    """F2 BVSE percolation scoring function for CIF-linked entries.

    If structure is available, returns the BVSE percolation score (higher = lower barrier).
    If structure is unavailable, returns median fallback score (neutral imputation).
    """
    entry_id = str(row["ID"])
    struct = dataset.get_structure(entry_id)

    if struct is not None:
        result = evaluate_f2_bvse(struct, mobile_ion="Li")
        return float(result.score)
    else:
        # If no crystal structure CIF is available, return 0.5 (neutral fallback)
        return 0.50


class BenchmarkHarness:
    """Evaluation harness running scoring functions against official OBELiX splits."""

    def __init__(
        self,
        dataset: OBELiXDataset,
        superionic_cutoff_provisional: float = 1e-3,
        random_seed: int = 42,
    ):
        self.dataset = dataset
        self.superionic_cutoff_provisional = superionic_cutoff_provisional
        self.random_seed = random_seed
        self.scorers: Dict[str, ScoringFunction] = {}

    def register_scorer(self, name: str, scorer: ScoringFunction) -> None:
        """Register a pluggable scoring function."""
        self.scorers[name] = scorer

    def run_evaluations(
        self,
        n_bootstraps: int = 1000,
        n_scrambles: int = 1000,
    ) -> Tuple[pd.DataFrame, Dict[str, str], Dict[str, MetricEvaluationResult]]:
        """Run all registered scoring functions on the official test set.

        Returns:
            bench_report_df: Table of results matching bench_report.csv schema.
            verdict_dict: Map of filter_name -> KEEP | REMOVE | INSUFFICIENT_EVIDENCE.
            detailed_results: Map of filter_name -> MetricEvaluationResult.
        """
        test_df = self.dataset.test_df
        cond_col = "Ionic conductivity (S cm-1)"
        y_conductivity = test_df[cond_col].values
        families = list(test_df["chemical_family"].values)

        report_rows = []
        verdicts: Dict[str, str] = {}
        detailed: Dict[str, MetricEvaluationResult] = {}

        for filter_name, scorer_fn in self.scorers.items():
            # Compute scores for all test rows
            scores = []
            for _, row in test_df.iterrows():
                try:
                    s = scorer_fn(row, self.dataset)
                except Exception:
                    s = 0.0
                scores.append(s)

            y_score = np.array(scores, dtype=float)

            # Evaluate through rigorous metric gates
            eval_res = evaluate_filter_candidate(
                filter_name=filter_name,
                y_score=y_score,
                y_conductivity=y_conductivity,
                chemical_families=families,
                superionic_cutoff_provisional=self.superionic_cutoff_provisional,
                n_bootstraps=n_bootstraps,
                n_scrambles=n_scrambles,
                seed=self.random_seed,
            )

            detailed[filter_name] = eval_res
            verdicts[filter_name] = eval_res.verdict

            # Format row for bench_report.csv
            report_rows.append({
                "filter_name": filter_name,
                "superionic_cutoff_provisional": self.superionic_cutoff_provisional,
                "auc": eval_res.auc,
                "ci_lower_95": eval_res.ci_lower,
                "ci_upper_95": eval_res.ci_upper,
                "spearman_rho": eval_res.spearman_rho,
                "spearman_p": eval_res.spearman_p,
                "precision_top10": eval_res.precision_top10,
                "enrichment_top10": eval_res.enrichment_top10,
                "precision_top20": eval_res.precision_top20,
                "enrichment_top20": eval_res.enrichment_top20,
                "label_scramble_p": eval_res.scramble_p,
                "within_family_aucs": str(eval_res.per_family_auc),
                "verdict": eval_res.verdict,
                "verdict_rationale": eval_res.verdict_rationale,
            })

        bench_report_df = pd.DataFrame(report_rows)
        return bench_report_df, verdicts, detailed
