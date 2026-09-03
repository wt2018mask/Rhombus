# AGENTS.md: Mandatory Invariants & Rules for AI Coding Sessions

> **CRITICAL**: Every AI agent working on the Rhombus / `rudeus` codebase must read and adhere to these HARD CONSTRAINTS. These are non-negotiable architectural invariants stemming from four prior failed architectures.

---

## 1. Zero Monetary Budget ($0) & No Background Daemons
- **No paid infrastructure**: Never introduce AWS, GCP, Azure, or paid API dependencies.
- **No daemons or external databases**: Do NOT use Redis, PostgreSQL/Neon, Upstash, Prefect, Celery, Render, or persistent background worker processes.
- **Git-as-a-Database**: The Git repository itself is the single system of record. Batch synchronization and state updates are executed via scheduled GitHub Actions (cron 1–2x daily or manual dispatch), never long-running processes.

## 2. Ephemeral Compute & Stateless Sharding
- Heavy compute (GPU MD, relaxation) runs exclusively on free, preemptible platforms (Kaggle notebooks, Google Colab) which can terminate without warning.
- **Never implement leases, distributed locks, or centralized work queues.**
- All compute workloads must be partitioned via **deterministic, hash-based sharding of stateless batches**. Any batch must be restartable from scratch by any worker without coordination or cleanup overhead.

## 3. Explicitly Deferred: No Generative or Active-Learning Loops Yet
- **DO NOT implement MatterGen integration, BoTorch, or Bayesian-optimization active learning loops.**
- These are explicitly deferred until an empirical calibration benchmark (`rudeus.bench`) exists and passes verification gates.
- **If prompted or requested to add them prematurely, PUSH BACK, quote this constraint, and explain why empirical calibration must come first.**

## 4. Tri-State Machine Architecture (Never Collapsed Scores)
- Every material candidate carries **THREE independent state fields**; never collapse evaluations into a single scalar fitness or score:
  - `existence_state`: `UNKNOWN` | `FAIL` | `PLAUSIBLE` | `SUPPORTED`
  - `dynamic_state`: `NOT_RUN` | `FAIL` | `INDETERMINATE` | `PASS`
  - `transport_state`: `NOT_RUN` | `NONDIFFUSIVE` | `INDETERMINATE` | `DIFFUSIVE`
- **Append-Only Evidence Log**:
  - Each candidate maintains an append-only log of `EvidenceEvent` objects (`level`, `method`, `conditions`, `uncertainty`, `source`, `artifact_hash`, `model_or_data_version`, `timestamp`).
  - **Never overwrite or delete prior verdicts.** When an evaluation completes, append a new event and update the relevant state enum.

## 5. Threshold Governance: All Numbers Are PROVISIONAL
- Any numerical threshold (energy-above-convex-hull cutoff, MSD slope cutoff, Lindemann criterion, BVSE percolation barrier, $\alpha_2$ non-Gaussian cutoff) **MUST be tagged `PROVISIONAL`** in code, comments, and configuration files.
- Never hardcode numeric thresholds as if they were proven physical constants. They require formal calibration against empirical data before graduation.

## 6. Empirical Anchors: OBELiX and LiIon Invariants
- **OBELiX Dataset** (`github.com/NRC-Mila/OBELiX`):
  - Must use the officially published leakage-aware grouped train/test split.
  - **NEVER re-shuffle, re-partition, or re-generate this split locally.** Doing so breaks comparability and destroys the empirical anchor.
- **LiIon Dataset** (~820 entries):
  - A supplementary, temperature-resolved experimental ionic conductivity dataset.
  - **NEVER merge LiIon rows into OBELiX datasets.**
  - **NEVER average away the temperature dimension**; temperature-resolved measurements are essential for activation barrier extraction.

## 7. MLIP Selection & Ensemble Ban
- Default primary MLIP is `mace_mp("medium-mpa-0")` (MIT license). Do NOT use MACE-MP-0.
- Cross-checking (stage `[X]`) requires a secondary MLIP trained on a fundamentally different data distribution (SevenNet or CHGNet).
- **Ensemble Ban**: Same-seed ensembles of the same base model are **strictly banned**. Correlated blind spots previously produced false-positive confidence in earlier project iterations.
