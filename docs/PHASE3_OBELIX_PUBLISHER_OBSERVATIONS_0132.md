# Phase 3 science checkpoint 0132 — real publisher observations, not artificial truths

## What is genuinely new

Checkpoint 0131 built **177 DOI-indexed TRAIN review groups** from real
pinned OBELiX 599-record evidence. Checkpoint **0132 reads actual publisher
article/abstract pages for four original TRAIN records** and binds carefully
scoped observations back to the exact preserved 0127 source-row SHA256,
0131 worklist and original DOI. These are **first source-page observations**,
not source-specific experimental figures/tables independently examined.

Primary publisher links were examined on **2026-10-11**; the publicly
available material is not always the full paper or supplementary figures.
The code cannot independently establish that text shown on publisher sites
is sufficient experimental ground truth. It deliberately does **not**
fetch copyrighted PDFs, infer experiment conditions or promote new scoreable
materials. No official public TEST records enter the developer review lane.

## Four deliberately bounded original-publisher observations

The four are from `TRAIN_A_EXACT_CIF_NO_SIGNAL`, the **54-record** priority
lane. They had a linked source CIF, but the CIF has not been verified as
the structure of the **actual measured sample**. Absence of an overlap
signal does not mean confirmed independence.

| Original TRAIN source ID | DOI / observed publisher text scope | Problem requiring original paper |
| --- | --- | --- |
| `dc8` | [10.1039/C3TA15264B](https://pubs.rsc.org/en/content/articlelanding/2014/ta/c3ta15264b): abstract explicitly reports **300 °C** impedance conductivity for selected Li-Mg fluorophosphates | OBELiX's numeric processed room-temperature entry must be reconciled with experimental curve or extrapolation; no claim of mismatch yet |
| `472` | [10.1021/ja302255d](https://pubs.acs.org/doi/abs/10.1021/ja302255d): publisher abstract explicitly reports a conductivity of order **5e-5 S/cm at 300 °C** for a Ce/Nd compound family | Determine which sample/structure and how the specific Nd record's room-temperature estimate was derived |
| `0o6` | [10.1021/acs.inorgchem.6b02274](https://pubs.acs.org/doi/10.1021/acs.inorgchem.6b02274): abstract reports **bulk** RT conductivity **2.5e-3 S/cm** at x=0.2 for NASICON Li1+xTi2-xScx(PO4)3 | Clarify whether the OBELiX source record is total/bulk, derived from another table or condition, and linked to the same measured sample |
| `an2` | [10.1021/acs.chemmater.1c00157](https://pubs.acs.org/doi/abs/10.1021/acs.chemmater.1c00157): article text describes Li6SiO4Cl2 conductivity ~**1e-10 S/cm at room temperature**, and a transition near **469.3 K** | Establish exact K, measured phase/disorder, site occupancy and CIF-to-experiment structure binding |

**Interpretation:** The first two observations reveal a high-temperature value
in the accessible abstract, but **do not establish the absence of a distinct
room-temperature experimental or extrapolated value** elsewhere in the paper.
The third does not automatically imply an error because bulk and total
conductivity can be different. Even the fourth cannot be marked as verified
room-temperature material truth from an approximate abstract phrase.

Full source-bound review descriptions live in
`data/benchmarks/known_material/obelix_publisher_observations_0132_v1.json`.
They include no copied original full texts or private materials.

## Run against real pinned public evidence

The exact 0130 bundle must contain the original `0127/`, `0128/`,
`0129/` plus `manifest.json` and be checked through 0131 again:

```powershell
py -3.11 scripts/science/obelix_publisher_observation_triage.py `
  --evidence-dir "C:\\path\\to\\obelix-0130-evidence" `
  --observations-json "data/benchmarks/known_material/obelix_publisher_observations_0132_v1.json" `
  --output-dir "C:\\path\\to\\obelix-0132-observations"
```

The offline validator uses 0131's source-bound queue to check every
observation's original material ID, SHA256, DOI and TRAIN access policy.
It rejects publisher URL/DOI disagreement, any official TEST observation,
unrecognized claims, unsigned assertions of scientific PASS, and forged
experiment provenance. Source pages themselves are **not live-fetched or
cryptographically verified in CI**; the reviewed text is a human-observed
publication lead, not a signed publisher artifact.

Output: `publisher_observation_review.jsonl` and `summary.json`
(hash-bound). All four observations retain explicit original figure/table,
experimental sample, temperature, phase and MACE training-lineage
uncertainty. This remains a public **diagnostic** subset.

The real-source GitHub Actions workflow runs this stage on the same pinned
OBELiX source as 0127–0131, records the 4/4 TRAIN check and a distinct
diagnostic artifact. Synthetic fixture tests cover tampering, DOI
substitution, fake publisher domains, split contamination, and attempted
science promotion.

## How to genuinely increase the independent material count

Future source adjudication should acquire appropriate legally accessible
full papers, supplementary measurements and original dataset derivation
metadata. For each case, review **the actual measured quantity, phase,
sample composition/defects, precise temperature, interpolation/extrapolation,
and traceable structure correspondence** with independent oversight. A
separate exact MACE selected-training-frame exposure audit and newly
sealed blind cohort remain mandatory.

**Current science verdict: INDETERMINATE; newly qualified material count 0.**
No Kaggle job, transport MD run, scientific GO or new private blind set was
created by this checkpoint.
