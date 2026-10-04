# Colab P2 ordered-expansion wave1 v1 — shard 0 of 1

This contract authorizes one GPU worker to execute the frozen P2 cohort from
the ordered-expansion wave1 campaign. It is an execution contract only; it does
not change any scientific verdict.

## Frozen inputs

- Worker branch: `worker/p2/ordered-expansion-wave1-v1-s0-of1`
- Upstream P2 authorization commit: `b079e6e`
- P1 done directory:
  `data/batches/done_ordered_expansion_wave1_v1`
- Authorization manifest:
  `data/batches/audit/p2_ordered_expansion_wave1_v1_authorized.json`
- Authorized candidates: **33**
- Cohort identity:
  `b21faafbbad50910d61ca9a8a695b3cddddd3fce8a8f7cf3d6bd5ce936e75200`
- P1 state required for every authorized candidate:
  `KEEP_FOR_P2`
- P0 state required for every authorized candidate:
  `PLAUSIBLE`

The authorization loader binds every batch ID to its exact
`relaxed_structure_sha256` and recomputes the cohort identity before any MD
calculator initialization.

## P2 protocol

- Protocol version:
  `p2-adaptive-v2-fixcom-constraint-provisional`
- 550 K NVT
- timestep: 1 fs
- equilibration: 2000 steps
- adaptive production tiers: 1000 / 3000 / 8000 cumulative steps
- production limit: 8000 steps
- sampling interval: 10 steps
- Langevin thermostat
- explicit ASE `FixCom` constraint when center-of-mass fixing is enabled;
  Langevin itself runs with `fixcm=False`
- MACE checkpoint SHA256 must match the value pinned in `config.yaml`
- CUDA only for this worker; do not silently substitute CPU.

P2 is a finite-temperature structural/thermal stability screen. It does not
make a diffusion or conductivity claim.

## Colab setup

Clone the exact worker branch:

```bash
%%bash
set -euo pipefail
rm -rf /content/Rhombus
git clone --branch worker/p2/ordered-expansion-wave1-v1-s0-of1 \
  https://github.com/wt2018mask/Rhombus.git /content/Rhombus
cd /content/Rhombus
git rev-parse HEAD
```

Install dependencies using the repository's normal environment contract.

Before any GPU run, execute only the lightweight admission tests:

```bash
%cd /content/Rhombus

!python -m pytest -q -p no:cacheprovider \
  tests/test_p2_fixcom_contract.py \
  tests/test_p2_ordered_expansion_authorization.py \
  tests/test_p2_ordered_expansion_wave1_admission.py
```

Expected admission: all tests pass.

Verify CUDA explicitly:

```python
import torch
print("torch", torch.__version__)
print("cuda", torch.cuda.is_available())
print("device", torch.cuda.get_device_name(0) if torch.cuda.is_available() else None)
assert torch.cuda.is_available()
```

## Production command

First production execution uses shard 0 of 1, no retry flags, and does not
auto-commit or auto-push results.

```bash
%cd /content/Rhombus

!python -m rudeus.mlip.run_p2 \
  --config config.yaml \
  --p1-done data/batches/done_ordered_expansion_wave1_v1 \
  --out data/batches/p2_ordered_expansion_wave1_v1 \
  --traj-out data/batches/p2_traj_ordered_expansion_wave1_v1 \
  --authorized-manifest data/batches/audit/p2_ordered_expansion_wave1_v1_authorized.json \
  --shard 0 \
  --of 1 \
  --device cuda \
  --worker colab-p2-ordered-expansion-wave1-v1-s0-of1
```

Do **not** add `--retry-errors` on the first run. Do **not** add
`--git-commit` or `--push-to` until the local P2 results and trajectory
artifacts have been audited.

## Expected execution accounting

The authorization census is exactly 33. A clean first run should therefore
have no unauthorized, P0-rejected, or P1-ineligible candidates. Adaptive P2
may return PASS, FAIL, or INDETERMINATE per candidate; those are scientific
outputs, not execution failures.

An `ERROR` result, authorization mismatch, CUDA failure, checkpoint mismatch,
or trajectory persistence error is a stop condition for review. Do not retry
blindly.

## Preservation

Colab storage is ephemeral. After execution and audit, archive both:

- `data/batches/p2_ordered_expansion_wave1_v1`
- `data/batches/p2_traj_ordered_expansion_wave1_v1`

Record archive SHA256 values before downloading. Do not commit archive ZIP
files to the repository.
