# 0185 SOLO O_ONLY original-public LLZO external source diagnostic

The user explicitly chose O_ONLY (oxygen-containing but no sulfur) as the sole ACTIVE research scope. This is an anion-presence formula proxy, **not a verified oxide crystal phase**. S_ONLY and the other chemistry-family bins are deferred.

This original-source workflow compares four unchanged predeclared models, all trained on the fixed publicly observed OBELiX original 478 TRAIN (449 usable numeric, 307 O_ONLY). All 121 original official TEST entries remain unread: pooled frozen RF (449), O_ONLY specialist RF (307), O_ONLY Ridge alpha=10 and O_ONLY train mean. No external labels are used in fitting or model choice.

New secondary original material source: public literature-derived [doped-LLZO dataset](https://github.com/abd-adhyatma/llzo-improvement), repository commit e65ac023b0613185666ad492cedce79a86633614, raw source Git blob SHA1 5293f717aebcc2c1396db335f9ac2a250d5567eb. Original file has 176 DOI-bearing nonempty records and many fully blank template rows. Source DOI, composition, conductivity and log-conductivity fields are validated at runtime; no original row or conductivity targets are redistributed.

Before external scoring, quarantines ALL matching original OBELiX TRAIN DOI (including censored TRAIN observations) and all exact reduced-composition overlap, then links remaining external observations transitively by shared DOI or exact reduced composition. No original publisher official TEST identities are accessed to perform deduplication. External cohort needs >=10 eligible rows and >=5 distinct connected source groups, else returns numerical diagnostic BLOCKED with an honest denominator.

Where eligible, compare equal-source-group macro and row log10(S/cm) MAE and group paired heuristic intervals. This is only a **retrospective source-transfer diagnostic**: external LLZO is an OLDER secondary literature compilation, public labels already visible in feasibility research, the individual experimental temperature, bulk vs total conductivity, physical pellet, phase and non-overlap with the original reserved TEST are NOT certified. Dataset formula silently assumes O12 as an LLZO schema convention, not measured structure. Source group bootstrap is not physical specimen CI.

Regardless of performance, DO NOT activate the production O_ONLY router or claim that P0-01/02/03 have been passed. Next 0186 must obtain genuinely distinct source-qualified O_ONLY experimental records and freeze a new validation cohort before truth inspection.

## ACTUAL original outside-repository numeric execution — diagnostic-only

[GitHub Actions #38745040942](https://github.com/wt2018mask/Rhombus/actions/runs/38745040942) SUCCESS, **40 anti-leakage and source tests passed**, [aggregate-only evidence artifact #11978116448](https://github.com/wt2018mask/Rhombus/actions/runs/38745040942/artifacts/11978116448), ZIP SHA256 30817e8fab99a884426d12574c35ceb30f9132fdf56450d153ff02b79e8f4254. Actually attempted 176 nonblank source rows, excluded invalid DOI 1, overlap with original TRAIN DOI 3, overlap with original TRAIN exact reduced formula 8, **164 eligible external observations in 36 connected DOI/formula source groups**. Results from identical external rows:

| Unchanged model | Row MAE log10(S/cm) | Equal source-group macro MAE |
| --- | ---: | ---: |
| POOLED_RF | 0.74089263 | 0.70002851 |
| O_ONLY_RF | 0.73788566 | 0.72592093 |
| O_ONLY_RIDGE(alpha 10) | 0.79153327 | 0.66757566 |
| O_ONLY_TRAIN_MEAN | 1.52614169 | 1.45484389 |

**Primary result is mixed**: O_ONLY RF improves row MAE by just 0.00300697 versus pooled but worsens equal-group MAE by 0.02589242. Ridge is best on equal-group macro but worse on rows; treating this as a newly selected winning model would misuse the already-exposed public source. Even these small errors are uncontrolled heterogeneous publication metrics lacking per-row measured temperature and bulk/total definition, NOT newly certified materials. O_ONLY specialist cannot be activated. Formal scientific external GO remains NO, all P0 BLOCKED.
