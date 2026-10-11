# Phase 3 short-term scientific P0 acceptance contract — 0138

**Status: ALL THREE P0 ITEMS OPEN / SCIENTIFIC NO-GO.** This is an execution roadmap, not a science result. Canonical starting `main`: `5692c9403388d314d0d3f53b1cbe421d49aced7a` (checkpoint 0137).

## Immediate goals and independently checkable exit gates

| Gate | Evidence needed for closure | Current state |
| --- | --- | --- |
| RT-P0-01 independent blind evaluation | New independent steward, privately generated sealed materials/truth; locked preregistration and exact prediction commitment before any truth access, with adversarial attempted identity recovery and independent audit | **BLOCKED** — prior public held-out data cannot regain blinding |
| RT-P0-02 exact MACE-MPA-0 training lineage | Exact checkpoint byte identity; independently authenticated source byte SHA256, actual selected MPTrj/sAlex training frame IDs, preprocessing, energy label choices; frozen overlap audit against evaluator materials | **BLOCKED** — source family/source file alone does not prove selected training members |
| RT-P0-03 material-level statistical adequacy | Pre-registered independent sample count and precision/power target by material/phase/sample; blinded measurements at defined temperature, conductivity quantity and uncertainty; all failures/abstentions, clustered intervals and independent replication | **BLOCKED** — source-record counts and repeat trajectories are not independent physical material counts |

## Priority and dependencies

1. **P0-03 source eligibility, without score promotion:** turn checksum-attested Shon, OBELiX TRAIN and Caltech source records into **rights-gated aggregate metadata**, then original-paper/sample/phase/temperature/measurement review. Deduplicate across sources and capture explicit rejection/unknown counts. This creates *review candidates*, not independent materials.
2. **P0-02 exact model membership (parallel):** seek authoritative model provider training manifests; pin model binary, selected frame provenance and preprocessing. Record `UNKNOWN` if evidence cannot be obtained; never classify training exposure from dataset membership guesses.
3. **P0-01 new private steward (parallel):** agree on legally usable source-independent sealed specimens and a third-party custodian; protect identity and truth outside public GitHub; freeze scoring/protocol and prediction hash before disclosure.
4. **P0-03 statistical preregistration:** determine target confidence width/power with *independent* materials, explicit uncertainty and attrition assumptions. The old six-material diagnostic is insufficient and must not be promoted.
5. Run scientific qualification only after independently auditable evidence satisfies all gates. GitHub CI/metadata downloads prove engineering, not materials-science validity.

## 0138 incremental deliverable

Audit the actual fixed-hash Shon JSON's **top-level record shapes and coarse presence of predefined field-name indicator families**, emitting only aggregated numeric counts. Never emit original field names, hashes of names, formulae, DOI tokens, conductivity values, raw rows or potentially identifying values. These indicator counts cannot establish experimentally measured Li conductivity, real sample identity, rights, deduplication, temperature comparability, MACE training exposure or blinded science acceptance. Original upstream bytes are never uploaded. Preserve original 121 OBELiX public TEST labels outside development worklists.

**Stop lines:** no Kaggle/GPU jobs, third-party redistributions, new claims of independent scoreable materials, changed old checkpoints or automated scientific GO. Review of external legal rights, original-paper matching and stewardship requires separate evidence, not a code switch.
