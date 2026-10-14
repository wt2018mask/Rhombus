# 0173 — MACE-MPA-0 upstream developer reveals actual TRAIN / VALID source locations

## Original authoritative lead discovered, priority P0-02

Previous Rhombus P0-02 records listed only generic training *families* MPTrj and sAlex and a partially verified sAlex+MPTrj source. We found two original official **ACEsuit/mace-foundations** GitHub issue author replies, by GitHub login `ilyes319`, which materially narrow the model's claimed dataset selection and training script:

1. [Official original GitHub issue #42 comment 3244634298](https://github.com/ACEsuit/mace-foundations/issues/42#issuecomment-3244634298), 2025-09-02. Developer explicitly names MACE-MPA-0:
   - **sAlex training:** [Meta sAlex/train.tar.gz](https://dl.fbaipublicfiles.com/opencatalystproject/data/omat/241018/sAlex/train.tar.gz)
   - **MPTrj training:** [developer original Google Drive train folder](https://drive.google.com/drive/folders/12RsjlEtSlBldhoQVJapfC9lIFZwpnVk6?usp=drive_link)
   - **sAlex validation:** [Meta sAlex/val.tar.gz](https://dl.fbaipublicfiles.com/opencatalystproject/data/omat/241018/sAlex/val.tar.gz)
   - **MPTrj validation:** [developer original Google Drive val folder](https://drive.google.com/drive/folders/10atLHo2VJyTcb9JqL8SjHZIornPntUh-?usp=sharing)
2. [Official issue #29 comment 3291737675](https://github.com/ACEsuit/mace-foundations/issues/29#issuecomment-3291737675), 2025-09-15. The author states [mace_omat/mace-omat-medium.sh](https://github.com/ACEsuit/mace-foundations/blob/main/mace_omat/mace-omat-medium.sh) is the analogous input template for MPA, **replace OMAT data with sAlex+MPTrj**. The published current script is a *template*, not an independently verified historical execution receipt for exact MPA checkpoint.

## Distinct evidence layers, science limit

| Layer | New actual scientific evidence | Qualification |
|---|---|---|
| Upstream research team's public identity and source comments | Two GitHub issue replies, date, issue/comment ID, body SHA receipt | **Author-stated** split provenance only |
| sAlex and MPTrj TRAIN vs VALID dataset locations | Exact URL split distinction; authoritative intent stronger than dataset families | **Source leads**; archive byte identity unverified |
| Actual selected training frame membership | Nothing downloaded / no full file manifest observed | **UNKNOWN** |
| Energy/force preprocessing + selected checkpoint transfer | No authoritative source-bound evidence receipt | **UNKNOWN** |
| Independent sealed new material exposure exclusion | No new steward/evaluation roster | **BLOCKED** |

**Important nuance:** An author publicly saying "we used the following data" materially improves evidence for the subset location, but it does not by itself establish cryptographic linkage from a particular checkpoint to the original archive byte SHA, source frame IDs, preprocessing and energy semantics. Don't automatically change RT-P0-02 to RESOLVED; use existing [strict verification](../rhombus/domain/training_manifest.py) and request source manifests/provider audit. GitHub may allow author comments to be edited; exact original body SHA256 is a *snapshot receipt*, not publisher cryptographic signature. Any upstream comment edits must fail old snapshot and be reviewed, not silently adopted.

## Live primary-source executable

[0173 script](../scripts/science/mace_author_training_splits_0173.py) reads GitHub API original issue-comment URLs #3244634298 and #3291737675 under fixed HTTPS exact origin, validates comment/issue IDs and `ilyes319` login, binds explicit TRAIN/VALID text and script substitution to MACE-MPA-0, and emits SHA256 for the comment bodies as aggregate reproducible provenance only. [Hostile tests](../tests/test_phase3_mace_author_training_splits_0173.py) reject wrong author/issue, swapped archives, Google folder tampering and unrelated model statements. [GitHub Actions source workflow](../.github/workflows/phase3-mace-upstream-training-splits-0173.yml) downloads only bounded 64KB public GitHub metadata for two comments, **never massive MPTrj or sAlex archives**. Actual GitHub original author source was fetched by [Actions #38589119917](https://github.com/wt2018mask/Rhombus/actions/runs/38589119917) — SUCCESS. Author comments 2, issue #42/#29, exact four MPA data split URLs and command-template substitution source bound; 12/12 adversarial tests passed and bounded-source metadata aggregation passed. [Aggregate-only original source artifact #11907355102](https://github.com/wt2018mask/Rhombus/actions/runs/38589119917/artifacts/11907355102), archive SHA256 `9148df3094b4211a8652eaf9e88338b1b9478f1bc32767f9a78292f03f03f38b`. No MPTrj/sAlex tarballs downloaded; actual selected frame inclusion and energy/preprocessing remain unverified. All selected frame and overlap gates remain false.

## Authorized follow-up without expensive speculation

1. Verify actual remote source endpoint archive headers/metadata and public eligibility, not the full multi-GB dataset; if source filenames are dynamic, obtain publisher stable individual file lists, recorded sizes and SHA from authors. Check exact MACE-MPA-0 checkpoint byte digest (publisher report versus independent local file).
2. Obtain **complete selected frame member/ID list** from authoritative provider split, canonical frame identity scheme, corrections to MPTrj energy and force labels, and selected preprocessing/validation settings. Verify data-source revision and selected-file provenance in a bounded reproducible pipeline before any expensive Kaggle jobs.
3. Independently check exposure against a new sealed material cohort only via authorized steward-controlled protocol. **Never access confidential hidden truths before predictions are frozen.**
4. If provider cannot provide full frame and correction manifests, explicitly record UNKNOWN; explore a redefined, provenance-verifiable MLIP under new preapproved scope, not false retroactive P0-02 PASS.

**Other P0 gates:** P0-01 external independent steward **BLOCKED**, P0-03 individually authenticated and adequately powered material cohort **BLOCKED**, and NO independently verified MACE-MPA-0 selected frames. SCIENTIFIC NO-GO.
