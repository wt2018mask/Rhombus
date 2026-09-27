# G-stage Candidate Supply v2 — Design Contract

Status: DESIGN ONLY
Scope: candidate supply and scheduling only. No GPU work, no P1/P2/P2.5 reruns.

## 1. Frozen evidence motivating v2

Observed funnel:

- G generated: 216 children from 72 ordered parents.
- P0: 121 passed, 95 rejected.
- Of 95 P0 rejections, 94 involved neutrality failure.
- P1-eligible: 47.
  - substitute: 31
  - displace: 16
  - strain/vacancy/interstitial: 0
- Parent-diverse wave1 executed: 36.
- P1 KEEP_FOR_P2: 33/36.
- P2 PASS: 9/33.
- Canonical evidence transition PASS: 5/9.
- Final P2.5: 5 NONDIFFUSIVE, 0 DIFFUSIVE.

Interpretation constraints:

- P1 is not the main observed bottleneck in executed wave1.
- P2 PASS does not imply diffusion.
- The five final NONDIFFUSIVE candidates must not be extended further.
- The 11 deferred wave1 children are same-parent-pool exploitation and are not
  evidence of a structural G-v2 solution.
- Operator-specific P0 rejection causes cannot be reconstructed from frozen
  artifacts, because the 216 per-child records were not persisted.
- Therefore no claim such as "vacancy caused X of the neutrality failures" is
  permitted from current evidence.

## 2. Contracts that v2 must preserve

1. Determinism:
   same parent + seed + generation config must reproduce the same child and
   provenance.

2. Provenance:
   every child must preserve parent identity, operator identity/version,
   parameters, seed, child index, generation-config identity, novelty evidence,
   and P0 evidence.

3. P0-at-birth:
   every generated candidate receives an explicit P0 result.

4. Parent-P0 execution precondition:
   before executing a currently scheduled composition-preserving baseline,
   candidate-supply-v2 evaluates the parent with the existing P0
   implementation. If `neutrality_ok` is `False`, no child is generated and
   the scheduling decision remains explicit as `BLOCKED_BY_PARENT_P0`.
   `BLOCKED_BY_PARENT_P0` is a generation scheduling state only; it is not a
   core existence, dynamic, or transport verdict.

5. P1 eligibility:
   keep the existing rule:
   novel AND (PLAUSIBLE OR geometry-only FAIL).

   Neutrality FAIL candidates do not enter P1 because relaxation preserves
   composition and cannot repair charge imbalance.

5. Novelty:
   retain calibrated StructureMatcher-based provenance unless separately
   recalibrated with evidence.

6. Published conductivity:
   provenance/diagnostic only. It must not be used as transport truth or as a
   sole candidate-ranking criterion.

7. Legacy semantics:
   existing operators must not silently change meaning. If defect or
   substitution chemistry is redesigned, introduce explicitly versioned new
   operator semantics.

## 3. Problems v2 is intended to address

### A. Sampling-policy problem

Current v1 samples one operator randomly for each child and generates only
three children per parent.

Consequences:

- per-parent operator coverage is not guaranteed;
- an inapplicable operator consumes a child slot;
- the effective five-way space
  (displace, strain, vacancy, interstitial, substitute)
  cannot be systematically covered with three random draws;
- observed operator counts are partly sampling noise.

Requirement:

v2 must replace random-three-draw supply with an explicit,
deterministic/applicability-aware scheduling policy.

Increasing children_per_parent while retaining the same random policy is not,
by itself, a v2 solution.

### B. Operator-semantics problem

#### displace

- composition preserving: it does not introduce a new composition change, but
  it inherits the parent composition's P0 neutrality state;
- currently reaches downstream stages;
- retain as a baseline operator;
- do not assume that more displacement gives better candidate diversity.

#### strain

- composition preserving: it does not introduce a new composition change, but
  it inherits the parent composition's P0 neutrality state;
- v1 produced no P1-eligible strain candidates;
- current matcher calibration indicates small strains can remain in the parent
  basin;
- do not simply increase strain count;
- determine whether a materially distinct, scientifically defensible strain
  regime exists before changing its magnitude.

#### vacancy

Legacy semantics remove one Li-containing site without compensation.

- preserve legacy op_vacancy semantics for provenance/reproducibility;
- do not expand it as the v2 defect strategy;
- any charge-compensated vacancy construction must be a new versioned operator.

#### interstitial

Legacy semantics add one Li at a uniform-random fractional coordinate without
charge compensation.

- preserve legacy op_interstitial semantics;
- do not expand it as the v2 defect strategy;
- any compensated and/or site-aware interstitial construction must be a new
  versioned operator.

#### substitute

Legacy semantics permit allowlisted isovalent or heterovalent single-site
substitution and defer neutrality rejection to P0.

- retain the legacy operator for reproducibility;
- do not simply increase its child count;
- v2 should distinguish chemically admissible substitution semantics from
  intentionally neutrality-breaking trials;
- any compensation-aware multi-site substitution must be versioned separately.

## 4. Parent supply

The prior ordered expansion used all 72 ordered parents in its selected pool.
The broader perturbable population included structures unsupported by the
current P1 disorder contract.

Therefore:

- do not equate high published conductivity with parent eligibility;
- do not pull disordered parents directly into P1 without a separate ordering
  design;
- parent-pool expansion and operator redesign are separate decisions.

## 5. v2 success criteria

Candidate-supply-v2 is not successful merely because:

- it generates more children;
- P0 pass rate rises;
- P1 KEEP rate rises;
- one chemical family is enriched.

A useful v2 design must instead demonstrate that it changes the supplied
candidate space in an auditable way while preserving scientific validity and
without spending compute on structurally known dead ends.

Before any GPU execution, v2 must expose an audit capable of reporting at least:

- parent ID / chemical family;
- scheduled operator and operator version;
- applicability outcome;
- P0 outcome and rejection class;
- novelty class;
- P1 eligibility;
- counts grouped jointly by operator and failure stage.

## 6. Explicit non-goals

- no P3 rerun;
- no extension of the five canonical NONDIFFUSIVE candidates;
- no blind rerun of the old frozen cohort;
- no automatic execution of the 11 deferred children;
- no conductivity-only candidate ranking;
- no claim that sulfide is intrinsically superior from the current small,
  confounded sample;
- no generator implementation change until this design contract is reviewed.

## 7. Candidate-supply-v2 decision matrix

This section fixes the design direction before implementation.  It does not
authorize generation, P1 work, or GPU execution.

### 7.1 Scheduling policy

v2 SHALL NOT use the v1 policy of three independent random operator draws per
parent.

The intended scheduler is:

1. deterministic for a fixed parent + generation config;
2. operator-explicit rather than random-draw;
3. applicability-aware before consuming a candidate slot;
4. auditable for both scheduled and skipped operators;
5. bounded independently of published conductivity;
6. able to report a skipped operator as an explicit scheduling outcome rather
   than silently replacing it with another random draw.

A parent/operator pair therefore has one of these scheduling states:

- `SCHEDULED`
- `INAPPLICABLE`
- `DISABLED_BY_POLICY`
- `DEFERRED_PENDING_DESIGN`
- `BLOCKED_BY_PARENT_P0`

The scheduler must record the state even when no child is produced.

This separates two quantities that v1 confounded:

- how often an operator was selected;
- how often an operator was scientifically/applicably capable of producing a
  candidate.

### 7.2 Operator decision matrix

| Operator semantics | v2 status | Reason |
| --- | --- | --- |
| `displace` legacy | `SCHEDULED_BASELINE` | Does not introduce a new composition change, but inherits the parent composition's P0 neutrality state; supplied real downstream survivors in wave1. Retain as a bounded baseline, not as a volume-expansion strategy. |
| `strain` legacy | `DEFERRED_PENDING_NOVELTY_DESIGN` | Does not introduce a new composition change, but inherits the parent composition's P0 neutrality state; v1 yielded zero P1-eligible strain children. Current evidence cannot distinguish operator weakness from same-basin novelty filtering well enough to justify scaling it. |
| `vacancy` legacy | `DISABLED_BY_POLICY` | Single uncompensated Li removal changes composition and is explicitly known to be able to fail neutrality. Preserve implementation for reproducibility but do not use it as v2 supply. |
| `interstitial` legacy | `DISABLED_BY_POLICY` | Single uncompensated Li insertion changes composition and has no charge-compensation or site-selection design. Preserve implementation but do not use it as v2 supply. |
| `substitute` legacy | `LEGACY_DIAGNOSTIC_ONLY` | Produced downstream candidates, but mixes isovalent and heterovalent semantics and relies on P0 to reject chemically invalid outcomes. Do not scale unchanged. |
| neutrality-aware substitution v2 | `DESIGN_CANDIDATE` | A separate versioned operator may restrict or construct substitutions so that chemical admissibility is addressed before spending a child slot. Exact chemistry rules require an explicit design and tests before activation. |
| charge-compensated defect v2 | `DEFERRED_PENDING_CHEMISTRY_DESIGN` | Potentially addresses the defect-supply failure mode, but current frozen evidence does not justify any specific compensation rule, defect pair, stoichiometry, or site-selection algorithm. |
| site-aware interstitial v2 | `DEFERRED_PENDING_CHEMISTRY_DESIGN` | Random fractional insertion is not an acceptable v2 assumption. Candidate site construction requires a separate scientifically justified design. |

### 7.3 Initial v2 supply rule

The first implementation increment SHALL be deliberately smaller than the full
future operator space.

It may implement infrastructure for deterministic/applicability-aware
scheduling and auditing without activating scientifically unresolved new defect
operators.

The first v2 implementation target is therefore:

- retain bounded legacy `displace` as a baseline;
- introduce a separately versioned neutrality-aware substitution path only
  after its admissibility rule is explicitly specified;
- record `strain`, legacy `vacancy`, and legacy `interstitial` scheduling
  decisions without automatically generating them;
- preserve all legacy operators unchanged for reproducibility.

This prevents an infrastructure refactor from being conflated with approval of
new chemistry.

### 7.3.1 Parent-P0 execution guard

The parent-P0 check is an efficiency and provenance guard. A
composition-preserving operator does not introduce a new composition change,
but it inherits the parent composition's P0 neutrality state. If the parent
has `neutrality_ok is False`, the scheduled displace baseline is marked
`BLOCKED_BY_PARENT_P0` and no child slot is spent. This guard does not alter
legacy `generate_children` semantics; it applies only to candidate-supply-v2
scheduling and execution.

This is a generation scheduling state, not a core existence, dynamic, or
transport verdict. The guard is intentionally narrow and does not authorize
new chemistry, rank parents, or change downstream state machines.

### 7.3.2 CPU smoke implementation evidence

A real three-parent OBELiX CPU smoke run exercised the guarded path:

- 3 requested parents;
- 15 schedule records;
- 2 generated children;
- 1 P1-eligible child;
- `obelix:d7f` displace: `BLOCKED_BY_PARENT_P0`;
- `obelix:dc8` displace: `SCHEDULED`, `rediscovery`;
- `obelix:rr5` displace: `SCHEDULED`, `novel`, P1-eligible.

This is implementation evidence that the parent-P0 guard and audit preserve
the intended distinctions. It is a small smoke result, not evidence for
operator superiority, family ranking, transport performance, or a general
P1 success rate.

### 7.4 Parent scheduling

Each eligible ordered parent is considered independently.

The scheduler must not:

- allocate more slots because published conductivity is higher;
- silently replace an inapplicable operator with another operator;
- consume candidate budget for an operator exception;
- generate repeated children merely to satisfy a fixed children-per-parent
  count.

The unit of scheduling is `parent x operator-version`, not "three random
children from a parent".

### 7.5 Required pre-GPU audit

Before any generated v2 candidate can be authorized for P1, a CPU-only audit
must show, jointly by operator version and parent chemical family:

- parents considered;
- operator scheduling states;
- children actually produced;
- operator errors;
- P0 PASS;
- P0 rejection class;
- novelty class;
- P1-eligible count.

The audit must retain per-child rows sufficient to reconstruct these
cross-tabs later.  v2 must not repeat the v1 loss of the 216 individual
pre-eligibility records.

### 7.6 Evidence boundary

The current data justify redesigning candidate supply, but do NOT establish:

- that sulfides should dominate the next parent pool;
- that displace is intrinsically superior to substitute;
- that compensated vacancies or interstitials will improve transport;
- that a particular heterovalent compensation scheme is chemically valid;
- that larger strain or displacement magnitudes will produce useful novelty.

Those questions require separate evidence and must not be encoded implicitly
in the scheduler.

## 8. Minimal implementation interface

The first implementation increment SHALL NOT modify the core pipeline state
machine in `rudeus/schema.py`.

`CandidateMaterial` represents a candidate that actually exists as a generated
child. Scheduling decisions where no child exists must therefore be represented
separately.

### 8.1 Scheduling record

Introduce a generation-local scheduling record with the conceptual fields:

GenerationScheduleRecord

- parent_id: str
- parent_chemical_family: str
- operator_name: str
- operator_version: str
- schedule_state:
  - SCHEDULED
  - INAPPLICABLE
  - DISABLED_BY_POLICY
  - DEFERRED_PENDING_DESIGN
  - BLOCKED_BY_PARENT_P0
- reason: str
- seed: int
- generation_config_hash: str
- child_material_id: optional[str]

Rules:

- one record represents one `parent x operator-version` decision;
- `child_material_id` is absent unless a child was actually produced;
- scheduler state is not an existence/dynamic/transport verdict;
- these states must not be added to `ExistenceState`, `DynamicState`, or
  `TransportState`;
- a scheduling record must exist even for operators that produce no child.

### 8.2 Generated-child audit row

For every produced child, retain a lossless pre-P1 audit row with enough
information to reconstruct the full funnel later.

Conceptual minimum fields:

- parent_id
- parent_chemical_family
- operator_name
- operator_version
- schedule_state
- child_material_id
- child_index
- seed
- generation_config_hash
- operator_error
- p0_state
- p0_neutrality_ok
- p0_pauling_ok
- p0_geometry_ok
- p0_rejection_class
- novelty_tag
- novelty_matched
- p1_eligible

This row is diagnostic/provenance data. It is not a replacement for
`CandidateMaterial` or its append-only evidence log.

### 8.3 Persistence requirement

Unlike v1, v2 must persist per-decision and per-child rows before downstream
filtering.

The audit output must contain both:

1. `schedule_records`
   - including decisions that produced no child;

2. `child_rows`
   - including every generated child, whether or not it becomes P1-eligible.

Aggregated counts may additionally be written, but they must be derivable from
these lossless records rather than being the only retained evidence.

### 8.4 API boundary

The initial implementation should remain inside `rudeus.generation`.

Do not modify:

- core `CandidateMaterial` state semantics;
- P1/P2/P2.5 schemas;
- legacy operator behavior;
- frozen batch artifacts.

Only after the scheduling/audit implementation has focused CPU tests should any
new chemistry operator be considered for activation.
