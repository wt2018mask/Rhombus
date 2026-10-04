# Downstream claim and OUT contract

After P3, the scientific sequence remains X → N → S → application compatibility
→ final Claim Vector → OUT. The `rudeus.science.downstream` sidecar is deterministic;
it does not run a model, search a database, assign synthesis chemistry, or qualify
any scientific threshold. Synthetic tests are contract demonstrations only.

## X: independent cross-check

`CrosscheckTask` binds the candidate, observable and conditions, input artifacts,
primary and secondary model identities (including base model and training
provenance), an explicit agreement rule, and independence evidence. No secondary
model is selected by default. `CrosscheckEvidence` binds both model outputs and
the disagreement artifact to the exact task hash. Missing model selection or
evidence is UNKNOWN; known shared base model, missing qualification, or missing
comparison is INDETERMINATE. A qualified applicable disagreement is FAIL and a
qualified applicable agreement is PASS. Applicability remains explicit. A
qualification reference is an evidence identity, not automatic certification;
scientific review must establish that the referenced protocol really qualifies
the comparison.

## N: final novelty

`NoveltyEvidence` records composition and structural novelty separately, known
rediscovery, versioned reference sources and their hashes, coverage, unresolved
sources, and evidence hashes. This is independent of generation-time novelty.
An evidenced match or rediscovery is FAIL. PASS requires complete declared
reference coverage, no rediscovery, and positive composition and structural
novelty evidence. Incomplete coverage remains UNKNOWN; no finite database is
silently treated as the entire material universe.

## S: synthesizability

The five named criteria cover precursor availability, compositional feasibility,
chemical plausibility, competing phases and synthesis route. Each criterion has
its own verdict, artifact hashes and optional limitation. Missing criteria are
UNKNOWN. The assessment uses the explicit mandatory conjunction; there is no
scalar synthesizability score or embedded chemistry rule. A real scientific
protocol must define and review the criteria before a material claim is made.

## Application profile

`ApplicationProfile` carries identity/version, protocol hash, mandatory and
optional claim IDs, provisional acceptance regions, applicability requirements,
and profile-specific requirements. Claim evidence binds the exact acceptance
region hash. Missing mandatory evidence or unmet requirements is UNKNOWN;
inapplicable profiles are INDETERMINATE. Optional claims are retained for profile
reporting but do not control the mandatory verdict. No species is hard-coded.

## Final Claim Vector and OUT

The mandatory vector includes existence, structural/energetic validity, dynamic
stability, diffusion, P3 transport, uncertainty qualification, X, N, S,
application compatibility, and provenance sufficiency. Its exact conjunction is:
any FAIL → FAIL; otherwise any UNKNOWN → UNKNOWN; otherwise any INDETERMINATE
→ INDETERMINATE; otherwise all PASS → PASS. Missing claims become UNKNOWN.
Existing `existence_state`, `dynamic_state`, and `transport_state` remain separate
upstream evidence; a future integration adapter must bind their qualified
assessments rather than translate operational success into a scientific PASS.

`make_out` creates an immutable, content-addressed `FinalDiscoveryManifest` with
the complete vector, stage assessments, applicability, unresolved claims,
protocol/config identities, input/output hashes, execution/provenance references,
limitations and final assessment. Missing X/N/S/application stages become
explicit UNKNOWN assessments. Missing provenance bindings or a missing candidate
identity prevents a final PASS. An OUT with FAIL, UNKNOWN, INDETERMINATE, or no
qualifying candidate is a valid conservative result. The sidecar does not mutate
frozen P2/P2.5 evidence or issue a v1 release.

## Known limits and runbook

No independent secondary model, cross-check qualification rule, complete novelty
reference universe, synthesis qualification protocol, or production application
profile has been scientifically selected here. Therefore the synthetic PASS
fixtures do not authorize a real candidate PASS. Before using a real P3-positive
candidate, collect each stage's retained artifacts and reviewed protocol, bind
upstream scientific assessments to all eleven claims, evaluate X/N/S and the
selected application profile, then create and archive a new OUT by content hash.
Retain earlier manifests; corrections require a new record. Run focused checks
with `python -m pytest -q tests/test_downstream.py tests/test_scientific_contracts.py`
in an environment with the project's development dependencies installed.
