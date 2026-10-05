# Blind Known-Material Benchmark — B2 Structure Binding

B2 now distinguishes a literature citation from an executable reference structure.

A material is **not** structure-closed because a paper, DOI, database page, or supplementary-file link exists.  Before a structure can feed a B1 `ReferenceStructure`, Rhombus requires all of the following:

1. exact composition and phase identity;
2. an artifact locator traceable to the scientific source;
3. an explicit disorder/partial-occupancy representation policy;
4. redistribution rights compatible with repository retention;
5. the actual retained structure artifact;
6. SHA256 binding of the retained bytes;
7. validation that the retained artifact is the intended phase/composition.

The binding state machine is:

`SOURCE_IDENTIFIED -> ARTIFACT_RETAINED -> HASHED_AND_VALIDATED`

`REJECTED` is available for a source/artifact that fails provenance, rights, identity, or representation checks.

## Fail-closed rules

- A remote supplementary CIF whose redistribution rights have not been verified remains `REMOTE_ONLY_UNVERIFIED`; it cannot be stored in the repository merely because it is downloadable.
- `HASHED_AND_VALIDATED` requires both a retained path and a full SHA256.
- Repo-retained validated structures require `VERIFIED_REDISTRIBUTABLE`.
- A validated structure cannot retain unresolved blockers.
- B2 structure closure is true only when every ledger entry is validated.
- This layer still cannot assign DEV/HELD_OUT, run the blind benchmark, or authorize Candidate Supply production.

## Current ledger status

All eight B2 intake entries remain deliberately unclosed.

For LGPS, the primary single-crystal paper exposes two supplementary CIFs.  The ledger points to the first primary CIF source, but keeps it remote-only until redistribution rights and executable partial-occupancy policy are resolved.

Cubic and tetragonal LLZO remain separate. The cubic Buschmann specimen is now source-bound to COD `7215448@176453`: `Al0.196La3Li6.06O12Zr2`, cubic `Ia-3d` (No. 230), 300 K. COD is CC0, so redistribution rights are resolved; the entry remains unclosed until the exact pinned CIF bytes are retained, hashed, and a deterministic fractional Li/Al occupancy execution policy is defined.

LiBH4 requires two temperature/phase-resolved structures.

Li3N and Li2S require lawful exact structure sources rather than treating transport papers as structure repositories.

Nanoporous beta-Li3PS4 retains an explicit representation blocker because a periodic bulk CIF cannot silently stand in for a surface/porosity-dominated experimental system.

Li6PS5Cl requires a disorder-aware structure.  An ordered proxy cannot silently erase S/Cl site disorder or Li occupancy.

## COD import verification

`rudeus/science/known_material_structure_import.py` defines an offline verifier for pinned COD artifacts. Network retrieval is intentionally not scientific evidence by itself. Retained CIF bytes must match the expected COD id, formula, space-group number, and coordinate-bearing CIF payload before their SHA256 can be accepted.

This prevents a mutable "latest" database URL, wrong polymorph, wrong composition, or metadata-only record from silently becoming a benchmark structure.

## What closes this part of B2

The next scientific curation operation is to locate redistributable primary/database structure artifacts, retain and hash them, then validate composition/phase/disorder semantics. Only after those records become `HASHED_AND_VALIDATED` can their structure hashes be promoted into complete B1 truth bundles.

B3 splitting remains forbidden until B2 truth and structure closure is complete.


## Generic artifact curation boundary

Artifact acquisition is now separated from scientific structure binding.

The generic curation path is:

```
artifact_registry_v1.json
        ↓
scope planner
        ↓
source adapter
        ↓
byte-preserving validation + retention
        ↓
artifact_retention_index_v1.json
        ↓
later scientific binding / representation resolution
```

The retention index is keyed by `artifact_key`, not by material identity. This is
intentional: one benchmark material may require multiple retained structures, phase
representatives, disorder realizations, or source artifacts. Mechanical acquisition
must not collapse those artifacts into one scientific structure hash.

The curation workflow therefore does **not** directly promote
`StructureArtifactBinding` to `HASHED_AND_VALIDATED`. It only proves that exact,
source-validated bytes were lawfully retained. A later binding resolver must decide
whether the retained artifact set adequately represents the phase/composition/disorder
scope required by the benchmark.

The workflow is registry-driven and exposes macro scopes:

- `unresolved`
- `all`
- `material`
- `family`
- `source`

Adding another material that uses an existing adapter requires registry data rather
than a workflow or production-code material allowlist.
