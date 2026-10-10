# Phase 3 — checkpoint 0127: OBELiX bulk benchmark intake

**Goal:** replace hand-curated six-material benchmark bottleneck with a
**verifiable, bulk, source-bound experimental-intake lane**. This is the first
scientific data acquisition/normalization step, not a GPU model evaluation.
It does not rewrite or rehabilitate the old B3 public HELD_OUT.

## Verified upstream reference

Official upstream: [NRC-Mila/OBELiX](https://github.com/NRC-Mila/OBELiX)
at pinned commit
`4eaac889809dd489e3bae468c45d5c0e02b9147a`.

Files at that reference:
- `data/processed.csv`: 599 rows, 12 columns, including
  `Ionic conductivity (S cm-1)`, `DOI`, and CIF provenance class.
- `data/train_idx.csv`: official 478 ID entries.
- `data/test_idx.csv`: official 121 ID entries.
- `data/randomized_cifs/`: 321 source CIF files.

Independent read-only GitHub source inspection for this checkpoint observed
260 rows declared `Match`, 61 `Close Match`, 278 `No Match`.
The 599 `processed.csv` conductivity fields are numeric *processed values*;
**they are not independently adjudicated point measurements**. Original raw
experiments can include censoring/upper limits, so it would be unsafe to claim
599 uncensored and comparable scientific truths. The source files were
inspected through GitHub but the *new executable intake has only been tested
against synthetic checkouts before a real pinned-checkout execution*. Verify
machine-reported hashes and counts by running the command below.

## Run on Windows PowerShell

```powershell
git clone https://github.com/NRC-Mila/OBELiX.git OBELiX
git -C OBELiX checkout 4eaac889809dd489e3bae468c45d5c0e02b9147a
py -3.11 -m rhombus.qualification.obelix_benchmark_intake --obelix-checkout "C:\\path\\to\\OBELiX" --output-dir "C:\\path\\to\\obelix-intake-0127"
```

Run that command **from the Rhombus repository** using a Python 3.11
environment with Rhombus importable. The external source checkout must be
clean. Use a new empty output directory **outside** the upstream checkout.
No Kaggle account, secret, GPU, or online model API is required after checkout.
The command does not fetch data by itself.

Output:
- `records.jsonl`: one deterministic normalized **source record**
  per official source ID; original split, reported formula, positive
  conductivity text and unit, upper-bound indication where explicitly
  present, DOI tokens, CIF match type and CIF file SHA256.
- `summary.json`: source commit/tree, input CSV/SPLIT hashes,
  inventory digest, output SHA256, split and CIF counts, declared censored
  value counts, direct cross-split formula/DOI overlap counts, and explicit
  scientific incompleteness.

The adapter itself does **not** parse CIF atomic sites or compute diffusion.
It reuses the existing strict
`rudeus.generation.candidate_supply_obelix_adapter` with no parser
invocations. The adapter verifies a clean Git checkout and computes source
CSV, inventory and CIF hashes. Only the source author's original index lists
specify the splits; intake **never** recomputes or rebalances them. New data
revisions must be explicitly reviewed and separately pinned by SHA.

## Levels of evidence that must not be confused

1. **599 upstream measurement records**: officially source-identified.
2. **321 source CIF files**: some are *close* structural matches; this is
   not a verified exact measured phase or atomic occupancy.
3. **Deduplicated independent material count**: **UNKNOWN** until
   composition, phase, disorder, temperature, DOI and repeated-experiment
   identity are reconciled, including cross-dataset duplicates.
4. **Scientifically scoreable transport references**: **NOT YET
   AUTHORIZED** by source ingestion; independent experimental source
   review, quantity/temperature matching and source exclusions are required.
5. **Independent blind HELD_OUT qualifications**: **ZERO NEW**. The OBELiX
   official test set is *public* and is **not** a new secretly governed blind
   cohort.

A raw OBELiX `processed.csv` observation is experimental ionic
conductivity in S/cm, **not** P2.5 self-diffusion or a verified activation
barrier. Do not train on the official test rows. Do not use public test
measurements to adjust estimators or thresholds. Do not merge LiIon entries
into OBELiX; treat the former as separately source-bound observations.

## Release/development gates

The benchmark collector is CPU-bounded (8MiB CSV, 1MiB per split, 50k rows,
50k CIF files, 16MiB per CIF). It rejects malformed data, contradictory
CIF inventory, dirty/unpinned source, malformed conductivity, duplicate IDs,
split omissions/overlap and source path escapes. Normalized JSONL is
content-hash-bound and the original checkout is never written to.

No Kaggle run or model inference is submitted here. Later explicit steps:
(0128) versioned multi-source measurement identity/dedup; (0129)
physical quantity/structure/temperature scoreability and independent
training-exposure policy; (0130) small authorized GPU screening with durable
checkpoint/resume; (0131) material/group evaluation with independent truth.

See `data/development/phase3_obelix_intake_0127_evidence_v1.json`
and `tests/test_phase3_obelix_benchmark_intake.py`.
