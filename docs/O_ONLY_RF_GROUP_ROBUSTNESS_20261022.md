# Historical O_ONLY RF model robustness audit (2026-10-22)

This is an **executed descriptive sensitivity calculation over existing repository
receipts**, not a new experiment or benchmark test.

- Frozen checkpoint 0188: 5 original author DOI groups, 22 reported conditions,
  source-group equal macro MAE log10(S/cm) O_ONLY_RF 0.41396469 versus POOLED_RF
  0.48968537, pooled-minus-specialist +0.07572068; specialist wins 4/5.
- Exact 5-group two-sided sign-flip enumeration gives a descriptive 8/32=.25
  extreme-tail frequency. Independent sign symmetry and physical/lab
  independence are **not attested**, thus **not a formal p-value**.
- Exhaustive 5^5 empirical DOI-group resamples give a sensitivity 2.5/97.5%
  range -0.00263295 to +0.17573590. This **is not a confidence interval**.
  Some group resamples have no specialist gain.
- Frozen checkpoint 0185: separate *unqualified* 36-group secondary cohort
  has specialist group MAE 0.72592093 versus pooled 0.70002851: specialist
  worse by 0.02589242. Row metrics yield a tiny opposite directional effect.
  This cohort has unauthenticated observable/temperature comparability and
  must NEVER be merged into 0188's exact-25C source cohort.

Scientific result: the domain specialist MAY improve error on selected source
families, but cross-source robustness, independent predictive superiority,
and top-1 manufacturing-choice advantage are **NOT established**.
SOLO_PUBLIC_BENCHMARK remains INCONCLUSIVE (for general benefit);
SCIENTIFIC_EXTERNAL_PHYSICAL remains NO-GO. No production activation,
P0 remains 0/3 BLOCKED, TEST 121 UNREAD, STRICT additions 0.

Reproduce without fetching new papers or fitting models:

`python -m pytest -q tests/test_literature_model_evidence_robustness.py`

`rhombus.literature.model_evidence_robustness.analyze_files(a, b)`
where a and b are the pre-existing 0188 and 0185 development receipts.
It emits SHA-256 identities for the raw local evidence receipts at execution.
The derived JSON below is sourced from the pinned historical GitHub main
commit; it is not an original-source byte SHA-256 certification.

Next useful *new science*: a frozen source-heldout manufacturing-choice
evaluation with process variables and actual observed top-1/regret under
predeclared comparisons, rather than further retrospective score tuning.
