# Phase 3 science checkpoint 0128 — experimental measurement identity review

This checkpoint follows scientific bulk intake 0127. Its purpose is to
**identify possible duplicate measurements/materials and possible source
leakage without silently merging physically distinct compounds or experiments**.

It does not increase the independently qualified benchmark count by itself.

## Run

First generate the OBELiX 0127 `records.jsonl` and `summary.json` using
`python -m rhombus.qualification.obelix_benchmark_intake` on the clean,
exact upstream checkout. Then, in a Python 3.11 Rhombus environment:

```powershell
py -3.11 -m rhombus.qualification.measurement_identity --obelix-records-jsonl "C:\\path\\to\\0127\\records.jsonl" --obelix-summary-json "C:\\path\\to\\0127\\summary.json" --output-dir "C:\\path\\to\\0128-overlap-review"
```

Optional: `--liion-records-jsonl` accepts only explicitly normalized,
source-addressed `rhombus-liion-temperature-source-record-v1` rows.
This is **not** a LiIon downloader, not an authenticated original LiIon
snapshot, and not permission to merge LiIon into OBELiX. Each optional
LiIon row must include its own source-record ID, artifact SHA256, DOI list,
reported composition, finite positive measurement temperature in Kelvin
as a string, experimental conductivity text and measurement qualification.
Keep the full LiIon per-row temperature; it cannot be replaced with the
OBELiX generic room-temperature scope.

## Conservative identity signals

The analyzer reads every original 0127 record and refuses changes to the
content-hash-bound normalized records or frozen train/test counts. It
builds **pairwise review links**, not inferred independent-material clusters,
from:

- `EXACT_REPORTED_COMPOSITION` — identical *reported strings*, not verified
  structural/defect/phase identity
- `SAME_REFERENCE_DOI` — one publication may report many different
  compositions, temperatures and individual experiments
- `IDENTICAL_CIF_FILE_BYTES` — exact archived structure bytes are identical,
  **not** proof that experimental samples or conditions are identical

Potential cross-official-OBELiX train/test matches are clearly marked
`PUBLIC_OFFICIAL_SPLIT_POTENTIAL_LEAKAGE` and **do not alter** either
official split. Separate OBELiX/LiIon signals are marked
`CROSS_SOURCE_POSSIBLE_OVERLAP`. All candidate links contain original
source IDs, original split context, explicit evidence signal codes and
whether the recorded temperature scopes match. An entirely absent signal
does **not** establish sample independence or model-training exclusion.

No transitive union-find merging is done: if source A resembles B and B
resembles C, the analyzer never assumes A and C are scientifically the
same material. No record is dropped or silently replaced.

Outputs: `review_pairs.jsonl` and `summary.json`, each deterministic;
the summary hashes exact output JSONL and binds the original 0127 record
stream SHA256. Resource limits cap the combined input to 50,000 records,
64 MiB per file, and 120,000 review links. Exceeding the pair budget
**fails closed**, never returns a misleading no-overlap verdict.

## Required scientific boundaries

- `independent_material_count = null` until phase, stoichiometry,
  disorder, measurement identity and cross-source source-evidence records
  are *independently resolved*
- `qualified_transport_material_count = null`: DOI and experimental
  conductivity do not by themselves establish quantity/temperature-specific
  self-diffusion truth or independently verified conductivity
- `externally_blinded_material_count = 0`
- `scientific_verdict = INDETERMINATE`
- `scientific_qualification_authorized = false`

The official OBELiX public test split stays public and is not an
externally sealed qualification cohort. The exact MACE-MPA-0 training
frames remain independently unattested. Do not promote diagnostic source
overlap findings to a claim of independently unseen generalization.

## Evidence and follow-up

Implementation: `rhombus/qualification/measurement_identity.py`

Test contracts: `tests/test_phase3_measurement_identity_review.py`.
All local fixtures are synthetic; no private experimental data is bundled.

Evidence: `data/development/phase3_measurement_identity_0128_evidence_v1.json`.

Checkpoint 0129 should implement *evidence-grade scoreability* for the
individually reviewed/curated experimental observations, including strict
quantity, temperature, structural-phase and provenance checks. Dataset
scale and the number of independent materials must be reported separately,
and insufficient evidence must remain UNKNOWN rather than an invented score.
