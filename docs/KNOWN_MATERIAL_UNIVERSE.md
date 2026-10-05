# Blind Known-Material Benchmark — B2 Literature-Grounded Universe Intake

## Status

B2 starts real-material curation under the B0/B1 contracts. This intake is deliberately **pre-split** and **non-executable**.

It does not yet contain sealed benchmark IDs, DEV/HELD_OUT assignment, exact executable structure artifacts, complete B1 truth bundles, numerical benchmark thresholds, or pipeline results.

## Selection principles

The intake must:

1. include both strong positive and demonstrably poor-ion-conductor controls;
2. span multiple chemistry families;
3. prefer primary peer-reviewed, phase-resolved experimental evidence;
4. preserve phase, disorder, composition, microstructure, and temperature dependence;
5. keep ionic conductivity distinct from self-diffusion;
6. require exact structure/evidence binding before B1 truth-bundle promotion;
7. postpone DEV/HELD_OUT assignment until B3.

No material is included merely because it is famous. Each entry is included because it stresses a specific external-validity failure mode.

## Initial source-screened universe

| Material context | Proposed role | Why it is useful | Current blocker |
|---|---|---|---|
| Li10GeP2S12 (LGPS) | POSITIVE | canonical high-conductivity sulfide control | exact structure + self-diffusion-specific P2.5 truth |
| Al-stabilized cubic LLZO | POSITIVE | fast garnet; paired with tetragonal phase | exact Al content/composition/structure |
| tetragonal LLZO | BORDERLINE | same nominal formula, much lower conductivity than cubic phase | exact phase structure; no arbitrary conductivity cutoff |
| LiBH4 phase-transition pair | BORDERLINE | conductivity changes sharply with structural transition | both phase structures + temperature-scoped truth |
| crystalline Li3N | POSITIVE | independent experimental fast-Li evidence; anisotropic/doping-sensitive | exact structure; pure/doped scope separation |
| microcrystalline Li2S | NEGATIVE | experimentally very poor Li-ion conductor | exact structure + self-diffusion-specific negative truth |
| nanoporous beta-Li3PS4 | BORDERLINE | microstructure/surface effects challenge periodic-bulk representation | representation policy + exact beta structure |
| Li6PS5Cl argyrodite | POSITIVE | disorder-sensitive fast-ion family | chloride-specific quantitative source + disorder-aware structure |

These roles are curation hypotheses, not benchmark outcomes.

## Primary literature currently bound at intake level

The intake records DOI identities for the following source set:

- Kamaya et al., *A lithium superionic conductor*, Nature Materials (2011), DOI 10.1038/nmat3066.
- Murugan, Thangadurai, Weppner, *Fast Lithium Ion Conduction in Garnet-Type Li7La3Zr2O12* (2007), DOI 10.1002/anie.200701144.
- Buschmann et al., *Structure and dynamics of the fast lithium ion conductor Li7La3Zr2O12* (2011), DOI 10.1039/C1CP22108F.
- Matsuo et al., *Lithium superionic conduction in lithium borohydride accompanied by structural transition* (2007), DOI 10.1063/1.2817934.
- von Alpen, Rabenau, Talat, *Li3N: A promising Li ionic conductor* (1979), DOI 10.1016/0022-4596(79)90195-6.
- Lapp, Skaarup, Hooper, *Ionic conductivity of pure and doped Li3N* (1983), DOI 10.1016/0167-2738(83)90045-0.
- Lin et al., *Lithium Superionic Sulfide Cathode for All-Solid Lithium-Sulfur Batteries* (2013), DOI 10.1021/nn400391h.
- Liu et al., *Anomalous High Ionic Conductivity of Nanoporous beta-Li3PS4* (2013), DOI 10.1021/ja3110895.
- Deiseroth et al., *Li6PS5X: A Class of Crystalline Li-Rich Solids With an Unusually High Li+ Mobility* (2008), DOI 10.1002/anie.200703900.

This list is not yet a B1 truth bundle. DOI identity alone is insufficient for benchmark truth.

## Critical scope rules

### Conductivity is not self-diffusion

A source reporting ionic conductivity can support a conductivity truth dimension but cannot, by itself, make P2.5 self-diffusion a scored truth. LGPS and Li2S therefore retain explicit P2.5 blockers.

### Phase identity is part of material identity

Cubic and tetragonal LLZO are separate entries. Their nominal formulas must not be merged into one benchmark identity.

LiBH4 must remain temperature/phase scoped across its structural transition.

### Microstructure may exceed periodic-bulk representation

Nanoporous beta-Li3PS4 is retained because it is scientifically useful, but its strong surface/porosity contribution may not be representable by the current periodic bulk pipeline. B2 must resolve that mismatch before it can become scoreable.

### Disorder must be explicit

Li6PS5Cl is retained as a source-screened argyrodite candidate, but site/anion disorder cannot be erased merely to obtain a convenient ordered CIF.

## Promotion rule

An intake entry may move to `TRUTH_BUNDLE_READY` only after:

- exact phase/composition identity is resolved;
- an executable reference structure is retained and hashed;
- B1 source/evidence atoms are retained;
- stage truths are explicitly scoped;
- evidence quantity kinds satisfy each scored truth;
- all material-specific blockers are closed.

Until then, no entry can enter B3 splitting.

## Next B2 work

The next work inside B2 is therefore evidence/structure closure, not adding a large number of famous materials:

1. obtain lawful, reproducible structure-source identities for each intake entry;
2. separate exact composition/phase variants;
3. locate self-diffusion-specific evidence where P2.5 scoring is intended;
4. decide whether nanoporous/microstructure-dominated controls are representable or must remain unscored;
5. create B1 `KnownMaterialTruthBundle` records only for entries that satisfy those requirements;
6. review class/family coverage before B3.

B3 will assign immutable DEV/HELD_OUT membership only after B2 is scientifically closed.
