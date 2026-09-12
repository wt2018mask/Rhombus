# Rhombus: $0-Budget Solid-State Electrolyte Discovery Pipeline

**Rhombus** (package name: `rudeus`) is a zero-budget, high-throughput computational pipeline for discovering solid-state electrolyte materials with fast ionic conductivity and thermodynamic stability.

This repository is a from-scratch restart designed around absolute frugality, statistical rigor, and stateless execution.

---

## Core Philosophy & $0-Budget Constraints

1. **Zero Monetary Budget & No Always-On Servers**:
   - No paid cloud infrastructure (no AWS/GCP instances, no Redis, no PostgreSQL/Neon, no Upstash, no Prefect, no Render).
   - The **Git repository itself is the single source of truth** ("Git-as-a-Database").
   - State updates occur via scheduled **GitHub Actions** (1–2x daily cron or manual dispatch), never long-running daemons.

2. **Preemptible, Stateless Compute**:
   - Heavy GPU calculations (molecular dynamics, relaxation) run on free, ephemeral environments (Kaggle notebooks, Google Colab) that can terminate at any moment.
   - Work is partitioned using **deterministic, hash-based sharding of stateless batches**.
   - No leases, locks, distributed coordinators, or message queues.

3. **No Collapsed Scores: Three Independent States**:
   Every candidate material carries three distinct, uncollapsed state fields:
   - `existence_state`: `UNKNOWN` | `FAIL` | `PLAUSIBLE` | `SUPPORTED`
   - `dynamic_state`: `NOT_RUN` | `FAIL` | `INDETERMINATE` | `PASS`
   - `transport_state`: `NOT_RUN` | `NONDIFFUSIVE` | `INDETERMINATE` | `DIFFUSIVE`
   
   Every evaluation writes an immutable record to an **append-only evidence-event log** (`level`, `method`, `conditions`, `uncertainty`, `source`, `artifact_hash`, `model_or_data_version`, `timestamp`). Prior verdicts are never overwritten.

4. **Empirical Calibration Before Generative Complexity**:
   - Generative ML loops (e.g. MatterGen) and Bayesian-optimization active learning loops (e.g. BoTorch) are **explicitly deferred** until the empirical calibration benchmark passes its verification gates.
   - All numeric cutoffs (energy-above-hull, Lindemann criterion, MSD slope, non-Gaussian parameter $\alpha_2$) are tagged `PROVISIONAL` until empirically calibrated.

5. **Empirical Datasets & MLIP Governance**:
   - **OBELiX**: Official published leakage-aware grouped train/test split (github.com/NRC-Mila/OBELiX). Never re-shuffled or re-generated locally.
   - **LiIon**: Separate temperature-resolved ionic conductivity dataset (~820 entries). Never merged into OBELiX rows; temperatures must never be averaged away.
   - **MLIP**: Default primary model is `mace_mp("medium-mpa-0")` (MIT license). Cross-checks utilize a model trained on distinct data (SevenNet or CHGNet). Same-seed ensembles of the same model are banned.

---

## Overall Pipeline Architecture

Candidates progress through sequential screening stages:

```
[E] Empirical Anchors (OBELiX / LiIon)
 ↓
[G] Generation (G1 Perturbation & G2 Substitution)
 ↓
[P0] Static Physical & Chemical Filters
 ↓
[F2 REMOVED 2026-09] BVSE percolation proxy — evaluated, failed, not in pipeline (see below)
 ↓
[P1] Athermal MLIP Relaxation & Convex Hull Stability
 ↓
[P2] Finite-Temperature Dynamical Stability (MD)
 ↓
[P2.5] Diffusive Regime Validator (F3 Mobile-ion MSD + α₂)
 ↓
[P3] Temperature-Dependent Arrhenius Fitting (Conductivity & Barrier)
 ↓
[X] Cross-Check (Secondary MLIP with distinct training distribution)
 ↓
[N] Novelty Assessment (Structure & composition dissimilarity)
 ↓
[S] Synthesizability Screening (Precursor cost & phase competition)
 ↓
[OUT] Verified Discovery Candidates
```

### Stage Descriptions

- **`[E]` Empirical Stage**: Ingests OBELiX benchmark (fixed split) and LiIon temperature-resolved conductivities to serve as ground-truth anchor and calibration baseline.
- **`[G]` Generation Stage**:
  - `G1`: Parent retrieval from known fast-ion conductors + local structural perturbation (vacancies, interstitials, strains).
  - `G2`: Isovalent/aliovalent chemical substitution guided by SMACT and ionic radii.
- **`[P0]` Static Filters**: Fast chemical validity checks (charge neutrality, electronegativity balance, atomic clash detection).
- **`[F2]` BVSE Screening — REMOVED (2026-09), not probationary**: The Bond Valence Site Energy percolation proxy was evaluated on the official OBELiX test split (AUC 0.44, significant negative Spearman correlation) and failed the falsification gate (45% of confirmed insulators ranked in the top-20%). It must not be used in the discovery pipeline. `rudeus/filters/bvse.py` is retained for history only; the bench harness keeps scoring it as a negative reference. Any BVSE-style reintroduction requires new bench evidence, never reuse of the removed implementation.
- **`[P1]` Athermal MLIP Relaxation**: MACE-MP relaxation to zero-force geometry, volume optimization, and energy-above-convex-hull calculation.
- **`[P2]` Finite-T Dynamical Stability**: Short molecular dynamics trajectories testing for amorphization or crystal breakdown (evaluated via Lindemann criterion).
- **`[P2.5]` Diffusive Regime Validation (F3)**: Rigorous check on mobile-ion trajectories ensuring genuine diffusion: mobile-ion-only mean squared displacement (MSD) slope and non-Gaussian parameter ($\alpha_2$) to rule out rattling in cage traps.
- **`[P3]` Arrhenius Fitting**: Multi-temperature MD runs (600 K – 1000 K) to extract activation energy $E_a$ and extrapolated 300 K ionic conductivity $\sigma_{300\text{K}}$.
- **`[X]` Cross-Check**: Confirmation using a secondary MLIP trained on a different dataset distribution (SevenNet or CHGNet) to protect against model-specific blind spots.
- **`[N]` Novelty**: Crystallographic and compositional fingerprint matching against existing ICSD/MP databases.
- **`[S]` Synthesizability**: Synthesis plausibility, precursor availability, and competing phase equilibria.
- **`[OUT]` Final Output**: Fully supported candidates with complete immutable evidence logs.

---

## Repository Structure

```
Rhombus/
├── .github/
│   └── workflows/
│       └── cron.yml         # Twice-daily GitHub Actions cron sync
├── rudeus/
│   ├── __init__.py          # Package initialization
│   ├── schema.py            # Three-state machine dataclasses & enums
│   ├── empirical/           # [E] OBELiX & LiIon loaders
│   ├── generation/          # [G] G1 perturbation & G2 substitution
│   ├── filters/             # [P0], [F2], [F3] filtering logic
│   ├── mlip/                # [P1], [P2], [P3] MLIP pipelines
│   └── bench/               # [BENCH] Calibration harness & enrichment metrics
├── tests/                   # Mirroring unit test suite
├── config.yaml              # Pipeline configuration & PROVISIONAL thresholds
├── pyproject.toml           # Project packaging & tool settings
├── requirements.txt         # Core dependencies
├── AGENTS.md                # Hard constraints & rules for coding agents
└── README.md                # Project documentation
```

---

## Getting Started

```bash
# Clone the repository
git clone <repo-url>
cd Rhombus

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # Or on Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run placeholder test suite
pytest
```
