# Phase 3 science checkpoint 0131 — OBELiX source-adjudication worklists

## Actual scientific purpose

Phase 3 0130 established a real, pinned, byte-verified 599-record
OBELiX run with 478 official TRAIN rows, 121 official TEST rows,
503 rows with possible overlap signals, 96 rows without exact
formula/DOI/CIF overlap signals but with outstanding experimental evidence,
and 1,869 possible overlap *pairs*. This is **not** a 599-material
independent generalization validation.

Checkpoint 0131 creates an actionable **source-paper and per-record
evidence review queue** from that real 0130 evidence, not another
prediction or experimental simulation.

## Reproduce locally

Use the 0130 `obelix-0130-pinned-public-diagnostic` artifact directory
from the exact GitHub Actions run, with `manifest.json`, `0127/`,
`0128/`, `0129/` intact. From the Rhombus root:

```powershell
py -3.11 scripts/science/obelix_adjudication_queue.py --evidence-dir "C:\\path\\to\\obelix-0130-evidence" --output-dir "C:\\path\\to\\obelix-0131-queue"
```

The task-specific workflow
`.github/workflows/phase3-obelix-real-source.yml` now executes the
entire public 0127–0129 pipeline **and then** builds the 0131 queue,
verifies all source/output digests, and uploads a separate
`obelix-0131-public-source-adjudication` evidence artifact.

Only exact frozen source `NRC-Mila/OBELiX` commit
`4eaac889809dd489e3bae468c45d5c0e02b9147a`
is accepted by this command. Tests use an explicitly distinct
`SYNTHETIC_FIXTURE_ONLY` pure-function mode. This mode is never exposed
in the real CLI.

## Worklist contents

`record_review_queue.jsonl` holds every original source entry exactly
once, including the **official original split and original source-record
SHA-256**, source CIF match class, DOI, possible overlap pair count,
missing experimental review requirements and access policy. It
deliberately does *not* contain conductivity truth values for ranking.

The priority lanes are *workflow ordering*, not scientific quality
rankings, fitness, material identity or statistically valid samples:

- `TRAIN_A_EXACT_CIF_NO_SIGNAL`: TRAIN, linked source `Match` CIF,
  available DOI, processed point-value field and **no current exact
  formula/DOI/CIF pair signal**; the material/phase and paper remain
  entirely unverified
- `TRAIN_B_EXACT_CIF_REVIEW_OVERLAP`: TRAIN, exact-source CIF but
  candidate pairs need phase/measurement independence review
- `TRAIN_C_EXPERIMENTAL_PHASE_REVIEW`: TRAIN, `Close Match` source
  structure; requires measured-phase linkage before structural scoring
- `TRAIN_D_STRUCTURE_ACQUISITION`: TRAIN, no source CIF; needs
  evidence-specific structural acquisition, not synthetic reconstruction
  presented as ground truth
- `TRAIN_E_SOURCE_VALUE_REVIEW`: other TRAIN experimental/censoring/DOI
  gaps without candidate-pair signal
- `TEST_RESERVED_AUDIT_ONLY`: **every official TEST row** is preserved
  for independently governed diagnostic integrity and **never enters
  the development source-paper worklist**. Public test identities are
  not a new secret held-out set.

`paper_review_queue.jsonl` indexes only TRAIN source rows by their
reported DOI (or a unique `MISSING_DOI_RECORD:` key). One row may
occur under multiple papers; DOI equality does **not** prove one paper
has one experimental sample, and overlapping DOI groups are never
automatically collapsed into independently validated materials. It
contains *neither test entries nor experimental conductivity values*.

`summary.json` provides all lane counts, report hashes, exact upstream
0130 stage hashes and explicit science NO-GO. It does not assert that
absence of an overlap signal confirms material independence.

## First real 0131 pinned-source output — 2026-10-11

The [task-specific real OBELiX workflow #38102820209](https://github.com/wt2018mask/Rhombus/actions/runs/38102820209)
executed the full pinned upstream 0127→0130 source and this new 0131 queue;
its verification and 0131 diagnostic evidence upload both **PASS** on
Rhombus commit `8710c33cbba4abce830b560100e4c86ac30c8aca`.
Artifact `obelix-0131-public-source-adjudication` (ID `11688631083`)
contains the actual source-bound JSONL and summary.

| Exact public source worklist lane | Records |
| --- | ---: |
| TRAIN A — source CIF match, no current exact overlap signal | 54 |
| TRAIN B — source CIF match with possible overlap signal | 148 |
| TRAIN C — close CIF requires experimental phase evidence | 52 |
| TRAIN D — no source CIF, structure evidence needed | 224 |
| TRAIN E — other unresolved source-value gaps | 0 |
| TEST — reserved, never included in developer paper-review queue | 121 |
| **Total** | **599** |

There are **177 DOI-indexed TRAIN paper review groups**. That is
neither 177 distinct independently certified studies nor 177 validated
independent materials. Original TRAIN contributes 478 records; 121 public
TEST records retain their original identities under reserved audit-only
policy. No true external independent blind set was created.

The exact queue hashes and the real workflow evidence URL are retained in
`data/development/phase3_obelix_adjudication_0131_evidence_v1.json`.
These are *source-paper review priorities*, not validated material
conductivities, structures, independent sample sizes or model accuracy.

The new PR must still pass its **final HEAD's** full required workflow set
before merging. Source data correctness requires separately obtaining
original paper-level measurements; no original paper is independently
reviewed by this checkpoint.

## Evidence required before promotion

For every candidate: source-paper original measured quantity, sample
phase/defects/occupancies and matching CIF, exact measurement
temperature, measurement censoring/units, paper/study-level identity,
and model training-exposure/selected frame provenance must be verified.
External stewardship must decide when a reviewed material is actually
independent and suitable for an unbiased final trial. A source record
can require many independent evidence receipts; a DOI and its SHA256
alone are not verified scientific truth.

Checkpoint 0131 itself **does not** download publisher manuscripts,
infer missing phases or temperatures, verify actual paper contents,
retrain a model, run a Kaggle GPU or dispatch an independent secret
blind validation. It cannot issue a scientific PASS.

Relevant files: `scripts/science/obelix_adjudication_queue.py`,
`tests/test_phase3_obelix_adjudication_queue.py`,
`data/development/phase3_obelix_adjudication_0131_evidence_v1.json`.

**Next science step 0132:** prioritize and curate bounded original
source-paper evidence, carefully distinguish independently reviewed
temperature/phase/transport claims from untrusted declarations, and
decide study-level sampling targets. Keep P0-01/02/03 separately blocked.
