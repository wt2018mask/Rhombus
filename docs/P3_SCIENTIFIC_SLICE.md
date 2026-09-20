# P3 scientific execution checkpoint

Implemented: verified P2 trajectory + P2.5 result → species-specific self diffusion
→ explicit uncertainty → canonical ClaimAssessment. No MD is run. The original
P2/P2.5 objects, events, verdicts and logical trajectory SHA semantics are preserved.

Run from the repository with the project Python environment:

```powershell
.venv/Scripts/python.exe -B -m rudeus.science.p3 --p2 p2.json --p25 p25.json --protocol p3-protocol.json --artifact-root . --timestamp 2026-09-20T00:00:00Z --output p3-result.json
```

`--timestamp` is explicit for reproducibility. `--claim` optionally reads a
serialized ClaimSpec. The output is published exclusively: identical reruns are
idempotent; different content at an existing path is an INTEGRITY error. This
operation does **not** attest Git ingestion or remote replication.

The minimal protocol is `{"target_species":"Li"}`. It intentionally yields no
quantitative observation: lag steps, fit window and reference frame remain
unresolved. For a numerical diagnostic supply `lag_steps` (frame offsets),
`fit_window_ps` and `reference_frame: "simulation_cell"` explicitly. No window or
scientific threshold is inferred. The supported trajectory has a fixed cell and
uniform recorded cadence. Irregular cadence requires a different explicit protocol.

The scalar diagnostic is the signed free-intercept MSD slope divided by six,
with Å²/ps converted to m²/s; the tensor and its trace average are retained.
Physical lag times come from recorded MD steps and timestep. No drift or mobile
center-of-mass subtraction occurs. Charge-dependent diagnostics additionally
require explicit `charge_numbers`, `charge_species` and `charge_justification`.

Optional `resampling` uses the serialized ResamplingSpec fields:
`block_origins`, `min_blocks_provisional`, `n_resamples`,
`nominal_coverage_provisional`, `seed`, `replica_scheme`, `joint_quantities`.
The implemented replica scheme is `single_trajectory_no_replica_resampling`.
All resampling scientific choices remain PROVISIONAL and user-supplied.

**Statistical qualification: UNKNOWN / NEEDS EVIDENCE.** The diagnostic bootstrap
uses complete blocks from a common truncated origin pool. The primary estimator
uses all available origins at each lag. Consequently bootstrap diagnostic
intervals are retained separately and are **not** assigned as confidence bounds
on the primary observation. Its canonical Uncertainty records this mismatch,
block accounting and missing effective independence; bounds remain null.

`p3_scientific_record` contains round-trippable ClaimSpec, Observation (or null),
Uncertainty and ClaimAssessment. Missing acceptance criteria yield UNKNOWN.
Explicit criteria with insufficient/unqualified evidence yield INDETERMINATE;
they cannot promote diagnostics to PASS/FAIL. No production qualification entry
is supplied. The general claim engine binds registered qualification to protocol,
scope, estimator/method versions, requirements and the exact observation hash.
Supplying a worker-side qualification string cannot confer qualification.

Insufficient trajectory support leaves the observation unavailable. Corruption,
missing artifacts, input identity mismatches and numerical errors are execution
failures, never inferred material failures. Existing P2 failures are preserved.

Supporting mathematical/statistical modules include collective/cross-species
diagnostics, explicit temperature analysis, synthetic generators and repeated
coverage reporting. Software tests do not qualify their physical applicability.
Evidence-artifact ingestion, follow-up execution, backends and scheduling remain
outside this executable checkpoint. No historical candidates were rerun.

## Checkpoint validation

```powershell
.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider tests/test_scientific_contracts.py tests/test_scientific_transport.py tests/test_p3_scientific_slice.py
# Final focused run: 24 passed.
.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider -k "not test_relax_structure_tiny_end_to_end and not test_real_checkpoint_cpu_end_to_end"
# Broader run before the final audit fix: 330 passed, 2 failed (missing nbformat), 2 deselected.
.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider tests/test_validation.py::test_kaggle_notebook_wrapper_valid tests/test_validation.py::test_kaggle_notebook_persistence_safety
# After installing nbformat and declaring it in dev dependencies: 2 passed.
```

The two real-model CPU integration tests were deliberately excluded. Existing
ASE small-system thermostat/deprecation warnings were not silently resolved by
changing historical scientific protocols.
