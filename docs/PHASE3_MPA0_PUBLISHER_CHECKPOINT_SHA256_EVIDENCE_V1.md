# Phase 3 — MACE-MPA-0 upstream-reported checkpoint identity (0116)

## Positive new evidence, narrowly interpreted

The public upstream MACE code repo
[`ACEsuit/mace` commit `0f5de4b15d9c7f86d4e50996533ecf6c0f48a51b`](https://github.com/ACEsuit/mace/tree/0f5de4b15d9c7f86d4e50996533ecf6c0f48a51b)
contains both
[`tests/golden/foundation_artifacts.py`](https://github.com/ACEsuit/mace/blob/0f5de4b15d9c7f86d4e50996533ecf6c0f48a51b/tests/golden/foundation_artifacts.py)
and
[`tests/golden/references/mpa0_medium_e3nn_cpu_fp64.json`](https://github.com/ACEsuit/mace/blob/0f5de4b15d9c7f86d4e50996533ecf6c0f48a51b/tests/golden/references/mpa0_medium_e3nn_cpu_fp64.json).
Both report exactly

`75428afe3a1d7d8062e19bcaabd5c433623cabf308242ec9fb493e38604fb638`

as the SHA256 of `mace-mpa-0-medium.model`. The official golden file
declares an in-tree tracked checkpoint and states that its release URL asset
has the same digest. The
[`mace_mpa_0` release](https://github.com/ACEsuit/mace-foundations/releases/tag/mace_mpa_0)
publishes a 79,462,305-byte model of that name. The official repository
README and the
[Matbench Discovery MACE-MPA-0 record](https://github.com/janosh/matbench-discovery/blob/6ffd8070e0a7133a795a9bd4b42ec8dd9e543a46/models/mace/mace-mpa-0.yml)
confirm *dataset families* MPTrj and sAlex.

**Evidence status:** The SHA256 is **reported by upstream golden tests**.
The original model binary was NOT downloaded into Rhombus and its full bytes
were NOT independently hashed here. The GitHub release API did not expose
a verified asset digest in this review. Thus
`binary_independently_rehashed=false` and `checkpoint_file_sha256_verified`
must not be promoted to true merely from the upstream golden's string.
No source frame manifests were discovered in the particular inspected files;
this is an inspection scope limit, **not** proof they do not exist elsewhere.

The complete input inventory is at
`data/development/phase3_mpa0_publisher_checkpoint_identity_v1.json`.
Offline no-network verification:

```bash
python -m pytest -q tests/test_phase3_mpa0_publisher_checkpoint_identity.py
```

This verifies pinned source identity and rejects a forged 'verified binary',
different upstream SHA, changed asset, false training-manifest claims and
unauthorized model exposure/generalization. The code does not consume raw
source files or issue a GitHub/Figshare/Kaggle request.

## Still blocking actual MACE model training exposure audit

1. The exact **MACE-MPA-0 binary** must be independently SHA256 verified before
   one can claim verified local checkpoint byte identity.
2. The complete original MPTrj source byte SHA256 and frame-count/MD5 must be
   authenticated; the real **1MiB, first 16 frame** pilot is not that.
3. For MPTrj and sAlex, obtain complete **checkpoint-selected training frame
   manifests**, checkpoint-bound preprocessing, and energy-label selection.
4. A separate scientific auditor must qualify any training exposure use. The
   existing `assess_mace_mpa0_training_lineage_review` is only a completeness
   checklist and never flips `exposure_audit_authorized` true.

Importantly, performing a 12.2GB MPTrj original-source stream alone cannot
resolve (3). Therefore the next development priority remains the small
external checkpoint durability/restart roundtrip before any separate expensive
source processing. None of those runs is authorized by this PR.
