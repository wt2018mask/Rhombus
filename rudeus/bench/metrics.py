"""Statistical evaluation metrics for the empirical benchmark and filter enrichment harness.

Computes:
1. ROC-AUC with 95% bootstrap confidence interval.
2. Spearman rank correlation with log10(conductivity).
3. Precision and enrichment ratios at top 10% and top 20%.
4. Label-scramble permutation test (N=1000) for null hypothesis testing.
5. Within-chemical-family holdout evaluation (families with n >= 15).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Union
import numpy as np
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score


@dataclass(frozen=True)
class MetricEvaluationResult:
    """Enrichment and benchmark metrics for a single filter/scoring function.

    Attributes:
        filter_name: Identifier for the filter evaluated.
        auc: Empirical ROC-AUC against superionic threshold.
        ci_lower: Lower bound of 95% bootstrap CI.
        ci_upper: Upper bound of 95% bootstrap CI.
        spearman_rho: Spearman rank correlation with log10(conductivity).
        spearman_p: Two-sided p-value for Spearman correlation.
        precision_top10: Precision at top 10% ranked candidates.
        enrichment_top10: Enrichment factor at top 10% relative to random baseline.
        precision_top20: Precision at top 20% ranked candidates.
        enrichment_top20: Enrichment factor at top 20% relative to random baseline.
        scramble_p: P-value from N=1000 label-scramble test.
        per_family_auc: Dictionary mapping family name to within-family ROC-AUC.
        verdict: KEEP | REMOVE | INSUFFICIENT_EVIDENCE.
        verdict_rationale: Detailed explanation of pass/fail gates.
    """
    filter_name: str
    auc: float
    ci_lower: float
    ci_upper: float
    spearman_rho: float
    spearman_p: float
    precision_top10: float
    enrichment_top10: float
    precision_top20: float
    enrichment_top20: float
    scramble_p: float
    per_family_auc: Dict[str, Optional[float]]
    verdict: str
    verdict_rationale: str


def compute_roc_auc(y_true: np.ndarray, y_score: np.ndarray) -> float:
    """Compute standard ROC-AUC handling edge cases where only one class exists."""
    unique = np.unique(y_true)
    if len(unique) < 2:
        return 0.5
    return float(roc_auc_score(y_true, y_score))


def compute_bootstrap_ci(
    y_true: np.ndarray,
    y_score: np.ndarray,
    n_bootstraps: int = 1000,
    ci: float = 0.95,
    seed: int = 42,
) -> Tuple[float, float]:
    """Compute bootstrap confidence interval for ROC-AUC."""
    rng = np.random.default_rng(seed)
    n = len(y_true)
    boot_aucs = []

    for _ in range(n_bootstraps):
        idx = rng.choice(n, size=n, replace=True)
        sample_y = y_true[idx]
        sample_score = y_score[idx]
        if len(np.unique(sample_y)) == 2:
            boot_aucs.append(roc_auc_score(sample_y, sample_score))

    if len(boot_aucs) < 50:
        return 0.5, 0.5

    alpha = (1.0 - ci) / 2.0
    lower = float(np.percentile(boot_aucs, 100 * alpha))
    upper = float(np.percentile(boot_aucs, 100 * (1.0 - alpha)))
    return lower, upper


def compute_enrichment_at_k(
    y_true: np.ndarray,
    y_score: np.ndarray,
    fraction: float = 0.10,
) -> Tuple[float, float]:
    """Compute precision and enrichment ratio at top fraction (e.g. 0.10 or 0.20).

    Returns:
        (precision_at_k, enrichment_at_k)
    """
    n = len(y_true)
    k = max(1, int(round(n * fraction)))
    baseline_rate = float(np.mean(y_true))

    # Sort in descending order
    rank_order = np.argsort(-y_score)
    top_k_labels = y_true[rank_order[:k]]

    precision = float(np.mean(top_k_labels))
    enrichment = float(precision / baseline_rate) if baseline_rate > 0 else 1.0

    return precision, enrichment


def run_label_scramble_test(
    y_true: np.ndarray,
    y_score: np.ndarray,
    observed_auc: float,
    n_scrambles: int = 1000,
    seed: int = 42,
) -> float:
    """Run label-scramble permutation test (N=1000) and return empirical p-value.

    Null hypothesis: No genuine relationship between score and labels.
    """
    rng = np.random.default_rng(seed)
    y_copy = np.array(y_true, copy=True)
    count_exceed = 0

    for _ in range(n_scrambles):
        scrambled_y = rng.permutation(y_copy)
        scrambled_auc = compute_roc_auc(scrambled_y, y_score)
        if scrambled_auc >= observed_auc:
            count_exceed += 1

    p_value = (1.0 + count_exceed) / (n_scrambles + 1.0)
    return float(p_value)


def compute_within_family_aucs(
    y_true: np.ndarray,
    y_score: np.ndarray,
    families: Sequence[str],
    min_family_n: int = 15,
) -> Dict[str, Optional[float]]:
    """Compute within-chemical-family ROC-AUC for all families with n >= min_family_n.

    Never pools families into a single metric.
    """
    unique_families = sorted(list(set(families)))
    results: Dict[str, Optional[float]] = {}

    for fam in unique_families:
        mask = np.array([f == fam for f in families])
        fam_n = int(mask.sum())
        if fam_n >= min_family_n:
            fam_y = y_true[mask]
            fam_score = y_score[mask]
            if len(np.unique(fam_y)) == 2:
                results[fam] = float(roc_auc_score(fam_y, fam_score))
            else:
                results[fam] = None  # Only one class present (cannot compute AUC)

    return results


def evaluate_filter_candidate(
    filter_name: str,
    y_score: np.ndarray,
    y_conductivity: np.ndarray,
    chemical_families: Sequence[str],
    superionic_cutoff_provisional: float = 1e-3,  # PROVISIONAL: 1 mS/cm superionic cutoff
    n_bootstraps: int = 1000,
    n_scrambles: int = 1000,
    seed: int = 42,
) -> MetricEvaluationResult:
    """Execute complete enrichment and calibration gate evaluation for a filter scoring function.

    Gate Criteria for KEEP:
    1. Official-split AUC gate: AUC >= 0.65 AND 95% CI lower bound > 0.55
    2. Label-scramble p-value < 0.05
    3. Within-family AUC gate: AUC >= 0.65 for at least one major family (n >= 15).

    Otherwise emits INSUFFICIENT_EVIDENCE (or REMOVE if uninformative).
    """
    y_true = (y_conductivity >= superionic_cutoff_provisional).astype(int)
    log_cond = np.log10(np.maximum(y_conductivity, 1e-15))

    # 1. ROC-AUC and bootstrap CI
    auc = compute_roc_auc(y_true, y_score)
    ci_lower, ci_upper = compute_bootstrap_ci(y_true, y_score, n_bootstraps=n_bootstraps, seed=seed)

    # 2. Spearman correlation
    rho, p_val = spearmanr(y_score, log_cond)
    spearman_rho = float(rho) if not np.isnan(rho) else 0.0
    spearman_p = float(p_val) if not np.isnan(p_val) else 1.0

    # 3. Precision & enrichment at top 10% and top 20%
    p10, e10 = compute_enrichment_at_k(y_true, y_score, fraction=0.10)
    p20, e20 = compute_enrichment_at_k(y_true, y_score, fraction=0.20)

    # 4. Label-scramble test
    scramble_p = run_label_scramble_test(y_true, y_score, observed_auc=auc, n_scrambles=n_scrambles, seed=seed)

    # 5. Within-chemical-family holdout
    family_aucs = compute_within_family_aucs(y_true, y_score, chemical_families, min_family_n=15)

    # Verification of Gates:
    gate_auc = (auc >= 0.65) and (ci_lower > 0.55)
    gate_scramble = (scramble_p < 0.05)

    # Within family gate: at least one family with n>=15 must have valid AUC >= 0.65
    valid_family_aucs = [v for v in family_aucs.values() if v is not None]
    gate_family = any(v >= 0.65 for v in valid_family_aucs) if valid_family_aucs else False

    reasons = []
    if not gate_auc:
        reasons.append(f"Failed official-split AUC gate (AUC={auc:.3f}, 95% CI=[{ci_lower:.3f}, {ci_upper:.3f}])")
    if not gate_scramble:
        reasons.append(f"Failed label-scramble gate (p={scramble_p:.4f} >= 0.05)")
    if not gate_family:
        reasons.append(f"Failed within-family gate (no family >=0.65: {family_aucs})")

    if gate_auc and gate_scramble and gate_family:
        verdict = "KEEP"
        rationale = "Passed all gates: official AUC >=0.65 with CI >0.55, label-scramble p <0.05, and within-family holdout."
    elif auc < 0.50:
        verdict = "REMOVE"
        rationale = f"Negative/inverse correlation (AUC={auc:.3f} < 0.50). " + "; ".join(reasons)
    else:
        verdict = "INSUFFICIENT_EVIDENCE"
        rationale = "Did not pass all required gates. " + "; ".join(reasons)

    return MetricEvaluationResult(
        filter_name=filter_name,
        auc=auc,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        spearman_rho=spearman_rho,
        spearman_p=spearman_p,
        precision_top10=p10,
        enrichment_top10=e10,
        precision_top20=p20,
        enrichment_top20=e20,
        scramble_p=scramble_p,
        per_family_auc=family_aucs,
        verdict=verdict,
        verdict_rationale=rationale,
    )
