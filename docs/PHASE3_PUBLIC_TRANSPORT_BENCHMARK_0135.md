# Rhombus public lithium transport benchmark — checkpoint 0135

## Purpose and unambiguous claims

Rhombus's first reproducible **PUBLIC diagnostic experimental conductivity
benchmark** is a **source-traceable, original TRAIN-only reference catalogue**.
It is not a new independently blinded benchmark, not a leaderboard of
scientifically qualified model accuracy, and not 478 independent materials.

The frozen source is the original [NRC-Mila OBELiX](https://github.com/NRC-Mila/OBELiX)
commit `4eaac889809dd489e3bae468c45d5c0e02b9147a`.
The 0127–0134 real-source execution, original `raw.xlsx` censored
conductivity correction and reviewer-evidence safeguards are mandatory.

### Three distinct denominators

1. **Registered external datasets:** discovery inventory; not yet obtained
   or legally cleared for unrestricted redistribution.
2. **Actual fetched original source records:** count of experimental
   *records*, not statistically independent materials.
3. **Scientifically authenticated independent materials:** only those
   with sample-level source adjudication, correct phase/temperature/
   transport target, material independence and model exposure reviewed.
   **Current count is unknown; newly qualified count is zero.**

## Data rights / source discovery register

Source-of-truth registry:
`data/benchmarks/public_transport/source_registry_0135.json`.

| Source | Upstream reported size | 0135 safe status |
| --- | ---: | --- |
| [OBELiX](https://github.com/NRC-Mila/OBELiX) | 599 records, 321 linked CIFs | **Actual original pinned source integrated**. 478 TRAIN diagnostic rows; public original TEST 121 reserved. Attribution/source CC BY 4.0. |
| [McHaffie–Laskowski CaltechDATA](https://data.caltech.edu/records/23mvv-6gk43) | 571 literature records | **Original CSV checksum acquisition**. Includes DOI, ICSD structure *identifier* and lowest reported experimental temperature; public source rights on record are not sufficiently explicit for blind relicensing. No raw third-party CSV or licensed ICSD CIFs are redistributed. |
| [Liverpool Ionics](https://pcwww.liverpool.ac.uk/~msd30/lmds/LiIonDatabase.html) | 820 measurements; 465 RT values or estimates | **Permission-gated**; academic access is not unconditional commercial-redistribution permission. Records at 5–873 °C must never be silently relabelled 298 K. |
| Laskowski et al. literature dataset | 1,346 values reported in survey | **Primary download/rights and duplicates unresolved**; large overlap possible. |
| Shon–Min study compilation | 4,032 *measurements* reported in survey | **Primary download/rights unresolved**; not 4,032 unique solid structures. |
| [DDSE 2.0](https://www.ddse-database.org/) | Dynamic multi-ion corpus | **API, licence, ion/phase filter needed**. Large values include nonlithium and computational measurements and are not interchangeable with Li experimental RT labels. |
| SPSE (He et al.) public subset | 75 (survey reported) | **Primary public experimental source/license retrieval needed**; private larger data not assumed usable. |

These sources are **not** summed into a benchmark size. Publications
derive from one another, and matching DOIs may represent multiple
samples, phases, temperatures, or measurement protocols. In addition,
a CIF ID/ICSD code does **not** authorize distributing ICSD atomic
coordinates. External corpus acquisition must respect source rights,
license attribution, publication primary-source checks and rate limits.

The OBELiX peer-reviewed comparison:
[Therrien et al., Digital Discovery (2026), DOI 10.1039/D5DD00441A](https://pubs.rsc.org/en/content/articlehtml/2026/dd/d5dd00441a).
Caltech primary original dataset DOI: [10.22002/23mvv-6gk43](https://doi.org/10.22002/23mvv-6gk43).
Liverpool primary paper DOI:
[10.1038/s41524-022-00951-z](https://doi.org/10.1038/s41524-022-00951-z).

## Rebuild the public diagnostic benchmark (no paid compute)

The GitHub Actions workflow
`.github/workflows/phase3-obelix-real-source.yml` reconstructs
the original 0127→0134 source-linked evidence, then executes:

```powershell
py -3.11 scripts/science/public_transport_benchmark.py build-obelix-public-train `
  --obelix-checkout "C:\\path\\to\\OBELiX" `
  --evidence-dir "C:\\path\\to\\obelix-0130-evidence" `
  --raw-lineage-dir "C:\\path\\to\\obelix-0133-raw-censor" `
  --registry-json "data/benchmarks/public_transport/source_registry_0135.json" `
  --output-dir "C:\\path\\to\\public-transport-0135"
```

The **actual source**, real data provenance and official original
478/121 partition are mandatory for this CLI; synthetic tests use
an explicitly separate Python-only fixture mode.

The output `public_train_diagnostic.jsonl` contains:

- Original OBELiX record ID plus per-record and raw Excel SHA-256,
  reported reference DOI, linked CIF match class and possible
  source-overlap pair count (never interpreted as sample independence)
- 29 original `<1E-10` / `<1E-8` inequality **metadata**,
  never corrupted into fictitious `1e-15` exact measurements
- 449 other original reported positive numeric source values, explicitly
  `SOURCE_NUMERIC_UNVERIFIED` until paper/quantity/phase/temperature
  adjudication
- `eligible_for_scientific_scoring=false` on **every** row.

The public original **TEST 121 records are not exported** into
developer benchmark/training/reference rows; summary counts only.
This is a convenience contamination-control policy, not a claim that
the public TEST is newly independently blinded.

Output `summary.json` binds the complete registry, original source,
original 0134 policy and generated row-by-row benchmark byte hash,
records all unknown independent-material denominators and sets scientific
`GO=false`.

GitHub Actions artifact (when the task-specific workflow succeeds):
`public-transport-0135-obelix-train-candidates`.
The source and reconstruction code are permanently in public GitHub;
the artifact is an ephemeral 14-day convenience copy, not a claim of
permanent hosted dataset snapshot.

## Independent acquisition of another primary data source

CaltechDATA openly hosts its original
`ionic_conductivity_database.csv`, 36.1 kB, 571 records.
Published original MD5:
`d1fcf7c9a7694c8f466932721b76b168`.

The task-specific GitHub workflow retrieves the original directly
over HTTPS with strict byte/time/redirect budgets and verifies:

- The official **published file checksum** before interpreting data.
- The original CSV row count, header schema and per-column missing
  counts (source schema audit only).
- A persisted original-file SHA-256 for all future source versions.

**It does not publish the original third-party CSV, row values,
potentially restricted crystal structures or external training labels
in the GitHub Actions artifact.** The artifact
`public-transport-0135-caltech-source-metadata-only`
contains only source-hash/schema/count audit.
Reuse/republication rights require independent review. The data is
*acquired for source verification*, not integrated into a claimed
independent scientific benchmark yet.

Once explicitly permitted and sample/DOI/temperature semantics are
checked, a separate next checkpoint can support bounded joining and
duplicate detection at the original experimental material/measurement
level. Source hashes and record counts must be confirmed from the
actual workflow result; fixture tests do not substitute for this.

## Criteria for further source integration

Require verified source file SHA256/version pin, reuse rights,
the original experimental evidence or provenance chain, stable
sample identifiers, DOI, ion species and measured quantity, exact
measurement temperature (or explicit extrapolation), censored/interval
semantics and known structure correspondence. Never mix bulk and total
conductivity, current and source original room temperature, measured
and computed labels, or experimental independent materials and
correlated trajectories.

Deduplicate using multiple **candidate signals** and independent
adjudication. Do not infer a new independent-material count from
matching formula alone or absence of matching DOI alone. Model
training-frame overlap is currently **UNATTESTED**; a new external,
independently sealed blind study remains separately required.

The next checkpoint should *either* obtain explicit reuse permissions
to publish normalized external source rows *or* publish a permission-
constrained connector and internally auditable aggregate duplicate
analysis without third-party row redistribution. **No P0 scientific
red-team gate is passed by the size of this catalogue.**
