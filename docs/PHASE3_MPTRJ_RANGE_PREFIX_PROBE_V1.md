# Phase 3 — bounded upstream MPTrj prefix probe (v1)

## Purpose

The original [MPTrj Figshare v2](https://figshare.com/articles/dataset/Materials_Project_Trjectory_MPtrj_Dataset/23713842) is a **12,188,168,685-byte** nested JSON (Figshare file ID `41619375`), and official documentation describes `mp-id → frame-id → frame.structure`. Yet our `ijson` parser has only been tested against synthetic fixtures. A small bounded source-derived prefix is useful to check whether the **first frame's field hierarchy** begins as documented, without downloading the 12.2GB file.

`scripts/development/probe_mptrj_source_prefix.py` implements an **explicit, optional** HTTPS `Range: bytes=0-N` request to the exact frozen Figshare file ID. It defaults to 256KiB and refuses any request above 1MiB.

### Fail-closed network contract

- No network call occurs on import or without `--probe`.
- Reject **HTTP 200** (server ignored Range) before reading the body, as well as any status other than **206**. There is **no full-download fallback**.
- Require `Content-Range` to cover exactly the requested initial byte range and declare the expected whole-file byte count. Reject unexpected compression, conflicting `Content-Length`, insecure redirects, short or long bodies.
- Read in chunks of at most 8KiB, never more than the explicitly requested byte budget plus one check byte.
- Observe only the first material ID, first frame ID, and whether the first frame's `structure` field begins a JSON object. If the first structure field is not reached within the bounded prefix, fail closed; a larger prefix (up to 1MiB) is a separate explicit choice.
- Write an optional observation report **only on success**, via exclusive creation (no replacement). It records prefix byte count and SHA256, but no full original-file hash or frame-level attestation.
- HTTP Content-Range is **server metadata**, not independent proof of source identity, and observing the prefix does not establish the first full pymatgen Structure is valid.

### Optional manual example

From the repository root, **only when a limited network request is appropriate**:

```powershell
python -m pip install -e ".[phase3-mptrj]"
python -m scripts.development.probe_mptrj_source_prefix --probe --report .\mptrj-prefix-observation.json
```

Do not invoke this automatically in CI, scheduled workflows, Kaggle, or production scientific data processing. Some source mirrors/CDNs may not support byte-range requests; on a missing 206 response the correct outcome is **safe failure**, not a larger download.

Expected success text: `MPTRJ_PREFIX_STRUCTURE_OBSERVED_NON_AUTHORITATIVE`. A successful prefix report is useful for deciding whether the **real original-file shape** is compatible with our parser, but a full canonical original-file read/MD5/row-count validation remains a separate task.

### MPTrj training-lineage evidence boundary

The [MACE foundation model table](https://github.com/ACEsuit/mace-foundations) documents **MACE-MPA-0** as trained on **MPTrj + sAlex**. That is a declaration of training dataset families, **not** a checkpoint-bound exact frame ID manifest, processed data bytes or preprocessing selection proof. The Figshare original describes data that trained **CHGNet**; its 1,580,395 records need not be identical to the frames used by MACE-MPA-0.

Do not infer full-source coverage, absence of training overlap, unseen-model generalization, application-domain qualification, or empirical uncertainty calibration from this probe.

### Next work

1. Use a genuine limited source prefix observation *only after separate operator authorization*, or inspect an already-held verified original.
2. Match it against full-file reader assumptions and benchmark parsing memory/throughput on representative bounded fixtures.
3. Continue seeking MACE-MPA-0 training-specific preprocessing and frame selection evidence. If no checkpoint-bound manifest exists, explicitly preserve **UNATTESTED**.
4. Decide whether a full source scan is justified given resource budget and the remaining training-lineage gaps. **Never rerun sAlex on Kaggle.**

The original sAlex results remain stored in Draft Release ID `406879217`; this PR changes no Releases, models, training data or past evidence records.
