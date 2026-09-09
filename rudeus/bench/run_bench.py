"""Single entry point CLI to run the empirical benchmark and filter enrichment harness.

Usage:
    python -m rudeus.bench.run_bench [config.yaml]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import yaml

from rudeus.empirical.obelix import OBELiXDataset
from rudeus.bench.harness import (
    BenchmarkHarness,
    composition_baseline_scorer,
    f2_bvse_probation_scorer,
)


def run_benchmark(config_path: str = "config.yaml") -> int:
    """Run benchmark harness using configuration specified in config.yaml."""
    cfg_file = Path(config_path)
    if not cfg_file.exists():
        print(f"Error: Configuration file not found at {config_path}", file=sys.stderr)
        return 1

    with open(cfg_file, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    obelix_repo = cfg.get("datasets", {}).get("obelix_repo", "data/obelix")
    random_seed = int(cfg.get("random_seed", 42))

    print("================================================================================")
    print("RHOMBUS EMPIRICAL BENCHMARK & FILTER ENRICHMENT HARNESS (rudeus.bench)")
    print("================================================================================")
    print(f"Loading OBELiX dataset from: {obelix_repo}")
    print(f"Random seed: {random_seed}")

    try:
        dataset = OBELiXDataset(obelix_repo)
    except Exception as e:
        print(f"Error loading OBELiX dataset: {e}", file=sys.stderr)
        return 1

    report = dataset.integrity_report
    print("\n--- DATASET INTEGRITY AUDIT REPORT ---")
    print(f"Total rows (finite conductivity):  {report.total_row_count}")
    print(f"Official train split rows:         {report.train_row_count}")
    print(f"Official test split rows:          {report.test_row_count}")
    print(f"CIF-linked count:                  {report.cif_linked_count}")
    print(f"Dropped non-finite rows:           {report.dropped_non_finite_count}")
    print(f"Leaked normalized formula keys:    {report.leaked_formula_keys_count}")
    print(f"Superionic (>=1e-3 S/cm) in test:  {report.superionic_test_count} ({report.superionic_test_fraction:.1%})")

    if report.leaked_formula_keys_count > 0:
        print(f"WARNING: Detected leaked formula keys: {report.leaked_formula_samples}")
    else:
        print("Integrity Check: Zero composition key leakage detected between train and test splits.")

    harness = BenchmarkHarness(dataset=dataset, random_seed=random_seed)

    # Register candidate pre-screening filters
    harness.register_scorer("composition_baseline", composition_baseline_scorer)
    harness.register_scorer("f2_bvse_probation", f2_bvse_probation_scorer)

    print("\nExecuting evaluations (N=1000 bootstrap CI, N=1000 label-scramble permutations)...")
    bench_df, verdict_dict, detailed_results = harness.run_evaluations(
        n_bootstraps=1000,
        n_scrambles=1000,
    )

    # Save output artifacts
    bench_report_csv = Path("bench_report.csv")
    filter_verdict_json = Path("filter_verdict.json")

    bench_df.to_csv(bench_report_csv, index=False)
    with open(filter_verdict_json, "w", encoding="utf-8") as f:
        json.dump(verdict_dict, f, indent=2)

    print("\n--- BENCHMARK RESULTS SUMMARY ---")
    for filter_name, res in detailed_results.items():
        print(f"\nFilter: [{filter_name}]")
        print(f"  ROC-AUC (95% CI):     {res.auc:.4f} [{res.ci_lower:.4f}, {res.ci_upper:.4f}]")
        print(f"  Spearman rho (p-val): {res.spearman_rho:.4f} (p={res.spearman_p:.4e})")
        print(f"  Precision @ Top 10%:  {res.precision_top10:.4f} (Enrichment: {res.enrichment_top10:.2f}x)")
        print(f"  Precision @ Top 20%:  {res.precision_top20:.4f} (Enrichment: {res.enrichment_top20:.2f}x)")
        print(f"  Label-scramble p-val: {res.scramble_p:.4f} (N=1000)")
        print(f"  Within-family AUCs:   {res.per_family_auc}")
        print(f"  VERDICT:              {res.verdict}")
        print(f"  Rationale:            {res.verdict_rationale}")

    print("\nArtifacts saved:")
    print(f"  - {bench_report_csv.resolve()}")
    print(f"  - {filter_verdict_json.resolve()}")

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Rhombus empirical benchmark harness.")
    parser.add_argument("config", nargs="?", default="config.yaml", help="Path to config.yaml")
    args = parser.parse_args()
    sys.exit(run_benchmark(args.config))


if __name__ == "__main__":
    main()
