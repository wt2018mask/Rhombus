# Rhombus 0204 — Tier A metadata preflight implementation (uncommitted patch)

2026-10-31. Status: `TIER_A_PROTOCOL_DRAFT_READY`; `BENCHMARK_NOT_FROZEN`; `TIER_B_NOT_FROZEN`; `SCIENTIFIC_NO_GO_ABSTAIN`.

## Source and exact scope

Development baseline: `wt2018mask/Rhombus` / `worker/k204-evidence-qualified-strategy` at `25e35999e3dd6ca8521838706acd5bb534ad13d7`. The patch is a **new, separate metadata-only module**; it does not modify historical checkpoints, CURRENT, HANDOFF, existing science, or MCP tool permissions. GitHub PR #376 remains draft and unmerged. The local Codex G1/P0 changes are *not* assumed present in the GitHub branch.

Input identity: the owner-supplied LiTraj `nebDFT2k.zip` is expected to be **68,583,182 bytes** with SHA256 `b7a99d89337902e9e1da319f57547170fdb132bf15bf6ffef03a0140e2207d7f`. A match verifies continuity to the *owner's archive*, not independent publisher origin. The script reads only the index member; it does not open XYZ members or repeat full ZIP CRC scans. It decodes only `material_id`, `edge_id`, `chemsys`, `has_specific_TM`, `_split`, while target columns are opaque byte tokens in the raw CSV line. No validation/test energy target decoding, errors, model fitting, predictions or performance scoring occurs.

First-party source: Dembitskiy et al., *npj Computational Materials* 11, 131 (2025), DOI 10.1038/s41524-025-01571-z; LiTraj GitHub official `litraj/utils.py::get_barrier()` computes `max(E_images)-min(E_images)` on a discrete trajectory. The Tier A quantity is **nondirectional discrete NEB image energy span**, not certified directional activation barrier, exact continuous saddle, global percolation, diffusion or conductivity.

## Implemented, actually exercised

1. Archive SHA256-and-size preflight; bounded selective ZIP index entry open; rejects ambiguous duplicate index names and compressed-archive size mismatch.
2. Restricted metadata-only CSV reader: fixed header and 7 columns, no quoted/flexible dialect, strict field/ID validation, duplicate edge and cross-published-split material rejection, without decoding target tokens.
3. Deterministic `TEST > VAL > TRAIN` chemical-system conflict purge, no reallocation or energy-based selection. Candidate split counts: original 1,220 / 241 / 220; retained **619 / 165 / 220**, total retained 1,004 and excluded 677. Unique material IDs 867; unique chemsys groups 277; 148 chemical systems span multiple original splits. Chemical-system disjointness is NOT source-out or model-pretraining-overlap evidence.
4. Tamper-evident SHA256 over the full ordered candidate registry. Deterministic train-only proposal of four edges in four distinct chemical systems, selected by fixed `RHOMBUS_0204_TIERA_TINY_METADATA_PILOT_V1` SHA rank. Records precise edge IDs and commitment hash, but **does not authorize a run or freeze this selection**.
5. Readiness check against the prior externally supplied 0204 Tier A candidate protocol. Explicit blockers: missing separate owner compute permission, unset `delta_eV`, training exposure UNKNOWN, missing model/budget freezes. `execution_authorized=false` unconditionally.
6. Zero accepted count => conditional false-acceptance risk is **undefined** (`null`), not zero or success.

Generated metadata-only artifacts (not historical evidence):
- `tier_a_metadata_registry_draft.json` — 1,681 edge metadata records with retained/excluded candidate split and SHA256; no labels.
- `tier_a_tiny_train_pilot_draft.json` — precisely four proposed TRAIN edge IDs, four distinct chemsys, SHA256 commitment; no labels.
- `tier_a_readiness_blockers.json` — gate statuses and reasons, explicitly no execution.

The CLI refuses an existing output directory or an output directory inside the current working repository tree; it writes new files with exclusive creation. It never writes to GitHub or existing historical files.

## Reproduction (Python >=3.11)

Copy new files from the patch ZIP into a checkout of the named base branch, without overwriting any existing file. **Keep the original ZIP and prior protocol JSON outside the Git repository**. Execute from the repository root:

```sh
python -m scripts.benchmark.prepare_tier_a_draft_0204 \
  --archive /trusted/nebDFT2k.zip \
  --protocol /trusted/RHOMBUS_0204_TIER_A_PROTOCOL_CANDIDATE_2026-10-31.json \
  --output-dir /tmp/rhombus-0204-tier-a-draft-NONEXISTENT
```

Run focused tests:

```sh
python -m pytest -q tests/test_tier_a_preflight_0204.py
```

Optional integration tests using owner-provided inputs, without checking them into Git:

```sh
export RHOMBUS_0204_OWNER_LITRAJ_ZIP=/trusted/nebDFT2k.zip
export RHOMBUS_0204_TIER_A_CANDIDATE_PROTOCOL=/trusted/RHOMBUS_0204_TIER_A_PROTOCOL_CANDIDATE_2026-10-31.json
python -m pytest -q tests/test_tier_a_preflight_0204.py
```

## Test evidence and limitations

- Focused local test: **25 passed** (including exact-source ZIP index integration and original candidate protocol read). The synthetic tests verify target-byte invariance, group split disjointness, SHA tamper rejection (including post-hoc recomputed registry digest), zero-coverage, unauthorized threshold/promotion/scoring flags, strict metadata field allowlist and owner archive counts.
- This is a **standalone patch-workspace test**, not a full `wt2018mask/Rhombus` checkout pytest run; the full 0204 branch was inspected through the GitHub connector because GitHub network access from the sandbox container is unavailable.
- Separate GitHub Action on HEAD `25e359...` shows 54/55 checks succeeded; Fast CI failed one historical `test_additive_science_diagnostics.py` comparison that assumes effective CURRENT state is identical after 0204 checkpoint. That CI failure was **not fixed by this patch**. It must be addressed without weakening continuity invariants and verified in a full repository checkout before merge.
- No new energy/force/NEB/MD, benchmark score, training, plugin exposure, remote Kaggle dispatch, GitHub commit, push or merge. No human authorization for any compute run follows from creating the draft.

## Next scientific decision

Before any four-edge TRAIN-only feasibility/cost run: owner must separately approve the exact edge list and its SHA, model checkpoints (official publisher small vs Rhombus medium are different), full model/runtime identity, numerical wall/CPU/force/RSS caps, endpoint + NEB convergence and failure accounting; do not access held-out targets. `delta_eV` and decision-risk protocol must be frozen before any future confirmatory scoring. MACE pretrained-overlap remains `UNKNOWN`; Tier B solid-electrolyte eligibility remains `NOT_FROZEN`.
