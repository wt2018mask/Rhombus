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

## 6. Q5 (OPEN — flagged, not decided): disordered structures in P1
Context (2026-09 Kaggle pilot): a disordered child (fractional occupancies,
e.g. the 9wf-derived `Na1Li11.2Er4I24`) hit `relax_structure`, which raised
`ValueError` and killed the whole shard. Fixed now at two levels: (a) the
shard runner records per-candidate ERRORs instead of aborting (sharding.py),
(b) disordered input returns an explicit `SKIPPED_DISORDERED` placeholder
result with a reason (relax.py) — triage, NOT a strategy.

The real choice, option A vs B:

- **Option A — canonicalize to one representative ordering** (e.g.
  `OrderDisorderedStructureTransformation`), relax that, record the
  canonicalization in the manifest. Pro: keeps disordered candidates (the
  majority population!) in the pipeline. Con: the relaxed energy belongs to
  one arbitrary ordering, not the disordered phase; choosing "representative"
  needs its own validation (enumeration? lowest-Ewald ordering?).
- **Option B — exclude disordered candidates at make_batches time.**
  Pro: every relaxed energy means exactly what it says; simplest correct
  thing for the pilot. Con: discards most real candidates (54/67 CIF-linked
  test structures are disordered) — acceptable for a pilot, fatal long-term.

**Recommendation: B for the pilot** (ship the 6-10 ordered shortlist now, keep
SKIPPED_DISORDERED records visible so the exclusion is auditable), then run A
as a tracked follow-up experiment with bench-measured impact before adopting.
Do NOT silently implement A — the ordering choice changes energies and needs
its own design note.

## 7. Pilot Results (2026-09, real Kaggle sessions — design VALIDATED)

- Sharding/resume worked as designed in production, not just the synthetic
  test: shards 0 and 1 ran on Kaggle GPUs; a fresh clone correctly skipped
  already-committed results (`skipped_done`, no duplication, no loss).
- CPU/GPU determinism confirmed: `g1-3a449d0d18a233fe` relaxed on GPU matched
  the local CPU dry-run energy EXACTLY (-114.994593 eV, 73 steps).
- The disordered-skip path was exercised for real (9wf-derived
  `Na1Li11.2Er4I24` child): SKIPPED_DISORDERED recorded, shard survived.
  Per-candidate ERROR records (added after the pilot crash) were NOT yet
  battle-tested at pilot close — the intentional session-kill test was
  deferred to the scaled run.
- Remaining 2 result files were NOT chased: Kaggle idle-timeout resets made
  per-file retrieval painful, and the validation goal was already met.

## 8. Kaggle operational notes (friction log — process, not code)

- Idle-timeout session resets wipe uncommitted `/kaggle/working` files. NEVER
  end a session with results only in working-dir files: commit in-notebook
  (`git add/commit`, disposable identity inline) and ALSO copy `done/*.json`
  to `/kaggle/output/` (persists as downloadable session output) before doing
  anything else.
- `%cd` and other shell magics do NOT persist across "Run current cell" after
  a kill/reset. Use one self-contained Python cell with `subprocess`
  (`cwd=` explicitly, absolute paths, `os.chdir` if needed) and prefer
  "Run All" over per-cell execution after any reset.
- `pip install -e .` failed on Kaggle (truncated log hid it): root cause was
  LOCAL, not environmental — setuptools flat-layout auto-discovery refuses
  when `rudeus/` and `tests/` both exist (fixed in pyproject.toml). The
  `python -m rudeus...` from repo-root workaround remains valid regardless.
- Manual download (DESIGN.md Q2) stays the write-back path; the scaled-run
  cell additionally commits in-notebook so a timeout loses nothing.
