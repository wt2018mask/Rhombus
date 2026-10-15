# 0182 — Actual SOLO OBELiX public TRAIN chemistry-family-out uncertainty selectivity

## Motivation / how this differs from 0181

The prior 0181 exact five original source-group-fold risk ranking reported a reduction in group-average RF MAE from 1.90046 to 1.72117 at 80% group coverage, and to 1.64083 at 60%. Those are **retrospective public TRAIN source group results**, not evidence that RF-tree disagreement predicts real error on an unseen whole anion chemistry class.

## Fixed experiment

Original NRC-Mila public OBELiX pinned upstream revision `4eaac889809dd489e3bae468c45d5c0e02b9147a`. Original publisher 478 TRAIN rows, 121 official TEST reserved and unread, 449 uncensored numeric TRAIN observations, 29 censored excluded, 102 transitive DOI/formula connected groups. Exactly the five existing 0148/0158 **anion-element-presence proxy** bins `O_AND_S`, `O_ONLY`, `S_ONLY`, `HALIDE_NO_O_S`, `OTHER_NO_O_S_HALIDE`. These are NOT physical crystal phases or independently confirmed individual material specimens.

For each class, hold out all its source rows and exclude other-family training rows that share any DOI/formula connected source group. If fewer than 10 heldout source rows, three connected source groups, or 20 unrelated training rows remain, record unscored. Otherwise fit the unchanged 0147 118-fraction-feature 50-tree RF on other families ONLY. Predict the heldout class, derive ensemble-tree disagreement with **no heldout labels used for ranking**, rank distinct original heldout DOI/formula groups by mean per-row disagreement, select predeclared 60%/80% source-group budgets and compare actual group MAE against full RF, TRAIN-only cheap mean on identical groups, and **128** SHA256-blind same-budget random connected-group selections. An eligible family must improve over both full and blind random at both budgets for a universal PASS. Unevaluated families always display their counts. This is a no-paid-compute, single-researcher original public-data experiment.

## Actual run, all class scores, negative results

[Primary-source GitHub Actions #38723195857](https://github.com/wt2018mask/Rhombus/actions/runs/38723195857) **SUCCESS**; 41 source/anti-leakage tests. [Original numerical aggregate receipt #11967068020](https://github.com/wt2018mask/Rhombus/actions/runs/38723195857/artifacts/11967068020), ZIP SHA256 `63897449089a7e75ba995339d9f2878f07d77ad156269c601ea100f3ef996883`.

| Source anion-presence family | Actual source rows | Heldout connected groups | RF full macro MAE | Select 60% groups MAE | Select 80% groups MAE | Conclusion |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| O_ONLY | 307 | 64 | 2.37930278 | **2.66037906** | **2.53356077** | BOTH budgets worse |
| S_ONLY | 117 | 21 | 2.35933897 | 1.91994298 | 2.30698472 | Both improve vs full and blind mean |
| HALIDE_NO_O_S | 14 | 11 | 1.59042696 | 1.45482414 | **1.73860523** | 60% improves, 80% worse |
| OTHER_NO_O_S_HALIDE | 11 | 6 | 2.01306731 | 1.85468499 | 1.81930298 | Both improve vs full and blind mean |
| O_AND_S | 0 | 0 | Not scored | Not scored | Not scored | No eligible source labels |

The O_ONLY source class holds **307/449 original numeric rows** and shows a real failure: sorting groups by presumed RF confidence increases rather than reduces error, for both budgets, despite ranking being based solely on model predictions. The halide class also deteriorates at 80% coverage. This invalidates unconditional transfer of the previous 0181 public risk signal.

The status, fixed prior to original live execution, is **`INCONCLUSIVE_MIXED_OR_NONTRANSFERABLE_SOURCE_FAMILIES`**, not universal PASS. Even the classes where relative MAE improves were investigated after prior 0181 source outcomes and are exploratory; tiny groups of 6/11 do not license general performance inference. Original public TEST remained unread. No calibrated uncertainty probability, experimentally verified physical phases, external laboratory or independent sealed blind data.

## Science gate

This solo retrospective source-domain stress is scientifically useful without external researchers. Yet original external/physical P0-01/02/03 remain **BLOCKED** and science **NO-GO**. No fictional lab data, MPA-0 selected-frame provenance or ionic transport proof was generated. [0182 script](../scripts/science/obelix_solo_family_out_risk_0182.py), [science workflow](../.github/workflows/phase3-solo-obelix-family-out-0182.yml), [failure/embargo tests](../tests/test_phase3_obelix_solo_family_out_risk_0182.py). Next solo 0183 should diagnose the O_ONLY failure and concentration, rather than add human collaborator prerequisites.
