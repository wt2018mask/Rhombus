# M7 Candidate Supply policy integration (parallel lane A)

Status: diagnostic code only; execution and scheduler activation are off.

`m7_candidate_policy.decide_candidate_supply` accepts a parent/context record,
per-operator evidence, a species-keyed provisional sigma policy, seed, and policy
identity. It returns an auditable proposal. It never calls a generator, alters
the frozen 100-unit allocation, authorizes P1, or changes scientific thresholds.
The only accepted `enabled` value is `False`; any activation attempt raises.

The portfolio contains `mobile-ion-displace-v2` and
`mobile-ion-local-clearance-gaussian-radius-v1` with direction budget 8. An
operator-scoped hash supplies a deterministic RNG seed. Exploration uses a
deterministic parent/seed hash to represent both arms. Exploitation prefers
useful diagnostic yield and geometry pass count. A separate Pareto front keeps
novelty, useful yield, geometry, and exhaustion visible. Computational effort
is retained as `(value, unit)` per arm and is never summed across operators.

Evidence interpretation:

- M5/version-9 observational evidence motivates a multi-objective portfolio;
  the existing frozen Pareto report and policy remain separate inputs. This
  module does not import their frozen allocation as a new authorization.
- M6-A replicated the geometry-aware D8 effect in its validation scope. That
  observation supports retaining D8 in the diagnostic portfolio.
- M6-B has 45 preregistered parent/seed identities, 24 generated per arm and
  21 parent-P0 blocks per arm. Geometry failures were 9/24 baseline and 0/24
  D8; useful diagnostic counts were 8/24 and 16/24. Nine geometry failures
  changed to passes and 15 passes remained passes. Novelty was 17 versus 16,
  so the decision representation keeps this tradeoff visible. No exhaustion
  or inapplicability was observed. The effect was observed across all seed
  blocks and halide, oxide, and oxyhalide subsets. Effort units differ.
- Li at sigma 0.35 Å is the validation profile, not a discovery-core default.
  A missing species-specific sigma input fails closed. All sigma values and
  scientific thresholds remain provisional.

M6-B provenance: `m6b_reconciliation.write_selection_reconciliation` writes
only a new receipt. The receipt in `data/batches/audit/` binds the original
failed report, panel, preregistration, pass-identity evidence, PREPARED and
SUBMITTED attempts, and the original run's content-addressed v9 source blobs.
It verifies exact family-stratified parent order and independently recomputes
the ordered cohort digest. It retains `SCIENTIFIC_VALIDATION_FAIL` and
`overall_provenance_pass=false`. It never reconstructs the unavailable
protected-state sidecar. The forward writer now emits the digest; future
collection requires the report-referenced standalone sidecar and verifies its
hash and length.

No shared schema change is proposed. Any later production integration needs
an explicit activation contract that consumes this diagnostic decision and
separately authorizes scheduling; it must not infer authorization from this
module or from M6-B reconciliation.
