# Phase 3 — repeat the real MPTrj first 256KiB observation (v1)

Checkpoint 0081 adds a **separately opted-in**, one-logical-Range-operation way to check whether
the first 256KiB of the published Figshare source still matches the first
real observed MPTrj diagnostic frozen by checkpoint 0080.

## Before the network request

The CLI validates the checked-in, bounded original **758-byte ZIP**
and its **1292-byte receipt** from manual run
[37852263493](https://github.com/wt2018mask/Rhombus/actions/runs/37852263493)
against the frozen GitHub API artifact ZIP SHA256
\`1704ce3ead958a853364129ff1554b07f8e031409ff7732271e4e979154fd231\`
and canonical receipt schema. The observed first prefix SHA256 was
\`60bb86a8f7d2c8cc5a4ec86dc49263c7abbb820a41eeee6f0b405746603c2ae2\`.

If the local evidence is missing or modified, no network request is made.

## Optional independently approved local execution

An operator must deliberately run:

\`\`\`powershell
python -m scripts.development.reobserve_mptrj_frozen_prefix --reobserve
\`\`\`

The script initiates **one logical** first-prefix HTTPS Range operation with
\`Range: bytes=0-262143\`. Strict HTTP **206**, exact Content-Range total,
identity coding and 256KiB bounded byte reads are enforced by the existing
probe. Normal HTTPS redirects can require additional transport-level GETs; the overall fetched source payload remains bounded. It reparses the entire first frame with pymatgen and compares:

- whole observed 256KiB prefix SHA256 to the frozen real prefix digest
- material/frame ID, atom count, reduced formula and all 3 energy field-presence flags
- original Figshare file ID and declared source total length

CDN redirect hostname may change, as long as HTTPS and all byte/range
and scientific contracts hold. No original source bytes are stored, no
report is overwritten, no Kaggle/GitHub Actions workflow is dispatched,
and no training-model checkpoint is fetched. Tests use simulated HTTP
206 for the transport and the preserved real receipt for the anchor.

Even a successful re-observation proves **only repeatability of this
single 256KiB prefix**, not all 12,188,168,685 bytes, the original MD5
or full SHA256, the exact frames MACE-MPA-0 selected for training,
their energy preprocessing, a WBM exposure audit or unseen
generalization. The tool never unlocks those scientific claims.

**Do not execute \`--reobserve\` without intentionally authorizing
a new bounded Figshare Range request.**


## Checkpoint 0082 multi-frame local source readiness

[The bounded multi-frame guide](PHASE3_MPTRJ_BOUNDED_MULTIFRAME_V1.md) explains an independent zero-network 256KiB/1MiB sample inspection that anchors the original first 256KiB SHA256. This new feature is fixture-tested and requires a separately authorized real source capture; it does not reinterpret a verified single frame as a verified MPTrj training dataset.
