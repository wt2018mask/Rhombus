# Phase 3 science checkpoint 0130 — real OBELiX source execution

This checkpoint **executes**, rather than merely unit-tests, the already
implemented 0127 experimental source intake, 0128 possible-overlap review and
0129 transport-reference scoreability preflight on the **entire pinned public
OBELiX checkout**. It does not request Kaggle, train a model or make a
scientific generalization claim.

## Source and reproducible computation

- Upstream: [NRC-Mila/OBELiX](https://github.com/NRC-Mila/OBELiX)
- Frozen commit: `4eaac889809dd489e3bae468c45d5c0e02b9147a`
- Attribution: NRC-Mila/OBELiX (CC-BY-4.0).
- `data/processed.csv` supplies **599 records**; original official
  `train_idx.csv` and `test_idx.csv` supply **478/121** IDs without
  shuffling; `data/randomized_cifs` contains **321 linked CIFs**.
- The original frozen source categories comprise 260 `Match`, 61
  `Close Match` and 278 `No Match` rows. Every group/record ID
  is preserved. These expected totals are a version-specific anti-drift
  contract, **not** a scientific qualification threshold.
- The official test partition is publicly disclosed, **not** a newly
  independently blinded set.

### Automatic GitHub Actions job

Workflow: `.github/workflows/phase3-obelix-real-source.yml`.
The science workflow runs for its own relevant PR changes and by manual
`workflow_dispatch` after it exists on `main`. It retrieves only the
public OBELiX upstream Git checkout at the exact pinned commit, verifies
its clean state and then executes:

```bash
PYTHONPATH=. python scripts/science/obelix_real_source_pipeline.py \
  --obelix-checkout /absolute/OBELiX \
  --output-dir /absolute/obelix-0130-evidence
```

The CLI accepts **no option to bypass the official source hash and record
count checks**. The pure function additionally supports an explicitly
labeled synthetic fixture mode for focused tests; fixture output can never
be labeled `OFFICIAL_PUBLIC_DIAGNOSTIC`.

The workflow is bounded to GitHub-hosted CPU, 15 minutes, no provider
credentials and no scientific GPU. It uploads a 14-day GitHub Actions
artifact `obelix-0130-pinned-public-diagnostic` **only after success**.
It does not write raw source back to the Rhombus Git repository.

### Persisted output

The workflow retains a source-bound diagnostic bundle:

- `0127/records.jsonl`, `0127/summary.json`
- `0128/review_pairs.jsonl`, `0128/summary.json`
- `0129/scoreability_records.jsonl`, `0129/summary.json`
- `manifest.json` with the exact upstream commit/tree, attribution,
  0127 split counts, 0128 possible-overlap pair counts, 0129 per-record
  scoreability states, and per-file SHA-256 and byte lengths.

A temporary sibling directory is populated and SHA-checked before it is
renamed into the final output location. A failed or modified run does not
present incomplete artifacts as completed audit evidence. Existing
destination bundles cannot be silently overwritten.

The workflow's real data execution result must be reviewed from its **own
Actions run and uploaded artifact** before changing any evidence status.
Passing fixture tests alone does not establish that the public source
was actually processed.

## First real pinned-source observation — 2026-10-11

The task-specific [actual public-source workflow run #38101282952](https://github.com/wt2018mask/Rhombus/actions/runs/38101282952) **completed successfully** at Rhombus source commit `56d392e7e7d3f6097223c881b79f4ea673c05b69`. The independently downloaded workflow artifact was rechecked byte-for-byte against its manifest.

| Pinned OBELiX measurement/provenance result | Observed |
| --- | ---: |
| Public experimental records | **599** |
| Original official TRAIN / TEST | **478 / 121** |
| Source CIF files | **321** |
| Exact / close / missing source CIF match classifications | **260 / 61 / 278** |
| Different *raw formula strings* | **518** |
| Candidate record-pairs sharing exact formula string or DOI | **1,869** |
| Individual records associated with possible overlap | **503** |
| Records with no current overlap signal but still missing external evidence | **96** |
| New externally blind materials | **0** |

Breakdown of the direct pairwise signals: 131 same formula-string pairs,
1,740 same DOI pairs, 0 identical source CIF-byte pairs; overlapping signal
categories mean these are **not additive independent materials**. No direct
cross-official-TRAIN/TEST signal was found by these particular exact matching
criteria, which **does not establish the absence of all training leakage**.

Run artifact ID `11687906601`, source-tree SHA
`e71a9ff2d9d92781b7b5a1ef6225cf6add934bf5`.
File evidence is content-addressed in
`data/development/phase3_obelix_real_source_0130_evidence_v1.json`.

This was a valid task-specific real-source run; the completed PR must still
pass the full exact-head **Fast CI, Development Continuity, Wave 2 and
real-source** jobs before merge. None of the 96 no-overlap-signal records is
independently qualified by this finding. All 599 source fields are processed
numerically in the upstream CSV; whether the *original experiments* included
censored limits remains independently unreviewed.

## Scientific limits (unchanged NO-GO)

`source_records=599` does not mean 599 unique materials or 599 independent,
qualified experimental truths. Same formula/DOI/CIF possible matches
require external adjudication; absence of a match is not proof of
independence. The exact experimental temperature, measurement quantity,
phase and sampling/defect conditions must be reconciled. Reported
conductivity is not the same target as simulated self-diffusion.

Thus `independent_material_count=null`,
`qualified_experimental_transport_count=null`,
`new_externally_blinded_count=0`,
`scientific_verdict=INDETERMINATE`, and
`scientific_qualification_authorized=false`.

P0 red-team blockers remain: independent exact MACE-MPA-0 model training
frame lineage; new truly blinded cohort steward; sufficient independent
material-level statistics. No Kaggle new submissions, no MD work, and
no science release GO are authorized.

## Next scientific development

After a successful real-source workflow and exact-head CI integration,
use the **actual** per-record gap list and overlap groups to prioritize
independent original-paper adjudication, precise temperatures, experimental
phase/structure evidence and a valid training-exposure assessment. Separate
blind-cohort and training-lineage programs remain independent gates.

Engineering tests:
`tests/test_phase3_obelix_real_source_pipeline.py`.
Evidence:
`data/development/phase3_obelix_real_source_0130_evidence_v1.json`.
