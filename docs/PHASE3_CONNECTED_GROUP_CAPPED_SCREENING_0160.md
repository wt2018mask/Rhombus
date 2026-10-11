# 0160-E — Actual original OBELiX connected source group budget, not row duplications

**Why:** 0159 demonstrated that source **row** top-20% conductivity screening hit count can improve (weighted RF outperformed baseline in 3/4 whole heldout anion-proxy families) even when the same model is worse on 0158 truly unseen-family regression MAE. None of the encouraging source-row hits had a significant uncorrected uniform-row overlap p-value, and identical DOI/formula source groups can contribute multiple correlated records. Row-level recall does not measure independent candidate material discovery.

**Actual experiment:** Clone immutable original `NRC-Mila/OBELiX@4eaac889809dd489e3bae468c45d5c0e02b9147a` 478 original TRAIN records; 29 censored upper bounds excluded; 449 eligible numeric TRAIN labels; public TEST **121 never inspected**; connected source DOI/composition groups **102**. Use exactly 0150 actual whole-family exclusion and transitive group embargo. Keep original 0150 RF features/parameters and 0157 fixed train-only inverse-sqrt group weights. For the heldout family **collapse every connected source group into one candidate review unit** before allocating identical **10% and 20% budgets**. Ranking uses median RF prediction over that group's rows, *without labels*. The group retrospective outcome is the median original source log10 conductivity (rather than max, which would cherry-pick). Oracle top-group overlap K-of-N, exact hypergeometric uniformly random group hit right tails and mean selected group-label score are computed only *after* masks freeze. Compare side-by-side with original 0159 **row-budget** hits, highlight largest group fraction of source rows and records in excess of one per group, preserving group-linked nonindependence.

**Caveat:** A connected DOI/formula group is not an independently authenticated physical experimental specimen, median group conductivity need not be a realizable single manufactured material, and repeated development on this same original TRAIN file does not create an external blind. These group-level tests are *sensitivity diagnostics*, not a claim of science GO or independently validated material discovery. P0 0/3 CLOSED, original TEST quarantined. Next **0161-E** use genuinely independent and physically verified source groups/specimens with frozen policies and equal cost budgets.

**Status:** First-party real CPU [0160 source Actions](../.github/workflows/phase3-obelix-group-budget-0160.yml) PENDING. Do not report invented group-level hit counts.

## Actual original-source numerical findings — checkpoint 0160

[Real 0160 pinned-source Actions #38151870647](https://github.com/wt2018mask/Rhombus/actions/runs/38151870647) **SUCCESS**. The real original OBELiX public TRAIN (449 valid numeric source rows / 102 connected groups; 121 public TEST quarantined) was reprocessed, with all four 0150 chemistry-family-out source embargo splits and the RF/weighted RF unchanged.

| Entire family held out | Source numeric rows | Distinct connected source groups | 20% group review K | Original RF top-group oracle hits | Weighted 0157 RF hits | Uniform group chance expected K²/N |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| O_ONLY | 307 | 64 | 13 | 2 | **4** | 2.640625 |
| S_ONLY | 117 | 21 | 5 | **1** | 0 | 1.190476 |
| HALIDE_NO_O_S | 14 | 11 | 3 | 1 | 1 | 0.818182 |
| OTHER_NO_O_S_HALIDE | 11 | 6 | 2 | 1 | 1 | 0.666667 |

**10% group review:** O_ONLY original RF 1/7, weighted RF 0/7; S_ONLY 0/3 for both; halides 0/2 for both; OTHER 0/1 for both. **20% group review:** weighted model beats old RF in **one of four groups of chemistry classes**, loses in one, ties in two. This reverses the prior *row-level* 0159 statement of outperforming on 3 of 4 families. The source rows from 307 oxide observations correspond to only **64 source identity groups**, and 117 sulfide rows only **21**. These are correlated source-cluster IDs, not independent material samples.

The oxide 4/13 group hit right-tail hypergeometric probability under a uniform group budget is **0.24568656**, not a significant claim; the S_ONLY 0/5 has p=1.0. Only one source group review unit was allowed per transitive DOI/formula identity; actual source group median label and median predicted conductivity produced the ranking/outcome *without using heldout labels to choose predictions*. The median conductivity of grouped source entries is a sensitivity-study construct and should not be reported as a realizable manufactured material label.

**Verdict:** the prior 0157/0159 apparent weighted-RF general screening advantage largely depended on evaluating source rows rather than distinct underlying provenance groups. This does not disprove every use of weighted RF, but **blocks 20%-budget default adoption** and rejects independent superiority claims. Next **0161-E** must prioritize truly new, independently verified source/experimental material candidates with a frozen decision budget and a physically meaningful ground truth rather than repeated tuning on the same publicly visible original TRAIN source.
