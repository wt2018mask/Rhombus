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

The implementation originally started at #369 HEAD
87446af01baefa4b1dc5e4f592012dca591ef795. After actual fallback science and its
0198 registration in #371, a normal worker merge bases this separate engineering
PR #370 on #371. Following the repository's executed engineering-event precedent
(0197), exactly one explicit ENGINEERING event 0199 records the implemented
contract and actual six-call SDK subprocess receipt. No scientific result or
second-family qualification is invented to satisfy continuity. The next science
action remains independent process-design evidence (0200). Canonical main is
unchanged; no earlier PR branch is rewritten.

Reproduce the synthetic transport receipt with
`python -m scripts.tools.verify_domain_context --output NEW.json` using the
existing optional MCP SDK. The retained versioned receipt includes exact code
hashes, synthetic EvidenceRecords, six normalized responses and measured call
latency/response bytes. It explicitly leaves autonomous model-selection accuracy
and actual model token usage unverified. These are architecture and protocol
measurements, not measurements of sulfide material behavior.

Validation of the completed unit: 78 focused contract, real SDK, science and
continuity tests passed; the final Fast CI selection passed 2,168 tests with
8 warnings. Per-PR continuity passes against #371's exact base
072d0cc (one added 0199 event). CURRENT is 4,088 bytes; all earlier effective
refs/state codes/blockers and the immutable baseline remain preserved. These
local results do not certify source availability or the final remote CI set.
