# Phase 3 — MPTrj canonical source identity preflight (v1)

## Intent and scientific boundary

The **upstream** MPTrj dataset is not the same as the **exact model training subset / converted representation**. Source-byte verification is needed but is **not sufficient** to prove that a candidate is unseen by MACE-MPA-0.

Authoritative metadata: [Figshare dataset article v2](https://api.figshare.com/v2/articles/23713842), file ID `41619375`, filename `MPtrj_2022.9_full.json`, size `12,188,168,685` bytes, declared MD5 `50ead5f27f9a4f6beb7564c4188f1e9f`, 1,580,395 declared structures. The official description explains nested `mp-id` → `frame-id` → `structure` (serialized pymatgen Structure) data and identifies a CHGNet dataset. It does **not** prove that MACE-MPA-0 was trained on precisely those unmodified bytes or all its frames.

Additional public source: [MACE foundation model documentation](https://mace-docs.readthedocs.io/en/latest/guide/foundation_models.html) states MACE-MPA-0 uses MPTrj + sAlex. This is model training-*dataset declaration*, **not training-byte attestation**. The later Matbench Discovery `mp-trj.extxyz.zip` is a converted dataset representation, not a canonical-byte substitute.

## What this PR implements

- Frozen official Figshare metadata, checked against existing `phase3_training_snapshot_resolution_v1.json`.
- `scripts/development/verify_mptrj_source.py`, **offline only**. Reads an existing local exact-filename JSON in bounded chunks and verifies file size and official MD5; calculates SHA256, with an explicitly separate flag for independent SHA256 match.
- Optional append-only JSON report `--report` created **only after** successful full-file verification. Never overwrites a report.
- Does not download the 12 GB source, store it in Git, parse 1.58 million structures, build membership, run Kaggle or authorize unseen-generalization claims.
- Regressions for altered bytes, missing/mismatched size, SHA mismatch, symlinks, source mutation gates, and evidence non-overwrite.

## Optional operator action, *only if the canonical file already exists*

From the Rhombus repository root:

```powershell
python -m scripts.development.verify_mptrj_source --source "D:\datasets\MPtrj_2022.9_full.json" --report ".\mptrj-local-source-verification.json"
```

The example path is just a placeholder. Use the actual file location. Do not trigger expensive downloads or a Kaggle kernel solely because this verifier exists. It needs sufficient disk space to **read** the already existing 12.2 GB file but does not need another 12.2 GB of output space. This one-pass hash can take time depending on storage speed.

Expected result: `MPTRJ_OFFLINE_SOURCE_SIZE_MD5_PASS <computed SHA256>` and `TRAINING_BYTES_UNATTESTED; EXPOSURE_AUDIT_NOT_AUTHORIZED`. On failure: `MPTRJ_SOURCE_FAIL_CLOSED` and **no verified report**.

Do not commit downloaded source, generated report with private local paths, or a self-computed SHA256 as though upstream independently attested it. The report is simply a local observation.

## Next scientific work

1. Investigate MACE-MPA-0 public training code, checkpoint metadata, provenance and publication to determine whether exact frame selection and dataset representation can be independently attested; if evidence is absent, retain `UNATTESTED`.
2. Implement a fixture-tested, bounded-memory **MPTrj nested-JSON structure reader** without claiming it has processed original source. Pin frame-to-structure semantics and record locators first.
3. Only with appropriate source and coverage attestations and adequate free-compute authorization, produce full MPTrj membership evidence; join with the frozen sAlex output without recomputing sAlex.
4. Keep the Phase 3 exposure/calibration and `unseen_generalization` authorization gates **false** until all declared training sources have been audited under frozen protocols.

The sealed qualification cohort remains unconsumed.
