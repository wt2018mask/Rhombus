# 0196 — Stable process recommendations can remain wrong

A separately preregistered, actually executed CPU experiment falsifies a proposed
robustness proxy on retained original-source evidence. It does not recover the
blocked 2021 SI, add new experimental measurements or establish scientific GO.

## Question and pre-answer freeze

Before running any new sensitivity calculation, freeze protocol SHA-256
`256d176c2e9f294fa99a144c89cc6e68be149be89f2ee5fcd14cc5220e72dcd2` in
`data/development/process_choice_stability_0196_protocol_v1.json`.

H1: Are both existing 0191 directional process recommendations unchanged after
every single training-condition deletion? Any change/tie falsifies it.

H2: Does a fixed filter combining deletion invariance and an adversarial label
stress radius greater than 0.1 log10 units retain at least one recommendation
with zero observed regret? Any retained wrong choice falsifies it. Retaining no
choice is INCONCLUSIVE, never perfect accuracy. The 0.1 threshold was frozen
before calculations; it is a **provisional stress test, not measured EIS error**.
No threshold was changed after results.

Inputs are the historically authenticated 2018 DOI `10.1039/c8ra01329b` original
process Table 1 and 25°C TOTAL conductivity Table 3, and 2020 DOI
`10.3390/ma13030560` original Table 2. Five source conditions per study, ten total,
two nominal formulas, two exposed papers. They are not ten independent pellets.
The immutable process audit SHA-256 is
`8af20fd82153bf67db318d9e091610f7979d76df6689ae0de4a33ba1331d34c2`;
original JATS SHA-256 values are respectively
`6dee69ef498243cc04c03a4d049175123cfac1b8dfa99257781da76d34979eea` and
`51b35a6b942557d1f6cb7ab77d63ca36dbd4d3fbd44a6e44d0ad6f3557392b63`.
Exact author row names, process conditions, values, units and source metadata
remain in the retained result's `source_rows`.

## Actual computation and comparison

Reuse the exact 0191 features `(T_C-1150)/100` and `log10(hold_min/60)`,
Ridge(alpha=1), intercept enabled. Train on all five conditions of one paper,
predict the other; repeat after each of five independent training-condition
omissions. Then reverse papers: **12 unique executed Ridge fits**.

Each paper has one nominal formula. The existing RF baseline and train-residual
constant are constant within that paper and cancel from all within-paper ranks
and margins. No RF was retrained or its absolute accuracy reassessed. No OBELiX
TRAIN or official TEST121 was opened. A test removes heldout conductivity fields
entirely and confirms identical proposals; labels enter only retrospective
regret evaluation.

For the full-model winner w and rival j, the exact training-label-to-prediction
linear map H gives the smallest L-infinity log-label shift that creates a tie:
`epsilon_j = (prediction_w - prediction_j) / sum(abs(H_w - H_j))`.
Take the minimum across rivals. The computation checks its influence matrix
against executed sklearn predictions, constructs the boundary perturbation and
verifies tie, below-bound retention and above-bound reversal. These are
adversarial deterministic diagnostics, not confidence intervals or a probability
of correctness. Leave-one-condition deletion is not paper bootstrap uncertainty.

| Training paper → evaluated paper | Full choice | All five deletion choices | Minimum label-stress radius | Actual best | Observed regret |
| --- | --- | --- | ---: | --- | ---: |
| 2018 → 2020 | SL2 | SL2 | 0.161080 log10 | SL2 | 0 |
| 2020 → 2018 | LLZALO-5 | LLZALO-5 | 0.410554 log10 | LLZALO-4 | 0.201645 log10 |

Both exceed the frozen 0.1 stress threshold and both pass all deletion checks.
**H1 is supported only on these two exposed studies; H2 is falsified.** A stable,
label-stress-resistant recommendation can still select the wrong preparation.
The existing wrong nonmonotonic choice was already public; its persistence under
all five training omissions and the exact robustness radii are newly computed
results, not independent rediscovery of the old prediction.

Full Ridge, the fixed robustness filter, highest-temperature/shortest-hold, and
shortest-hold/lowest-temperature all select exactly the same two conditions:
1/2 correct at full coverage, mean regret **0.100823 log10**. No decision utility
advantage was demonstrated. Both composition-only RF comparators necessarily tie
within each source and abstain; their conditional regret is UNKNOWN, not zero.

The experiment gives every fitted policy the same maximum six-fit menu per
source, then shares the observed computations. Cheap baselines need no fit.
Record shared measured cost once; do not invent equal standalone runtimes or
compute savings. Results use source-reported conductivity to score a retrospective
choice, not causal processing effects, source-independent model accuracy or
performance confidence intervals.

## Execution, evidence and limits

The retained final local calculation took **0.025502 seconds** of diagnostic wall
time after imports (0.025565 process CPU seconds), including **0.017066 seconds**
for 12 fit/predict calls. Python startup/import time was not included; individual
standalone policy runtimes are unmeasured. Two CPU threads permitted; $0; zero
network requests and zero new original bytes. Test/verification repetitions are
separate from this retained scientific run.

`data/development/process_choice_stability_0196_result_v1.json` retains every
fit, coefficient, prediction, source condition, matrix rank/singular values,
certificate and actual timing, plus two content-addressed EvidenceRecords.
Their operational status is SUCCEEDED; scientific verdict INDETERMINATE and
applicability UNQUALIFIED. Existence/dynamic states remain UNKNOWN; transport is
source-reported but not physically qualified. The computed falsification is not
a physical material FAIL. Diagnostic metrics explicitly identify the stress as
not measured error; the existing MCP evidence tool can expose them without a
new tool or automatic dispatch.

Source labels were already exposed; paper N=2, specimen independence and EIS
uncertainty unresolved, process variables confounded, no independent holdout or
blind evaluation. New STRICT DOI groups/manufacturing comparisons: **0**.
New original measurements: **0**. New exploratory *sensitivity results*: **2**,
reusing existing measurements. P0-01/02/03 BLOCKED; GO false; production OFF.

## Original SI and integration remain separate

Runtime source hosts are still absent from effective policy. Saved draft
revision 9 is not applied here; global publication is unverified. No denied
endpoint was retried. Original 2021 Table S1 geometry remains UNKNOWN/BLOCKED;
its prior protocol and four failed acquisition receipts are unchanged.

The user's current mission explicitly permits an independently frozen local
scientific fallback. Checkpoint 0196 records this new falsification experiment;
it does **not** reclassify the prior blocked publisher experiment as successful.
PR #367 remains based on #365, adds exactly one 0196 event, and preserves every
older checkpoint and the immutable 0118 baseline. Compact CURRENT removes only
redundant blocker entries already restored by that unchanged baseline; all old
effective refs/state codes/blockers remain accessible.

PR #369's legitimate path is a normal merge from validated #367, retarget its
base to #367, then add one separate 0197 engineering event only after the existing
MCP client actually retrieves the new computed evidence conservatively. This is
worker-stack integration, never a main merge. No duplicated 0195/0196 event or
continuity bypass is needed.

Highest-value next scientific experiment: an authenticated, independent source
with temperature and dwell varied without their present confounding, original
25°C TOTAL measurements and defined uncertainty. Freeze a study-out test against
the same cheap rules before evaluating it. Do not tune the stress threshold on
these exposed outcomes. Restore/publish source network policy to pursue the
separate original Table S1 geometry question when accessible.
