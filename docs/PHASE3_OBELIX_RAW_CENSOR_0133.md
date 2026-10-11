# Phase 3 science checkpoint 0133 — original OBELiX Excel censoring recovery

## Scientific discovery requiring immediate benchmark policy change

The *original* public [OBELiX upstream repository](https://github.com/NRC-Mila/OBELiX)
at commit `4eaac889809dd489e3bae468c45d5c0e02b9147a`
contains both `data/raw.xlsx` and a lossy training-only
`data/processed.csv`.

The source's **own** `data/README.md` explicitly defines `raw.xlsx`
as the raw dataset and `processed.csv` as a selection of fields
needed for training. Its `data/scripts/preprocessing.py` includes:

```python
def replace_text_IC(cond):
    if cond == '<1E-10' or cond == '<1E-8':
        return 1e-15
```

This is the original source author's source code (not a Rhombus design
decision). **An original upper bound such as `<1E-10` is not a direct
point measurement of `1e-15` S/cm.** Using that stand-in as an exact
experimental truth, as a regression target with symmetric errors, or as
a scientific score would distort a benchmark.

A fresh source-only inspection of the frozen `processed.csv`
counted **37 fields equal to `1e-15` among 599**. That observation
alone cannot prove all 37 raw source entries were originally upper
limits; this checkpoint independently joins the exact original
`raw.xlsx` by immutable entry IDs to establish the mapping.

The public OBELiX scientific paper additionally documents source
curation from original publications and differentiates **total** and
**bulk** conductivity. The upstream raw workbook has fields including
`IC (Total)` and `IC (Bulk)`, which must not be silently conflated
with MD self-diffusion or each other.

## Implementation

`scripts/science/obelix_raw_censor_lineage.py` reads
`data/raw.xlsx` with a bounded Python standard-library OOXML reader
(ZIP+XML, no downloaded dependencies) from a **clean pinned Git
checkout** of exactly the same upstream commit as the immutable 0130
evidence bundle.

Every processed `0127` entry must be present in the raw workbook.
For each entry, the original column
`Ionic conductivity (S cm-1)` and the original source ID are matched:

- `ORIGINAL_UPPER_BOUND_NUMERIC_PLACEHOLDER`: exact raw upper-bound
  syntax `<1E-10` or `<1E-8`, corresponding processed numeric
  field `1e-15`. The actual inequality is preserved as a text
  interval/upper-bound restriction, **not** relabeled as an exact
  observation.
- `RAW_REPORTED_NUMERIC`: original positive numeric source field.
  This still does not independently authenticate the paper's sample,
  temperature or structural phase.
- `RAW_NONNUMERIC_UNRESOLVED`: other original source qualifiers
  requiring manual review.

Outputs are source-bound, deterministic
`train_raw_measurement_lineage.jsonl` and `summary.json`,
including source SHA256, split-level censoring counts, raw workbook
SHA256 and optional bulk/total source metadata.

**Public TEST protection:** the report emits only the 478 official
TRAIN records at the record level. Original TEST 121 IDs, exact
measurement values and other metadata are **never exported** to
the developer-facing artifact; only aggregate counts are included.
No public TEST is promoted to an independently sealed trial.

Version-specific official real-source CI requires **37 exact raw
upper-bound ↔ 1e-15 transformations**, 599 source records, and the
original 478/121 split. Source mismatch, dirty checkouts, unexpected
censor qualifiers, tampered earlier science evidence and inconsistent
row mappings fail closed.

### Reproduce

Run from the Rhombus root with Python 3.11 and the clean official
public upstream checkout plus matching 0130 artifact:

```powershell
py -3.11 scripts/science/obelix_raw_censor_lineage.py `
  --obelix-checkout "C:\\path\\to\\OBELiX" `
  --evidence-dir "C:\\path\\to\\obelix-0130-evidence" `
  --output-dir "C:\\path\\to\\obelix-0133-censor-evidence"
```

Task-specific GitHub workflow:
`.github/workflows/phase3-obelix-real-source.yml`.

Offline synthetic adversarial fixtures are in
`tests/test_phase3_obelix_raw_censor_lineage.py`.
The original censoring evidence and test result are recorded in
`data/development/phase3_obelix_raw_censor_0133_evidence_v1.json`.

## Verified pinned original-workbook census — 2026-10-11

The [0133 real-source GitHub Actions run #38104711288](https://github.com/wt2018mask/Rhombus/actions/runs/38104711288)
**PASSed** on code SHA `9e81efb73b793a376a337b21ed412d169097281e`.
The publicly released raw `data/raw.xlsx` and processed input
were joined by all **599 original IDs**, with **37 original upper bounds**
corresponding exactly to 37 substituted `1e-15` numbers.

| Frozen original-source count | Result |
| --- | ---: |
| All raw workbook entries | **599** |
| Source raw numeric positive measurements | **562** |
| Upper-bound records in raw workbook | **37** |
| Censored official TRAIN entries | **29** |
| Censored official TEST entries (aggregate only) | **8** |
| TRAIN original bounds `<1E-10` | **28** |
| TRAIN original bounds `<1E-8` | **1** |
| Original TEST identifiers/values in developer evidence | **0** |

Downloaded Actions artifact
`obelix-0133-train-raw-censor-lineage` ID `11689133329`
has SHA-256 `45727761cecb006a4c5326ad2a003de82dac879bc6d690e250e7f58a969449de`
for its ZIP. Its TRAIN-only JSONL SHA-256 is
`35d3fe7ae3812ccdc94d413b625f98b51b5d74acb1fa5c7bf526dd4d9ee0e5dc`,
independently recomputed from the downloaded artifact.

Original raw workbook SHA-256:
`ef58c3b5c10b2e1f71f00bc2cafdc23d8e4a4e82f61ef94adc54f5c6753562ed`.

This corrects the earlier implicit numeric-point interpretation of
the 37 placeholders: **they are original upper limits**, not measured
`1e-15` conductivities. Whether other 562 raw numerical labels have
correct experiment-to-sample matching remains a separate scientific
question. The final PR commit must pass all required CI again.

## Status and next scientific milestone

The 0127–0132 artifacts historically captured the source authors'
**numeric processed label**. They are **not retrospectively described
as 599 exact experimentally verified point truths**. This 0133 audit
is the traceable loss-of-censoring correction overlay, not silent
editing of immutable preceding artifacts.

The next code change must add interval-aware scoring/exclusion policy
to subsequent numerical transport comparisons, with explicit temperature,
quantity and material-independent scientific evidence gates. Even when
all 37 upper bounds are successfully mapped, the independent benchmark
material count remains **unknown**, new independently blinded test
samples remain **0**, and scientific qualification remains **NO-GO**.
