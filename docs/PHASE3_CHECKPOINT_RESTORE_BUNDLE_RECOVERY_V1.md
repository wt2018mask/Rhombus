# Phase 3 — recovering 0056/0057 checkpoint verifier work onto 0115 main

## Why a new PR instead of merging #218/#219

PR [#218](https://github.com/wt2018mask/Rhombus/pull/218) is rooted in
the old checkpoint 0055, and [#219](https://github.com/wt2018mask/Rhombus/pull/219)
is stacked on the head of #218 (0056). Canonical main is now at 0114.
Merging their original branches as-is risks stale CURRENT.json and handoff.
Both old branches are kept intact. Their previously unmerged **implementation
files and four-file API surface** are ported to the new PR #279:

- `rhombus/domain/checkpoint_restore.py` and `tests/test_phase3_checkpoint_restore.py`
- `rhombus/domain/checkpoint_bundle.py` and `tests/test_phase3_checkpoint_bundle.py`

Run the real no-network tests:

```bash
python -m pytest -q tests/test_phase3_checkpoint_restore.py tests/test_phase3_checkpoint_bundle.py
```

The staged checkpoint verifier requires host-controlled filenames, validates
the exact checked-in staging manifest contract, bounded output and SHA256,
and rejects tampering or changed source claims. It intentionally does not
call SQLite PRAGMA integrity_check or inspect original dataset provenance.

The bounded part bundler splits only a *finalized*, WAL/SHM-free local input
into no-overwrite SHA256 chunks; its verifier re-reads every part and checks
their length, order, individual hash and concatenated hash. All science,
external durability, source verification and execution-permission flags stay
false. Merely creating these files does not create externally retrievable
Kaggle outputs. Part packing is NOT evidence that the on-disk file is a valid
and complete original sAlex index. A future test must independently upload,
retrieve, verify, and simulate safe continuation before production dispatch.

## Scope and next steps

After #279 merges, **and only then**, close the original #218/#219 as
superseded, retaining their historical branches and discussions. Do not
delete, overwrite or rewrite checkpoint 0056/0057 historical files.
The next scientific task is official MACE-MPA-0 checkpoint-bound training
frame lineage research, with `UNATTESTED` unchanged until immutable
selection/preprocessing evidence is independently produced. Next compute
milestone is small external archive roundtrip/recovery, no full Kaggle job.
