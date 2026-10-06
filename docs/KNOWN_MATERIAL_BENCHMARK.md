# Blind Known-Material Falsification Benchmark — B0 Scientific Contract

## Status

B0 freezes the scientific design of Rhombus's external-validity benchmark. It does **not** select benchmark materials, import structures, tune thresholds, run P0–Application, or authorize Candidate Supply v2 production.

The canonical discovery pipeline remains:

```text
E → G → P0 → P1 → P2 → P2.5 → P3 → X → N → S → Application compatibility → Final Claim Vector → OUT
```

The benchmark uses a different ingress path because it tests the scientific gates, not G:

```text
known reference structure
        ↓
opaque benchmark identity
        ↓
P0 → P1 → P2 → P2.5 → P3 → X → N → S → Application
        ↓
frozen blinded results
        ↓
unblind truth labels
        ↓
stage-wise falsification analysis
```

A benchmark control can never be promoted as a discovered candidate and can never be used as evidence that G is effective.

## Scientific question

The benchmark asks whether Rhombus:

- preserves real, supported materials rather than over-rejecting them;
- rejects known poor/failure controls rather than over-accepting them;
- separates MLIP/domain failure from material failure;
- leaves finite-time or finite-cell transport insufficiency unresolved;
- refuses unsupported-regime extrapolation;
- recognizes a known benchmark material as known at N;
- remains compatible with retained synthesis evidence at S;
- keeps Application claims inside the actual profile/evidence scope.

This is **not** a request to make famous materials pass. PASS, FAIL, INDETERMINATE, and UNKNOWN remain legitimate stage states when justified by the frozen evidence contract.

## Truth taxonomy

B0 freezes four benchmark roles:

- `POSITIVE`
- `NEGATIVE`
- `BORDERLINE`
- `FAILURE_CONTROL`

Admissible truth-evidence classes are:

- `DIRECT_EXPERIMENTAL`
- `MULTIPLE_EXPERIMENTAL`
- `REFERENCE_COMPUTATION`
- `CONSENSUS_REFERENCE`
- `CONFLICTING`
- `INSUFFICIENT`

No material is assigned to a class in B0.

Experimental ionic conductivity must not be silently substituted for P2.5 self-diffusion truth or for a P3 self-diffusion estimand.

## Blinding

Execution may see only:

```text
benchmark_id
split
structure_hash
benchmark_protocol_hash
```

The following remain sealed until blinded results are frozen:

```text
material_identity
truth_class
literature_evidence
expected_stage_outcomes
```

Opaque identifiers are not sufficient by themselves. If repository-visible files,
prior logs, or other pre-freeze artifacts already bind an execution-visible field
(such as a split identifier or structure hash) back to material identity or truth,
the cohort is contaminated for strong blind qualification. Replacing the public
identifier with a new opaque permutation does not restore blinding. Such a cohort
may remain useful for DEV or diagnostic falsification, but it must not be presented
as independent HELD_OUT qualification evidence. A replacement/versioned held-out
cohort must keep identity/truth bindings externally sealed through the science
freeze and one-shot evaluation.

## DEV / HELD_OUT

DEV may be used for debugging, failure localization, estimator development, and scientifically justified recalibration.

HELD_OUT may not select or tune:

- estimator parameters;
- block length;
- fit windows;
- scientific thresholds;
- acceptance regions;
- uncertainty requirements;
- qualification criteria.

Held-out membership is immutable after freeze. Once labels are unblinded, that cohort cannot be reused as held-out evidence. Bootstrap resamples do not create independent scientific datasets.

## Stage falsification scope

### P0
Test whether static plausibility preserves real reference materials and rejects explicit failure controls.

### P1
Test whether MLIP relaxation preserves a supported stable phase. Model-domain error must not be converted into evidence that nature is unstable.

### P2
Test finite-temperature framework survival separately from mobile-sublattice motion. Mobile-ion disorder must not automatically become framework collapse.

### P2.5
Test detection of supported mobile-ion self-diffusion and rejection of supported poor-conductor controls. Insufficient sampling must not be forced into a resolved DIFFUSIVE/NONDIFFUSIVE result.

### P3
Test scoped quantitative transport consistency. Self-diffusion, temperature dependence, activation regime, and uncertainty support remain distinct. Experimental conductivity is not interchangeable with self-diffusion truth.

### X
Test whether an independently qualified model corroborates the scoped conclusion or exposes primary-model domain error.

### N
Every benchmark material is known by construction. A known benchmark control classified as novel is a direct falsification signal, subject to the frozen reference-coverage contract.

### S
Experimentally synthesized controls must not be called unsynthesizable without adequate contrary evidence. Computed-only materials are not treated as experimentally synthesized.

### Application
Only condition- and profile-specific claims are evaluated. Unsupported regimes remain UNKNOWN or INDETERMINATE.

## Evaluation

B0 requires reporting:

- sensitivity;
- specificity;
- false-negative rate;
- false-positive rate;
- UNKNOWN rate;
- INDETERMINATE rate;
- cumulative positive retention;
- stage-attributed false rejection;
- chemistry-family stratification;
- temperature/regime stratification;
- model-disagreement rate.

There is no scalar benchmark score.

B0 intentionally leaves numerical qualification thresholds as `UNKNOWN / NEEDS EVIDENCE`. A later science-freeze must pre-register any numerical held-out acceptance rule before held-out labels/results are inspected.

The final benchmark decision vocabulary is:

```text
QUALIFIED
RECALIBRATION_REQUIRED
PIPELINE_BLOCKED
```

## Historical integrity

B0 does not reinterpret v1.0.0, does not retry the five frozen NONDIFFUSIVE candidates, does not invent P3 evidence, and does not alter any existing scientific threshold.

## Next milestones

1. **B1 — Reference/Truth Record contract**
2. **B2 — Literature-grounded material universe**
3. **B3 — Immutable DEV/HELD_OUT split**
4. **B4 — Blind benchmark ingress + provenance adapter**
5. **B5 — DEV falsification execution**
6. **B6 — Science freeze**
7. **B7 — One-shot HELD_OUT evaluation**
8. **B8 — Unblind + qualification report**

Candidate Supply v2 production remains blocked by this benchmark program until the held-out qualification decision permits it.
