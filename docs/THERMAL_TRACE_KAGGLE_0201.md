# 0201 — Kaggle-first thermodynamic trace engineering

Date: 2026-10-26 (Asia/Seoul). Engineering checkpoint; scientific study NOT_EXECUTED.
Parent: Draft PR #372, source 549c94aa6e9906271e08555d4e20d7449148e6da.
Main remains 0192 / 1aaaa555a9a1ce2c9123845402fec4e664626708.

## Actual readiness and execution boundary

The current managed runtime reports no bound credentials, runtime variables or
outbound identities. The existing secret-free Kaggle probe observed no CLI,
SDK, credential file, access-token file or credential environment variables.
PowerShell is also absent. These are local prerequisite observations, not a
claim about the owner's Kaggle account. Account authentication, CPU/GPU free
allocation, quota, memory, runtime, internet, package installation, model upload,
provider logs and output retrieval are UNKNOWN. No authenticated provider probe
or job submission occurred. No local MACE inference/relaxation/MD was performed.
Only tiny synthetic/harmonic ASE tests, Git and offline numerical checks ran.
Money spent: $0. Model downloads: zero. Remote jobs: zero.

Audited the existing backend, contracts, scheduler, code-bundle implementation,
`run_generic_mobile_ion_e2e.py`, gamma extension, GPU smoke, `scripts/run.ps1`,
sAlex workflow/policy and retained 0200 receipts. Generic backend submit/status/
retrieve remain disabled; the hardened PowerShell path is specialized to its
mobile-ion workspace/kernel/dataset contract, not a general MD service. The
scheduler creates plans and does not grant execution. The legacy CodeBundle
covers rudeus plus selected project files, not new rhombus driver bytes.

The small new adapter reuses TaskSpec, BackendAttempt and the existing state
transition validation. It emits CREATED → PREPARED snapshots and an explicit
committed inventory covering rudeus AND rhombus and the driver/protocol/config.
This inventory is deliberately not represented as a legacy CodeBundle/TaskBundle
or a legacy authenticated execution receipt. No provider write implementation
exists. Repeated submit calls fail closed. Existing sAlex armed=false, manual
and automatic submit=false remain byte-for-byte unchanged.

Missing trusted-host controls are current authenticated $0 allocation,
task-specific authorization, durable atomic request consumption, and an
independently authenticated run/output receipt. The computation driver has an
internal Kaggle-only entry point requiring that trusted context, and no compute
or submit CLI. Its context must come from a future verified host adapter; the
adapter is not provisioned here. Scientific request fields, old credentials,
old receipts and PREPARED cannot supply this authority. No complete autonomous
AI → Kaggle → evidence path is asserted. There is no local compute fallback.

## What changed in the science engine

`rudeus/mlip/p2.py` already samples temperature, potential energy, pressure
(configurational stress when calculator supports it), volume, max force,
positions and total completed step index. NPZ retains production positions,
cell, species and step indices; thermal data were discarded. Pressure is not
silently relabelled as a full kinetic-plus-virial thermodynamic pressure.

Opt-in `retain_thermal_trace=True` in fixed and adaptive NVT adds measured
kinetic and mechanical (potential + kinetic) energy and actual completed steps.
The historical fixed-length `production_steps` field still records configured
length even on abort; the new actual field prevents confusing it with execution.
Default calls retain their old fields and behavior. Kinetic energy reads
momenta/masses without calculator calls or RNG. Harmonic-control tests show
identical sampled coordinates, temperatures, potential energies and calculator
call counts with instrumentation enabled/disabled. No model-backed test occurred.

New `rhombus-thermal-trace-v1` sidecars retain equilibration AND production,
actual step/time in fs, explicit units, candidate/source/relaxed/model/protocol/
source-commit/runtime identity, seed, thermostat/integrator configuration, energy
components, temperature, volume, max force, optional pressure and termination.
Thermostat heat/work is NOT_MEASURED/null. Non-finite measured values become
explicit invalid-measurement entries with null values, never invented finite
measurements; independent numerical acceptance fails. No historical energies
are reconstructed. Each canonical JSON sidecar has an exclusive SHA-named path,
a 16 MiB limit and read-back verification. Partial/failed files are preserved.

0200 evidence/report/NPZ bytes are unchanged. The exact P2 source executed in
0200 is preserved as `digital0201/legacy_p2_0200.source.txt`; its hash matches
0200's original report. The old code-identity regression now verifies those
executed bytes for P2 rather than asserting that today's extended module ran in
0200. Every other code identity assertion remains intact.

## Independent verification and scientific interpretation

The verifier requires externally pinned bytes and ancestry; a self-reported
producer receipt or successful download cannot authenticate a Kaggle job. A
trusted host observation must pin job, task and result-manifest hash. That
provider authentication channel is currently UNPROVISIONED. Synthetic tests
supply explicitly fake host observations solely to test verifier behavior.

Offline verification checks all result bytes, output bounds, inventory closure,
planned run order/completeness, runtime, source/model/protocol/structure binding,
trace steps, timestamps, phase, seeds, dimensions and trajectory step identity.
It recomputes population temperature mean/std, potential trend per atom per ps,
kinetic mean, mechanical span/trend, pressure summaries and a descriptive thermal
half-window mean shift, and compares existing P2 thermal summaries. There is no
interpolation, forced stationary verdict or material promotion. Pure trace math
uses numpy; remote ancestry verification also uses existing ASE/pymatgen/scipy
helpers. Neither requires torch, MACE, GPU or scientific model downloads.

Existing P2 fits potential energy against evenly spaced array indices after
selecting usable production frames. Our verifier uses measured MD steps and
also reports that legacy-index slope. For intact uniform sampling their slopes
agree; missing samples are detected rather than silently compressed into a
shorter time axis. Existing engine aborts at non-finite samples. Sampling errors
can leave the latest scheduled measurement absent; partial records expose this.
A hard process kill before serialization cannot recover in-memory frames: only
already persisted completed runs are durable. No restart-from-MD-state is claimed.

Langevin NVT exchanges energy with its bath; potential and total mechanical
energies are not conserved. A potential trend alone cannot identify numerical
integration error, physical instability or inadequate equilibration. The old
provisional drift gate and historical 0200 PASS/FAIL states remain unchanged.
No replacement gate is activated or empirically qualified. Independent synthetic
recomputation validates arithmetic, not an interpretation of new real trajectories.
NVE conservation, actual seed/dt convergence, thermal stationarity and finite-size
convergence are NOT_TESTED. P2.5 eligibility and P3 transport are not established;
conductivity/qualified diffusion remain null, digital qualification ABSTAIN.

## Frozen bounded experiment and reproducibility

Protocol `data/development/digital0201/protocol_v1.json` was committed before any
0201 model-backed execution (none occurred). Reuse the exact retained 0200 P1
relaxed gamma-LiAlO2 COD1008166 / Li2S COD9009060 structures; no new relaxation.
MACE-MPA-0 medium weights SHA256:
`75428afe3a1d7d8062e19bcaabd5c433623cabf308242ec9fb493e38604fb638`.
No applicability or unknown training-exposure claim is upgraded.

CPU float64, two threads, 550 K, ASE Langevin/FixCom, friction 0.02/fs.
First gamma probe: 10 equilibration +20 production steps at 1 fs, sample every
2 steps; assess actual runtime, memory, loading and per-step total cost. Only
if its factor-two projected duration fits 80% of budget, run two materials ×
three conditions: seeds550/551 at1 fs and seed550 at0.5 fs, each1 ps equilibration
+4 ps production, sample every10 fs. Different Langevin timesteps do not share
identical stochastic paths even with identical integer seeds. Seven planned
runs including probe, 40,030 MD steps maximum, six study trajectories each400
production samples. Study is more informative than0200 but is not a transport
convergence criterion. No GPU task is prepared without a measured CPU estimate
and verified free GPU allocation. NVE and finite-size studies remain separate.

Frozen limits: 10,800s total,300s CPU probe,4096 MiB observed RSS,128 MiB output,
$0,one submission,no retries. Budget/engine abort stops further runs and retains
PARTIAL evidence. Source/model/runtime validation precedes model deserialization.
The current CPU package pins match0200; compatibility/installability on Kaggle is
UNVERIFIED. Supply weights as read-only verified input. A verified host must
materialize the exact Git commit, install pinned CPU torch from the official
CPU index and constrained MACE/ASE/pymatgen dependencies, and call the internal
driver only after the missing host controls are established. No network/TLS/hash
checks are disabled. Provider COMPLETE remains separate from scientific validity.

Preparation, without scientific computation or provider writes:

```bash
python -m scripts.science.thermal_study_0201 --source-commit <exact-committed-driver-sha> --prepare /tmp/new-0201-request.json
python -m pytest -q tests/test_thermal_trace_0201.py tests/test_kaggle_thermal_0201.py
python -m scripts.tools.verify_digital_pilot --output /tmp/new-0201-mcp-compatibility.json
```

The retained preparation request pins its source commit, complete inventory,
TaskSpec, protocol, model and parent report. It is explicitly NOT_SUBMITTED.
No new remote EvidenceRecord exists. Existing six MCP tools are unchanged;
actual subprocess checks retrieve real0200 records, not synthetic0201 results.
Scripted SDK calls do not establish autonomous AI selection.

## Validation and remaining scientific task

39 new engineering tests,181 focused thermal/P2/P2.5/P3/retained-artifact tests
and2,231 Fast CI tests pass. A separate environment without torch/MACE passed
56 tests and four genuine0200 MCP retrieval calls. Broader persistence selection exposed an inherited
stale assertion in `test_p2_persist::test_h_p2_protocol_constants_frozen` expecting
v2 while the recovered engine is v3. Running that assertion with the exact0200
source snapshot reproduces its failure; it remains unchanged. Historical0169/
0170 live source authentication gates are also untouched. Exact-head remote CI
must be reported separately; no fully-green claim follows from focused tests.

The next scientific task is the authorized, authenticated Kaggle CPU probe,
followed by raw-trace retention/retrieval and the frozen equal-duration seed/dt
comparison if the measured budget permits. Then design a separate NVE integration
control before attributing NVT trends to integration error. Longer duration,
replica/finite-size uncertainty, model applicability and transport-regime evidence
remain necessary before any P3 qualification. No lab milestone is introduced.
