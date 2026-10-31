# Rhombus Tier A P1 model/ASE instrumentation integration (2026-10-31)

This is offline infrastructure, not a model-run authorization, scientific
qualification, NEB result, conductivity estimate or benchmark freeze.

- GitHub official release metadata is recorded only as asset identities (MACE
  MP-0 small: 32,581,838 bytes; MPA-0 medium: 79,462,305 bytes). It does not
  authenticate weights; publisher API digests were unavailable.
- Model preflight rejects an incorrect release-asset size, including the small
  baseline, even when a digest is not yet pinned.
- ASE-style calculator method hook separately records property requests and
  calculate entry attempts. Cache hits do not inflate the model evaluation
  count. It is NOT proof of Torch forward counts, subprocess work, or actual
  model operations.
- Instrumentation errors and unsupported properties irreversibly taint a
  local meter, including when an outer runner catches them inside a phase.
- Synthetic tests and optional inert ASE integration test; no MACE, NEB, DFT,
  scoring, real held-out targets or production dispatch.
- This work remains owner-gated for checkpoint pinning, numerical budgets,
  model execution and scientific evaluation. Retain benchmark NOT FROZEN and
  SCIENTIFIC_NO_GO_ABSTAIN.
