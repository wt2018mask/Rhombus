# P1 Athermal MLIP Relaxation — Design Note (no implementation yet)

Status: DESIGN ONLY (2026-09). `rudeus/mlip/` contains no code. This note must be
reviewed before any P1 implementation, since stateless-shard failures killed two
prior architectures (Colab daemon deaths; Drive-mounted SQLite locks).

## 1. What goes through P1, and the GPU budget shape

Reference point (2026-09 smoke run, 20 parents x 3 children = 60 candidates,
calibrated matcher tolerances, all numbers plumbing not capability):

- 14 PLAUSIBLE, of which only **6 are novel** (8 are same-basin rediscoveries).
- 46 FAIL, of which **4 are geometry-only FAILs** (neutrality PASS).
- The other 42 FAILs all fail SMACT neutrality.

Relaxation preserves composition, so it can never fix a neutrality FAIL, but it
CAN fix a clash. Proposed P1 input rule: **novel + (PLAUSIBLE or geometry-only
FAIL)**. At current generator settings that is **6-10 relaxations per 20-parent
batch** — i.e. roughly one third of generated children, heavily enriched for
G2 substitutions (4/6 of the smoke shortlist).

GPU budget shape (UNMEASURED — first Kaggle run must time 3 pilot relaxations
before committing to a batch size):

- ~10 relaxations per batch, structures mostly < 100 sites.
- Guess: 1-5 GPU-min each on a free Kaggle T4/P100 -> **~0.5-1.5 GPU-h per batch**,
  comfortably inside one 12h Kaggle session. Batches are independent, so
  throughput scales with number of sessions, never with session length.

## 2. Stateless, resumable sharding (Kaggle sessions can die mid-run)

Batch = one JSON file committed to the repo, e.g.
`data/batches/pending/<batch_id>.json`, where

```
batch_id = sha256(parent_id | child_index | generation_config_hash | checkpoint_id)[:16]
```

Worker protocol (no locks, no queue, no daemon, no SQLite):

1. All pending batch files are committed to git BEFORE any GPU session starts.
   The batch file contains everything needed: child structure_dict, parent
   provenance, operator record, P0 verdict, checkpoint pin (section 4).
2. A session is launched with two manual arguments: `SHARD=i`, `OF=M`
   (e.g. 4 parallel Kaggle notebooks get 0/4, 1/4, 2/4, 3/4).
3. The worker processes exactly the batches with `int(batch_id, 16) % M == i`,
   in sorted batch_id order. Assignment is a pure function of committed data —
   no coordination, nothing to lock, nothing in memory that death can lose.
4. Each finished relaxation is written as its own result file
   `data/batches/done/<batch_id>.json` (atomic write: temp file + rename).
   A batch with no result file is simply unfinished — the next session re-runs
   it from scratch. Partial progress inside one relaxation is DISCARDED by
   design (relaxations are minutes, not hours; checkpoint-resume adds state
   machinery we refuse to maintain).
5. Two workers on the same shard is harmless: same inputs + pinned checkpoint
   give the same physical result up to GPU nondeterminism; last-writer-wins in
   git, and the manifest records which worker wrote it (section 3).

Why this avoids the two prior failures:

- Colab daemon deaths: there is no daemon. Death loses at most the one
  in-flight relaxation; everything finished is already a standalone file.
- Drive SQLite locks: there is no database and no shared mutable file. Workers
  never write to the same path concurrently (one result file per batch_id),
  and merging happens in git, which is built for exactly this.

## 3. Git-as-DB write-back (manifest fields)

Per-batch result file `data/batches/done/<batch_id>.json`:

- `batch_id`, `child_material_id`, `parent_id`, `input_structure_sha256`
- `mlip_checkpoint`: `{name: "medium-mpa-0", mace_version, url, sha256}` (section 4)
- `relaxed_structure_sha256` + `relaxed_structure_dict`
- `relaxed_energy_ev`, `energy_per_atom_ev`
- `e_hull_ev_per_atom` + `hull_source` (see open Q1 — absent if not computed, never null-filled)
- `converged: bool`, `n_steps`, `max_force_ev_A`, `force_tol_ev_A`
- `wall_clock_s`, `worker: {session, gpu, seed}`, `mace_precision`
- `p1_verdict`: `KEEP_FOR_P2 | FAIL_CONVERGENCE | FAIL_UNPHYSICAL`

Flow back to the repo: the worker session produces `done/*.json` as session
output artifacts; they enter the repo via the existing batch-sync path
(scheduled GitHub Actions 1-2x daily or manual dispatch per AGENTS.md section 1),
which validates manifests (schema + hash checks) before merging. A session that
dies mid-batch leaves behind only complete per-batch files; absent files are
recomputed, never resumed — so partial progress is never "lost", it is
deliberately re-derivable.

## 4. Checkpoint pinning: mace_mp("medium-mpa-0")

Per AGENTS.md section 7 the primary MLIP is `mace_mp("medium-mpa-0")` (MIT).
Reproducibility rule: NO relaxation result is valid without all four pinned in
its manifest — (a) `mace` package version, (b) checkpoint download URL,
(c) sha256 of the checkpoint FILE computed at download time, (d) floating-point
precision used. The worker verifies (c) against the manifest-expected hash before
running and FAILS LOUDLY on mismatch (checkpoint updated upstream, cache
poisoning, truncated download). If upstream publishes a new checkpoint file under
the same name, old manifests stay valid (they carry their own hash) and new runs
record the new hash — results are comparable by hash, never by name alone.

## 5. DECISIONS (finalized 2026-09 — do not re-litigate without new evidence)

- **Q1: convex-hull reference — DEFER E_hull (MP API).** No MP API key, no hull
  snapshot for now. `e_hull_ev_per_atom` is written as explicit `null` with
  `"hull_source": "deferred"` in every manifest — present-but-null, never
  silently omitted. A vendored snapshot happens only when actually needed.
- **Q2: Kaggle-to-repo write-back — MANUAL DOWNLOAD for this pilot phase.**
  Session outputs are downloaded by the operator and committed locally (or via
  the scheduled Actions sync path). No PAT inside the Kaggle session yet.
- **Q3: P1 shortlist INCLUDES geometry-only FAIL candidates.** Final input rule:
  novel + (PLAUSIBLE or geometry-only FAIL). Rationale: relaxation preserves
  composition (neutrality FAILs are unfixable, excluded) but can fix clashes.
- **Q4: 5 meV/atom convergence tolerance, PROVISIONAL.** Pinned in
  `config.yaml` (`mlip.force_tol_ev_A` is the optimizer gate; the 5 meV/atom
  figure governs energy-comparison/dedup logic). Recalibrate once real
  relaxation energies exist.
