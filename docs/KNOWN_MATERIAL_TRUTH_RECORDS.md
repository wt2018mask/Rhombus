# Blind Known-Material Benchmark — B1 Reference/Truth Record Contract

## Purpose

B1 defines how an external scientific fact becomes benchmark truth. It does not select any real material, assign DEV/HELD_OUT membership, change a scientific threshold, or run the scientific pipeline.

B0 fixed the benchmark logic. B1 now fixes the provenance chain:

```text
reference source
      ↓
retained audit artifact
      ↓
EvidenceAtom
      ↓
ReferenceStructure
      ↓
StageTruthRecord × every benchmark stage
      ↓
KnownMaterialTruthBundle
```

A stage truth that cannot be traced through this chain is not admissible benchmark truth.

## Source identity

A `ReferenceSource` binds:

- persistent source identity;
- source kind;
- locator;
- citation identity;
- source version/date;
- retained audit-artifact hashes.

The retained artifact need not be a copyrighted full-text publication. It can be a retained metadata snapshot, structured extraction, or other lawful audit artifact sufficient to verify what source was used. B1 does not authorize copying full copyrighted works into the repository.

Supported source kinds are:

- peer-reviewed article;
- primary dataset;
- curated database;
- review/standard;
- reference computation.

## Evidence atoms

An `EvidenceAtom` is one scoped scientific statement extracted from one bound source. Each atom records:

- source hash;
- B0 truth-evidence class;
- evidence-family/lineage identity;
- quantity kind;
- claim dimension;
- exact phase identity;
- species;
- conditions;
- reported value;
- units;
- uncertainty when available;
- retained evidence hashes;
- scope and limitations.

Publication count is not treated as evidence independence. Two papers that reuse the same underlying dataset must share an evidence-family identity so later analysis can avoid pseudo-replication.

## Quantity semantics

B1 distinguishes at least:

- structure;
- energetic stability;
- dynamic stability;
- self-diffusion;
- ionic conductivity;
- activation energy;
- model agreement;
- novelty identity;
- synthesis;
- application evidence.

This distinction is mandatory because experimental ionic conductivity is not interchangeable with a P2.5 self-diffusion truth or a P3 self-diffusion estimand.

A stage truth declares the quantity kinds required to support it. The truth bundle is invalid if the referenced evidence does not contain those quantity kinds.

## Exact structure and phase binding

A `ReferenceStructure` binds:

- material identity;
- composition;
- phase identity;
- exact structure hash;
- structure format;
- source-evidence hashes;
- explicit mobile species;
- chemistry family;
- reference conditions.

A composition alone is not a benchmark structure. Polymorph, disorder, occupancy, and temperature/phase context must not be silently collapsed into one material label.

## Stage truth

Every material truth bundle must explicitly account for:

```text
P0 → P1 → P2 → P2.5 → P3 → X → N → S → APPLICATION
```

No stage may silently disappear.

Each `StageTruthRecord` binds:

- stage;
- exact reference-structure hash;
- scoped truth statement/value;
- disposition;
- evidence hashes;
- required evidence quantity kinds;
- permitted pipeline verdicts;
- falsifying pipeline verdicts;
- reason codes.

Truth dispositions are:

```text
SUPPORTED
CONFLICTING
INSUFFICIENT
NOT_APPLICABLE
```

Only `SUPPORTED` truth is scoreable. A supported truth requires retained evidence and an explicit falsification rule.

`CONFLICTING`, `INSUFFICIENT`, and `NOT_APPLICABLE` truth is not scoreable and cannot be used to declare Rhombus scientifically falsified. Those states exist specifically to prevent weak literature truth from becoming a stronger benchmark claim than the source supports.

## Material-level truth bundle

A `KnownMaterialTruthBundle` contains:

- exact B0 protocol hash;
- benchmark role: POSITIVE / NEGATIVE / BORDERLINE / FAILURE_CONTROL;
- one exact reference structure;
- all bound source records;
- all evidence atoms;
- exactly one stage truth for each B0 stage;
- curation state.

The bundle verifies transitively that:

- every evidence atom references a source retained in the same bundle;
- every reference-structure evidence hash exists in the bundle;
- every stage truth binds the exact reference structure;
- every stage truth evidence hash exists in the bundle;
- required quantity kinds are actually present in the cited evidence;
- duplicate content-addressed records are rejected.

## What B1 intentionally does not contain

B1 contains no:

- real benchmark material;
- real DOI or database selection;
- DEV/HELD_OUT assignment;
- opaque `KM-` benchmark ID;
- numerical benchmark qualification threshold;
- P0/P1/P2/P2.5/P3 threshold change;
- pipeline execution;
- candidate-generation claim;
- production authorization.

Those are later milestones.

## Next step

B2 may now research and curate the literature-grounded material universe using the B1 contract.

The order remains:

```text
B0 scientific benchmark contract
→ B1 source-bound truth contract
→ B2 literature-grounded material universe
→ B3 immutable DEV/HELD_OUT split
→ B4 blind ingress
→ B5 DEV falsification
→ B6 science freeze
→ B7 one-shot HELD_OUT
→ B8 unblind + qualification
```

Candidate Supply v2 production remains blocked until the benchmark program reaches a valid held-out qualification decision.
