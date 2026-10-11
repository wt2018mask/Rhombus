# Checkpoint 0142 — prospective independent material study feasibility (P0-01 + P0-03)

**Status: SCIENTIFIC NO-GO.** This is a *prospective sample-recruitment planning calculator*, not a result, a power study, empirical estimate, population-representative validation or independent source attestation. It does not possess the private sample roster.

## Critical study-design boundary

The existing `rhombus/qualification/sealed_evaluation.py` already uses conservative material-level aggregation and an IID-only Wilson interval on `CORRECT_FRACTION_ALL_MATERIALS`. A repeated trajectory is **never an extra independent material**. Source dataset rows and public OBELiX held-out materials are **not a newly independent sealed cohort**. Failure, UNKNOWN, abstention, INDETERMINATE, NONDIFFUSIVE and all negative predictions count in the denominators of the *actual pre-registered prospective material outcome*, rather than silently disappearing.

Checkpoint 0142 fills a different, unmet need: prospective minimum **new independent materials** under an explicit confidence-level/half-width design and additional *recruitment oversampling* allowance for a bounded, **prospective** pre-enrollment shortfall. It does **not** allow excluding failed model predictions after enrollment. The withdrawal/selection/loss mechanism must be documented by the independent custodian. A planned loss rate is not evidence that loss will actually be below the limit.

For IID Bernoulli material outcomes, worst-case Wilson interval half-width occurs at p=0.5:

`w_max = z / (2 * sqrt(n + z^2))`, with `z = NormalDist().inv_cdf((1+CL)/2)`.

The minimum independent-material count is `ceil(z^2 / (4w^2) - z^2)`, verified by directly evaluating boundary cases rather than trusting rounded approximations. Recruit at least `ceil(n / (1-loss_fraction))` *prospectively*, prior to random selection under the same pre-registered sampling frame. This is a **precision** justification only: it is NOT statistical power for per-class sensitivity, rare events, temperature-specific comparisons, causal effects or physics model bias.

**Important**: quotas by known POSITIVE/NEGATIVE/BORDERLINE category are not IID draws from a representative material population. Such a plan cannot claim the IID Wilson interval without a separately specified stratified weighted or clustered analysis. The script returns **BLOCKED_NON_IID** for quota/dependent designs, rather than silently multiplying record counts. For prospective IID plans the output remains **PLAN_ONLY_NOT_EVIDENCE** until a third-party steward attests materials and blinded truths.

## External actions still required

1. Independent steward (not Rhombus developers) selects new previously private experimental materials, documents sampling frame and independence, owns privately sealed material identifiers and truth; existing public B3/OBELiX TEST cannot be reused for strong blind qualification.
2. Steward documents temperatures, measured conductivity quantity, bulk/total distinction, phase, sources, measurement uncertainty and experimental replicate hierarchy, including negatives, censoring, failed tests and abstentions.
3. Freeze scoring version, full prediction commitment and source-independent auditor log **before** truth disclosure.
4. Authenticate the MACE-MPA-0 actual checkpoint-selected MPTrj/sAlex training frames and overlap audit. Without [P0-02](https://github.com/wt2018mask/Rhombus/issues/305) provenance the cohort remains unqualified for unseen/generalization claims.

## Example interpretation (assumptions only)

With confidence level 95%, target Wilson worst-case half-width ±0.10, IID independent sampled materials and hypothetical maximum 20% *prospective pre-enrollment* nonacquisition, the calculator returns minimum **93 independently evaluated materials** and a prospective recruitment target of **117**. An actual external cohort, power and all model outcome estimates **do not exist by virtue of computing these numbers**. If precision ±0.05 is required, the minimum grows to **381** independent materials before any recruitment allowance.

## Science stop lines

- `P0_01_status = BLOCKED`: no real steward, new sealed IDs or cryptographic release commitment provided by this module.
- `P0_02_status = BLOCKED`: MACE exact training frame membership still unverified.
- `P0_03_status = BLOCKED`: no independent physical material sample cohort has been attested.
- `scientific_release_authorized = false`. Never publish a score from this planning receipt.
