# 0143 — Independently signed, identifier-free blinded cohort preregistration envelope

## Purpose and threat boundary

The real independent steward and witness are not Rhombus developers. They may create a **new**, never-public blinded cohort with private material identities, specimen records, truth and experimental measurements, then supply an *aggregate public envelope* that contains **only cryptographic commitments** and count **assertions**. This repository must never receive cohort material identifiers, private formulas, DOIs tied to sealed participants, truths, issuer private keys or training-frame identities.

This checkpoint accepts a **two-signature Ed25519 chain** using the already deployed `rhombus.evidence.receipts` verifier. Trusted public keys / roles / independence groups / log ID are supplied **by the host separately from the untrusted envelope**. An arbitrary JSON self-reported key does not become trust. The strict verifier authenticates *a signed assertion*, not physical specimens or the identity/independence of entities controlling the keys. Independent institution/authority, measurement provenance, prospective roster and sample counts must be audited outside this code.

- Steward signs `cohort_preregistered` over SHA256 of the immutable envelope with `previous_receipt_sha256=000…000`, sequence 1.
- Separate witness signs `cohort_commitment_witnessed` over the same envelope hash with previous receipt pointing to the steward receipt hash, sequence 2.
- The two roles must have **distinct independence groups**, neither equal to the developer group. Identical logging context and scope are mandatory. Test-only `SYNTHETIC` keys may prove *cryptographic code functionality* but are never trusted as real external science.
- The declared identity scheme is `STEWARD_CANONICAL_MATERIAL_TOKEN_V1`, with `cohort_commitment_sha256` and `model_sha256` bound into the preregistration. The declared model must be the already full-file-observed original MACE-MPA-0 medium SHA, not a newly selected model guessed after outcomes.
- The declared plan digest is linked to the full **0142 prospective material feasibility input**. Counts are self-reported; the evaluator does not see roster or denominator records. Post-enrollment FAILED/UNKNOWN/NONDIFFUSIVE/INDETERMINATE/abstained outcomes must **never** be dropped.
- No private material data or raw signed packet is copied into GitHub Actions artifacts. Tests use only deterministic **synthetic** identities/keys with explicit `SYNTHETIC` scope.

## Intended external handoff — NOT performed

1. An authorized external steward generates and privately holds a new cohort, physical specimen/provenance inventory, source rights, sealed identity/sampling frame, experiment records and truth. Public legacy B3 and OBELiX official TEST cannot be rehabilitated.
2. A separate witness independently observes the preregistration and prediction freeze. Their public trust anchors and roles are provisioned via controlled host policy independently of packet bytes.
3. Only a canonical, identifier-free public envelope and two valid, ordered receipts may be given to Rhombus; the raw keys/identity roster and truth remain private. Do **not** upload an uninspected provider packet to a public repository.
4. The independent steward must later show frozen predictions before truth release, actual independent material counts, physical measurement/temperature/phase verification, authoritatively audited exact MACE selected-training-frame absence and third-party replication. Those stages exist separately in `rhombus/qualification/sealed_evaluation.py` and the P0 closure plan.

## Meaning of success

A valid synthetic exercise proves only the *receipt parser, contextual bindings, signing role independence* and leak-minimized output. Even an EXTERNAL host-provisioned signed packet returns **SIGNED_PREREGISTRATION_ASSERTION_ONLY**, `scientific_go=false`, `independent_materials_qualified=0` and **P0-01/02/03 all BLOCKED**. Proof of receipt possession is not provenance of measurement or entitlement to an empirical generalization claim.

This security/research workflow needs **no Codex cloud, Kaggle, GPU or fresh model training**. It is bounded CPU-only; external independent human stewardship remains the real scarce resource.
