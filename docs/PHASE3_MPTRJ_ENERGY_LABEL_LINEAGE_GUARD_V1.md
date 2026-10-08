# Phase 3 MPTrj energy-label provenance guard (v1)

## Scientific motivation

The canonical [MPtrj Figshare v2 dataset](https://figshare.com/articles/dataset/Materials_Project_Trjectory_MPtrj_Dataset/23713842) was curated as a **CHGNet** training dataset. Its documented fields have different meanings:

| MPTrj JSON field | Documented meaning | Unit |
| --- | --- | --- |
| `uncorrected_total_energy` | Raw VASP DFT output energy | eV |
| `corrected_total_energy` | MP2020-compatible corrected VASP total energy | eV |
| `energy_per_atom` | Corrected energy per atom, the CHGNet training label | eV/atom |

The official [ACEsuit MACE implementation README](https://github.com/ACEsuit/mace) separately says **MACE-MP** models use MPTrj **raw DFT energies**, in contrast to MP2020-compatible CHGNet energies. The [MACE foundation repository](https://github.com/ACEsuit/mace-foundations) declares MACE-MPA-0 as trained on **MPTrj + sAlex**. Neither public declaration binds **this exact medium-mpa-0 checkpoint** to a source byte representation, frame selection, energy-field mapping, train/validation split or manifest hash.

**Do not infer that the original CHGNet `energy_per_atom` is a MACE-MPA-0 training target.** Equally, observing `uncorrected_total_energy` in the source does not prove the specific MPA-0 checkpoint consumed that field. The MACE-MP general training-label statement must not be promoted into specific MPA-0 preprocessing attestation.

## Implemented change

- `rhombus/domain/mptrj_energy_labels.py` produces a frozen `MPTrjFrameEnergyProvenance` recording the source's raw-total, corrected-total and CHGNet-corrected-per-atom energy as **separate** observed properties.
- `iter_mptrj_frames` now carries that optional annotation on every diagnostic `MPTrjFrame`. The existing canonical record identity, structure and source locator stay unchanged; membership comparison remains structure-oriented.
- Reject unsupported, non-numeric, boolean, non-finite source energy values when supplied. Missing values are `None` (never silently zero).
- A named `require_mace_mpa0_energy_training_label_provenance` policy guard **always fails closed** under this version. No fallback inferred from identical numerical raw/corrected energies. Future activation requires a separate evidence-backed protocol amendment; not a bool switch.
- The fixture tests check raw-vs-corrected differences, missing/invalid values, integration in the stream, and prevention of model-training/calibration claim escalation.
- New append-only evidence `data/development/phase3_mptrj_energy_label_lineage_evidence_v1.json` preserves official source statements and their limits.

## Not established

The ~12.2GB original MPTrj JSON has not been downloaded, fully parsed, SHA256-hashed or approved for new large computation. The capped Range inspector from checkpoint 0068 has not been run against the live original. The exact MACE-MPA-0 training frame manifest, preprocessing selection, label transformation, and checkpoint-bound hashes remain **UNATTESTED**.

The original sAlex Kaggle archive stays unchanged (Draft Release ID `406879217`). No Kaggle or GitHub Action is authorized to rerun science or publish dataset contents. No WBM unseen-generalization or empirical calibration claim is authorized.

## Next bounded work

1. Validate canonical MPTrj field shape against an authorized limited upstream source observation or retained authentic sample.
2. Seek MACE-MPA-0-specific training frame selection and label transformation evidence, not only generic MACE-MP and CHGNet docs.
3. Decide whether full MPTrj frame streaming plus source/hash-bound diagnostic comparison is worth the resources **after** upstream model-lineage evidence audit.
4. Retain a strict distinction between **structure exposure** and **energy-label consistency** when Phase 3 C0–C4 qualification resumes.
