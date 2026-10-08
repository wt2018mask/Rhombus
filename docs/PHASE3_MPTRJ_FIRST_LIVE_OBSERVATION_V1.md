# Phase 3 — first observed MPTrj 256KiB diagnostic (run 37852263493)

This file records the first **real**, explicitly manual GitHub Actions
`workflow_dispatch` MPTrj source observation, after the staged parser
contracts were fixture-tested. The bounded source probe succeeded on
**2026-10-08 22:15 UTC** against pinned `main` commit
`573fda0c5e5604911416d2746c2d7e7eb23cbbf8`.
Run: https://github.com/wt2018mask/Rhombus/actions/runs/37852263493

## Immutable, retained observations

The GitHub Actions job executed the constrained 256KiB first-frame
probe, emitted `MPTRJ_PREFIX_FIRST_COMPLETE_FRAME_PARSED_NON_AUTHORITATIVE`,
validated its receipt with `MPTRJ_DIAGNOSTIC_REPORT_SCHEMA_PASS`, and
uploaded an artifact (`id=11582107118`) with GitHub REST declared
`sha256:1704ce3ead958a853364129ff1554b07f8e031409ff7732271e4e979154fd231`.

The original **758-byte artifact ZIP**, **1292-byte JSON member**, and
manifest in `data/development/observations/mptrj-run-37852263493/`
were preserved byte-exact on a new append-only branch. This avoids sole
reliance on the artifact after its 7-day retention deadline
(2026-10-15 22:15:43 UTC). A Fast CI test re-checks ZIP SHA256, JSON
member SHA256, canonical receipt SHA256, size budget, exact member
binding, schema, material/frame identity and scientific false gates.
No raw MPTrj source bytes were retained in this repository.

- Figshare file ID: **41619375**
- HTTP `Content-Range` total reported: **12,188,168,685 bytes**
- Capped observed prefix: **262,144 bytes**, SHA256
  `60bb86a8f7d2c8cc5a4ec86dc49263c7abbb820a41eeee6f0b405746603c2ae2`
- First material ID: **mp-1005792**
- First frame ID: **mp-1012897-0-0**
- Formula and atom count: **Sm2CuAs3O**, **28 sites**
- Diagnostic presence flags: uncorrected total energy **true**,
  corrected total energy **true**, energy per atom **true**.
  These flags DO NOT attest energy labels' numerical values, accuracy,
  evaluation fitness or model training membership.

The job logs reported canonical metadata SHA256
`180f17fdd406dd0da9820c6bd8c82b5ac71779b3eccc84e5d60f51a55fc0da28`.
The archived receipt independently reconstructs that digest. The
downloaded ZIP hash also matched the GitHub REST artifact digest.

## What changed and what remains blocked

This observation confirms that **one complete first MPTrj frame**
can be parsed by the Phase 3 source probe inside the fixed prefix
under a successful strict 206-range request. It is real-source adapter
evidence but **not** full-source coverage, complete source SHA256, or
MACE-MPA-0 checkpoint-bound selected-frame manifest.

The stored ZIP contains JSON diagnostic metadata only, not the original
256KiB range bytes; therefore independent reparsing of real source
bytes is still unperformed. Do not report that the new local sample
replay path already ran on real data.

Do not infer `TRAINING_FRAME_KNOWN`, absence of model exposure, unseen
generalization, empirical calibration, or safe deployment. Preserve all
unsupported authorization flags as false. Next work should use this
observation to design a bounded real multi-frame continuation or full
data lineage path only once explicit source permissions and resource
budgets have been reviewed. No additional Figshare/Kaggle job was
triggered by this evidence preservation.


## Checkpoint 0081 — optional same-prefix re-observation

For operators independently authorizing one additional strictly bounded source request, [the opt-in re-observation guide](PHASE3_MPTRJ_FROZEN_PREFIX_REOBSERVATION_V1.md) describes a one-GET comparison of the newly fetched 256KiB prefix SHA256 with this original observed source digest, without storing source bytes or promoting model-training claims. This operation has not been performed by the development PR.
