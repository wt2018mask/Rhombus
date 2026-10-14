# Rhombus 2.0

**Scientific Architecture Audit and Zero-Cost Development Roadmap — October 2026**

Rhombus is an open-source scientific system for discovering, falsifying, qualifying, and prioritizing candidate solid-state ionic conductors under severe compute and cost constraints.

Rhombus is not intended to replace every scientific simulator, foundation model, database, or research agent. Its long-term role is to become an **AI-native scientific control plane**: a protocol, evidence, applicability, uncertainty, claim-authorization, and audit layer that can accept results from heterogeneous external scientific tools without widening what those results scientifically justify.

```text
external scientific tools / models / databases / experiments
                              │
                              ▼
                    evidence normalization
                              │
                    protocol + model identity
                              │
                 applicability + uncertainty
                              │
                     claim authorization
                              │
                         audit trail
```

Solid-state ionic conductors remain the reference domain in which these contracts are implemented, falsified, and qualified first. Domain-neutral contracts should remain separable from Rhombus-specific science so they can later support other scientific workflows if validated beyond this domain.

Rhombus 2.0 is currently in **Phase 3 — Domain Map / C0–C4**, where the project is empirically grounding applicability and generalization limits rather than inferring them from model reputation or small internal benchmarks.

The original Rhombus pipeline produced a large body of useful scientific infrastructure: source-bound evidence, content-addressed structures and results, fail-closed semantics, deterministic execution, benchmark falsification, real MLIP relaxation, finite-temperature MD, transport-oriented analysis, candidate-supply scheduling, and conservative final claims.

Rhombus 2.0 preserves those validated assets but no longer treats the historical stage sequence itself as permanent architecture.

> **Freeze the evidence, not the research.**

The new objective is not merely to process more candidates. It is to maximize useful scientific information per unit of free compute while explicitly representing uncertainty, model applicability, evidence coverage, and generalization limits.

---


**Archive update (2026-10-08):** The original DRAFT GitHub Release ID `406879217` now contains **8/8 verified assets** (five sAlex membership parts, one WBM overlap part, summary JSON, and preserved evidence manifest). An independent GitHub API check confirmed every asset's reported size, `uploaded` state, and SHA256. See [`data/development/phase3_salex_github_release_remote_verification_v1.json`](data/development/phase3_salex_github_release_remote_verification_v1.json). The original Kaggle run receipt's raw JSON remains missing; this is **not a claim that every original Kaggle output was archived**. The Release remains a **draft**, no redistribution authorization is implied, MPTrj lineage is unverified, and the separate duplicate empty draft ID `406892209` is untouched. Do not rerun Kaggle.

## Current development status — 2026-10-14 · 0167 merged; 0168 PR #337

**Canonical main** `9ac3414d53c4cc8c5b01960bf17091f611ebebd4` after [PR #336](https://github.com/wt2018mask/Rhombus/pull/336) merged with **32/32 exact-head Actions SUCCESS**. **[PR #337](https://github.com/wt2018mask/Rhombus/pull/337)** checkpoint **0168-A** is **DRAFT / NOT MERGED** pending latest original-process source, Fast CI, Continuity and Wave2.

**User-approved target:** under equal limited/free computation, Rhombus must make **better justified scientific material decisions** than cheap or standalone methods—not merely produce more checkpoints, GitHub PASS results or unverified source records. [Approved five-milestone scientific roadmap A→B→C→D→E](docs/SCIENTIFIC_EVIDENCE_MILESTONES_A_E_0147.md): A source-grounded ML generalization diagnosis, B physical phase/measurement/CIF occupancy qualification (**ACTIVE**), C converged repeatable finite-temperature ion transport, D measured OOD error/uncertainty/abstention, E fixed-budget material candidate-selection utility.

**Real scientific computations and negative results:** [0145 official MACE CPU](https://github.com/wt2018mask/Rhombus/actions/runs/38121897232) has **39/39 real original OBELiX TRAIN structure single-point energies/forces**, not transport. [0146 source numeric grouped OOF](https://github.com/wt2018mask/Rhombus/actions/runs/38122882464): **449 original uncensored public TRAIN entries** in **102 connected DOI/formula groups**; original upper-bound entries 29 censored/excluded and all public TEST 121 reserved. [0147](https://github.com/wt2018mask/Rhombus/actions/runs/38125387307) log10-conductivity MAE: training-fold mean **1.86702336**; fractional RF **1.94487886**; MLP **2.26334295**; Ridge **2.29511512** (all worse than mean). [0149 publisher-inspired raw+geometry RF](https://github.com/wt2018mask/Rhombus/actions/runs/38127945076) improves retrospectively to **1.62526468** but **is not independently validated**. [0150 source/chemistry stress](https://github.com/wt2018mask/Rhombus/actions/runs/38129121068) shows RF loses to mean **+1.0588909 log10 MAE** for S-only composition-proxy held-out retraining. These 449 source rows and 102 identity groups are not independently verified experiments.

**Actually inspected original CIFs — [0151 pinned original TRAIN audit](https://github.com/wt2018mask/Rhombus/actions/runs/38130478891):** 599 original rows, **478 TRAIN** / **121 public TEST reserved-unparsed**, **202 TRAIN exact-CIF Match** and **52 Close Match** (not experimental phase-qualified). Pymatgen inspected **254 TRAIN CIF** structures: **195 fractional site occupancy**, **170 partial vacancies** (overlap, including Close Match), earlier conservative MACE admission stays 39. Generated **ten** exact-Match TRAIN source CIF/DOI paper review targets. None was yet qualified as an independent source-verified experimental specimen.

**0152-B ACTUAL publisher-abstract review (first-party literature, not full paper)** — [evidence protocol](docs/PHASE3_OBELIX_PUBLISHER_ABSTRACT_REVIEW_0152.md): retrieve the [first-party 0151 Actions original source artifact](https://github.com/wt2018mask/Rhombus/actions/runs/38130478891) and its **SHA256 `960cf078fcac71b244a087f0e73d781614aa515d38e6964dcfffcd654f90070a`**. The ten queued exact source-CIF rows correspond to **eight distinct primary ACS/RSC publisher DOI papers**, two DOI papers referenced twice. We **inspected all eight indexed publisher-public abstracts** (titles, experimental methods, source-level chemistry/phase/temperature/processing caveats). [Curated DOI primary-abstract source evidence](data/development/phase3_original_paper_abstract_review_0152_v1.json) captures URLs and restricted literature context without reproducing publisher full text. The new Actions script **recomputes** immutable pinned original 0151 CIF audit and fails if SHA/ten source rows/eight DOI binding drifts. It does **not** transfer paper-series conductivity values, room temperature statements, exact phase or disordered atomic arrangements to an individual queued CIF. **Full primary paper text and supplementary data actually read: 0; individual CIF↔experimental composition/phase/temperature independently verified: 0; newly qualified physical specimens: 0.** Scientific permission remains NO-GO.

**0153-B genuine original manuscript access probe (PR #321, pending live Actions)** — A primary-source [US DOE OSTI openly hosted accepted author manuscript](https://www.osti.gov/servlets/purl/1434719) is identified for 0152 paper `10.1021/acsami.8b00842` (LAGP). New bounded reader downloads bytes on GitHub CPU, verifies PDF header, exact DOI and topic in extracted full-text, reports SHA256/bytes/pages and aggregate context markers only, and refuses malformed/wrong-DOI/excess-size inputs. **Proposed access is not actual evidence until live Actions SUCCESS.** This accepted manuscript may differ from the publisher version of record; DOI/paper association alone does not qualify either OBELiX CIF row, no full SI ZIP/PDF has been read, no exact specimen/phase/temperature/bulk conductivity is assigned and **new independent qualified materials remain zero**. [0153 original manuscript protocol](docs/PHASE3_OBELIX_ORIGINAL_MANUSCRIPT_AUDIT_0153.md). Next 0154-B: directly examine verified original supplementary structure/table data and attempt specific original-CIF sample composition/phase matching. No MACE MD or P0 promotion from PDF text markers.

**0154-B genuine supplementary-source probe (PR #322; real-source result pending exact-head Actions)** — The publisher explicitly lists a free **Rietveld diffraction PDF and experimental composition CIF ZIP** for DOI `10.1021/acsami.8b00842`; availability of those routes on GitHub runners remains to be *measured*, not inferred from the landing page. The new bounded original-source reader probes two conventional `.s001`/`.s002` DOI suffix routes, reports actual HTTP/content type, bounded source SHA256 and PDF page count or ZIP CIF member digest census **only when bytes verify**, and rejects unsafe archives. If access fails, it reports `HTTP_UNAVAILABLE` or `SOURCE_CONTENT_REJECTED` with **zero added evidence**. Original OBELiX 121 public TEST preserved; two original TRAIN CIFs linked to this DOI remain **not sample/phase/temp/measurement qualified**. No simulated transport, no P0 closure. [0154 experiment protocol](docs/PHASE3_ORIGINAL_SUPPLEMENTARY_SOURCE_PROBE_0154.md). Next **0155-B**: obtain working first-party files via authenticated approved repository/figshare if DOI routes fail; only then compare exact publisher CIF structure/composition with original verified OBELiX TRAIN CIFs and actual source experimental conditions.

**0154-B VERIFIED primary supplementary source bytes — [original live Actions](https://github.com/wt2018mask/Rhombus/actions/runs/38135604841)**: the public ACS direct DOI `.s001` / `.s002` routes returned HTTP 403, but DOI-exact [official Figshare API metadata](https://docs.figshare.com/v2/) identified two downloadable public first-party files. GitHub CPU actually verified **Rietveld PDF 553,276 bytes** SHA256 `db747a82235860cdcd21a798ad51d2fd0d22b906d3a213cd31e9ea9af72d94d3` and **experimental CIF ZIP 6,261 bytes** SHA256 `dc88a0a83857b172ebe7a8194eb1b50148f117d6cddb39f1adbb628ac7d1c382`, with **8 original CIF members**. Each member is privately rehashed, not redistributed. This materially advances Phase 3 Milestone B original structure data accessibility, **NOT** independent experimental specimen count, source-row exact phase assignment, experimental conductivity, MD or P0 gates. [Complete original source protocol](docs/PHASE3_ORIGINAL_SUPPLEMENTARY_SOURCE_PROBE_0154.md). Next 0155-B: real original structure-to-OBELiX TRAIN source-row cross-check and precise x/sample/phase matching; no TEST analysis.

**0155-B ACTUAL source-geometry comparison (PR #323; [real original-geometry Actions PASS](https://github.com/wt2018mask/Rhombus/actions/runs/38137695018), remaining final-head CI pending)** — [scientific A–E milestone scorecard](docs/SCIENTIFIC_MILESTONE_SCOREBOARD_0155.md) and [actual source matching protocol](docs/PHASE3_OBELIX_ORIGINAL_CIF_MATCH_0155.md). Fetch previously verified SHA-frozen **8 publisher original SI CIFs**, recompute original **0151 TRAIN-only** inventory and compare them with exactly **2 DOI-linked first-party original TRAIN CIFs**. **Actually computed 16 chemistry/geometry pairs: 15 stoichiometry-compatible and 2 permissive geometry-fit diagnostics**, alongside occupancy and source SHA; zero paper sample/temperature/conductivity identities qualified. Even an exact geometric fit cannot by itself establish experimental specimen, phase, conductivity or temperature. P0 0/3, scientific NO-GO. Next **0156-B**: specimen-specific original paper/measurement adjudication, excluding any unverifiable source rows. Do not touch original TEST or run MACE MD prematurely.

**0156-B ACTUAL nominal versus refined source labeling (PR #324, source CPU execution PENDING):** previously source-frozen primary paper `10.1021/acsami.8b00842`, 0155 structural matches `0fh` and `1dm` (SHA verified), and all 8 real publisher SI CIF source members. The new experiment binds the **actual publisher CIF filename** (nominal Al doping x) to each matching source SHA and separately calculates **refined Al, Li, Ge substitution x** without changing partial occupancies. It also downloads the previous SHA-pinned full OSTI accepted manuscript and first-party original Rietveld SI PDF, records source PDF page-context indicators only. **Nominal filename ↔ crystal** can be proven, but **individual experimental specimen ↔ diffraction phase and measured temperature/bulk-or-total conductivity** is still unverified until direct original figure/table row adjudication. No MACE MD / P0 closure. [0156 method](docs/PHASE3_LAGP_NOMINAL_V_REFINED_0156.md) and [A–E milestones](docs/SCIENTIFIC_MILESTONE_SCOREBOARD_0155.md). Next 0157-B: source-specific primary paper transport table/figure adjudication or report absent linkage.

**0156-B actual source crystal ↔ original nominal composition observation ([first real run](https://github.com/wt2018mask/Rhombus/actions/runs/38143192408))**: source TRAIN `0fh` maps by frozen CIF SHA to publisher `lagp-1.2.cif`, nominal Al x **0.2** vs refined **0.242**; source TRAIN `1dm` maps to publisher `lagp-1.6.cif`, nominal x **0.6** vs refined **0.480**. Both actual accepted manuscript (26 pp) and genuine Rietveld SI (15 pp) were read, and scientific zero-promotion assertions passed; the initial run had an artifact filename typo, corrected for current-head verification. **These are structural filename/x links only**; measured experimental specimen/phase, T, and bulk/total conductivity remain unverified. [0156 full result and scope](docs/PHASE3_LAGP_NOMINAL_V_REFINED_0156.md). P0/GO unchanged.

**0157-A REAL PREDICTIVE ERROR REDUCED ([original actual-source Actions #38146722873](https://github.com/wt2018mask/Rhombus/actions/runs/38146722873), PR #325 pending final CI):** Pivot from consecutive original paper checks to **training-only group balanced Random Forest** on the same frozen **449 original uncensored public TRAIN source labels / 102 connected source groups / exact 5 DOI+composition holdout folds**. Exactly reuse existing 0149 RF features and all hyperparameters, but apply inverse-square-root connected group size weights *computed only within each training fold*. Score versus original no-search 0149 geometry RF (log10 MAE **1.62526468**) and 0146 fold mean (**1.86702336**), including equal-group macro and chemical proxy error diagnostics; no original TEST entry accessed. **Actual same-frozen-fold source-train row-weighted log10 MAE improved from 1.62526468 to 1.48588191 (−0.13938277)** versus 0149 RF; cheap fold mean remains 1.86702336. **Equal-source-group macro MAE improved only 1.66954551 → 1.64649874**; 512 group bootstrap 95% heuristic interval for paired group-MAE difference **[−0.10568478,+0.06600920] includes zero**. All five fixed folds improved, but original halide proxy worsened (0149 RF 1.83174291 → 0157 1.94413273; cheap baseline 1.50061445). 0150 genuine family-left-out transfer still has not been re-run for this new model. This is **actual public TRAIN retrospective performance improvement, not demonstrated independent or all-chemistry generalization**. [0157 source experiment](docs/PHASE3_GROUP_BALANCED_RF_PERFORMANCE_0157.md). Next **0158-A**: diagnose real group/chemical failure and decide whether group balancing is retained or discarded; reserve future numerical work for actually measured gains. All P0 and GO unchanged.

**0158 real unseen-family failure of 0157 balanced RF ([first source run](https://github.com/wt2018mask/Rhombus/actions/runs/38148543442)):** The 0157 model's **retrospective** 449 public TRAIN mixed-chemistry outer group-fold MAE improved from 1.62526468 to 1.48588191. **But actual 0158 leave-entire-anion-proxy-family-out evaluation with same connected DOI/formula group embargo found the weighted RF worse than the unweighted 0150 RF in all four admissible heldout chemistry classes**: O_ONLY 1.53510261→1.54580638, S_ONLY 3.32781812→3.66335436, HALIDE_NO_O_S 1.60502714→1.65080353, OTHER 1.41318765→1.44332988 (lower MAE better). S_ONLY weighted RF is **+1.39442714 log10 MAE worse than a mean trained only on other chemistries**. **Conclusion: do NOT deploy 0157 group-balanced RF as a globally superior default or claim unseen-family generalization**. Preserve positive retrospective source-fold result but record genuine family-out falsification. [0158 detailed results](docs/PHASE3_CHEMISTRY_FAMILY_OOD_0158.md). Next **0159-D**: bounded out-of-domain detection, uncertainty calibration and abstention on properly heldout source groups/families, without tuning away the observed negative result.

**0159-D/E ACTUAL same-budget screening and selective prediction NEGATIVE original-source result ([real first-party run #38150068258](https://github.com/wt2018mask/Rhombus/actions/runs/38150068258); latest HEAD still pending):** Instead of another model-weight search, run actual original source 449 numeric TRAIN rows / 102 connected DOI/formula groups, with entire O, S, halide and other anion-proxy classes excluded from training and exactly original 0150/0158 connected-group embargo. Refit unchanged RF and 0157 source-weighted RF. For each heldout class rank unknown candidate conductivity, compare **top 10%/20% fixed review budgets** for oracle top-k overlap and actual selected source log10 conductivity versus pre-frozen blind random ranking. Separately evaluate original unweighted RF's **25%/50%/75% acceptance** using only source TRAIN composition-nearest-cosine similarity, within-RF tree disagreement, and predetermined blind random acceptance; measure *post-selection* accepted and rejected MAE and risk-coverage. No holdout labels in ranking or screening, no hyperparameter tuning, original 121 TEST untouched. **Actual observed 10% review budget:** 0150 RF and 0157 weighted RF both failed to outperform even the *analytical expectation* for uniform random top-budget oracle recall in every evaluable unseen chemistry family (O: 2/31 true top among selected vs random expectation 3.13/31; S: RF 0/12, weighted 1/12 vs chance expectation 1.23/12; halides RF/weighted 0/2 vs chance 0.29/2; other 0/2 vs chance 0.36/2). An individual seeded random draw sometimes beat both RFs, but small pools cannot establish randomized statistical significance. 50% acceptance by chemistry support beat one seeded random selection in S/halide only (2/4) and failed in O/other; tree-variance rank beat random only in halide (1/4). **No universally reliable budgeted OOD candidate selection or abstention was observed**, despite previous mixed-chemistry MAE improvement. This is original public TRAIN retrospective simulation, **not independently authenticated candidate discoveries** and no physically validated specimens. [Protocol](docs/PHASE3_EQUAL_BUDGET_SCREENING_ABSTENTION_0159.md). Next **0160-E** assess true utility, source-group leakage and prospective blinded admission if useful; disallow default model promotion absent external proof.

**0159 20%-review-budget surprise ([real original source aggregate](https://github.com/wt2018mask/Rhombus/actions/runs/38150068258/artifacts/11705569479))**: Despite worse 0158 unseen-family regression MAE and no top-10% chance lift, **at predeclared 20% same-review-budget the 0157 balanced RF selected more true top source conductivity rows than the unweighted RF in 3/4 evaluated chemistry families**: O_ONLY 15 vs 12, S_ONLY 7 vs 6, HALIDE_NO_O_S 1 vs 0; OTHER 0 vs 0. Exact chance expected hits respectively 12.52, 4.92, 0.64, 0.82. This suggests objective/budget-dependent *screening* utility: the weighted RF may help at 20% even while its MAE and 10%-budget selection fail. **Do not adopt as validated 20% operational strategy**: this source TRAIN cohort has now informed analysis repeatedly, small families lack power, 121 public TEST untouched, no independent blind or authenticated physical specimens. The correct next test must freeze budget/model before an independent pool. [Complete first-party analysis](docs/PHASE3_EQUAL_BUDGET_SCREENING_ABSTENTION_0159.md).

**Exact fixed-budget row-level chance tails (0159)**: Under a uniform K-of-N source-row draw (ignoring correlated source identity groups), the hypergeometric probabilities of observing *at least* the balanced RF's top-20% oracle hits were **p=0.23848694 for O_ONLY (15/62)**, **p=0.18369152 for S_ONLY (7/24)**, and **p=0.54670330 for HALIDE (1/3)**. None meets even an uncorrected 0.05 threshold, let alone repeated-workflow correction; these are **diagnostic row-level chance probabilities, not independent physical specimen p-values**. The budget-conditional ranking pattern is scientifically worth follow-up, not a validated efficacy claim.

**0160-E ACTUAL connected source-group budget FALSIFIES MOST ROW-BASED BENEFIT ([real 0160 original source Action #38151870647](https://github.com/wt2018mask/Rhombus/actions/runs/38151870647), PR #328 final-head checks pending):** The 0159 source-row screening budget could overrepresent repeated entries in large transitive DOI/formula source groups. Same original 449 valid public TRAIN rows, 102 frozen identity groups, original 0150/0158 entire-chemistry-family embargo, unchanged baseline and weighted RF parameters. **At 10% and 20% *source-group* review budget**, collapse candidate predicted conductivity to the **median per connected group** and compare with retrospective **median source measured log10 conductivity** for that group, each source identity reviewed once. Report actual group top-oracle overlap, exact analytic group-uniform random expectation and hypergeometric source-group tail, plus 0159 row-level top-k overlap for side-by-side sensitivity and group-size concentration. **ACTUAL observed group-budget 20% true top-group hits:** O_ONLY 64 groups/307 rows, k=13, original RF 2 vs weighted RF **4** (group-uniform expectation 2.640625, exact p≥4 **0.24568656**); S_ONLY 21 groups/117 rows, k=5, original RF **1** vs weighted **0** (expectation 1.19048); HALIDE 11 groups, k=3, both 1; OTHER 6 groups, k=2, both 1. Previously source-ROW budget weighted RF improved in 3/4 families at 20%; with **group units it improves only 1/4, worsens 1/4 and ties 2/4**. At 10% group review, weighted RF matched or worsened original RF in every family (O 0 vs original 1; others ties 0). **Source group de-duplication removes most of the apparent top20 gain**; all results are retrospective source TRAIN and not independent physical discovery. **Source identity group ≠ independent physical specimen**. Repeated source PUBLIC TRAIN cannot confer prospective discovery. [0160 original-source trial](docs/PHASE3_CONNECTED_GROUP_CAPPED_SCREENING_0160.md). Next **0161-E**: genuinely independent qualifying candidate cohorts and frozen, same-budget comparison rather than reweighting already known source data. P0 remains 0/3 CLOSED, science NO-GO.

**0161-E FIRST ACTUAL DIFFERENT-PUBLISHER CROSS-CORPUS MODEL PERFORMANCE (PR #329, real source Actions PENDING):** Fit frozen 0147 **composition-only** RF and previously fixed 0157 TRAIN-connected-group weighted **composition-only** RF plus original TRAIN mean to the **449 real source numeric OBELiX TRAIN** labels (102 identity groups) **before** parsing external targets, no geometry available in external corpus and no original public TEST records inspected. Retrieve independently hosted primary [CaltechDATA McHaffie 571 experimental-conductivity record file](https://data.caltech.edu/records/23mvv-6gk43) (previous 0135 source MD5 `d1fcf7c9a7694c8f466932721b76b168`, SHA256 `868c4bd793d7c31b929787dc69478691b27ced0440d19269075143c98ecd1545`), compare log10 MAE in nested tiers: valid external numeric Li-compound rows; no exact original TRAIN source DOI; and no exact TRAIN DOI **nor** reduced composition. Duplicate external source formulas collapsed separately by median label for a **sensitivity** metric. **Not a blind/independent physical experiment:** both public archives include overlapping literature, nonmatching DOI/formula is not proof of independent sample, external reported room-temperature reference may include extrapolated temperature, bulk-vs-total/phase not independently reviewed, reuse rights for raw external CSV unclear. Repo/Actions artifact emit **aggregate metrics only**, never source CSV, DOI/compound/ICSD rows or per-row predictions. No scientific GO. [0161 original source experiment](docs/PHASE3_CALTECH_EXTERNAL_ZERO_SHOT_0161.md); next **0162-E** freeze and seek independently authenticated material validation after actual cross-source errors.

**0161-E ACTUAL cross-publisher external source error ([Caltech real source GitHub Actions #38153468942](https://github.com/wt2018mask/Rhombus/actions/runs/38153468942), first source run SUCCESS; PR #329 latest HEAD pending):** Train model only on original OBELiX 449 numeric public TRAIN, 102 source groups, 121 original public TEST untouched; original CaltechDATA 571 rows verified by official file MD5/SHA, **565 parseable Li experimental-source labels**, 225 external records with exact original TRAIN DOI signal (before numeric filtering), and **301 external source records / 280 normalized formulas without exact TRAIN DOI or reduced formula match**. Strictest external MAE log10(S/cm): cheap original TRAIN mean **2.71016387**, original 0147 **composition-only RF 2.19038829**, 0157 source-group-balanced **composition-only RF 2.28821752**. Median-per-external-formula aggregated MAE: mean **2.78009165**, unweighted RF **2.22397612**, weighted RF **2.32654585**. Other 565/343 tiers and all source-error aggregates in [0161 original-source report](docs/PHASE3_CALTECH_EXTERNAL_ZERO_SHOT_0161.md). **Cross-publisher actual transfer supports the simpler RF over weighted RF for this diagnostic; original 0157 retrospective mixed-source gain is not reliable on the external archive.** Do NOT compare 2.19 to prior geometry RF 1.49 as an exactly same feature/split benchmark: Caltech supplies composition only; temperature/phase/bulk-total may differ and sample independence remains unverified. Newly physically attested specimens **0**, not 301. P0 and science GO blocked.

**APPROVED foundational scientific change — 0162 (2026-10-12):** Preserve A–E success conditions but execute **B authenticated experimental specimen–phase–exact temperature–bulk/total conductivity target before C finite-T transport**. A/D regression/abstention must match the physical measurement quantity; E equal-budget candidate utility needs genuine physical unseen independent materials. Pursue in parallel three P0: P0-01 independent sealed steward and unknown samples; P0-02 authenticated selected MLIP checkpoint training frames or traceable alternative; P0-03 sufficiently independent physical specimens, not literature rows or related trajectories. Stop repeated public TRAIN RF tuning. [Approved scientific plan](docs/SCIENTIFIC_FOUNDATIONAL_REPRIORITIZATION_0162.md).

**0162 original LAGP physics evidence ([PR #330](https://github.com/wt2018mask/Rhombus/pull/330)):** verify pinned first-party author PDF, Rietveld SI and eight publisher CIFs; trace prior two source-TRAIN CIF labels (0fh nominal x=.2, refined x=.242; 1dm nominal x=.6, refined x=.480); calculate actual *processed-source* S/cm label contrast without exposing raw labels, and inspect experimental inverse resistance, impedance, bulk/grain boundary and temperature definitions. **No automatic figure/page to physical specimen bulk/total conduction mapping or finite-T MD admission.** Legacy OBELiX general intake reads TEST metadata, though these experiments fit/compare only TRAIN labels—do not continue claiming entirely unparsed TEST for this specific legacy route. [Method and review stops](docs/PHASE3_LAGP_MEASUREMENT_TARGET_0162.md).

**0162-B REAL LAGP original primary source physical TARGET result ([GitHub original PDF/CIF experiment #38156094032](https://github.com/wt2018mask/Rhombus/actions/runs/38156094032))**: Exact original manuscript, original Rietveld SI and 8 publisher CIFs reverified; original TRAIN processed conductivity log10(S/cm) **x_nominal=0.6 minus x_nominal=0.2 = +0.76937121 (≈5.88×)**. The manuscript itself has a Li1.6 Al0.6/figure-6 context (PDF page 15), **reciprocal resistance 'instead of conductivity'** (PDF page 15), 25 °C context (PDF page 16); no direct parsed Li1.2 Al0.2 explicit formula sample context in text. This is **only a public processed-source label contrast**, not a matched measured sample conductivity, T/phase/synthesis/geometry validation, or scientific GO. No new verified independent specimen, 0 original bulk/total matched sample labels. Existing legacy generic intake accesses original TEST metadata; TEST is **not fitted or scored**. [Measured target report](docs/PHASE3_LAGP_MEASUREMENT_TARGET_0162.md).

**0163-B LIVE ORIGINAL TRAIN-ONLY SOURCE INTAKE (PR #331; source test PENDING):** Repair 0162 exposed TEST-cell ingestion **without** changing inherited historic benchmark outputs: construct a separate pinned original OBELiX TRAIN-only physical source scanner. It streams the mixed `processed.csv` physical lines, reads **only the ASCII ID prefix for TEST** to confirm official membership, never UTF-8 decodes or CSV-parses TEST DOI/formula/experimental conductivity fields and never reads TEST CIF. It verifies 478 eligible TRAIN IDs / 121 reserved TEST IDs; performs TRAIN-only DOI/numeric-label checks and reauthenticates the two pinned 0155 LAGP CIF geometry and 0156 source publisher CIFs, primary paper/SI and reported 0162 label contrast. **Single-source-file caveat**: TEST raw bytes necessarily pass through the input stream; this is **not cryptographic or prospective blinded inaccessibility**. Refuse malformed or multiline original records; do not certify a physical pellet, measured exact T, phase, bulk vs total conductivity or MLIP MD. P0 all BLOCKED, NO-GO. [Actual method](docs/PHASE3_STRICT_TRAIN_ONLY_PHYSICAL_SOURCE_0163.md). Next **0164-B**: original graph/table sample T, phase, bulk/total numerical source adjudication and real outside steward.

**0163-B LIVE ORIGINAL-SOURCE TRAIN-only leak-falsification SUCCESS:** [Original pinned OBELiX CPU run #38190606191](https://github.com/wt2018mask/Rhombus/actions/runs/38190606191) executed a novel standalone scanner with **478 TRAIN rows parsed, 121 TEST ID prefixes only, 0 TEST DOI/formula/conductivity fields UTF-8/CSV decoded, 0 TEST CIF reads**, and reverified original publisher CIF+paper source physical-context links; 0162 two TRAIN original processed label contrast **+0.76937121 log10 S/cm reproduced**. Actual original processed.csv **478 point-looking numerical records, 0 text-censored symbols**; the different 0146 original raw workbook censor policy yielded **449 scored numeric source records and 29 censored upper bounds**, and **0163 did NOT rerun that independent raw policy**. Never count all 478 processed numeric appearances as validated measurement points. **Raw mixed CSV TEST bytes still traverse the stream**, so new code does not retroactively erase historic source exposure or create external blind; sample/phase/T/bulk-total qualified **0**, science NO-GO. [Full report](docs/PHASE3_STRICT_TRAIN_ONLY_PHYSICAL_SOURCE_0163.md).

**0164-B CORE PHYSICAL TARGET DISTINCTION (PR #332; original-source Actions pending):** First-party original [Weiss et al. 2018 LAGP paper](https://doi.org/10.1021/acsami.8b00842) reports **Figure 6** representative nominal Al x=0.6 sintered at 800°C impedance sample; Arrhenius plot uses **reciprocal resistance (1/R), not σ in S/cm**. A 25°C impedance panel does NOT prove that the neutron-refined x=0.6 CIF is the identical measured pellet. **Figure 7** reports bulk and total room-temperature conductivity as **composition-level average values from multiple samples with identical nominal composition; error bars represent SD**; neither curve is an independently attested single-CIF/single-pellet result. Increased x above ~0.5 has solubility/phase-fraction and secondary-phase effects, so stronger pooled conductivity is not solely a bulk diffusion consequence. New executable source audit [0164 paper figures](docs/PHASE3_LAGP_FIGURE_POPULATION_0164.md) records exact-SHA primary PDF page/semantic indicators, **not copyrighted figure text or digitized numeric point predictions**, and blocks Figure 6 1/R→σ, Figure 7 population mean→pellet, artificial specimen identity and MD eligibility. Existing two source TRAIN labels still differ +0.76937121 log10 but are NOT verified Figure 7 group mean, bulk or total. No independent physical specimens newly verified; P0 0/3, SCIENTIFIC NO-GO.

**0164-B CONFIRMED FROM ACTUAL FIRST-PARTY ACCEPTED AUTHOR PDF ([GitHub CPU Run #38192412215](https://github.com/wt2018mask/Rhombus/actions/runs/38192412215), original-source SCIENCE SUCCESS):** SHA256-pinned original 26-page accepted manuscript text confirms **Figure 6 inverse resistance vs σ at PDF p15**, **Figure 7 heading p16 and contiguous caption p17 explicitly averaging multiple pellets with identical nominal composition and standard-deviation uncertainty**. Strict-source Figure 7 anchoring checks all four words on the same caption page and permits the Figure number on that page or **immediately preceding page only**; unrelated distant-page words are rejected by negative tests. This original primary-source evidence strengthens the **exclusion** decision: Figure 7 is a composition-group summary, NOT the σ of any single specific neutron-refined CIF pellet; 800°C synthesis and 25°C measurement are distinct and cannot be silently substituted. No figure numerical digitization, individual measured sample count or bulk/total-phase exact T verified; **0 admitted physical pellets**. Results artifact only metadata [#11722415306](https://github.com/wt2018mask/Rhombus/actions/runs/38192412215/artifacts/11722415306). P0 0/3, SCIENCE NO-GO.

**0165-B EXPERIMENT — CAN ORIGINAL FIGURE 7 YIELD DEFENSIBLE NUMERIC σ MEANS AND SD?** The original peer-reviewed [Weiss LAGP 2018](https://doi.org/10.1021/acsami.8b00842) Figure 7 plots **room-temperature bulk and total conductivity population means over multiple same-nominal-composition experimental pellets, error bars SD**, not single-sample truth. The accepted first-party PDF has Fig7 title p16, complete multi-sample mean±SD caption p17; [original source pinned CPU graphics audit](docs/PHASE3_LAGP_FIGURE7_QUANTITATIVE_0165.md) now inventories original PDF **page 15/16/17 graphics operators, raster images, vector paths, and unclassified typography numeric tokens**, with strict SHA/size/operation caps; **none** are classified as measured points, replicate count or calibrated error bars without actual source digitization. A separate population-level data type rejects means without source-calibrated ordinate, bulk/total channel, SD and raw independent replicate n. Even with these, it cannot certify an individual CIF-to-pellet physical measurement or independent blindness. Original TEST field non-parsing maintained; MD **not** executed; P0 **0/3**, **NO-GO**. Primary evidence run pending latest HEAD science Actions; next 0166-B numeric graph calibration only if first-party graphic allows calibrated replicable extraction, otherwise actual independent author/raw data acquisition.

**0165-B REAL PINNED ACCEPTED PDF FIGURE 7 GRAPHICS (first actual original science [Actions #38193859927](https://github.com/wt2018mask/Rhombus/actions/runs/38193859927), SUCCESS; final HEAD checks pending):** The genuine source **p15** has **5 image XObjects / 0 vector drawing path operators / 92 unclassified numeric text tokens**; **p16**, where Figure 7 is anchored, **4 image XObjects / 0 vector paths / 74 numeric typography tokens**; Figure 7 full multi-pellet SD caption on **p17** has **0 image XObjects / 0 vector paths / 78 numeric typography tokens**. These are counted actual original PDF graphic operators, **NOT measurement values**; the original PDF figure-7 graphic is embedded in page image resources, not extractable as a direct vector series by the current source decoder. Numeric point means 0 recovered, SD 0, true independent replicate **n unknown**, and **0 individually attested physical specimen truth**. Calibrated raster/author original source data extraction is a scientifically necessary next step, **not** more RF training on public source. Original source TEST fields remain nonparsed; P0 0/3 closed and GO false. [Actual figure readiness report](docs/PHASE3_LAGP_FIGURE7_QUANTITATIVE_0165.md).

**0166-B ACTUAL DIFFERENT PRIMARY PAPER NUMERICAL TRANSPORT TABLE:** [Kraft et al. 2018 JACS DOI 10.1021/jacs.8b10282](https://doi.org/10.1021/jacs.8b10282) [original university Supporting Information Table S17 PDF p20](https://purehost.bath.ac.uk/ws/files/187666868/Supporting_Information.pdf). Actual [GitHub CPU original-source Action #38197782436](https://github.com/wt2018mask/Rhombus/actions/runs/38197782436) SUCCESS: 10 nominal Ge compositions, 10 author sample-thickness values, 12 temperature rows 253–333 K including a second 298K row, and **120 genuine primary fitted bulk R(Ohms) numeric entries** analyzed. Two 298K rows show median relative difference **3.91568%** (min **1.79104%**, max **9.90664%**) across composition columns; 11-unique-temperature ln(R) versus 1/T apparent Arrhenius activation **median 0.226805 eV** (range 0.200880–0.360360), median R² **0.999490**. This is **real experimental source physics**, NOT model performance, ionic conductivity S/cm, 120 materials or independently proved repeat pellets. High Ge compositions have **source-author warned unreliable bulk process resolution**, electrode area per original sample and same measured pellet ↔ neutron CIF identity unverified. Institutional PDF wrapper SHA can change (cover download stamp); new scientific source validation pins canonical Table S17 numeric content digest, not a purported immutable whole-file PDF SHA. No original source rows/PDF republished, original public TEST not analyzed here, P0 0/3 and NO-GO. [0166 study](docs/PHASE3_KRAFT_ORIGINAL_IMPEDANCE_TABLE_0166.md).

**0167-B FUNDAMENTAL IDENTIFIABILITY FALSIFICATION ([PR #336](https://github.com/wt2018mask/Rhombus/pull/336); actual new two-paper source CI pending):** Do not mistake more source rows for independent benchmark success. Integrate fully tested but stale-unmerged [PR #334](https://github.com/wt2018mask/Rhombus/pull/334) **2019 Yubuchi original Li6PS5Br publisher-deposited numerical conductivity table**, six processing (heat treatment **150, 200, 300, 400, 500, 550 °C**) conditions with 25 °C ionic conductivity `0.19, 0.20, 0.53, 1.49, 1.23, 1.94 mS/cm`. Source DOI `10.1039/C9RA00949C`, PMC9064144; pressing 720 MPa. Same nominal chemistry, observed maximum/minimum conductivity **10.210526×**, log10 span **1.00904813** and **minimum possible retrospective log10 MAE for any chemistry-only one-output predictor 0.37447227** on six public conditions. This is a deterministic information-loss *diagnostic*, **not** an unseen test-set error or independent sample count. Observable and temperature/processing semantics stay distinct. Separately, existing merged Kraft 2018 Table S17 `10.1021/jacs.8b10282` contains **120 original R_bulk(Ω)** across 10 nominal Ge x and 12 temperatures (11 distinct), with electrode area and exact pellet/CIF identity unqualified; NEVER pool Ω with S/cm MAE or claim 126 materials. All six processing condition rows are **one nominal formula**, independence unverified. New authentic original-source CPU study and tests [0167](docs/PHASE3_TWO_PAPER_IDENTIFIABILITY_0167.md); original archive/paper acquisition and aggregate-only Actions required. P0 0/3, science NO-GO; next prioritize actual pellet/sample/phase, synthesis/method/geometry and independently blind cohort, not RF retuning.

**0167-B VERIFIED ACTUAL TWO-PRIMARY-SOURCE SCIENTIFIC TEST:** [Real GitHub Actions #38562016280](https://github.com/wt2018mask/Rhombus/actions/runs/38562016280) **SUCCESS**: authentic 2019 Yubuchi publisher-deposited six Li6PS5Br processing-condition conductivity values re-fetched and 2018 Kraft institutional paper Table S17 **120 bulk-R (Ω)** values re-fetched/rechecked via SHA-pinned *numeric table contents*. Chemistry-only fixed-output minimal empirical source-six `log10(S/cm)` MAE **0.37447227**, fixed nominal chemistry max/min conductivity **10.21052632×**; actual heat-treatment 500°C has lowest source Ea, 550°C highest σ. All six σ points belong to one nominal chemistry and public processing study, not six independently new materials. The 120 Ω measurements cannot be pooled into S/cm accuracy. **0 physically qualified specimens, 0 new blind measurements, P0 all BLOCKED and scientific NO-GO.** [Actual method / exact scope](docs/PHASE3_TWO_PAPER_IDENTIFIABILITY_0167.md).

**0168-A REAL PRIMARY SOURCE PROCESS-AWARE PREDICTION ([original firstparty Actions #38565237436](https://github.com/wt2018mask/Rhombus/actions/runs/38565237436), initial source experiment SUCCESS):** In the original deposited 2019 Li6PS5Br paper's six **same nominal formula** heat-treatment conditions 150–550°C, ionic σ was measured **at 25°C**, not at the preparation temperatures. Frozen **leave-one-processing-condition-out** 5-row-training log10(S/cm) predictions yield **chemistry-only train-median MAE 0.55728689** versus **simple linear OLS on heat-treatment C MAE 0.13095762** (an observed within-source **76.50%** error reduction). This does NOT represent independent heldout material prediction: only **one compound, one public paper, six *processing conditions***; source values were publicly inspected before study design, and process-dependent phase/microstructure and sample identity remain unknown. Do not infer causal thermal-processing benefit, extrapolation beyond source or MACE MD accuracy. No hyperparameter search, no source external blind, 0 physically matched individual pellets, P0 0/3 and science **NO-GO**. [Actual science report](docs/PHASE3_ORIGINAL_PROCESS_HOLDOUT_0168.md).

**Red Team scientific P0 remain 0/3 closed:** [#304](https://github.com/wt2018mask/Rhombus/issues/304) new externally sealed blind, [#305](https://github.com/wt2018mask/Rhombus/issues/305) exact selected MACE training frames, [#306](https://github.com/wt2018mask/Rhombus/issues/306) independently authenticated paper/specimen/phase/temperature. Next **0153-B** seeks genuinely accessible full primary texts/supplementary tables to check specific source rows and occupancy, without guessing unavailable measurements or preemptive MD.

### Public experimental lithium-conductivity benchmark: actual accomplishments

| Evidence stage | Actual count | Scientific meaning |
| --- | ---: | --- |
| Pinned original OBELiX experimental records | **599** | 478 official TRAIN, **121 original public TEST kept outside developer worklists** |
| Reproducibly published OBELiX TRAIN diagnostic records | **478** | Canonical source-row SHA256, DOI, CIF match signal, conservative source-overlap review and conductivity metadata |
| Raw experiment upper bounds among published TRAIN rows | **29** | 28 original `<1E-10` and one `<1E-8` S/cm; transformed `1e-15` surrogate **must never be scored as a measured point** |
| Other raw reported positive numeric TRAIN values | **449** | Experimental source *metadata*, **not** independently authenticated truths |
| Independently acquired CaltechDATA/McHaffie original CSV | **571** | Original MD5 `d1fcf7c9a7694c8f466932721b76b168` and SHA256 `868c4bd793d7c31b929787dc69478691b27ced0440d19269075143c98ecd1545` verified; **rights for redistributing source rows not cleared** |
| Caltech records sharing an exact DOI with public OBELiX TRAIN | **225** | Overlap **signals only**; remaining 346 are **not verified independent materials** |
| Shon–Min first-party source original JSON | **4,924 original JSON root entries** | Original 7,063,926-byte Git file independently authenticated; **not** 4,924 measured Li material records, original reuse licence unclear; raw data not republished |
| Other registered source candidates awaiting primary-source validation | **4** | Liverpool Ionics, Laskowski, DDSE 2.0 and SPSE; rights, primary source and exact measurement scope pending |
| Newly independently science-qualified experimental materials | **0** | Count of underlying independent physical samples remains **unknown** |
| Legacy known-material minimal benchmark | **6 materials** | Historical diagnostic: two each POSITIVE/NEGATIVE/BORDERLINE, **not** a high-power external blind validation |

These numbers are **distinct denominators**. In particular, **478 + 571 must not be described as 1,049 independent benchmark materials**. The new benchmark is a **PUBLIC DIAGNOSTIC source-traceability catalogue**, not a final model leaderboard or new sealed blind qualification. The Caltech CSV was acquired and audited in a GitHub Actions job but is **not** redistributed or added to scored material counts while its rights, exact experiment temperatures, phase and sample identities are unresolved.

**Current scientific release: NO-GO.** Three major red-team P0 blockers remain: (1) previously public held-out identities/truth are contaminated for strong blinding; a newly externally governed sealed cohort is required, (2) exact MACE-MPA-0 selected training structures and preprocessing are not independently authenticated, and (3) the six legacy material-level samples provide insufficient statistical precision. Original paper/sample/phase/temperature/bulk-versus-total evidence and material overlap must be adjudicated before measured transport values become scientific scoring truth. Real source runs or passing GitHub CI do **not** resolve these P0 requirements.

**Source/version entry points:** [0135 public diagnostic and original Caltech acquisition](docs/PHASE3_PUBLIC_TRANSPORT_BENCHMARK_0135.md), [0134 censored experimental label policy](docs/PHASE3_CENSOR_AWARE_POLICY_0134.md), [0133 original Excel censor recovery](docs/PHASE3_OBELIX_RAW_CENSOR_0133.md), [source rights registry](data/benchmarks/public_transport/source_registry_0135.json), [verifiable 0135 experiment receipt](data/development/phase3_public_benchmark_0135_evidence_v1.json), [continuing multi-source acquisition issue #300](https://github.com/wt2018mask/Rhombus/issues/300). The reproducible workflow uses public source data with no required Kaggle GPU run.

### Actual 0136 source-quality evidence — merged PR #301

The [new 0136 real-source audit](https://github.com/wt2018mask/Rhombus/actions/runs/38108708936)
has successfully checked the original 571 Caltech records against exact
source digests and the original 478 public OBELiX TRAIN review subset:
**571** positive finite source-conductivity numbers, **569** usable
`10.` DOI entries, **135** numeric *lowest extrapolation temperatures*,
**134** five-field-complete *manual source-review candidates*, and
**56** of those without an exact OBELiX TRAIN DOI overlap signal.
The 56 are **not** certified novel/independent materials.
Scientific temperature, actual sample structure, original publication
evidence and permitted use remain unresolved; **scientific GO stays
false**. Details:
[0136 source-quality evidence](docs/PHASE3_PUBLIC_BENCHMARK_QUALITY_0136.md).
The `main` commit printed above is the verified 0135 *start* baseline,
not a representation that PR #301 has already merged.

### Actual 0137 third primary-source acquisition — PR #302 (merged)

The [original first-party Shon/Min source audit](https://github.com/wt2018mask/Rhombus/actions/runs/38110061878)
passed at a prior PR SHA and verified the immutable Git object
`b0e8a20c8806aec337e3547fbd0101094cd4f624` and file SHA256
`4d7c50ed3ddf21f47c88e81625695d1a526c93003fee2e9e7cbb3a39d788b809`.
The original JSON root is an **array with 4,924 entries and 159,720
value nodes**. This is a **raw author-export census, not the 4,032
measurements quoted in earlier secondary studies and emphatically
not 4,924 independently verified Li solid electrolytes**. The source's
per-row contents are not redistributed without verified rights; a
metadata-only original-source audit was uploaded instead. See
[0137 Shon primary-source provenance](docs/PHASE3_PUBLIC_SOURCE_ACQUISITION_0137.md).
Scientific independent-material and external-blind gates remain **NO-GO**.

### Next: 0139 original-author Shon extraction quality triage and independent P0 closure preparation

**Priority one** is to inspect the exact Caltech original CSV without republishing licence-unresolved rows; generate auditable aggregate classifications of DOI/structure-code evidence, upper-limit/temperature/phase ambiguities, and source-record suitability for different tasks. The source funnel must keep `downloaded`, `source-verified`, `rights-cleared`, `temperature-and-quantity-compatible`, `structure/sample-bound`, and `independent-scientifically-qualified` separate. Future Liverpool/Laskowski/Shon–Min/DDSE/SPSE intake will reuse this contract; any new physical-sample claim requires direct evidence rather than a DOI nonmatch or identical formula.

---

## Verified development status — 2026-10-09

**Checkpoint 0118 (CI pending) — Critical red-team remediation:** The 2026-10-09 adversarial scientific/security audit is now integrated as an 11-finding, six-stage **R0–R5 fail-closed development plan**. All **P0 scientific claims remain NO-GO**: public B3 HELD_OUT and truth are already contaminated for independent qualification (the existing guard blocks strong blind claims), MACE-MPA-0 selected MPTrj/sAlex training frames are not attested, and 2 scoreable materials per role are insufficient for precise generalization statistics. P1 tracks effective branch protection **unknown pending GitHub administrator confirmation** (API returns 403), opaque compressed-artifact scanning, non-consumable sAlex `armed` launch, and real Kaggle interruption/resume not yet proven; P2 tracks Arrhenius rank/temperature degeneracy, fractional charge coercion and environment drift. The audit's #281 initial-head CI FAIL is **historical**: final #281 merged at `e1e6317` after all required tests and real two-job *synthetic* GitHub artifact roundtrip passed. No findings are prematurely marked resolved and no original-source/Kaggle full run is authorized. [Adversarial remediation roadmap](docs/PHASE3_REDTEAM_REMEDIATION_PLAN_V1.md).

**Checkpoint 0117 (merged):** A **synthetic eight-row SQLite checkpoint** is now uploaded to GitHub Actions Artifacts and independently downloaded in a second runner job, with per-part and reassembled SHA256 validation, SQLite quick_check, and exact artificial row verification. This small real GitHub artifact-service roundtrip uses only artificial data, no Kaggle secret and no scientific source bytes. It does **not** prove Kaggle cross-session checkpoint persistence, long-term storage, or interruption-safe provider resume. [Roundtrip procedure](docs/PHASE3_GITHUB_SYNTHETIC_CHECKPOINT_ROUNDTRIP_V1.md).

**Checkpoint 0116 (merged):** Upstream **MACE-MPA-0 medium** model identity has a new bounded evidence lead: ACEsuit/mace [official golden test implementation](https://github.com/ACEsuit/mace/blob/0f5de4b15d9c7f86d4e50996533ecf6c0f48a51b/tests/golden/foundation_artifacts.py) reports exact checkpoint SHA256 `75428afe3a1d7d8062e19bcaabd5c433623cabf308242ec9fb493e38604fb638` and asserts the tracked model and same-named GitHub release binary match. This is an **upstream-reported SHA256** (not a Rhombus independently computed hash of the 79,462,305-byte release asset). The official model declares MPTrj+sAlex data families, but exact checkpoint-selected frame lists, preprocessing, label selection and complete MPTrj source SHA256 remain **UNATTESTED**. No training exposure/generalization claim or large computation is newly authorized. New offline inventory and fail-closed tests make this distinction machine-checkable. [Publisher checkpoint digest scope](docs/PHASE3_MPA0_PUBLISHER_CHECKPOINT_SHA256_EVIDENCE_V1.md).

**Checkpoint 0115 (merged):** Recovered useful, unmerged *offline-only* checkpoint restoration and multipart bundle verifiers from stale stacked PRs [#218](https://github.com/wt2018mask/Rhombus/pull/218) and [#219](https://github.com/wt2018mask/Rhombus/pull/219) onto current canonical main as [PR #279](https://github.com/wt2018mask/Rhombus/pull/279), without merging the old checkpoint 0056/0057 state. `verify_staged_checkpoint` verifies bounded manifest + staged bytes SHA256; `pack_checkpoint_parts` and `verify_checkpoint_parts` package and independently rehash fully finalized local files with fail-closed source/science flags and interruption/tamper regression tests. **No GitHub remote upload, restartable Kaggle shard, SQLite integrity attestation or MACE training lineage is established.** Once all PR checks pass and the code merges, old PRs may safely be closed as superseded. [Checkpoint recovery guide](docs/PHASE3_CHECKPOINT_RESTORE_BUNDLE_RECOVERY_V1.md).

**Checkpoint 0114 (merged):** Real, user-approved **MPTrj 1MiB manual pilot** [run #37937653254](https://github.com/wt2018mask/Rhombus/actions/runs/37937653254) succeeded on `main` SHA `c5ccf2da207f9dc4874c436e46d32b4a31a1ad8f`. Frozen 256KiB original prefix SHA256 and actual 1MiB digest verified; **16 complete frames** (the 16-frame cap, **tail uninspected**) from just **3 material IDs** (6/8/2 frames). All 16 report three energy field presences. Runner-local capped Range **1,862ms** and frame inspection **11ms** are *not full 12.2GB projections*. The exact original GitHub **1,120-byte metadata ZIP** (sha256 `5413d90c1f5087b831ceec1ad4707b21f3281db3bd84f98fa100766fc3f5678d`), 7,246-byte JSON member, review receipt and digest-bound manifest are preserved in `data/development/observations/mptrj-1mib-run-37937653254/`, with offline replay and tamper rejection before seven-day artifact expiry. Whole-source identity, MACE-MPA-0 training membership and generalization remain unauthenticated. No new MPTrj or Kaggle source processing was launched. [Bounded 1MiB pilot](docs/PHASE3_MPTRJ_MANUAL_1MIB_MULTIFRAME_V1.md).

**Checkpoint 0113 (CI pending):** The optional **MPTrj 1MiB original-source manual pilot** can now be verified against an exact successful GitHub Actions `main` run and its one metadata-only ZIP: the new `scripts.development.review_mptrj_1mib_github_run` checks HEAD SHA, run attempt, named artifact SHA256, immutable bounded ZIP snapshot, preserved real first-256KiB identity, 1MiB frame count and separately scoped runner-local timings. Strict read-only two-GET review requires `--live-review` and cannot dispatch workflows or download full MPTrj. **Actual 1MiB real-source pilot has NOT been executed**; future use requires explicit operator `run_1mib_probe=true`. The sAlex local checkpoints from 0112 do not guarantee external persistence; large Kaggle rerun remains gated. [1MiB pilot guide](docs/PHASE3_MPTRJ_MANUAL_1MIB_MULTIFRAME_V1.md).

**Checkpoint 0112 (CI pending):** Future **sAlex Kaggle** production runs now emit *locally staged* committed partial results: after each 50,000 SQLite-committed membership records, a complete gzip JSONL archive and SHA256/row-range receipt is sealed in `/kaggle/working/rhombus_salex_partial_chunks/`, and a structured progress event is flushed to stdout. A source interruption does not retroactively qualify incomplete segments; unsealed `.inflight` files cannot be replayed as science. **These are NOT guaranteed remotely retrievable during a Kaggle run or after worker termination.** Durable external upload, independently completed source shards and resumable exact-coverage validation remain separate unfinished work. No Kaggle computation or source transfer was triggered. [Partial-checkpoint guide](docs/PHASE3_SALEX_PARTIAL_CHUNK_RECOVERY_V1.md).

**Checkpoint 0111 (CI pending):** Following the first real WBM source-profile evidence freeze, the optional **MPTrj 1MiB manual multi-frame** GitHub Actions workflow now requires explicit `run_1mib_probe=true` (default false) and performs a **no-network runtime/frozen first-frame baseline preflight before any source GET**. It imports the required parser modules, verifies the prior real 256KiB Git-retained ZIP/receipt, pinned 12,188,168,685-byte source total and exact 1MiB Range cap. Failure prevents the original source request; successful opt-in still produces metadata-only evidence and cannot attest full-source SHA256, MACE-MPA-0 training-frame selection or unseen generalization. No new MPTrj source download or Kaggle run was initiated. [Manual 1MiB pilot guide](docs/PHASE3_MPTRJ_MANUAL_1MIB_MULTIFRAME_V1.md).

**Checkpoint 0110 (CI pending):** The first **real**, opt-in WBM v2 original-source profile [#37929699171](https://github.com/wt2018mask/Rhombus/actions/runs/37929699171) completed: frozen SHA256/MD5, **256,963 original initial structures**, and source-only histograms verified. Actual **v2 composition buckets: 168,150**; legacy composition+sitecount buckets: **195,549**; **21,700** v2 buckets contain differing site counts; largest **v2 22 vs v1 14** targets. Index-only equal-target-weight pair proxy **596,225 v2 vs 433,549 v1**, about **37.5% larger**—NOT a full MPTrj runtime or transfer forecast. Original GitHub 882-byte ZIP, the 1,608-byte JSON report, review receipt and digest-bound manifest are preserved locally and replayed in offline CI so GitHub's seven-day artifact expiry cannot erase this small metadata-only observation. No raw WBM gzip or full MPTrj/sAlex recomputation; scientific applicability and model training remain blocked. [Source-profile guide](docs/PHASE3_V2_CANDIDATE_BUCKET_RESOURCE_PREFLIGHT_V1.md).

**Checkpoint 0109 (CI pending):** Real operator-dispatched [WBM v2 manual run #37927676486](https://github.com/wt2018mask/Rhombus/actions/runs/37927676486) successfully downloaded the frozen ~47.2MiB original gzip and passed MD5+SHA256 but **failed before analysis** on missing `ijson` transitive import. The manual workflow's constrained install now includes `ijson==3.5.1` and a focused no-network regression asserts the runtime dependencies and approval/cleanup boundaries. **Do not rerun the old failed attempt** (old code SHA); after CI and merge, use a new manual `workflow_dispatch` with explicit true opt-in. No original WBM v2 profile artifact was produced by that failed attempt. [Operator guide](docs/PHASE3_V2_CANDIDATE_BUCKET_RESOURCE_PREFLIGHT_V1.md).

**Checkpoint 0108 (CI pending):** WBM v2 original-profile ZIP review now **bounds the actual file read to 512KiB plus one byte**, rather than trusting an earlier file-size stat before unbounded `Path.read_bytes()`. A concurrent ZIP growth/replacement is rejected without proportional memory allocation; accepted JSON is still parsed only from the exact ZIP bytes used for SHA256 proof. Offline fixture regressions cover growth between stat/open, absence of unbounded file reads and prior pathname swaps. This is local artifact review hardening, not execution of the still-unrun original WBM profile. [Source-profile guide](docs/PHASE3_V2_CANDIDATE_BUCKET_RESOURCE_PREFLIGHT_V1.md).

**Checkpoint 0107 (CI pending):** WBM v2 target-index preflight and subsequent original MPTrj source-only comparisons now share **one SQLite read transaction/snapshot**, rather than independently observing target DB rows that another process could replace after validation. WAL concurrent-writer regressions check that verified target JSON remains stable during matching, a fresh reader refuses modified targets and aborted readers release the snapshot. A long source read can pin WAL history, so concurrent index writers must be avoided in production. No original WBM/MPTrj source fetched. [Index protocol guide](docs/PHASE3_MPTRJ_WBM_INDEX_PROTOCOL_BINDING_V1.md).

**Checkpoint 0106 (CI pending):** The source-only MPTrj↔WBM comparator now performs **no-network consistency checks between the actual stored WBM target `structure_json` and its indexed v2 composition/site-count fields** before any costly MPTrj download. Previous hash checks bound only an index field to another index field. Fixture regressions reject fabricated metadata, replaced structures, malformed JSON and supercell site-count drift, but preserve valid supercells. This cannot independently authenticate original WBM bytes or model training selection. [Target-index protocol guide](docs/PHASE3_MPTRJ_WBM_INDEX_PROTOCOL_BINDING_V1.md).

**Checkpoint 0105 (CI pending):** The independent scheduled workflow failed in a real run (#37921275418) because legacy installation omitted Phase 3 packages and broad `pytest tests/` collected unsupported optional tests. It now preserves the twice-daily schedule as an explicitly **read-only, bounded offline scientific readiness smoke**, reusing Fast CI's pinned packages, Python module-based pytest, focused WBM v2 evidence tests, compact continuity validation and a 10-minute budget. No scheduled discovery engine, source downloads, Kaggle calculation, DB writes, or scientific promotion. [Scheduled readiness workflow](.github/workflows/cron.yml).

**Checkpoint 0104 (CI pending):** WBM v2 original-profile artifact ZIP verification now SHA256-checks **the same bounded ZIP byte snapshot** used to parse the JSON, closing a second file-open pathname swap gap in live GitHub review and archived replay. Synthetic regression cases exchange the ZIP path after hashing for a valid-but-different profile or corrupt bytes; neither substitutes unchecked data. No original WBM profile executed or scientific claims expanded. [Original WBM v2 evidence guide](docs/PHASE3_V2_CANDIDATE_BUCKET_RESOURCE_PREFLIGHT_V1.md).

**Checkpoint 0103 (CI pending):** The as-yet-unrun original-WBM v2 direct profiler now emits **source-bound, material-ID-free v2 composition and v1 sitecount bucket-size histograms** in report schema v2. Independent live GitHub ZIP and archived offline review derive exact bucket totals, 256,963 target rows, largest buckets and sum-of-squares proxies from those histograms rather than accepting only plausible scalar aggregates. Still **no real original WBM manual profile**, MPTrj runtime measurement, or model training/unseen attestation. [Resource preflight guide](docs/PHASE3_V2_CANDIDATE_BUCKET_RESOURCE_PREFLIGHT_V1.md).

**Checkpoint 0102 (CI pending):** The operator-only WBM v2 original-gzip profiling workflow now enforces one **20-minute aggregate transfer timeout across every curl retry and redirect**, not merely 20 minutes per retry. Existing 2 GiB cap, source MD5/SHA256 verification, raw-source cleanup and metadata-only artifact policy are preserved. No original WBM run or real v2 cost numbers have been observed. [Resource preflight guide](docs/PHASE3_V2_CANDIDATE_BUCKET_RESOURCE_PREFLIGHT_V1.md).

**Checkpoint 0101 (CI pending):** Frozen original WBM profiling now holds the same regular-file descriptor through initial SHA256, bounded gzip JSONL structure parsing, and final SHA256. It rejects a replaced pathname or persistently altered compressed bytes instead of claiming verified source identity from a different file. No real manual WBM run or full MPTrj verification occurred. [Original source profiling guide](docs/PHASE3_V2_CANDIDATE_BUCKET_RESOURCE_PREFLIGHT_V1.md).

**Checkpoint 0100 (CI pending):** Saved manual WBM v2 profile ZIP and the exact opt-in GitHub run-review JSON receipt can now be rehashed and cross-checked entirely offline, even after the 7-day Actions artifact expires. This checks user-preserved evidence consistency only; it **does not reauthenticate GitHub**, independently recompute WBM, or qualify MACE-MPA-0 learning/generalization. No real WBM profile was dispatched. [Archived replay guide](docs/PHASE3_V2_CANDIDATE_BUCKET_RESOURCE_PREFLIGHT_V1.md).

**Checkpoint 0099 (CI pending):** A read-only, opt-in GitHub run/ZIP verifier now ties the 0098 manually produced WBM v2 cost-profile JSON to an exact successful `workflow_dispatch` on main, commit SHA, artifact ID and SHA256. It checks immutable original WBM source identities, 256,963 target count, scientifically safe flags and bucket proxy arithmetic; **no real WBM manual run has been observed** and no signed scientific provenance is claimed. [Operator guidance](docs/PHASE3_V2_CANDIDATE_BUCKET_RESOURCE_PREFLIGHT_V1.md).

**Phase 3 original WBM v2 manual measurement path (checkpoint 0098; CI pending):** a new [GitHub Actions manual-only opt-in workflow](.github/workflows/phase3-wbm-v2-original-profile-manual.yml) can fetch the pinned WBM gzip with a 2GiB/20-minute network cap, check frozen MD5/SHA256, run the bounded 256,963-row v2 bucket profiler, delete original data and upload **JSON metadata only**. Default workflow input is false; PR CI never downloads the original WBM source. No real dispatch or real v2 profile has occurred in this checkpoint. [Operator guidance](docs/PHASE3_V2_CANDIDATE_BUCKET_RESOURCE_PREFLIGHT_V1.md).

**Checkpoint 0097 (fixture-CI pending):** Direct, no-network profiling of original WBM initial-structure gzip: verify frozen complete SHA256 before any structure parsing, validate all 256963 unique material IDs, then derive v2 composition bucket and v1 site-count subbucket fan-out. No SQLite/index construction or reprocessing 10.4M sAlex frames required. Authentic original WBM source not available in current Library; no real profile yet. [Manual offline tool](docs/PHASE3_V2_CANDIDATE_BUCKET_RESOURCE_PREFLIGHT_V1.md).

**Phase 3 v2 candidate-bucket budget preflight (checkpoint 0096; CI pending):** A no-network WBM index profiler reports composition bucket fan-out, mixed-sitecount groups and an index-only comparison proxy. The opt-in complete MPTrj source runner now requires an operator-selected positive candidate-per-frame cap and fails before original source download if the verified index exceeds it. No default budget or original 1MiB/12.2GB source request. [Resource preflight guide](docs/PHASE3_V2_CANDIDATE_BUCKET_RESOURCE_PREFLIGHT_V1.md).

**IMPORTANT PHASE 3 SCIENTIFIC CORRECTION (checkpoint 0095; CI pending):** The v1 candidate fingerprint used **reduced composition plus original site count**, but the near-duplicate matcher may consider primitive/supercell representations with **different original site counts**. This mismatch could silently omit valid near duplicates. A frozen **v2 composition-only candidate bucket** now fixes the prefilter; previous v1 indices are refused for v2 runs. **Historical verified sAlex source-overlap union 1,946 remains a real *detected v1 positive count*, NOT evidence that all near duplicates were enumerated**. In particular 255,017 v1 nonmatches remain unresolved, not known disjoint or MACE-MPA-0-unseen. Original archived source bytes/SHAs and 0093 evidence are retained unchanged. No expensive recomputation authorized. [Correction and migration contract](data/development/phase3_candidate_fingerprint_prefilter_soundness_v2.json) · [Historical sAlex v1 erratum](data/development/phase3_salex_v1_candidate_prefilter_scope_erratum_v1.json).

**Phase 3 source-only MPTrj/WBM matched export SHA256 and offline pair verification (checkpoint 0094; CI pending):** A completed canonical MPTrj whole-source one-pass compare can now bind its **positive-only matched WBM JSONL** to the **aggregate original-source-only report** with a SHA256 over the exact JSONL bytes. A no-network verifier rejects swapped/truncated/tampered files, changed source IDs, unmatched class totals, duplicate material IDs, false frame witnesses, and any model-training or unseen-generalization promotion. **Fixture-tested only: no new real MPTrj 1MiB or 12.2GB source request**, and exact MACE-MPA-0 training lineage remains unknown. [Source target evidence guide](docs/PHASE3_MPTRJ_WBM_SOURCE_TARGET_ROWS_V1.md).

**Phase 3 preserved sAlex source-overlap de-duplicated union (checkpoint 0093; CI pending):** A zero-Kaggle, local-only analyzer can consume the previously preserved, exact compressed-SHA256-bound 369,521-byte sAlex/WBM overlap JSONL.zst and separately hashed 1,185-byte original summary. It stream-validates all 256,963 WBM rows and computes exact/near/prototype intersections, positive union, and source-unresolved remainder without double counting or pretending the remainder is foundation-model unseen. **Actual pre-existing archived source was now independently streamed and verified offline:** all 256,963 rows; **distinct positive sAlex-source overlap = 1,946 WBM structures** (near-only 1,879, prototype-only 53, both 14, exact 0). No new Kaggle computation; no claim that the remaining 255,017 are MACE-MPA-0-unseen. [Frozen offline observation](data/development/phase3_salex_preserved_source_overlap_union_observation_v1.json). [Offline preserved-data analyzer](docs/PHASE3_SALEX_PRESERVED_OVERLAP_UNION_V1.md).

**Phase 3 WBM candidate bucket semantic preflight (checkpoint 0092; CI pending):** Original-source WBM one-pass comparator now **recomputes every frozen candidate fingerprint from stored composition and site count before requesting the full 12.2GB MPTrj file**; index row corruption or incompatible digests are rejected. This is an internal consistency check, not independent source authentication or MACE-MPA-0 training membership evidence. No real source request was made. [Protocol validation](docs/PHASE3_MPTRJ_WBM_INDEX_PROTOCOL_BINDING_V1.md).

**Phase 3 fail-closed WBM target-index protocol provenance (checkpoint 0091; stacked CI pending):** WBM target SQLite indices now record whether the frozen candidate fingerprint and prototype executors actually produced their fields. The MPTrj original-source overlap preflight refuses missing/stale/mismatched indices **before any full original source GET**; custom callbacks are diagnostic-fixture-only. This does not independently attest the SQLite database bytes, establish exact MACE-MPA-0 training frames, or authorize model-unseen claims. [Protocol compatibility contract](docs/PHASE3_MPTRJ_WBM_INDEX_PROTOCOL_BINDING_V1.md).

**Phase 3 deterministic MPTrj source frame witnesses (checkpoint 0090; stacked CI pending):** Positive-only WBM source-overlap rows now carry the **first original MPTrj frame locator** supporting strict equivalence, near duplicate, or prototype-only overlap *separately*. Frame locators are emitted only after complete canonical source identity verification and do not imply these frames trained MACE-MPA-0. No real original 1MiB or full 12.2GB run was made. [WBM source match witnesses](docs/PHASE3_MPTRJ_WBM_SOURCE_TARGET_ROWS_V1.md).

**Phase 3 positive-only WBM original MPTrj source evidence (checkpoint 0089, stacked CI pending):** An optional separate JSONL output records which WBM material IDs had strict/near/prototype overlap with a fully verified canonical original source. Publication occurs only after the whole-file gate; all model-training and unseen-generalization claims remain false. No 12.2GB run or new 1MiB observation was executed. [Source-only material evidence](docs/PHASE3_MPTRJ_WBM_SOURCE_TARGET_ROWS_V1.md).

**Phase 3 original MPTrj↔WBM one-pass source overlap (checkpoint 0088; CI pending):** An explicitly opted-in single-pass source-data-only comparator is now wired into the original full-file MPTrj frame/MD5/SHA256 gate. It queries a *preexisting, source-identity-bound* read-only WBM initial-structure SQLite index, counts strict, near and prototype source overlap, and emits metadata **only after** complete original MPTrj validation. **It is not MACE-MPA-0 training exposure evidence.** No real full source run or optional manual 1MiB observation occurred in this PR. [Source-only comparison contract](docs/PHASE3_MPTRJ_WBM_SOURCE_ONLY_ONE_PASS_V1.md).

**Phase 3 original-source stream redirect security (checkpoint 0087; CI pending):** The **opt-in** 12.2GB MPTrj HTTPS streamer validates every intermediate HTTP redirect before following it, as well as the final response; HTTP, unrelated-domain, nonstandard-port, and credentialed endpoints are refused before downloading redirected content. The original full source and the optional manual 1MiB pilot remain unexecuted. [Resource and provenance gate](docs/PHASE3_MPTRJ_ONE_PASS_REMOTE_SOURCE_GATE_V1.md).

**Phase 3 no-raw-file-staging MPTrj full-source identity (checkpoint 0086; CI pending):** A *separately opted-in* one-pass HTTPS stream verifier can read the pinned original Figshare 12.2GB MPTrj source directly (without a local 12GB raw archive), count every parsed frame, match full byte count and official MD5, and compute one local SHA256. It requires strict HTTP 200, HTTPS redirect, identity response and exact Content-Length. **No full run or network GET was performed by the development PR**, and original MPTrj being valid would still not attest the exact MACE-MPA-0 training selection. [Execution safety gate](docs/PHASE3_MPTRJ_ONE_PASS_REMOTE_SOURCE_GATE_V1.md).

**Phase 3 realistic source-processing budget evidence (checkpoint 0085; CI pending):** The explicit manual-only 1MiB original MPTrj source workflow now reports separately measured Range and bounded frame-parsing elapsed milliseconds in a **v2 metadata-only diagnostic receipt**. This does **not** run automatically, estimate the whole 12.2GB source runtime, or certify MACE-MPA-0 training frame selection. [Pilot review and resource gate](docs/PHASE3_MPTRJ_TIMED_PILOT_RESOURCE_GATE_V1.md).

**Phase 3 full original-source runtime observability (checkpoint 0084; CI pending):** The offline-only 12.2GB MPTrj ijson/frame/MD5/SHA256 verifier now emits **unverified** complete-frame progress and parser-prefetched byte counters to stderr, and refuses a mutable source file or output report collision. No real full source was processed; MACE-MPA-0 selected training frames remain unverified. [Full-source manual guide](docs/PHASE3_MPTRJ_COMPLETE_STREAM_IDENTITY_V1.md).

**Phase 3 operator-dispatched 1MiB real multi-frame observation (checkpoint 0083; CI pending):** A separate manual-only GitHub Actions workflow can, after explicit operator dispatch, perform a bounded 1MiB HTTPS Range source probe and return **only a max-16KiB JSON metadata artifact** covering up to 16 complete frames, anchored to the real prior 256KiB hash. Original manual 256KiB workflow unchanged. No source request was executed by this PR, and source-wide/MACE training claims remain unverified. [Guide](docs/PHASE3_MPTRJ_MANUAL_1MIB_MULTIFRAME_V1.md).

**Phase 3 bounded multi-frame source-adapter readiness (checkpoint 0082; CI pending):** A zero-network local inspector now accepts exactly 256KiB/1MiB raw MPTrj prefixes only when their first 256KiB SHA256 equals the frozen **real** source observation, and records up to 16 fully parsed pymatgen structures with an explicitly unverified tail. The local-only source probe may now optionally capture an explicitly requested 1MiB; original manually dispatched GitHub Actions remains **256KiB metadata-only**. No second actual network observation, full-source verification, or MACE-MPA-0 training membership claim. [Guide](docs/PHASE3_MPTRJ_BOUNDED_MULTIFRAME_V1.md).

**Phase 3 first real source-prefix repeatability (checkpoint 0081; CI pending):** A separately opted-in, **single logical 256KiB HTTPS Range operation** can reparse the first MPTrj frame and compare the observed full prefix SHA256/structure/energy-field presence to the git-frozen first real observation (run #37852263493). This operation is **not executed in this checkpoint**, stores no source bytes and cannot establish full-source identity or MACE-MPA-0 training membership. [Guide](docs/PHASE3_MPTRJ_FROZEN_PREFIX_REOBSERVATION_V1.md).

**First real MPTrj first-frame observation (checkpoint 0080; CI pending):** Manual Actions run [#37852263493](https://github.com/wt2018mask/Rhombus/actions/runs/37852263493) successfully parsed first complete `mp-1005792` / `mp-1012897-0-0` frame (`Sm2CuAs3O`, 28 sites) from a strict 256KiB prefix. The authenticated GitHub API-declared ZIP SHA256 matches the locally reviewed and now preserved 758-byte diagnostic ZIP. The **full 12.2GB source**, original 256KiB raw sample, and MACE-MPA-0 training membership remain **unattested**. [Frozen evidence and limits](docs/PHASE3_MPTRJ_FIRST_LIVE_OBSERVATION_V1.md).

**Phase 3 local raw-prefix replay preflight (checkpoint 0079; CI pending):** Operators may **explicitly** preserve exactly 256KiB of a successful locally run Figshare prefix probe using `--sample-output`, then separately reparse and hash the resulting sample against the diagnostic receipt offline. The GitHub Actions manual workflow still uploads **metadata only** and is unchanged. This is sample/frame integrity, **not** full-source or MACE-MPA-0 training-set attestation. [Guide](docs/PHASE3_MPTRJ_LOCAL_PREFIX_SAMPLE_REPLAY_V1.md).

**Phase 3 machine-readable live review diagnostics (checkpoint 0078; CI pending):** Opt-in GitHub REST reviewer now offers JSON-only stdout with versioned run/artifact hashes and explicit false scientific authorization flags, alongside stricter nonfinite-JSON rejection. This remains read-only, fixture-tested, and is **not** a signed provenance or model-training receipt. [Guide](docs/PHASE3_MPTRJ_LIVE_GITHUB_REST_REVIEW_V1.md).

**Phase 3 opt-in live GitHub REST diagnostic review (checkpoint 0077; CI pending):** A read-only reviewer makes two bounded public GitHub API GET requests for an operator-specified run and artifact, then matches the API ZIP SHA256 to a local ZIP and its single diagnostic receipt. No workflow dispatch, 12.2GB MPTrj transfer or MACE training frame attestation. [Guide](docs/PHASE3_MPTRJ_LIVE_GITHUB_REST_REVIEW_V1.md).

**Phase 3 GitHub artifact digest/ZIP binding (checkpoint 0076; CI pending):** Optional offline ZIP review now requires a canonical GitHub REST artifact `sha256:` digest and checks it against the entire bounded ZIP before parsing the receipt. API JSON is caller supplied and **not origin-authenticated**. No Figshare live read, scientific promotion, or workflow dispatch. [Diagnostic ZIP guide](docs/PHASE3_MPTRJ_DIAGNOSTIC_ARTIFACT_ZIP_V1.md).

**Phase 3 diagnostic artifact ZIP byte binding (checkpoint 0075; CI pending):** An offline bounded ZIP inspector checks that a locally downloaded manual Actions diagnostic archive contains exactly one safe JSON member whose uncompressed bytes match a locally supplied receipt. No extraction, remote data transfer, science claim, or workflow dispatch; **local equality does not authenticate GitHub artifact origin**. [Guide](docs/PHASE3_MPTRJ_DIAGNOSTIC_ARTIFACT_ZIP_V1.md).

**Phase 3 manual-run GitHub metadata review (checkpoint 0074; CI pending):** A bounded, offline operator tool checks a manually saved GitHub Actions run and artifact-list JSON against the exact authorized workflow, `main` SHA and earlier strict diagnostic receipt. Saved JSON is **not** authenticated by this check, and receipt bytes are **not** cryptographically bound to the named artifact. The manual probe has **not** been dispatched by this change; exposure, calibration and MACE-MPA-0 training provenance remain closed. [Review guide](docs/PHASE3_MPTRJ_MANUAL_RUN_METADATA_REVIEW_V1.md).

**Phase 3 MPTrj source-prefix receipt validation (checkpoint 0073; CI pending):** The **manual-only** 256KiB Figshare first-frame Actions probe now runs a strict **offline metadata receipt validator before upload**: confirms frozen file ID/declared total, first frame and structure IDs, bounded numeric metadata, canonical digest syntax and explicit false scientific authorization fields. Rejects malformed, duplicate-key, oversized or claim-promoting JSON. A passing report is **diagnostic schema validation only**, not authentic GitHub run provenance, full MPTrj original source hash, MACE-MPA-0 training selection, or unseen-generalization evidence. **No real prefix request or Kaggle run has been initiated.** [Receipt validation guide](docs/PHASE3_MPTRJ_PROBE_RECEIPT_VALIDATION_V1.md).



**Phase 3 MPTrj manual limited source observation (checkpoint 0072; CI pending):** Add a **workflow_dispatch-only** GitHub Actions job to request at most the initial **256KiB** of the frozen MPTrj Figshare file (strict HTTP 206 only) and parse the first complete `pymatgen Structure`. HTTP 200 is rejected before reading; no bulk fallback, no Kaggle, no automatic start, no secrets, and artifact retention is 7 days for a **small diagnostic JSON only**. **No live source fetch has occurred**, and such an observation cannot attest the full MPTrj source or MACE-MPA-0 training selection. [Manual-only Actions operator guide](docs/PHASE3_MPTRJ_MANUAL_ACTIONS_PROBE_V1.md).



**Phase 3 checkpoint-bound MACE-MPA-0 lineage review (checkpoint 0071; CI pending):** Official MACE model release asset and the public declared **MPTrj + sAlex** training datasets are now separated from missing checkpoint-bound selected-frame, preprocessing, and energy-label manifests. A new fail-closed checklist requires those artifacts **for both datasets** before independent review; even a complete synthetic checklist does **not** authorize training exposure, calibrated uncertainty, or unseen-generalization claims. [Guide](docs/PHASE3_MPA0_CHECKPOINT_LINEAGE_REVIEW_V1.md). No 12GB input read, live Figshare prefix probe, Kaggle compute or checkpoint download performed.



**Phase 3 MPTrj complete-first-frame range check (checkpoint 0070; CI pending):** The existing 256KiB-default/1MiB-max HTTPS 206-only Figshare prefix inspector now optionally validates the **first complete pymatgen Structure**, its frame identity and energy-label **field presence** using `--require-complete-frame`. Synthetic fixtures test truncation, invalid Structure, duplicate fields and HTTP 200 rejection. This is **not** full source coverage, whole-file SHA256, a checkpoint-bound MACE-MPA-0 training frame manifest, or unseen generalization evidence. No actual Figshare prefix GET or Kaggle compute has been executed. [Complete-first-frame guide](docs/PHASE3_MPTRJ_FIRST_FRAME_COMPLETE_PROBE_V1.md).



**MPTrj frame energy label provenance (checkpoint 0069, PR #233 pending):** Streamed MPTrj frames now retain source-observed raw DFT total, MP2020 corrected total and CHGNet-corrected per-atom energies as separate optional labels. Neither MPTrj energy-label availability nor public MACE-MP raw VASP training declarations attest **MACE-MPA-0** selected training frames/labels. Scientific calibration and unseen-model generalization authorization remain **closed**. No 12GB source download, live prefix or Kaggle run. See [energy-label guide](docs/PHASE3_MPTRJ_ENERGY_LABEL_LINEAGE_GUARD_V1.md).



**Phase 3 MPTrj source-prefix probe (checkpoint 0068; pending CI):** An explicit opt-in, bounded HTTPS Range inspector can test the original Figshare MPTrj file's initial `mp-id → frame-id → structure` hierarchy using **at most 1MiB** (default 256KiB). If the source server ignores HTTP Range and returns 200, the inspector fails before reading the body; it never falls back to a 12.2GB download. Currently **fixture-tested only; no actual live prefix requested, source MD5/SHA256 computed, or full source parsed**. [Guide](docs/PHASE3_MPTRJ_RANGE_PREFIX_PROBE_V1.md). Exact MACE-MPA-0 training frame selection remains unattested and scientific exposure/generalization claims stay closed.



**MPTrj source integrity checkpoint 0067:** The original Figshare MPTrj v2 API confirms its licence is **MIT**, correcting the erroneous checkpoint 0066 CC BY 4.0 erratum via [append-only final correction](data/development/phase3_mptrj_figshare_license_final_correction_v1.json). A new offline-only, fixture-tested full-source reader verifies frame coverage, full size, official MD5 and computes SHA256 **only after complete stream consumption**. The original 12.2GB file has NOT been downloaded or parsed; MACE-MPA-0 exact training-frame membership remains UNATTESTED. [Full-stream verification contract](docs/PHASE3_MPTRJ_COMPLETE_STREAM_IDENTITY_V1.md).



**Phase 3 MPTrj streaming adapter (checkpoint 0066; PR #230 pending):** An optional `ijson`-based nested `mp-id → frame-id → Structure` reader now streams bounded individual frames with duplicate-key and malformed-record rejection, stable RFC 6901 source locators, and **synthetic fixture tests only**. No 12GB original MPTrj was downloaded/hashed, no source-verified production MPTrj membership index exists, and MACE-MPA-0 exact training representation remains **UNATTESTED**. [Adapter guide](docs/PHASE3_MPTRJ_STREAMING_ADAPTER_V1.md). **License correction (checkpoint 0067):** the original Figshare MPTrj v2 licence is **MIT**, as in the initial frozen metadata; the earlier CC BY 4.0 erratum was erroneous and is [superseded by a final append-only correction](data/development/phase3_mptrj_figshare_license_final_correction_v1.json).



**Phase 3 MPTrj first step (checkpoint 0065; CI pending):** Canonical Figshare v2 source metadata was independently reviewed (file ID `41619375`, 12,188,168,685 bytes, official MD5). An **offline-only, bounded-memory whole-file hash verifier** and fail-closed regressions were added, with an optional no-overwrite source-identity report. **No 12GB file has been downloaded or fully hashed by this change.** Public MACE-MPA-0 training-set declarations (MPTrj+sAlex) do **not** attest an exact training-byte representation; full MPTrj exposure audit and unseen-generalization claims remain unauthorized. [MPTrj source verification guide](docs/PHASE3_MPTRJ_SOURCE_VERIFICATION_V1.md).



**Draft archive tool (checkpoint 0061, pending CI):** [`archive_salex_evidence.py`](scripts/release/archive_salex_evidence.py) verifies all six preserved compressed pieces, both concatenated stream SHA256 values, and the byte-checked summary before optionally uploading a **DRAFT-only** GitHub Release. It validates GitHub-reported release asset digests and refuses automatic publication or asset replacement. This is a local operator workflow because the raw science bytes are only in prior user file uploads and cannot be fetched by GitHub Actions. See [Windows instructions](docs/PHASE3_SALEX_GITHUB_RELEASE_ARCHIVE_V1.md). **No GitHub Release assets have been uploaded by this change.** Original run receipt raw bytes are still unavailable; scientific claim gates stay closed.

**Phase 3 sAlex output preservation (checkpoint 0060):** The complete Kaggle CPU run (immutable commit `643b8a260b6f...`) previously completed. Its **six compressed original archive parts** were rediscovered in user-provided ChatGPT Library files and independently rechecked: all six per-part SHA256 and both reconstructed compressed-stream SHA256 hashes match the original local verification report, and the saved summary JSON's SHA256 matches. The earlier local report also records 10,447,765 sAlex SQLite rows, 256,963 WBM JSONL rows and `PRAGMA quick_check=ok`. These full raw checks have **not** been repeated at checkpoint 0060. **Original raw receipt JSON and successful remote GitHub artifact upload are still unavailable.** Actions [#37780385110](https://github.com/wt2018mask/Rhombus/actions/runs/37780385110) failed because the proposed results recovery dataset ref was `NOT_FOUND`; the historical Kaggle private *request* dataset was a separate input-delivery mechanism. **Do not rerun the long computation or recreate an unverified dataset slug.** See [local preserved-evidence record](data/development/phase3_salex_preserved_local_evidence_v1.json). Full MPTrj training lineage remains unattested; no unseen-generalization claim is authorized.

**Phase:** Rhombus 2.0 Phase 3 / Domain Map C0–C4 (active). Phase 0–2 foundations are frozen. The compact authoritative handoff is [`data/development/CURRENT.json`](data/development/CURRENT.json); scientific completeness still requires independent evidence.

**Integration status:** [PR #210](https://github.com/wt2018mask/Rhombus/pull/210) merged as `7debf1d0d557bc105027e9a01e8e347b3e6d4444` (checkpoint 0048), adding host-bound read-only scientific task status. [Draft PR #211](https://github.com/wt2018mask/Rhombus/pull/211) records **checkpoint 0049 recovery-readiness documentation only**; it does not change the in-flight Kaggle kernel, launch request, controller YAML or scientific execution code.

### Active Kaggle sAlex/WBM full-run: do not conflate polling and progress

| Component | Current evidence / boundary |
|---|---|
| Source expectation | Frozen sAlex: **10,447,765 structures**; frozen WBM initial structures: **256,963 targets**. |
| In-flight compute identity | CPU kernel `wt2018mask/rhombus-salexcpu-643b8a260b6f` tied to merged [PR #198](https://github.com/wt2018mask/Rhombus/pull/198), exact commit `643b8a260b6fcff78bb02f3a63f348c29fd91317`. |
| Current observed report | User reports notebook runtime beyond 28,000 seconds and GitHub controller polling past 200 status checks. **No independently verified full-run completion receipt yet.** This is a reported runtime snapshot, not a provider-state attestation. |
| Controller semantics | `Poll Kaggle terminal state` queries at ~60-second intervals up to 300 times per controller, then dispatches `resume` if not complete, `retrieve` upon `COMPLETE`, or saves a sanitized error log upon `ERROR`. A logged status query does not mean the provider returned `RUNNING`. |
| Durability risk | Current driver keeps provisional membership SQLite in `/kaggle/temp`; it emits independently retrievable archive parts and final receipt only after complete processing. Interrupted partial data are **not guaranteed retrievable or qualified**. |
| Success rule | Require Kaggle COMPLETE, independent GitHub output retrieval, frozen hashes, full row counts and complete receipt before declaring the sAlex/WBM component verified. |
| Outstanding science | MPTrj canonical source identity and training-lineage audit are unresolved. Held-out qualification remains sealed; unseen-generalization claims are **not authorized**. |
| Recovery plan | [Phase 3 Kaggle recovery playbook](docs/PHASE3_KAGGLE_RECOVERY_PLAYBOOK_V1.md) documents COMPLETE/ERROR/TIMEOUT procedures and future progress telemetry, shard checkpointing, bounded resume and deterministic merge requirements; these engineering improvements are **not yet implemented**. |

**Operational hold:** Do not cancel or resubmit the existing production kernel, rewrite the old exact-commit request, or treat GitHub workflow steps as scientific progress. Future continuation may wait on `kaggle-production` GitHub Environment approvals; the exact-commit `resume`/`retrieve` exception must remain available until recovery/retrieval is complete.

For details see [Development handoff](docs/DEVELOPMENT_HANDOFF.md), [Security operations](docs/SECURITY_OPERATIONS.md), and [Kaggle recovery playbook](docs/PHASE3_KAGGLE_RECOVERY_PLAYBOOK_V1.md).

---

## Executive decision

**Rhombus will not be rewritten from scratch.**

The existing repository remains the canonical project. Historical v1/B-series evidence stays immutable. Rhombus 2.0 will be built beside the legacy pipeline and progressively replace scientific decision logic only after each new capability is independently validated.

This is intentionally a **Strangler-style migration**:

```text
existing validated infrastructure
        │
        ├── retained as historical evidence
        │
        └── wrapped by compatibility adapters
                     │
                     ▼
             Rhombus 2.0 evidence graph
                     │
                     ▼
             new scientific capabilities
```

A clean rewrite would discard some of the project's most expensive assets: accumulated scientific failure cases, representation semantics, provenance contracts, workflow evidence, and CI regressions.

Simply extending the old P0/P1/P2/... sequence indefinitely would create the opposite problem: new science would remain constrained by historical stage boundaries.

Rhombus 2.0 therefore keeps the repository and validated machinery while allowing the scientific architecture itself to change.

---

## Development continuity / cross-chat recovery

Development is resumable from the repository with bounded context cost.

Normal recovery reads **only** `data/development/CURRENT.json` first. It stores
a small rolling state and a SHA-256-bound immutable baseline. Run
`python scripts/development/continuity.py resolve --ref KEY` to obtain any
current or inherited evidence pointer. `resolve` returns all effective state;
`resolve --baseline` returns complete prior metadata. Missing or invalid
snapshots stop recovery. Detailed files are opened only when the next action
requires them.

`data/development/checkpoints/` stores tiny append-only delta events for audit;
normal recovery never replays the full history. `docs/DEVELOPMENT_HANDOFF.md`
is a deterministic rendering of the verified effective state, including all
inherited evidence pointers and state codes.

Every PR must update CURRENT, add exactly one compact event, regenerate the
handoff, and pass **Development Continuity** CI. CI also bounds CURRENT/event
size so recovery cost does not grow with project age.

---

# 1. Project objective

Rhombus 2.0 aims to build a reproducible scientific discovery system that:

- explores solid-ion-conductor chemical and structural space broadly;
- can operate without paid APIs, paid DFT, or paid compute in its core path;
- records exactly what evidence supports every scientific claim;
- can ingest and normalize evidence produced by external scientific tools without treating tool output as an automatically authorized scientific claim;
- binds strong claims to explicit protocol identity, model identity/lineage, applicability, uncertainty, limitations, and audit provenance;
- explicitly represents applicability domain and uncertainty;
- distinguishes physical failure from representation, model-domain, evidence, and infrastructure failure;
- selects expensive calculations only when they are scientifically informative;
- supports expansion across structural families and mobile-ion chemistries without rewriting core contracts;
- measures prospective discovery reliability rather than assuming it from retrospective benchmarks.

The primary optimization target is:

```text
useful scientific information gained
────────────────────────────────────
       unit of scarce free compute
```

Rhombus should not optimize for the number of candidates processed.

---

# 2. Non-negotiable scientific principles

The following remain project invariants.

1. **Missing evidence is never PASS.**
2. Physical material failure must remain distinct from:
   - operational ERROR,
   - representation failure,
   - unsupported model domain,
   - insufficient evidence,
   - unqualified extrapolation.
3. Ionic conductivity, self-diffusion, tracer diffusion, hopping, and collective transport are related observables but are not interchangeable truths.
4. A universal MLIP is not automatically a universal scientific authority.
5. Foundation-model non-exposure must not be claimed unless training-exposure evidence supports it.
6. Historical results remain historically true records and are never silently reinterpreted.
7. Scientific protocol versions become immutable once qualified.
8. Scientific changes after qualification require a new protocol version and appropriate revalidation.
9. Held-out evidence is not repeatedly reused until it becomes development data.
10. The final result must not collapse into a single opaque scalar score.
11. Every strong claim should expose:
    - evidence identity,
    - protocol identity,
    - model identity,
    - applicability,
    - uncertainty,
    - limitations,
    - provenance.

---

# 3. Current project state

Rhombus v1.0.0 remains an immutable historical baseline.

The original canonical scientific sequence is:

```text
E → G → P0 → P1 → P2 → P2.5 → P3 → X → N → S
→ Application compatibility → Final Claim Vector → OUT
```

Historically:

- **E** — empirical anchors / source materials
- **G** — candidate acquisition and generation
- **P0** — static existence/basic plausibility
- **P1** — MLIP relaxation
- **P2** — finite-temperature structural stability
- **P2.5** — transport-regime screening
- **P3** — transport MD
- **X** — independent-model cross-check
- **N** — novelty assessment
- **S** — synthesis-oriented assessment
- **Application** — application-profile qualification
- **Final Claim Vector** — conservative conjunction of required claims
- **OUT** — immutable evidence output

This sequence remains authoritative for historical records but is **not assumed to be the final Rhombus 2.0 architecture**.

## Current benchmark state

The known-material benchmark remains active because it is an important falsification harness.

Its purpose is:

> **Does the scientific machinery behave honestly on known real materials?**

It does **not** prove global generalization across material space.

Current high-level benchmark roadmap:

```text
B0 Scientific Benchmark Contract          complete
B1 Source-bound Truth Records             complete
B2 Evidence / structure curation          complete
B3 DEV / HELD_OUT split                   frozen
B4 Ingress / provenance / readiness       complete for current cohort
B5 DEV execution + falsification          active
B6 Legacy science freeze                  deferred pending v2 architecture
B7 Legacy one-shot held-out               deferred
B8 Legacy unblind / qualification         deferred
```

The existing repository-visible v1 HELD_OUT cohort is not sufficient for strong blind qualification. A future qualification cohort must remain externally sealed until execution.

Candidate Supply v2 production remains paused.

## Current B5 frontier

Real P1 relaxation has already been executed for the currently authorized DEV units.

The currently P2-authorized cohort is:

- gamma-LiAlO2 direct structure;
- hexagonal LiBH4;
- orthorhombic LiBH4.

Cubic Al-stabilized LLZO remains intentionally held at P0 `INDETERMINATE` rather than being forced downstream.

A real 550 K P2 pilot on gamma-LiAlO2 exposed multiple important issues and therefore fulfilled the purpose of the benchmark:

- oxidation-state-bearing species such as `Li+` initially bypassed mobile-ion detection;
- species normalization was corrected generically;
- real equilibration still terminated through the existing explosive-abort condition;
- numerical-abort provenance was extended to retain the abort phase, MD step, sample index, step jump, configured threshold, instantaneous temperature, energy, force, and finite-state evidence.

Canonical development state is no longer recovered from a README commit hash. Read `data/development/CURRENT.json` first and dereference only the evidence and policy files needed by its current frontier.

---

# 4. Existing assets that Rhombus 2.0 should preserve

The most valuable parts of Rhombus are not its stage names. They are the infrastructure and scientific discipline accumulated while building them.

| Existing asset | Why it matters | Rhombus 2.0 role |
|---|---|---|
| Evidence/provenance contracts | Every conclusion can be reconstructed and challenged | Common Evidence Ledger |
| Content-addressed structures/results | Detects substitution and stale evidence | Universal artifact identity |
| Fail-closed semantics | Prevents unsupported claims from becoming PASS | Shared state semantics |
| Known-material benchmark | Real materials expose hidden scientific/software assumptions | Semantic regression harness |
| Real MLIP relaxation/MD paths | Expensive execution plumbing already works | Atomistic executors |
| Stateless sharding/resume | Well suited to unreliable free compute | Budget-aware execution layer |
| Candidate Supply v2 scheduling | Existing deterministic selection infrastructure | Exploration Engine foundation |
| X/N/S/Application contracts | Useful interfaces already exist | Inputs to real v2 protocols |
| GitHub Actions evidence chain | Reproducible free orchestration | Core execution backend |
| Source-bound truth records | Expensive scientific curation already exists | Benchmark/generalization evidence |

These assets should be wrapped and reused wherever their semantics remain valid.

---

# 5. What must change

Rhombus 2.0 should not preserve the following assumptions merely for compatibility:

- that one fixed serial pipeline is optimal for every candidate;
- that success on a few known materials implies reliability throughout chemical space;
- that model cross-checking belongs only after transport analysis;
- that one universal pretrained MLIP is equally reliable across bulk, defects, interfaces, transition states, and unfamiliar chemistry;
- that perfect periodic bulk structures alone are sufficient for practical electrolyte claims;
- that candidate discovery should depend on a fixed collection of structure-perturbation operators;
- that a single-temperature short trajectory is sufficient final transport evidence;
- that one global PASS/FAIL qualification status is meaningful for all material families and carriers.

The scientific architecture should be driven by **claims and evidence requirements**, not historical stage numbering.

---

# 6. Rhombus 2.0 target architecture

The target architecture is a **coverage-aware, uncertainty-aware, multi-fidelity evidence graph with a closed discovery loop**.

Architecturally, Rhombus should behave as a scientific control plane above heterogeneous executors. A MACE-family model, MatterSim-like model, DFT code, public database, experimental source, or future research agent may contribute evidence, but none is permitted to bypass Rhombus evidence normalization, protocol/model identity, applicability, uncertainty, and claim-resolution semantics.

```text
PUBLIC DATA / LITERATURE / KNOWN STRUCTURES / GENERATORS
                         │
                         ▼
                  CANDIDATE UNIVERSE
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
       Coverage / OOD map    Constraint validity
              │                     │
              └──────────┬──────────┘
                         ▼
              MULTI-FIDELITY EVIDENCE GRAPH
         ┌───────────────┼───────────────────┐
         ▼               ▼                   ▼
   cheap topology    MLIP ensemble      thermodynamics /
   & geometry        + uncertainty      public evidence
         └───────────────┼───────────────────┘
                         ▼
                  ADAPTIVE ATOMISTICS
          relaxation → finite-T → transport
                         │
             defect / disorder / interfaces
                         │
        novelty / synthesis / application context
                         │
                         ▼
                   CLAIM VECTOR + DOMAIN
                         │
                         ▼
           ACTIVE SELECTOR chooses next action
                         │
                         └──────────────────↺
```

The final feedback arrow is essential.

Rhombus should continuously ask:

> **What do we not know, and which next free calculation or evidence-gathering action would reduce the most important uncertainty?**

---

# 7. Core shared services

## 7.1 Evidence Ledger

Every relevant scientific object should be representable as a content-addressed evidence record.

Possible record types include:

- literature evidence;
- source independence;
- structure;
- representation;
- candidate-generation event;
- model identity;
- model training lineage;
- protocol;
- trajectory;
- result;
- uncertainty;
- applicability;
- limitation;
- artifact hash;
- claim assessment.

Existing provenance contracts should form the initial implementation.

## 7.2 Domain Map

The system must quantify how closely a candidate resembles regions where the pipeline has been validated.

Candidate/domain representation may include:

- composition descriptors;
- SOAP or similar local-environment descriptors;
- learned structural embeddings;
- mobile-ion identity;
- coordination environments;
- symmetry;
- density;
- structural family;
- chemistry class;
- model-specific embeddings.

Possible domain outputs:

```text
IN_DOMAIN
NEAR_OOD
FAR_OOD
UNQUALIFIED
```

A candidate may be in-domain for one claim and out-of-domain for another.

For example:

```text
geometry domain:        IN_DOMAIN
relaxation domain:      IN_DOMAIN
finite-T domain:        NEAR_OOD
transport domain:       FAR_OOD
synthesis domain:       UNQUALIFIED
```

Applicability should therefore become claim-specific.

## 7.3 Executor Registry

Scientific calculations should become registered capabilities instead of being permanently hard-wired to stage names.

Examples:

- static structure validation;
- oxidation-state analysis;
- relaxation;
- short finite-T dynamics;
- adaptive dynamics;
- force disagreement probe;
- trajectory analysis;
- diffusion-regime analysis;
- multi-temperature transport;
- novelty search;
- public thermodynamic evidence lookup;
- synthesis evidence audit.

## 7.4 Claim Engine

Scientific claims should specify the evidence they require.

Example:

```text
claim: finite_temperature_stability

requires:
    valid_structure
    executable_representation
    acceptable_model_domain
    interpretable_dynamic_evidence
    sufficient_provenance
```

Application claims can require a much larger conjunction.

This allows the final scientific result to emerge from evidence relationships rather than simply reaching the end of a pipeline.

## 7.5 Active Selector

The system should compare alternative next actions.

Possible actions:

- evaluate another candidate;
- evaluate a second model;
- run a longer trajectory;
- test another temperature;
- probe a sparse structural cluster;
- collect literature evidence;
- inspect a defect;
- analyze a grain boundary;
- stop computing on a redundant family.

Conceptually:

```text
next_action_utility
    = expected_information_gain
    + coverage_gap_bonus
    + promising_property_signal
    + model_disagreement_bonus
    - compute_cost
    - duplicate_penalty
    - unsupported_domain_risk
```

This is a design heuristic, not a frozen physical equation.

---

# 8. Candidate generation and materials-space exploration

## 8.1 Candidate generation must become multi-source

Rhombus should treat candidate proposal as a federation of adapters.

Priority order under a zero-cost constraint:

1. public known-structure databases;
2. existing experimentally reported materials;
3. isovalent/aliovalent substitutions;
4. charge-compensated vacancies/interstitials/doping;
5. mobile-ion and local-environment perturbations;
6. prototype decoration/enumeration;
7. optional open pretrained generative-model adapters;
8. AI/LLM idea generation only as a proposal source, never as scientific evidence.

Candidate identity must remain independent of proposal source.

All candidates ultimately enter the same Evidence Ledger.

## 8.2 Scientific constraints should move inside generation

Where possible, avoid:

```text
generate arbitrary candidates
        ↓
reject most of them later
```

Prefer:

```text
scientific constraints
        ↓
candidate construction
        ↓
higher-quality proposal distribution
```

Generation-time constraints should include, where applicable:

- oxidation-state and valence consistency;
- charge neutrality;
- explicit mobile carrier;
- allowed chemistry;
- minimum-distance constraints;
- site-overlap constraints;
- explicit disorder semantics;
- partial-occupancy semantics;
- correlation assumptions;
- compensation rules for composition-changing operations;
- exact parent provenance;
- deterministic RNG identity;
- generation-config hashes.

Novelty must never be optimized independently from plausibility.

## 8.3 Coverage-driven exploration

The candidate universe should be embedded into a structural/chemical representation space.

Sampling should intentionally include:

- cluster centers;
- cluster boundaries;
- sparse regions;
- outliers;
- high-disagreement regions;
- high-promise regions;
- underrepresented carriers;
- underrepresented structural motifs.

This is preferable to repeatedly generating candidates near already explored parents.

---

# 9. Scientific validation capabilities

The following should become reusable capabilities rather than permanent sequential stage names.

| Capability | Scientific question | Legacy source |
|---|---|---|
| Identity and provenance | What exact material/phase/source is this? | B1–B4 |
| Representation validity | Can disorder/occupancy/correlation be represented defensibly? | LLZO benchmark work |
| Cheap physical feasibility | Is the structure/composition clearly invalid? | P0 |
| Domain/UQ preflight | Are the scientific models applicable? | X-like logic moved earlier |
| Relaxation evidence | Is the structure energetically/geometrically reasonable? | P1 |
| Finite-T stability | Does the host remain meaningful dynamically? | P2 |
| Transport-regime evidence | Does observed motion represent meaningful ionic transport? | P2.5 |
| Transport quantification | What are D(T), activation behavior, uncertainty? | P3 redesigned |
| Defect/carrier evidence | Are physically relevant mobile carriers available? | New capability |
| Chemical/electrochemical stability | Will the material survive the intended environment? | New/expanded |
| Interface/microstructure evidence | Do grain boundaries/interfaces invalidate bulk conclusions? | New selective layer |
| Novelty | Is the candidate unmatched in the declared reference universe? | N |
| Synthesizability | Is there credible synthesis evidence? | S |
| Application qualification | Does it satisfy a versioned real use profile? | Application |

---

# 10. Universal MLIP policy

No single model should become the truth model.

Where practical, Rhombus should compare models with meaningfully different training lineages.

Potential signals include:

- force disagreement;
- energy disagreement where scientifically meaningful;
- relaxed-structure disagreement;
- dynamic-behavior disagreement;
- local atomic uncertainty;
- distance to validated training/evidence regions.

Shared training ancestry must be recorded. Two models built on highly overlapping data should not automatically count as independent confirmation.

A zero-cost escalation policy should be used:

```text
cheap single-model probe
        ↓
domain/disagreement check
        ↓
only if scientifically valuable
        ↓
multi-model relaxation
        ↓
only if still valuable
        ↓
multi-model dynamics
```

This avoids paying ensemble cost for every candidate.

---

# 11. Transport validation v2

A single 550 K trajectory remains useful as a screening tool but should not be treated as universal final transport evidence.

A stronger future transport path is:

```text
finite-temperature structural stability
        ↓
transport-regime qualification
    - enough mobile ions
    - enough usable trajectory
    - MSD regime
    - non-Gaussian behavior
    - hopping evidence
    - finite-time convergence
        ↓
selected candidates only
        ↓
multi-temperature trajectories
        ↓
D(T) + activation behavior + uncertainty
        ↓
defect/carrier concentration
+ collective-correlation evidence
        ↓
application-specific transport claim
```

Transport claims should explicitly state unresolved assumptions.

---

# 12. Defects and carrier concentration

A low migration barrier is not sufficient if physically relevant carriers are unavailable.

Where relevant, Rhombus should distinguish:

- intrinsic carriers;
- vacancy populations;
- interstitial populations;
- aliovalent substitutions;
- dopability;
- compensation mechanisms;
- phase-specific defect populations.

The zero-cost evidence hierarchy should be:

1. literature evidence;
2. public computational databases;
3. chemistry and oxidation-state constraints;
4. known analogue/dopability evidence;
5. selected MLIP defect calculations;
6. external DFT or experimental evidence where required.

If evidence remains insufficient, the corresponding claim remains UNKNOWN.

---

# 13. Stage C — Generalization Qualification

Stage C has been approved as the next major qualification program.

Its central question is:

> **How much trust should Rhombus place in a material that was not directly represented in the benchmark?**

## C0 — Evidence-space schema

Define descriptors for:

- composition;
- structure;
- mobile carrier;
- local coordination;
- structural family;
- model lineage;
- evidence coverage.

Human family labels remain useful metadata but must not be the only representation.

## C1 — Automatic clustering

Use SOAP or another defensible structural representation, optionally supplemented by learned embeddings.

The goal is to discover regions of material space rather than relying only on manually named families.

## C2 — Leave-One-Cluster-Out / Leave-One-Family-Out validation

For each region:

```text
develop / calibrate on the other regions
              ↓
evaluate a fully excluded region
```

Measure:

- false PASS rate;
- false FAIL rate;
- INDETERMINATE rate;
- operational ERROR rate;
- model-domain rejection rate;
- uncertainty calibration;
- stage-specific failure patterns.

## C3 — Applicability domain

Every candidate receives a claim-specific domain assessment.

Possible status:

```text
IN_DOMAIN
NEAR_OOD
FAR_OOD
UNQUALIFIED
```

## C4 — Uncertainty calibration

Potential inputs:

- heterogeneous model disagreement;
- structural-space distance;
- ensemble variance;
- local atomic uncertainty;
- historical error-versus-distance curves;
- conformal calibration where enough evidence exists.

Raw uncertainty values must not be treated as calibrated confidence without empirical support.

## C5 — Active benchmark expansion

Benchmark growth should itself be information-driven:

```text
identify largest coverage gaps
        ↓
identify high-error/high-disagreement regions
        ↓
choose representative known materials
        ↓
run expensive benchmark evidence
        ↓
update domain map
```

This is **active testing**, not merely active model training.

## C6 — Multi-carrier expansion

Li-domain qualification does not imply species-general qualification.

Other carrier domains should be added only when evidence supports them.

Possible future carriers include:

- Na;
- Ag;
- H;
- Mg;
- F;
- O.

Each begins as an unqualified scientific domain.

## C7 — Prospective time-split validation

Future information provides the strongest realistic test.

```text
development knowledge cutoff
        │
────────┼────────
        │
new publications / structures /
externally sealed candidates
```

The frozen protocol evaluates those materials without tuning.

## C8 — Generalization Map Freeze

Qualification should become regional rather than global.

Example:

```text
Domain / family       Status
--------------------------------
Li garnet             QUALIFIED
Li borohydride        LIMITED
Li sulfide            LIMITED
Na oxide              UNQUALIFIED
Mg conductor          UNQUALIFIED
```

This is more scientifically meaningful than a single global `qualified=true`.

---

# 14. Realistic materials layer

A perfect periodic bulk crystal is not equivalent to a practical solid electrolyte.

Relevant realism may include:

- defects;
- substitutions;
- partial occupancy;
- disorder;
- grain boundaries;
- pores;
- amorphous regions;
- impurities;
- electrode interfaces;
- space-charge layers;
- secondary phases.

Under the zero-cost constraint these effects should be evaluated selectively.

| Area | Cheap evidence | Higher-cost free evidence | Policy |
|---|---|---|---|
| Defect chemistry | literature, oxidation states, public DBs | explicit MLIP defect cells | High priority before strong transport claims |
| Chemical stability | public phase diagrams and literature | selected reaction calculations | Prefer public evidence |
| Electrode interface | known reaction products/compatibility | explicit interface calculations | Finalists only |
| Grain boundaries | literature and topology | large-cell GB MD | Representative/final candidates |
| Porosity/mechanics | density, modulus, processing literature | continuum/multiscale models | Application-specific |

The goal is not to simulate every real-world effect.

The goal is to identify which missing realism factor could overturn the scientific claim.

---

# 15. Novelty

Novelty must remain a provenance-aware claim.

If database coverage is incomplete, Rhombus should not state simply:

`NOVEL`

Prefer:

`NO_MATCH_IN_DECLARED_REFERENCE_UNIVERSE`

Novelty evidence should record:

- searched databases;
- database snapshot/version;
- reference hashes where possible;
- search coverage limitations;
- structure-matcher configuration;
- composition match status;
- structural match status;
- known rediscovery status;
- generator/model exposure where known.

Composition novelty and structural novelty remain separate.

---

# 16. Synthesizability

Synthesizability requires a real scientific protocol, not an arbitrary scalar score.

Evidence dimensions may include:

- precursor availability;
- compositional feasibility;
- reaction thermodynamics;
- competing phases;
- known synthesis routes;
- analogous synthesis routes;
- required temperature;
- atmosphere;
- pressure;
- metastability;
- kinetic accessibility;
- experimental precedent;
- independence of literature sources.

Missing critical evidence remains UNKNOWN.

---

# 17. Application qualification

There should be no universal claim named simply:

`GOOD_SOLID_ELECTROLYTE`

Application claims must be profile-specific.

Examples:

- Li-metal-compatible oxide electrolyte;
- sulfide catholyte;
- sodium solid electrolyte;
- elevated-temperature ionic conductor;
- thin-film electrolyte.

A profile may require different combinations of:

- ionic transport;
- chemical stability;
- electrochemical stability;
- electrode compatibility;
- operating temperature;
- processing;
- mechanics;
- moisture sensitivity;
- precursor availability;
- density;
- interface resistance.

Application profiles must be versioned and evidence-bound.

---

# 18. Zero-cost compute strategy

Rhombus cannot win by matching the raw compute budgets of frontier industrial or academic materials programs.

It must win through **compute selection efficiency**.

## Compute tiers

| Tier | Cost | Typical work | Promotion criterion |
|---|---|---|---|
| T0 | Almost zero | literature, DB search, provenance, charge, geometry, descriptors | Basic validity |
| T1 | Low CPU | clustering, topology, cheap surrogate, single-uMLIP probe | Promise or coverage gap |
| T2 | Limited CPU/GPU | relaxation, disagreement, short adaptive MD | Domain support + information value |
| T3 | Scarce free GPU | longer MD, multi-T MD, selected defects/disorder | High scientific value |
| T4 | External evidence | DFT, AIMD, experiment | Not mandatory for core zero-cost execution |

## Compute stop rules

Do not compute merely because a next stage exists.

Examples:

- FAR_OOD + no supporting evidence → do not force expensive MD;
- clear early physical contradiction → stop downstream compute;
- dense/redundant cluster → redirect compute elsewhere;
- duplicate candidate → keep only the more informative representative;
- operational ERROR → retry according to policy, never convert to physical FAIL;
- free GPU unavailable → preserve the queue rather than weaken protocol semantics.

---

# 19. Repository strategy

Historical evidence remains immutable.

The canonical Rhombus 2.0 package is `rhombus`. New v2 capabilities belong under that namespace; `rudeus` remains a compatibility surface for validated legacy machinery rather than the destination for new architecture.

Representative v2 namespaces:

```text
rhombus/evidence/
    ledger
    claims
    provenance
    applicability
    protocol
    audit

rhombus/domain/
    descriptors
    coverage
    calibration
    exposure

rhombus/exploration/
    candidate_universe
    proposal_adapters
    acquisition
    active_selection

rhombus/atomistics/
    executor_registry
    model_registry
    model_lineage
    ensemble
    adaptive_simulation

rhombus/transport/
    regime
    diffusion
    multi_temperature
    defect_carriers
    collective_transport

rhombus/realism/
    chemistry
    interfaces
    grain_boundaries
    microstructure

rhombus/qualification/
    known_material_benchmark
    generalization
    prospective
    generalization_map

rhombus/application/
    novelty
    synthesis
    profiles
```

Domain-neutral evidence/protocol/claim/audit contracts should avoid unnecessary ionic-conductor assumptions. Rhombus remains the reference application; extraction into a separate general scientific-verification core is justified only after the same contracts are demonstrated in another scientific workflow without weakening semantics.

Legacy outputs should enter the v2 system through explicit adapters:

```text
historical P0/P1/P2/P2.5/P3 result
                ↓
         compatibility adapter
                ↓
          v2 Evidence Ledger
```

Do not rewrite historical bytes or reinterpret old results silently.

---

# 20. Development roadmap

## Phase 0 — Closed: current B5 diagnostic

Phase 0 closed on 2026-10-07.

Authoritative DEV conclusions:

- gamma-LiAlO2: P0 plausible, P1 retained, corrected finite-temperature stability PASS, and transport-regime NONDIFFUSIVE only after the authorized one-shot 8,000-production-step evidence extension;
- hexagonal LiBH4: finite-temperature stability FAIL;
- orthorhombic LiBH4: finite-temperature stability FAIL;
- cubic Al-LLZO: upstream P0 INDETERMINATE and therefore not admitted downstream.

The gamma transport extension remained stable at 550 K and produced enough origin blocks for a transport-regime claim. That claim is NONDIFFUSIVE under the frozen provisional P2.5 contract. It is not a conductivity, self-diffusion, tracer-diffusion, synthesis, or application-fitness claim.

Phase 0 also established that protocol/execution failures, representation failures, physical failures, insufficient evidence, and unsupported domains must remain distinct. Legacy B6-B8 remain deferred.

Durable closure: `data/development/phase0_closure_v1.json`.

## Phase 1 — Closed: architecture and public tool contract frozen

Phase 1 is frozen by `data/development/rhombus_v2_architecture_freeze_v1.json`.

The freeze makes the evidence graph, claim-specific applicability/uncertainty semantics,
legacy/deferred boundary, and small semantic AI-facing tool catalog explicit. The same
scientific tool contract is the target for Python, MCP, and a future ChatGPT/Codex Plugin;
adapter layers may change invocation framing but may not weaken evidence, provenance,
scientific-verdict, operational-status, applicability, uncertainty, or limitation semantics.

The future sealed qualification cohort remains unconsumed. Legacy B6–B8 remain deferred.
No tool is made executable merely by appearing in the frozen catalog; `rhombus.tools`
exports remain gated on implementation and scientific admission.


## Phase 2 — Closed: Evidence Ledger + compatibility adapters

Phase 2 is frozen by `data/development/rhombus_v2_evidence_ledger_freeze_v1.json`.

Rhombus 2.0 now has content-addressed EvidenceRecord and ClaimRecord schemas,
claim-specific Applicability and Uncertainty, typed ModelIdentity, ModelLineage,
ProtocolIdentity, Limitation, SourceBinding, and ArtifactBinding records, plus
explicit legacy compatibility adapters.

The compatibility boundary is allowlist-only. Unknown historical schemas fail
closed rather than being inferred. Legacy P1 retention, corrected P2 stability,
and current authoritative P2.5 transport evidence are imported without widening
their original scientific meaning. Legacy PASS never implies IN_DOMAIN
applicability, transport-regime evidence does not imply conductivity or diffusion
coefficients, and DEV evidence does not imply sealed prospective qualification.

Model identity is resolved only by exact checkpoint SHA-256, lineage only from
the frozen exposure ledger, and protocol identity only from explicit legacy
records. `rhombus.tools` remains gated; no MCP server or ChatGPT/Codex Plugin
surface is activated by the Phase 2 freeze.


## Phase 3 — Active: Domain Map / C0–C4

Phase 3 is now in empirical-calibration preparation rather than initial architecture design.

Implemented and frozen so far:

- composition descriptor and exact element-support preflight;
- transparent structural descriptor and structural-distance baseline;
- reference-coverage profile using k-neighbor coverage rather than a single nearest neighbor;
- evidence-bound calibration contract with minimum reference count and leave-group-out requirements;
- fail-closed empirical calibration readiness gate;
- public nonsealed reference-error source selection with WBM identified as a candidate, not automatically admitted;
- deterministic outcome-blind WBM sampling;
- frozen WBM source/file identities plus verified MD5/SHA256 evidence for the MACE-MPA-0 discovery predictions and WBM summary;
- streaming verification support for larger WBM structure files;
- fail-closed exposure-audit input contracts requiring the full declared MACE-MPA-0 training lineage (MPTrj + sAlex), explicit fingerprint protocol identity, and near-duplicate protocol identity.

Current frontier:

```text
stream-verify WBM structure source
        ↓
freeze exact MPTrj + sAlex audit basis
        ↓
freeze fingerprint / near-duplicate protocols
        ↓
execute exposure / dedup audit
        ↓
construct paired per-structure error ↔ distance evidence
        ↓
empirical leave-group-out calibration
        ↓
Phase 3 Domain Map freeze
```

WBM remains **not admitted** for empirical generalization calibration until those checks are complete. Absence of a detected match is not sufficient to call a structure foundation-model-unseen, and the future sealed qualification cohort remains unconsumed.

This phase directly addresses the central question:

> **How trustworthy is Rhombus on an untested material, and what exact evidence permits that trust?**

## Phase 4 — Exploration Engine

Build a common proposal interface for:

- public structures;
- existing Candidate Supply v2;
- substitutions;
- vacancy/interstitial operations;
- defect-aware transformations;
- prototype decoration;
- optional generative models.

Add constraint-aware generation and active acquisition.

## Phase 5 — Atomistics v2

Implement:

- model registry;
- training lineage;
- model independence metadata;
- domain preflight;
- cheap single-model probes;
- heterogeneous disagreement;
- multi-model relaxation when justified;
- adaptive MD;
- numerical-abort provenance;
- trajectory convergence and sufficiency.

## Phase 6 — Transport and defect/carrier physics

Implement:

- transport-regime qualification;
- MSD sufficiency;
- non-Gaussian/hopping analysis;
- multi-temperature D(T);
- activation behavior;
- finite-time sensitivity;
- selected finite-size sensitivity;
- defect/carrier evidence;
- collective transport evidence;
- application-specific transport claim rules.

## Phase 7 — Realism / synthesis / application

Implement:

- chemical/electrochemical stability adapters;
- interface evidence;
- grain-boundary evidence;
- selective microstructure analysis;
- real synthesis evidence protocol;
- novelty service;
- versioned application profiles;
- final claim vector v2.

## Phase 8 — Generalization and prospective qualification

Complete C5–C8:

- active benchmark expansion;
- multi-carrier generalization map;
- sealed prospective cohort;
- one-shot evaluation;
- regional qualification report.

Candidate production should eventually be authorized **by validated region**, not by one global switch.

Example:

```text
Li oxide / validated structural domain:
    production discovery authorized

Na sulfide / near-domain:
    exploratory only

Mg conductor:
    unqualified
```

---

# 21. Development priority

| Priority | Development block | Reason |
|---|---|---|
| P0 | Current B5 diagnostic closure | Immediate scientific blocker |
| P1 | Evidence Ledger + adapters | Foundation for v2 |
| P2 | Domain Map / C0–C4 | Solves generalization question |
| P3 | Exploration Engine | Reduces candidate-generation bias |
| P4 | Atomistics v2 | Reuses mature existing executors |
| P5 | Transport + defect physics | Core scientific quality |
| P6 | Realism / synthesis / application | Final-candidate qualification |
| P7 | Prospective qualification | Required before strong discovery claims |

---

# 22. Minimum definition of Rhombus 2.0 readiness

Rhombus 2.0 should not be considered ready until:

1. candidates from different proposal sources enter one common Evidence Ledger;
2. every evaluated candidate receives a domain/coverage assessment;
3. atomistic results carry model identity, lineage, and uncertainty/disagreement evidence;
4. structural stability and ionic transport remain separate claims;
5. transport claims expose sufficiency and convergence;
6. known-material semantic benchmarks still falsify incorrect behavior;
7. leave-one-cluster-out or equivalent generalization performance is measured;
8. degradation under OOD conditions is quantified;
9. a sealed prospective cohort can be evaluated without development leakage;
10. final outputs explain PASS, FAIL, UNKNOWN, and INDETERMINATE;
11. core operation does not require paid APIs, paid DFT, or paid compute;
12. historical evidence remains reproducible and immutable.

---

# 23. When a new repository would become justified

The default decision is to remain in this repository.

A new repository should be considered only if multiple conditions become true:

- the current package/import graph prevents clean v2 namespaces;
- legacy CI coupling causes prohibitive compute on every v2 change;
- v1 and v2 licensing/distribution constraints become incompatible;
- the project expands beyond solid-ion-conductor discovery into a fundamentally different product;
- historical compatibility requirements prevent clean scientific qualification;
- v2 requires a fundamentally incompatible runtime/public API.

Until then, a second repository would discard validated infrastructure without eliminating the hard scientific problems.

---

# 24. Mapping historical stages to v2 capabilities

| Historical stage | Historical responsibility | Rhombus 2.0 destination |
|---|---|---|
| E | Empirical anchors | Evidence Ledger / Public Evidence Sources |
| G | Candidate acquisition/generation | Exploration Engine |
| P0 | Static plausibility | Constraint + Representation Validity |
| P1 | MLIP relaxation | Atomistic Relaxation Evidence |
| P2 | Finite-T stability | Adaptive Dynamics Evidence |
| P2.5 | Diffusive-regime screen | Transport-Regime Qualification |
| P3 | Transport MD | Transport Quantification |
| X | Independent model cross-check | Model-domain/UQ layer spanning atomistics |
| N | Novelty | Novelty Claim Service |
| S | Synthesizability | Synthesis Evidence Service |
| Application | Profile-specific compatibility | Application Profile Engine |
| Final Claim Vector | Mandatory conjunction | Claim Engine + domain-aware OUT |

The mapping deliberately does not preserve the old names as permanent architecture.

---

# 25. Scientific audit reference set

The architecture audit is informed by current directions in materials discovery, OOD validation, uncertainty, generative design, solid-electrolyte modeling, and atomistic simulation.

Representative reference set:

- Zeni et al. (2025), *A generative model for inorganic materials design*, Nature. DOI: `10.1038/s41586-025-08628-5`
- Tan et al. (2026), *MatUQ: a benchmark for uncertainty-aware out-of-distribution materials property prediction with graph neural networks*, npj Computational Materials. DOI: `10.1038/s41524-026-02272-x`
- *Enhancing materials discovery with valence-constrained design in generative modeling* (2026), Nature Computational Science. DOI: `10.1038/s43588-026-01037-2`
- Riebesell et al. (2025), *A framework to evaluate machine learning crystal stability predictions*, Nature Machine Intelligence. DOI: `10.1038/s42256-025-01055-1`
- Dutra et al. (2025), *Understanding solid-state battery electrolytes using atomistic modelling and machine learning*, Nature Reviews Materials. DOI: `10.1038/s41578-025-00817-y`
- Bilbrey et al. (2026), *Assessing universal MLIP robustness with per-atom uncertainty for simulations of solid-liquid interfaces*, npj Computational Materials. DOI: `10.1038/s41524-026-02051-8`
- Kim et al. (2026), *Optimizing cross-domain transfer for universal machine learning interatomic potentials*, Nature Communications. DOI: `10.1038/s41467-026-70195-8`
- *Budget-constrained augmentation of universal interatomic potentials for reliable multicomponent molecular dynamics* (2026), npj Computational Materials. DOI: `10.1038/s41524-026-02202-x`
- *Microstructural insights into fast ion transport in solid electrolytes via multiscale modeling* (2026), Nature Communications. DOI: `10.1038/s41467-026-76216-w`
- *A perspective on training machine learning force fields for solid-state electrolyte materials* (2026), npj Energy Materials. DOI: `10.1038/s44456-026-00014-4`
- Mannan et al. (2026), *UniFFBench: evaluating universal machine learning force fields against experimental measurements*, Nature Computational Science. DOI: `10.1038/s43588-026-01019-4`

The reference set is not itself a frozen scientific protocol. New high-quality evidence may change the architecture.

---

# 26. Maintenance rule

This README records the Rhombus 2.0 architecture decision as of October 2026.

When new research, prospective benchmark evidence, or real Rhombus results falsify an assumption here:

- publish a new versioned architecture decision;
- retain the previous historical state;
- do not silently redefine old protocols;
- do not reinterpret historical PASS/FAIL without an explicit compatibility adapter;
- do not repeatedly consume held-out evidence.

The governing principles are:

> **Freeze the evidence, not the research.**

and

> **Search broadly, quantify where the system is uncertain, spend expensive computation only where it creates the most information, and never claim more than the evidence supports.**
