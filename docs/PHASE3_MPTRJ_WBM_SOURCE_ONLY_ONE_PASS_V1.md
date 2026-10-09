# Phase 3 — original MPTrj ↔ WBM source-only overlap in one verified stream

Checkpoint 0088 creates a real next-step scientific data path without assuming the entire CHGNet MPTrj source is identical to the exact MACE-MPA-0 training frames.

## Input and execution

The WBM target SQLite file must already exist (from the frozen initial-structure WBM source), with SHA256 `98d545172c1ea9060f03f40cace6f8173a4ac06f1ee875ccd963765211519b58` and **256,963** unique targets. Its size, metadata and presence are checked **before** any full MPTrj source GET. This PR neither fetches the WBM source nor builds that index.

An offline-only WBM-target metadata preflight can be run with:

~~~bash
python -m scripts.development.run_mptrj_wbm_source_overlap --preflight --wbm-target-db /path/to/existing-wbm-target.sqlite
~~~

Only if the previously requested real **1MiB** MPTrj pilot has succeeded and a separate suitable large-run resource/transfer budget has been reviewed and approved, an operator can intentionally issue one original ~12.2GB stream:

~~~bash
python -m scripts.development.run_mptrj_wbm_source_overlap --execute-full-download --wbm-target-db /path/to/existing-wbm-target.sqlite --report /path/to/new-source-overlap.json
~~~

The source **is never staged on disk**. The verified, trusted original-file HTTPS downloader and full-stream ijson/pymatgen parser emit one complete-frame callback at a time. The observer uses the existing frozen candidate fingerprint, near-duplicate, strict structural matcher and prototype protocol, comparing directly to materialized WBM initial structures fetched by indexed bucket from local WBM SQLite.

## Exact gate and epistemic boundary

Partial matches are not written to report files; a result exists only after **all** complete MPTrj source frames, original total source byte count, official MD5 and locally calculated SHA256 agree. Premature termination or hash mismatch aborts without a report. No output contains WBM structure payloads or original MPTrj raw bytes.

- The result records **source-level** strict, near-duplicate, and prototype overlap with original MPTrj.
- It does **not** state that the compared WBM targets were used by MACE-MPA-0. Official MPTrj contains many frames and the released checkpoint's actual subset/preprocessing are still unresolved.
- Neither a detected original-source match nor the absence of a source match authorizes full training exposure or unseen generalization.
- The sealed qualification cohort, domain calibration and training exposure promotion remain untouched.
- GitHub CI exercises only small constructed structures and fake responses. No 1MiB or 12.2GB real HTTP request is executed in this change.


## Checkpoint 0089 — target-specific positive source-level rows

The [target-specific source-only JSONL](PHASE3_MPTRJ_WBM_SOURCE_TARGET_ROWS_V1.md) is created only after the complete original MPTrj byte+frame verification; unmatched WBM materials are not labelled unseen, and source-level matches must not be promoted to MACE training-membership verdicts. No original 12.2GB request executed by this PR.


## Checkpoint 0091 — existing WBM SQLite protocol preflight

The preexisting WBM target index must now include frozen candidate fingerprint and prototype-group protocol metadata. Legacy or custom-protocol indices fail closed before an original MPTrj full-source GET, even if their source SHA256 string and row count are correct. [Details](PHASE3_MPTRJ_WBM_INDEX_PROTOCOL_BINDING_V1.md). No real source request was made by this development change.
