# Domain-neutral research scope — architecture decision v1

Date: 2026-10-25. Status: owner-authorized implementation proposal; unmerged.
Authority: the owner's Approved Strategic Scope Revision supplied with the
comprehensive development mission. It supersedes the permanent O_ONLY-only
future scope in AGENTS, the earlier mission and roadmap. Issues #349 and #368
were recovered from their live public pages before implementation.

## Decision and scientific boundaries

Rhombus is a general-purpose, AI-native, evidence-bound research engine.
Solid-state ionic conductors remain its first practical application. O_ONLY is
a historical validation domain, not the project's permanent identity. The core
must represent other families and eventually other research domains without
rewriting evidence, applicability, planning or audit semantics.

Preserve historical events, source hashes, frozen experiments, O_ONLY and pooled
comparators, official TRAIN partitions and reserved TEST121. Family labels are
not phases, compositions, processing states or physical specimens. Element
coverage does not establish model applicability. Observables, units,
measurement temperature, source exclusions and uncertainty are specific to each
experiment and model. P0-01/02/03 remain BLOCKED; production remains OFF.
This revision authorizes research, not cross-family claims or remote dispatch.

## Small additive contract

`rhombus.domain.context` implements `rhombus-research-context-v1`. It separates
domain, family, candidate, nominal composition, structure artifact, processing
state, observable, units and measurement temperature in Kelvin. Unknown identity
and conditions stay null. The host supplies labels; the contract does not infer
or authenticate them or silently relabel contradictory metadata.

A typed host `CapabilityDeclaration` names an intended domain/family/observable/
unit, model and protocol. `assess_declared_capability` records mismatches as
NOT_APPLICABLE. Even an exact match returns UNKNOWN/ABSTAIN with UNQUALIFIED
applicability, unknown uncertainty and no prediction or execution authorization.
A declaration is not a qualified model registry or an inference backend.

The adapter creates an ordinary content-addressed v1 EvidenceRecord with
SourceBindings. Its context is inside the hashed payload. The existing
`get_candidate_evidence` exposes optional bounded context after schema and
candidate-binding validation. `build_evidence_manifest` retains the same IDs;
`plan_scientific_task` remains proposal-only and treats supplied manifest IDs as
unverified. Historical records and IDs do not change. No new MCP tool, database,
service, deployment or paid dependency is introduced.

## Second-family path and acceptance

Sulfides are the first integration candidate because the repository documents
source-qualified 25 C total measurements (0172), original experimental files
(0177) and negative source-transfer results (0169/0170). This choice is based on
available measurement/provenance evidence. It does not imply that all
sulfur-present materials share a model domain. S_ONLY remains an element proxy;
halides, polymers and composites need their own profiles.

Synthetic tests demonstrate representation, content-hash-checked query,
manifest preservation, rejection by an oxide-only declaration, and continued
abstention even with a sulfide declaration. They do not demonstrate scientific
generalization or authenticated sulfide prediction. Missing or contradictory
composition/structure/processing evidence remains unresolved.

Before second-family selection, freeze a source-separated public benchmark with
comparable quantities/temperature, formula/DOI embargo, disclosed pretrained
exposure, uncertainty and cheap baselines under a common observation/compute
budget. Reuse existing adapters and retain failures. Do not fit/tune on TEST121
or claim independent specimens from paper conditions.

## Integration boundary

This engineering branch starts at #369 HEAD
87446af01baefa4b1dc5e4f592012dca591ef795. CURRENT remains 0197, with
0198-INDEPENDENT_PROCESS_DESIGN_EVIDENCE pending. No scientific checkpoint is
invented for policy/contract changes. The normal one-event PR continuity gate
remains an explicit integration prerequisite; do not bypass it or merge this
engineering unit until a legitimate checkpoint/integration route is available.
No existing stacked PR is rewritten.
