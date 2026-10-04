# P1 ordered-expansion wave1 — Colab execution contract

This run is execution-only. The scientific cohort was frozen upstream by the
G/P0/P1 eligibility funnel and the parent-diverse wave policy. Published parent
conductivity remains acquisition metadata only; it is not evidence that any
child is diffusive.

## Frozen inputs

- Worker branch: `worker/p1/ordered-expansion-wave1-v1-s0-of1`
- Upstream frozen-data commit: `592b287`
- Pending cohort: `data/batches/pending_ordered_expansion_wave1_v1`
- Execution-order audit: `data/batches/audit/g_ordered_expansion_wave1_v1.json`
- Wave policy: `one-child-per-parent-first-v1`
- Cohort identity:
  `2229256d68c46da4ae2082158e8714a66bf8d2d8662cb53673863756eb74e78c`
- Expected batch count: 36
- Expected unique parents: 36
- Operators: displace 16, substitute 20
- Parent families: other 2, oxide 25, oxyhalide 3, sulfide 6
- Sharding: shard 0 of 1
- Device: CUDA only
- Output directory: `data/batches/done_ordered_expansion_wave1_v1`

The execution-order audit must validate the exact pending batch IDs and exact
input structure SHA256 values before checkpoint/calculator initialization.
Any mismatch must abort the run. The manifest order is scheduling only and
does not change scientific eligibility or verdicts.

## Colab run

Use a fresh GPU runtime.

```bash
git clone --branch worker/p1/ordered-expansion-wave1-v1-s0-of1 \
  https://github.com/wt2018mask/Rhombus.git
cd Rhombus
git rev-parse HEAD
```

Install dependencies and run only the lightweight admission tests first:

```bash
python -m pip install -q -r requirements.txt
python -m pytest -q -p no:cacheprovider \
  tests/test_p1_ordered_expansion_wave1.py
```

Verify CUDA and abort if unavailable:

```bash
python - <<'PY'
import torch
print("torch", torch.__version__)
print("cuda", torch.cuda.is_available())
print("device", torch.cuda.get_device_name(0) if torch.cuda.is_available() else None)
assert torch.cuda.is_available(), "CUDA unavailable: abort P1 run"
PY
```

Run P1:

```bash
python -m rudeus.mlip.run_p1 \
  --config config.yaml \
  --pending data/batches/pending_ordered_expansion_wave1_v1 \
  --done data/batches/done_ordered_expansion_wave1_v1 \
  --priority-audit data/batches/audit/g_ordered_expansion_wave1_v1.json \
  --shard 0 \
  --of 1 \
  --device cuda \
  --worker colab-ordered-expansion-wave1-v1-s0-of1
```

Do not use `--retry-errors` or `--retry-skipped` on the first run.

After the run, inspect count and verdicts before committing or pushing:

```bash
python - <<'PY'
import json
from collections import Counter
from pathlib import Path

d = Path("data/batches/done_ordered_expansion_wave1_v1")
files = sorted(d.glob("*.json"))
verdicts = Counter()
parents = set()
operators = Counter()
families = Counter()

for p in files:
    rec = json.loads(p.read_text())
    verdicts[(rec.get("result") or {}).get("p1_verdict", "<missing>")] += 1
    parents.add(rec.get("parent_id"))
    operators[rec.get("generation_operator", "<missing>")] += 1
    families[rec.get("parent_chemical_family", "<missing>")] += 1

print("files", len(files))
print("unique_parents", len(parents))
print("verdicts", dict(verdicts))
print("operators", dict(operators))
print("families", dict(families))
assert len(files) == 36, "incomplete P1 output set"
assert len(parents) == 36, "parent-diverse cohort identity lost"
PY
```

Do not push result files until the complete 36-record output set and its
provenance have been reviewed.
