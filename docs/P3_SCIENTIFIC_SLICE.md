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
`fit_window_ps`, `reference_frame: "simulation_cell"`, and a reconstruction
declaration explicitly. No window or scientific threshold is inferred.

## Phase 1 estimator/data contract (scientifically unqualified)

The protocol's optional `reconstruction` field must be supplied to obtain a new
numerical diagnostic. It is omitted from canonical serialization when absent,
preserving old protocol identities. Old protocols remain readable; attempting new
analysis without a declaration leaves the observation unavailable with
`reconstruction_declaration_unresolved`. Historical records are not recomputed.

```json
"reconstruction": {
  "coordinate_convention": "wrapped_cartesian_primary_cell",
  "periodic_directions": [true, true, true],
  "cell_origin_A": [0, 0, 0]
}
```

The declaration is checked against finite coordinate arrays and their fractional
domain relative to the declared origin. Cell-face equivalents are allowed within
floating-point arithmetic roundoff. No coordinate is automatically wrapped to
make the declaration pass. This is a checked representation declaration, not an
independent witness of the producer's coordinate history. The current P2 sampler
does not request wrapping from ASE; its raw output must not simply be relabeled
as wrapped because the artifact documentation says so. Contradictory coordinates
are unsupported, and P2/P2.5 writing/serialization remain unchanged.

Only finite, nonsingular, fixed orthogonal cells with all three periodic directions
explicitly enabled are supported for this reconstruction. Skew cells, variable-cell
arrays/NPT, unsupported conventions and partial periodicity are rejected. Orthogonality
uses only a scale-aware floating-point dot-product roundoff bound, not a scientific
skew tolerance. The existing P2 fractional-rounding accumulation algorithm is reused;
no alternative is substituted. Half-cell image ties are rejected. Missing whole-cell
crossings cannot be detected from sparse wrapped samples: `sampling_aliasing` stays
UNKNOWN and reconstruction applicability remains UNKNOWN / NEEDS EVIDENCE even
when coordinate checks pass. No maximum safe displacement or cadence is invented.

P3 validates integer increasing frame steps, positive finite declared integration
timestep, uniform cadence and the complete production sampling schedule (including
first/last expected samples, equilibration offset and completed production bound).
Available P2 schedule declarations must agree. Missing frames, even regularly
decimated frames, are rejected against that schedule. P3 does not fill frames,
reset clocks or implement irregular lag bins. Lag times use actual recorded step
differences multiplied by the declared timestep, not frame indices. Integration
timestep, saved-frame spacing and saved trajectory span are recorded separately.
This uses the declared fs time basis; it does not independently qualify the MD
integrator's unit conventions or dynamics.

All atoms of the selected species are used in their persisted array order. The
original index is the identity basis; P3 never sorts ions by position, picks only
hopping ions, or asserts independent particles. Identity continuity relies on the
producer's persistent-order contract; it cannot detect an upstream permutation of
otherwise indistinguishable same-species atoms from positions alone.

The primary population is all origins `range(n_frames - lag)` independently at each
requested lag. Exact ranges, selected atom indices and a canonical population hash
(including step times, lags and origin multiplicities) make this reproducible.
Mean displacement vectors are retained per species and lag. The arithmetic mean
motion of unselected atoms is recorded separately; it is not automatically a host
center of mass or a qualified framework frame. An empty complement remains null.
There is no drift subtraction, recentering or time-dependent rotation. Translation
of coordinates and declared cell origin together preserves displacements; constant
rotation transforms the tensor covariantly and preserves its trace. Drift remains
an unresolved qualification blocker.

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

Phase 2 adds the explicitly versioned
`joint_contiguous_full_origin_blocks-v2-diagnostic` method. It partitions the
complete origin union into contiguous blocks and retains a short final block.
Each draw samples block indices exactly once according to the declared draw count,
turning those selections into integer weights on the original origins. The same
weights are applied jointly to every selected species, atom, lag and tensor
component. Each lag uses only its own valid origin prefix; unsupported origins are
masked, never replaced with zero. Coordinates are never concatenated, so block
boundaries cannot introduce artificial displacements.

The unit-weight evaluation reproduces the primary all-origin estimator. The stored
contract binds the original population hash and the fixed estimator specification:
recorded steps, timestep, lags, fit window, species, reference frame, physical
conditions, free intercept, signed slopes, and unchanged unit conversion. No draw
may choose a new fit window, clip a negative slope, project a tensor to positive
semidefinite form, force a zero intercept, or perform hidden preprocessing.

Exact block boundaries, per-lag support counts and block masks, displacement source
ranges, block picks, origin-weight hashes, RNG/seed, planned draws, failures,
quantile rule, NumPy version and diagnostic intervals are retained. Failed draws
remain at their planned indices and are not retried or deleted. A zero lag-weight
denominator is an explicit failed draw. Any required failed draw makes the affected
diagnostic interval unavailable. `min_blocks_provisional`, when present for schema
compatibility, is recorded but is not used by the Phase 2 method as a scientific or
computational sufficiency gate.

These percentile intervals are a **diagnostic resampling distribution**, not a
validated confidence interval. They remain outside `Uncertainty.bounds`;
`calibration_reference` stays null, effective independent block count stays null,
and qualification remains UNKNOWN / NEEDS EVIDENCE. Blocks are not independent
replicas. Phase 2 accepts only one trajectory and does not infer a replica pooling
rule. A diagnostic interval cannot create PASS or FAIL.

**Statistical qualification: UNKNOWN / NEEDS EVIDENCE.** The legacy v1 diagnostic bootstrap
uses complete blocks from a common truncated origin pool. The primary estimator
uses all available origins at each lag. Consequently bootstrap diagnostic
intervals are retained separately and are **not** assigned as confidence bounds
on the primary observation. Its canonical Uncertainty records this mismatch,
block accounting and missing effective independence; bounds remain null.
The primary and bootstrap-point population hashes and their mismatch are recorded.
`joint_origin_bootstrap(expected_population_hash=...)` explicitly refuses a
different sufficiently populated point population. It does not implement a matched
resampler or confer coverage even if populations match; insufficient support still
returns an unavailable interval. No block length, effective sample size, minimum
block count, fit cutoff, coverage threshold or acceptance region is added by Phase 1.

Phase 3 must resolve block-length selection, effective information, empirical
coverage and bias, stationarity/mixing, rare-hopping sufficiency, replica pooling,
selection/stopping effects, reconstruction and drift applicability, finite-window
versus long-time diffusion, and finite-cell versus bulk interpretation. Until
independently calibrated for a registered scope, every item remains UNKNOWN / NEEDS
EVIDENCE.

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


## Real-MD S3 admission contract

Real-MD statistical calibration is not authorized merely because the P3
estimator can emit a numerical diagnostic.  Admission to the real-MD S3
calibration population is a separate fail-closed decision implemented by
`rudeus.science.real_md_s3_admission`.

A candidate is calibration-eligible only when all of the following are true:

- upstream execution and integrity checks succeeded;
- P2 and P2.5 candidate/batch identities are mutually consistent;
- `p2_verdict == "PASS"`;
- `p25_verdict == "DIFFUSIVE"`;
- `transport_state == "DIFFUSIVE"`;
- P2.5 verdict and transport state agree.

`NONDIFFUSIVE` candidates are not calibration members.  When P2 is PASS and
P2.5 consistently reports NONDIFFUSIVE, the record may be retained as
negative-control / falsification evidence.  `INDETERMINATE`, `NOT_RUN`,
upstream non-PASS states, execution failures, identity mismatches and integrity
failures are excluded.  Execution/integrity failures are blockers, never
material FAIL verdicts.

A collection containing no eligible P2.5-DIFFUSIVE candidate has population
status `BLOCKED_NEEDS_DIFFUSIVE_CANDIDATE`.  This status means that software
may be operational while real-MD S3 scientific qualification remains blocked.

Qualification scope is domain-bound.  A qualification registered for synthetic
Brownian trajectories does not authorize real-MD uncertainty bounds.  Exact
domain equality is required by the admission guard; no Brownian `q_hat`,
coverage result or certificate may be rebound to the real-MD domain.

The persisted 100 ps pilot for
`g1-3a449d0d18a233fe` / batch `0d4de6bc17174a64` is classified only as
real-MD reference-method feasibility / negative evidence.  Its artifact is
`p3-real-md-reference-feasibility-interim-v1`, its status is
`NON_QUALIFIED_INTERIM`, and its claim scope explicitly denies final Stage-1
qualification, qualified diffusion and uncertainty transfer.  The pilot's
numerical diffusion estimate therefore cannot promote it into the S3
calibration population.

The frozen full reference plan remains separate from admission: after a genuinely
P2.5-DIFFUSIVE candidate exists, independent long replicas and the registered
long-time stability/precision gates must still be satisfied before any real-MD
uncertainty calibration or S4 acceptance work can proceed.
