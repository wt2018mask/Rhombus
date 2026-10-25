# 0200 — Actual bounded digital qualification pilot

Owner mission update, 2026-10-26: required project scope ends at digital
scientific qualification and candidate selection. Physical P0-01/02/03 gates
remain BLOCKED, with their meaning unchanged; new laboratory measurements are
not a prerequisite to separate computational progress. The O_ONLY scope decision
already exists in 0199 and is not repeated here. This unit implements and runs
a real bounded workflow, rather than replacing the frontier with another plan.

## Recovered state and capability decisions

Main remains 1aaaa555a9a1ce2c9123845402fec4e664626708 (0192).
Verified all seven Draft PR bases/heads and Git ancestry, one added event per PR,
unchanged 0118 baseline. #371 072d0cc has 52 successful/2 failed job checks;
#370 b824a72 has 55 successful/2 failed checks. The failures remain original
0169/0170 source acquisition, with historical timeout tracebacks supplied by the
owner. No live-source requirement was weakened or replaced. Earlier source
and physical qualification failures do not authorize withholding all local
digital science. Issues #349/#368, naming, scope, milestones and red-team
contracts were recovered before implementation.

Status below is scoped to operation/evidence, not to material qualification.

| Capability | Existing interface/module | Execution evidence and limits | Status |
| --- | --- | --- | --- |
| Generation | `rudeus/generation/generator.py` | Reused known source structures here; generation not run. The generic OBELiX retrieval path includes TEST and must not be used for this benchmark. | IMPLEMENTED_BUT_UNEXECUTED in this pilot |
| P0 | `evaluate_p0`, `rudeus/filters/p0.py` | Actual SMACT neutrality/Pauling and geometry checks on two retained CIFs. PLAUSIBLE is not physical stability. | EXECUTED_AND_VERIFIED |
| P1 | `relax_structure`, `rudeus/mlip/relax.py` | Prior B5 real receipt; current exact-weight CPU cell/position relaxations. Hull energy remains null. | EXECUTED_AND_VERIFIED |
| P2 | `run_nvt`, `build_p2_result`, `rudeus/mlip/p2.py` | Prior corrected gamma receipt; current eight final trajectories. All legacy thresholds remain PROVISIONAL. | EXECUTED_AND_VERIFIED numerically |
| P2.5 | `analyze_p25`, verified NPZ loader | Prior gamma INDETERMINATE receipt; four actual current analyses, all INDETERMINATE; other four blocked by P2 rejection. | EXECUTED_AND_VERIFIED / BLOCKED by case |
| P3 | `rudeus/mlip/p3_transport.py` | Existing diffusion/NE/Arrhenius helpers and tests. Current 0.2 ps production cannot qualify transport; no current P3 fit or conductivity is claimed. | BLOCKED in this pilot |
| Applicability | `rhombus/domain/applicability.py` | Exact element snapshot tied to model hash. Inclusion remains UNQUALIFIED; training overlap UNKNOWN. | EXECUTED_AND_VERIFIED preflight only |
| Model falsification | Existing same-model MD, two seeds, dt control | Actual seed/dt and deterministic repeat checks; no independent model, size or long-time convergence. | Partial EXECUTED_AND_VERIFIED; independent methods BLOCKED |
| Novelty | Existing local StructureMatcher logic | Both structures are known references, not new discoveries; no global novelty search. | IMPLEMENTED_BUT_UNEXECUTED |
| Digital realism | Existing explicit deferred hull/claim semantics | No compatible decomposition/interface reference calculation; not silently treated as stable. | BLOCKED |
| Digital selection | Existing `evaluate_claim` / `final_claim_vector`, new `rhombus/qualification/digital.py` | Six explicit claim requirements; source/numerical predicates can PASS while four substantive requirements remain UNKNOWN. Zero qualified survivors. | EXECUTED_AND_VERIFIED assessment |
| AI access | Existing six-tool MCP server | Four actual SDK subprocess evidence/manifest calls on real computed records; model-driven selection remains UNVERIFIED after earlier connection 403. | EXECUTED_AND_VERIFIED protocol, not AI autonomy |
| Dispatch | Existing execution contracts / local backend | LocalBackend still does not support scientific submission; this is an explicitly authorized direct local CLI runner, not hidden MCP dispatch. | BLOCKED for automatic scientific dispatch |

## Frozen experiment and authentic inputs

Protocol committed before calculation: a7866af, SHA256
`a0814f43716d0a3cf5407505cda0d1e98e9c4c1e294c464bb1918cab857b083f`.
All candidates, seeds, physical times, thresholds, baseline and budget were fixed
before scoring. This is a small known-reference integration pilot, not a new
blind accuracy benchmark or discovery experiment.

- gamma-LiAlO2: COD 1008166 retained CIF, 16 ordered atoms, SHA256
  `94aa55ef4b1a2aeb94c5c07ddd7cdc18201ac752546a283c8543cb8faa05f589`.
- Li2S: COD 9009060 retained CIF, 12 ordered atoms, SHA256
  `ff1d7eeb11f6d91c3adb7af92c8b6cfc938f9c9f412e26bd4187a021de7470b0`.

The source receipts and their byte digests are frozen in the protocol; CC0 is
recorded by those receipts. The latest-URI COD revision is explicitly UNASSERTED;
the retained byte identity is not a new source reauthentication, experimental
specimen identity or a new conductivity measurement.

Model: official MACE-MPA-0 medium, 79,462,305 bytes, full weights SHA256
`75428afe3a1d7d8062e19bcaabd5c433623cabf308242ec9fb493e38604fb638`.
Runtime: mace-torch 0.3.16, e3nn 0.4.4, torch 2.14.1+cpu, float64, two CPU
threads, no GPU. Source URL is the repository's pinned official release; exact
training-frame exposure and domain accuracy remain UNKNOWN. Model license was
not independently reauthenticated in this unit. Hash verification precedes model
deserialization; no TLS, checksum or signature verification was disabled.

Reuse existing P0, P1 cell/position LBFGS (30 steps, 0.05 eV/A), unchanged P2
Langevin/FixCom and provisional gates, artifact-bound P2.5, and existing claim
assessment. At 550 K use 100 fs equilibration plus 200 fs production, sample
every 2 fs. Each material runs seeds 550/551 at 1 fs, seed 550 at 0.5 fs with
the same physical duration, and a 1 fs seed-550 replay. Replay is not another
independent seed. No unit-cell or sub-ps result establishes bulk convergence.

## Actual outcomes and falsification

| Material | P0 | P1 energy change | Final max force | P2 cases | P2.5 | P3 / digital portfolio |
| --- | --- | ---: | ---: | --- | --- | --- |
| gamma-LiAlO2 | PASS/PLAUSIBLE | -0.09208681 eV | 0.04763038 eV/A | 3 PASS, 1 FAIL | 3 INDETERMINATE, 1 BLOCKED | BLOCKED / ABSTAIN |
| Li2S | PASS/PLAUSIBLE | 0 eV | ~3.1e-15 eV/A | 1 PASS, 3 FAIL | 1 INDETERMINATE, 3 BLOCKED | BLOCKED / ABSTAIN |

The cheap baseline is actual same-model static energy/forces at the unrelaxed
reference geometry. Relaxation lowers gamma model energy; Li2S already has
negligible forces, so relaxation adds no energy benefit. This is not superior
prediction accuracy, energy-hull stability or equal-budget selection advantage.

P2 failures are the existing energy-drift gate (>0.05 eV/ps/atom): gamma seed551
drift -0.073568; Li2S seed550/551 at 1 fs drift +0.107653/-0.127574. Li2S at
0.5 fs has -0.048008 and passes that screen. Same-seed replays reproduce those
outcomes. These are PROVISIONAL screen failures on short stochastic NVT runs,
not proof of physically unstable materials or a causal timestep-only effect.
Langevin exchanges energy; separate Brownian discretizations and transients
prevent attributing this difference solely to integration error.

Maximum replay position differences: gamma 1.226e-13 A, Li2S 1.030e-13 A;
both satisfy the frozen 1e-8 numerical tolerance. All 8 final MD runs completed;
only 4 pass the existing P2 admission gate, and all 4 P2.5 analyses remain
INDETERMINATE. P3 conductivity and qualified diffusion stay null, not zero.
No 25 C extrapolation, independent-model validation or transport confidence is
invented. Digital claim vector is UNKNOWN; qualified portfolio is empty.

## Errors, cost and retained evidence

Attempt 1 exposed a new adapter bug: an oxidation-labelled composition string
was passed to P0, producing UNKNOWN for gamma chemical checks despite valid
geometry. It was not a material FAIL. Corrected to the elemental formula without
changing site coordinates, stoichiometry, frozen physics or thresholds. Original
attempt, valid Li2S calculations, log and exact executed runner source are retained.
The complete pilot was rerun after correction and the current source-normalization
regression prevents recurrence. Failures are not hidden or overwritten.

Attempt 1: 174.20 s wall / 339.73 s CPU, peak 841 MiB.
Final attempt: 595.69 s wall / 1153.54 s CPU, peak 956.93 MiB.
Both attempts total 769.89 s measured calculation wall, below the 900 s budget;
CPU totals 1493.28 s with two threads. Dependency installation, model transfer,
tests and later SDK verification are outside these calculation timings. Model
download was 79.46 MB; zero model fits, new physical measurements or explicit
remote scientific dispatches, $0. No standalone policy speedup is inferred.

`data/development/0200.json` pins both reports. Final report binds 20 files,
8 canonical NPZ trajectories, P1/P2 structure ancestry and two typed
EvidenceRecords, with exact model/runtime/source/protocol/code identities.
Separate raw-file SHA256 and logical trajectory SHA256 are both verified.
The records are operationally SUCCEEDED, scientifically INDETERMINATE and
UNQUALIFIED. Existing MCP preserves IDs, original CIF bindings, real energy/force
diagnostics and explicit unknown uncertainty; no claim or execution is authorized.

Reproduce with the pinned CPU PyTorch/MACE dependencies and an already verified
model file, using a NEW output directory:

```bash
python -m scripts.science.digital_pilot_0200 --model /workspace/.cache/rhombus/mace-mpa-0-medium.model --output-dir /tmp/new-digital-observation --authorize-local-calculation
python -m scripts.tools.verify_digital_pilot --output /tmp/new-digital-mcp-observation.json
```

Offline tests and CI verify retained original computed artifacts; they do not
rerun MACE or manufacture new simulation evidence. No new MCP tool was added.
Next: freeze a convergence study with longer thermal stationarity, paired
timestep/seed controls and finite-size evidence before any transport escalation;
do not tune the existing gate on this pilot or treat these two known structures
as a validated new-family predictor. Historical physical gates remain BLOCKED,
production OFF, and original TEST121 is not accessed.
