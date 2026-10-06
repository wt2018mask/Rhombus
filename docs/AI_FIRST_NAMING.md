# Rhombus 2.0 AI-First Naming Contract

This document defines the canonical naming policy for Rhombus 2.0.

The goal is to make the project easy for generative AI systems, coding agents,
tool-calling models, and human developers to understand and compose correctly
without relying on hidden historical context.

## 1. Canonical project and package names

- Project/product name: `Rhombus`
- Canonical Python package for all new v2 code: `rhombus`
- Historical Python package: `rudeus`
- `rudeus` is legacy compatibility surface only once equivalent v2 adapters exist.
- Do not expose `rudeus` as a preferred tool namespace to AI systems.

Historical files, hashes, imports, and evidence using `rudeus` remain immutable.
They are not renamed in place.

## 2. Naming principle

Prefer names that answer three questions without external context:

1. What action is performed?
2. What scientific object is acted on?
3. What kind of result is returned?

Prefer:

```text
validate_candidate_structure
relax_structure
assess_finite_temperature_stability
classify_transport_regime
quantify_ionic_transport
assess_model_agreement
assess_novelty
assess_synthesizability
assess_application_fit
resolve_claims
build_evidence_manifest
```

Avoid new public names such as:

```text
P0
P1
P2
P2_5
P3
X
N
S
run_stage
process_item
check
analyze
execute
```

unless the historical identifier is explicitly required for provenance.

## 3. Historical-stage migration map

Historical stage names remain valid metadata but are not canonical v2 capability
names.

| Legacy | Canonical v2 capability | AI-facing intent |
|---|---|---|
| E | `ingest_evidence` | Add source-bound scientific evidence |
| G | `propose_candidates` | Propose candidate materials from a declared source or generator |
| P0 | `validate_candidate_structure` | Check static chemical, geometric, representation, and provenance validity |
| P1 | `relax_structure` | Relax a structure with an explicitly identified atomistic model |
| P2 | `assess_finite_temperature_stability` | Test whether the host remains dynamically meaningful under declared conditions |
| P2.5 | `classify_transport_regime` | Determine whether observed motion supports a qualified transport regime |
| P3 | `quantify_ionic_transport` | Estimate transport observables under explicit conditions |
| X | `assess_model_agreement` | Compare sufficiently independent models and expose disagreement |
| N | `assess_novelty` | Assess novelty against a declared reference universe |
| S | `assess_synthesizability` | Evaluate evidence for practical synthesis |
| Application | `assess_application_fit` | Evaluate a versioned application profile |
| Final Claim Vector | `resolve_claims` | Resolve evidence-bound claims without collapsing uncertainty |
| OUT | `build_evidence_manifest` | Produce the immutable final evidence manifest |

Legacy stage identifiers should be stored as fields such as:

```json
{
  "legacy_stage": "P2",
  "capability": "assess_finite_temperature_stability"
}
```

They should not determine new API structure.

## 4. Canonical v2 namespaces

New code should converge toward these domains:

```text
rhombus.evidence
rhombus.discovery
rhombus.validation
rhombus.domain
rhombus.atomistics
rhombus.transport
rhombus.realism
rhombus.qualification
rhombus.application
rhombus.tools
```

### `rhombus.evidence`

Evidence identities, provenance, artifact bindings, claims, limitations.

### `rhombus.discovery`

Candidate universe, proposal adapters, constrained transformations, active
selection.

### `rhombus.validation`

Cheap scientific validity checks and representation validity.

### `rhombus.domain`

Applicability domain, descriptors, OOD, uncertainty calibration.

### `rhombus.atomistics`

Model registry, relaxation, finite-temperature dynamics, model agreement.

### `rhombus.transport`

Transport-regime qualification, diffusion, multi-temperature transport,
collective effects, defect/carrier evidence.

### `rhombus.realism`

Chemical stability, interfaces, grain boundaries, microstructure.

### `rhombus.qualification`

Known-material falsification, generalization qualification, prospective
evaluation.

### `rhombus.application`

Novelty, synthesizability, application profiles, final application evidence.

### `rhombus.tools`

The intentionally small AI-facing tool surface. Internal helper functions should
not automatically become tools.

## 5. AI-facing tool naming rules

Every AI-facing tool should:

- use a stable lower_snake_case verb-object name;
- describe a concrete user/scientific intent;
- avoid unexplained acronyms;
- avoid historical stage codes in the primary name;
- expose explicit inputs instead of asking the model to infer hidden identifiers;
- return structured compact output;
- return stable IDs/hashes needed by follow-up calls;
- explicitly distinguish scientific verdict from operational status;
- document when not to use the tool;
- be idempotent where practical;
- expose side effects and resource cost class.

Good examples:

```text
get_candidate_evidence
get_domain_assessment
validate_candidate_structure
relax_structure
assess_finite_temperature_stability
classify_transport_regime
quantify_ionic_transport
compare_atomistic_models
assess_novelty
assess_synthesizability
assess_application_fit
select_next_experiment
build_evidence_manifest
```

Bad examples:

```text
run_p2
do_x
finalize
process
analyze_material
best_candidate
smart_check
```

## 6. Tool grouping for generative AI

Do not expose the entire internal repository as one giant tool set.

Default tool surface should stay small and task-oriented.

Suggested top-level groups:

```text
evidence.*
discovery.*
validation.*
atomistics.*
transport.*
qualification.*
application.*
```

An agent should load more specialized tools only when needed.

Example:

```text
validation.validate_candidate_structure
atomistics.relax_structure
atomistics.assess_finite_temperature_stability
transport.classify_transport_regime
transport.quantify_ionic_transport
```

## 7. Input/output naming rules

Prefer explicit scientific names:

```text
candidate_id
structure_artifact_id
mobile_species
temperature_K
timestep_fs
model_id
protocol_id
evidence_id
artifact_sha256
domain_status
scientific_verdict
operational_status
limitations
```

Avoid generic names such as:

```text
id
data
result
status
config
value
output
```

when a more specific field is possible.

Every result should separate:

```text
operational_status
scientific_verdict
applicability
uncertainty
limitations
evidence_ids
artifact_ids
```

## 8. State vocabulary

New v2 APIs should use stable, explicit scientific vocabulary.

Preferred scientific verdicts:

```text
PASS
FAIL
UNKNOWN
INDETERMINATE
NOT_APPLICABLE
```

Preferred operational states:

```text
PENDING
RUNNING
SUCCEEDED
ERROR
CANCELLED
```

Preferred domain states:

```text
IN_DOMAIN
NEAR_OOD
FAR_OOD
UNQUALIFIED
```

Never overload one `status` field with all three meanings.

## 9. Migration rule

Migration is additive.

1. Historical `rudeus` code and frozen evidence remain unchanged.
2. New v2 implementations use `rhombus.*`.
3. Compatibility adapters translate historical results into v2 evidence objects.
4. Public docs and AI tools prefer semantic capability names.
5. Legacy stage codes remain in provenance metadata only.
6. A legacy implementation is removed from active use only after:
   - equivalent v2 behavior exists;
   - regression tests prove semantic preservation where intended;
   - historical artifacts remain readable;
   - the migration is explicitly versioned.

## 10. Naming should improve tool performance, not merely aesthetics

A naming change is justified when it improves one or more of:

- tool selection accuracy;
- argument selection accuracy;
- composability;
- discoverability;
- reduction in prompt/context tokens;
- reduction in ambiguity;
- separation of scientific and operational semantics;
- compatibility with strict structured schemas;
- ability to defer specialized tools until needed.

A rename that only changes style but breaks evidence or increases ambiguity is
not useful.

## 11. First implementation sequence

The safe migration sequence is:

1. freeze this naming contract;
2. create the canonical `rhombus` package namespace;
3. add compatibility imports/adapters for selected `rudeus` capabilities;
4. introduce semantic v2 evidence schemas;
5. expose a small `rhombus.tools` API;
6. add tool-selection tests using realistic prompts/tasks;
7. migrate internals gradually;
8. keep legacy stage IDs only in provenance and compatibility code.

The initial package migration must not rename historical evidence files or alter
frozen hashes.
