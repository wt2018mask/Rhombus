# 0198 — observation budget and target-label sensitivity

The planned independent process-design source remains unavailable in the current
source-access environment. This is a separately frozen, newly executed numerical
fallback under the owner's mission. It is not new original-source acquisition.
Draft PR #371 now supplies the actual registration identity. Exactly one 0198
checkpoint records the executed numerical fallback, with compact CURRENT and
generated HANDOFF. It remains stacked on #369 and is not a canonical main merge.

## Scientific question and provenance

Does a fixed hottest-first observation order dominate exact uniform selection
for every series at the same nominal observation count? Are the reported source
winners uniquely identifiable under a hypothetical +/-0.1 log10 target-value
stress? These are distinct from 0194's single hottest-condition diagnostic,
0195's applicability coverage (no regret scoring), and 0196's **training-label**
stability analysis. Here the new calculations enumerate observation subsets and
perturb **target measurement values**, not training labels or model confidence.

The protocol was committed before running this numerical study (b24b220),
SHA256 `00d60b81d8cc05dedff337e7849733db6982ea3855dd7c3ee0a848e1dbcebf2c`.
All source outcomes were already exposed historically. This is a frozen analysis
of exposed data, not prospective preregistration or independent validation.

Inputs are the existing authenticated institutional publisher VOR receipt for
Campanella et al., ChemSusChem 2023, DOI 10.1002/cssc.202300399, receipt SHA256
`4cce0d4b9329e369d61db5116687c7297316fbda77be63fb96f1cbac6de18b75`,
original PDF SHA256
`871e6ff252cce27799e8e2bf5455667bdaf6dc639dde2875ad57a4ecce5fc58b`.
Source rights: CC BY 4.0, as recorded by that historical verifier. No PDF was
newly downloaded or reauthenticated. All six nominal series and 18 author
conditions are retained: 600/650/700 C hot pressing at 56 MPa; author-reported
25 C TOTAL conductivity in S/cm. Whether each exact-25 C value was measured
directly is unattested. Series and conditions are not independent physical
specimens; there is **one source group**.

## Actual same-budget comparison

Each policy reveals exactly k historical conductivity labels per series and
chooses the largest revealed value. Uniform control enumerates all k-subsets,
equally weighted. Orders use process temperatures only; outcomes enter scoring
after selection. The cost unit is a cached label reveal, not measured EIS time,
new experiments, MD compute or a demonstrated monetary saving.

| Labels per series | Policy | Mean log10 regret | Mean source-maximum recovery |
| ---: | --- | ---: | ---: |
| 1 | hottest first | 0.01402411 | 5/6 |
| 1 | coldest first | 0.58046713 | 0 |
| 1 | exact uniform | 0.26423122 | 1/3 |
| 2 | hottest first | 0 | 6/6 |
| 2 | coldest first | 0.19820242 | 1/6 |
| 2 | exact uniform | 0.07074218 | 2/3 |
| 3 | every policy | 0 | 6/6 |

The average favors the cheap hottest-first rule on this source. However the
frozen **every-series dominance hypothesis H1 FAILS**: Te0.1 at budget 1 is a
counterexample. A favorable aggregate must not be presented as uniform benefit.
The complete per-series/subset outcomes are retained in the result artifact.

H2 also **FAILS**: Te0.1, Te0.25, Te0.375 and Te0.5 source winners cannot be
certified under independent +/-0.1 log10 shifts of the target values. The
smallest shifts that permit a top/runner-up tie are respectively 0.04207233,
0.02264462, 0.07691908 and 0.02829064 log10; Al/Ta references require 0.23363325
and 0.23311966. This uses the exact gap/2 bound and tested boundary/reversal,
not an estimate of actual experimental noise. Real EIS uncertainty is UNKNOWN;
the stress grid was not calibrated or tuned to certify desired winners.

Frozen process Ridge and composition RF comparators remain ABSTAIN on all six
series because hot-press applicability and/or complete per-condition composition
is unqualified. No predictions or fits were invented; conditional regret is
null rather than zero. No Rhombus model-selection advantage is demonstrated.
The overall utility verdict is **INCONCLUSIVE**, with both specific hypotheses
falsified. This is not a physical material FAIL or qualified model comparison.

## Execution and reproducibility

`python -m scripts.science.observation_budget_0198 --output NEW.json`

The first retained run took 0.002021 s wall including input verification,
0.002020 s process CPU, peak process RSS 19.89 MiB; startup/imports precede the
timed calculation. Budget: <=120 s, <=256 MiB, <=2 CPU cores, $0, zero requests,
zero model fits and zero new measurements. A separate repeat reproduced every
scientific field and content-addressed evidence ID exactly; measured costs
vary. Policy-specific standalone CPU savings were not measured or inferred.

`python -m pytest -q tests/test_observation_budget_0198.py` checks exact sampling,
analytic log units, no outcome-dependent allocation, ties, boundary perturbation,
duplicates/invalid values/budget violations, immutable source/protocol binding,
reserved-data read paths and refusal to overwrite observations. The scoped
workflow reproduces numerical fields against the retained run, ignoring costs.
No new remote CI result is claimed.

Local validation: 23 focused study tests and 12 existing process-stability
regressions passed; existing Fast CI passed 2,145 tests with 8 warnings.
Compilation and continuity passed. The workflow's actual recomputation step
was executed locally and reproduced all retained scientific fields exactly.

The EvidenceRecord is operationally SUCCEEDED, scientifically INDETERMINATE and
UNQUALIFIED, with original SourceBinding and explicit limitations. Physical
existence/stability and specimen independence remain unqualified. P0-01/02/03
stay BLOCKED, production OFF, original TEST121 unread. The next scientific
priority (0199) remains an independently sourced, temperature/dwell-resolved process
comparison with actual uncertainty; do not tune this policy on the exposed
source and relabel it independent generalization.
