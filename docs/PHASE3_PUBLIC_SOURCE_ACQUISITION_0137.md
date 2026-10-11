# Public benchmark 0137 — acquisition of third first-party original source

## Source policy and motivation

Canonical starting `main`:
`253a223cf9849f8ef56a4f85ace120f69de1b40d`,
after successful merge of [PR #301](https://github.com/wt2018mask/Rhombus/pull/301)
with all four exact-HEAD GitHub Actions PASS.

The earlier source registry named seven possible datasets but had
**actually downloaded original bytes only from two**: OBELiX
(599 entries) and CaltechDATA/McHaffie–Laskowski (571 entries).
The next expansion must not fabricate 1,170 *independent materials*
or treat Caltech's 56 full-metadata / unmatched-DOI source review
candidates as confirmed novel conductors.

### Third directly published research source: Shon/Min (2023)

Primary paper: Yeajin Shon and Kyoungmin Min,
*Extracting Chemical Information from Scientific Literature Using Text
Mining: Building an Ionic Conductivity Database for Solid-State
Electrolytes*, ACS Omega (2023), DOI
[10.1021/acsomega.3c01424](https://doi.org/10.1021/acsomega.3c01424).

**Original authors' repository:**
[shonyeajin/Ionical_conductivity_database](https://github.com/shonyeajin/Ionical_conductivity_database).
Its own README advertises
`database/IonicalConductivityDatabase.json` as the JSON database export.
The `SHON_MIN_2024` registry identifier is retained as an immutable
compatibility key from 0135, **not an assertion the original paper is
dated 2024**. The primary publication is dated 2023.

Exact immutable upstream commit:
`bec7ffb07b3dde33191eba6aceda1fbfd3b03ea3`.
Exact original file Git blob SHA-1:
`b0e8a20c8806aec337e3547fbd0101094cd4f624`.
File size reported by the official GitHub contents API: **7,063,926
bytes**. The SHA above is a Git blob identity of the complete original
file, not a checksum of a JSON re-serialization or subset.

The upstream repository currently does **not display a recognized
repository-level software/data licence** in its GitHub metadata. This
does not prove redistribution rights; it is an independent blocker
to republishing source rows. The original source may contain material
that is not Li-ion specific, measured at room temperature, associated
with a CIF, or a validated single experimental sample. The historical
4,032 figure from a secondary data catalogue remains a **reported
literature count, not the audited original JSON object count**.

The existing [Liverpool Ionics Dataset](https://pcwww.liverpool.ac.uk/~msd30/lmds/LiIonDatabase.html)
is freely usable for academic research with proper citation but needs
a separate licence for commercial reuse. Therefore this change does
not mirror the Liverpool CSV publicly or represent the separate
[Laskowski/McHaffie EES 2023 paper](https://doi.org/10.1039/D2EE03499A)
as a newly independent cohort.

## Implemented source acquisition contract

`scripts/science/public_transport_shon_original_audit.py` operates
only on an original bounded byte file and computes:

- Official source byte size and **Git object SHA-1** as:
  `SHA1("blob " + decimal byte count + NUL + source file bytes)`.
- An independent source file SHA-256 for future source replay.
- Strict JSON decoding and finite numeric semantics; bounded byte size,
  maximum nested depth, total nodes and object/array entry counts.
- Aggregate-only original root type, number of top-level entries (which
  are **not** automatically measurement records), number of JSON value
  nodes and types.
- Separate explicit `confirmed_experimental_Li_solid_state_measurements=null`,
  `newly_qualified_independent_materials=0`,
  `official_scientific_benchmark_scoring_authorized=false`,
  `data_license_permission_to_republish_verified=false`.

Original data bytes, JSON source content, source formula strings, DOI
identifiers, conductivity values, and per-row descriptions **are
never uploaded or committed**. The GitHub Actions worker downloads
the exact pinned original HTTPS URL, limits the transfer to 8MB,
validates its original Git blob and emits the small aggregate receipt
`public-transport-0137-shon-first-party-original-audit` with
14-day retention. Its permanent reproducibility contract is in Git
(the code, source commit, blob SHA and evidence summary), not an
unlicensed snapshot of the original database.

Command, for a locally acquired exact original file:

```powershell
py -3.11 scripts/science/public_transport_shon_original_audit.py `
  --original-json "C:\\sources\\original-shon-database.json" `
  --output-dir "C:\\reports\\shon-0137-source-audit"
```

Synthetic fail-closed regressions:
`tests/test_phase3_public_transport_shon_original_audit.py`.

## Scientific status and next expansion

Even after successful primary source acquisition, the source corpus
has **not** been filtered to original experimental lithium-only solid
electrolyte measurements or matched to independent papers, structural
phases, exact temperatures, duplicates, exact selected MACE training
frames, or a new externally held blind cohort. No new materials are
admitted to an independently scored evaluation and scientific P0
remains **NO-GO**.

Next checkpoints should implement a source-bound, rights-aware
**original record schema inspection** (aggregates only until the original
record rights are cleared), then retrieve Liverpool primary source
bytes and original Laskowski supplementary information with explicit
temperature and measurement provenance; followed by Shon, DDSE
and SPSE independent original source audits as each is available.
Prefer directly authenticated *new independent material candidates*
to increasing raw row counters. All prior source evidence remains
immutable.
