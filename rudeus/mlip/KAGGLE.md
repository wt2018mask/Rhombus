# P1 Kaggle Runbook (pilot phase: manual download, no PAT — DESIGN.md Q2)

Goal: relax one shard of committed P1 batch files on a free Kaggle GPU, then
bring result manifests back into the repo. Single source of truth stays git.

## Step 0 — LOCAL preparation (CPU, do this first, commit + push)

Pending batch files must exist in the repo BEFORE any GPU session starts:

```bash
# 20-parent pilot mix (deterministic; or --parent-ids a,b,c for custom)
python -m rudeus.mlip.make_batches --smoke20 --out data/batches/pending
git add data/batches/pending/
git commit -m "p1 pilot batches (N files)"
git push
```

Record the pushed commit SHA — the notebook checks it out exactly.

## Step 1 — Kaggle notebook setup (manual, in the Kaggle UI)

1. Create a notebook, accelerator = **GPU T4 x2** (fallback P100), Internet = **ON**
   (needed for the checkpoint download + git clone).
2. One notebook per shard (pilot: 1-2 shards is plenty; e.g. `--shard 0 --of 2`).

## Step 2 — Exact notebook commands (one code cell each, in order)

```bash
!git clone https://github.com/wt2018mask/Rhombus.git Rhombus
%cd Rhombus
!git checkout <COMMIT_SHA_FROM_STEP_0>
!pip install -q -r requirements.txt
```

```python
import torch
print("cuda:", torch.cuda.is_available())  # must be True; abort otherwise
```

```bash
# Shard 0 of 2 on GPU (change --shard/--worker per notebook):
!python -m rudeus.mlip.run_p1 --pending data/batches/pending \
    --done data/batches/done --shard 0 --of 2 --device cuda \
    --worker kaggle-pilot-s0
```

What this does: verifies the checkpoint sha256 against `config.yaml`
(refuses on mismatch), relaxes only `int(batch_id,16) % 2 == 0` batches,
skips any batch already finished (resume-safe: re-running is a no-op),
writes atomic `data/batches/done/<batch_id>.json` manifests.

## Step 3 — Bring results home (manual download, Q2 decision)

1. At session end, download `data/batches/done/` (Kaggle UI file browser or
   `shutil.make_archive` + Output download).
2. Locally: copy new `*.json` into `data/batches/done/`, sanity-check one
   manifest (`p1_verdict`, `converged`, checkpoint `sha256`), then
   `git add data/batches/done/ && git commit && git push`.
3. Next scheduled Actions sync (or manual dispatch) validates manifests.

## Scaled run (111 pending batches: 104 new + 7 pilot) — ONE self-contained cell

Batch: full 321-parent OBELiX pool -> 111 eligible P1 batches
(~49 ordered-relaxable, ~62 instant SKIPPED_DISORDERED triage).
Shards: **2** (Kaggle 2xT4 -> one notebook per shard, each uses 1 GPU).
Paste this whole cell, set SHARD per notebook (0 and 1), Run All:

```python
import os, shutil, subprocess, sys

REPO = "/kaggle/working/Rhombus"
OUT_BACKUP = "/kaggle/output/done-shard"
SHARD = 0          # <-- SET THIS PER NOTEBOOK: 0 in notebook one, 1 in notebook two
OF = 2
COMMIT_SHA = "c61757c"   # code + all 111 batch files
WORKER = f"kaggle-scaled-s{SHARD}"

def run(cmd, cwd=REPO):
    print("+ " + cmd, flush=True)
    r = subprocess.run(cmd, shell=True, cwd=cwd,
                       capture_output=True, text=True)
    print((r.stdout or "")[-1500:], flush=True)
    if r.returncode != 0:
        print((r.stderr or "")[-3000:], file=sys.stderr, flush=True)
        raise RuntimeError(f"command failed ({r.returncode}): {cmd}")
    return r

if not os.path.isdir(os.path.join(REPO, ".git")):
    run("git clone https://github.com/wt2018mask/Rhombus.git Rhombus",
        cwd="/kaggle/working")
run(f"git fetch origin && git checkout {COMMIT_SHA}")
run("pip install -q -r requirements.txt")
run("python -c \"import torch; assert torch.cuda.is_available(), 'NO GPU - abort'\"")
run(f"python -m rudeus.mlip.run_p1 --pending data/batches/pending "
    f"--done data/batches/done --shard {SHARD} --of {OF} "
    f"--device cuda --worker {WORKER}")

# Backup to session output (survives idle-timeout resets as a download)...
shutil.copytree(os.path.join(REPO, "data/batches/done"),
                OUT_BACKUP + str(SHARD), dirs_exist_ok=True)
# ...AND commit in-notebook (disposable identity, nothing secret here).
run("git config user.email 'kaggle-pilot@local' && "
    "git config user.name 'kaggle-pilot'")
run("git add data/batches/done/")
run(f"git commit -m 'p1 scaled results shard {SHARD}/{OF} ({WORKER})' || true")
print("NOW RUN THIS YOURSELF IN A NEW CELL (git will ask for a PAT):")
print(f"  cd {REPO} && git push origin HEAD:refs/heads/p1-scaled-s{SHARD}")
```

Notes: the push goes to a per-shard branch (`p1-scaled-s0/s1`) so the two
notebooks never push-conflict; merge locally after both land. Re-running the
cell resumes (done files skipped). NEVER paste a PAT into a stored cell —
type it only at the prompt of the manually-run push.

## Resume rules (memorize these)
- Same command re-run = resume (done files skipped, missing ones computed).
- Across sessions: works ONLY because Step 3 committed prior done files —
  always `git pull` them into the pending/done dirs before launching.
- Crash/death loses at most the one in-flight relaxation; never edit or
  delete a `done/*.json` by hand (recompute instead).
- NEVER commit the `.model` checkpoint file (lives in `~/.cache/rudeus/`,
  outside the repo; `.gitignore` also blocks `*.pt/*.ckpt/*.pth`).
- NEVER put any token/PAT in the notebook (Q2: manual download only).
