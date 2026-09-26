# P1 frozen ordered top-conductivity cohort — Colab execution contract

This run is execution-only. Published parent conductivity determines scheduling
priority only; it is not evidence that any child is diffusive.

## Frozen inputs

- Worker branch: `worker/p1/topcond20-ordered-v2-s0-of1`
- Base code commit: `e0b4e43b946ad1024789e3828d948faff9090bd2`
- Pending cohort: `data/batches/pending_topcond20_ordered`
- Priority audit: `data/batches/audit/p1_topcond20_ordered_priority.json`
- Cohort identity: `abc231df84ac3c53fe4a59196d075983165c1b5ee1c5ffbb282218095cb42621`
- Priority artifact SHA256:
  `16aca37535b65de52e23d1f5e6e5189fc82239801d4c2e4a80c724fb22ce190e`
- Expected batch count: 13
- Sharding: shard 0 of 1
- Device: CUDA only
- Output directory: `data/batches/done_topcond20_ordered_v2`

The priority audit must validate against the exact pending batch IDs and exact
input structure SHA256 values before checkpoint/calculator initialization.
Any mismatch must abort the run.

## Colab run

Use a fresh GPU runtime.

```bash
git clone --branch worker/p1/topcond20-ordered-v2-s0-of1 \
  https://github.com/wt2018mask/Rhombus.git
cd Rhombus
git rev-parse HEAD
```

The initial checked-out commit must descend from the frozen base above. Before
the first scientific calculation, run the lightweight priority checks:

```bash
python -m pip install -q -r requirements.txt
python -m pytest -q -p no:cacheprovider tests/test_p1_priority_execution.py
```

Then verify CUDA:

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
  --pending data/batches/pending_topcond20_ordered \
  --done data/batches/done_topcond20_ordered_v2 \
  --priority-audit data/batches/audit/p1_topcond20_ordered_priority.json \
  --shard 0 \
  --of 1 \
  --device cuda \
  --worker colab-topcond20-ordered-v2-s0-of1
```

Do not use `--retry-errors` or `--retry-skipped` on the first run.

After the run, inspect the result count and verdicts before committing:

```bash
python - <<'PY'
import json
from collections import Counter
from pathlib import Path

d = Path("data/batches/done_topcond20_ordered_v2")
files = sorted(d.glob("*.json"))
verdicts = Counter()
for p in files:
    rec = json.loads(p.read_text())
    verdicts[(rec.get("result") or {}).get("p1_verdict", "<missing>")] += 1
print("files", len(files))
print("verdicts", dict(verdicts))
assert len(files) == 13, "incomplete P1 output set"
PY
```

Do not push results until the 13-record output set and provenance are reviewed.
