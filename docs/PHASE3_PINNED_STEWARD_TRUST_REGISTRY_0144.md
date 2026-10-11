# Checkpoint 0144 — fail-closed externally pinned steward trust registry

**Science status: P0-01/P0-02/P0-03 all BLOCKED.** The existing 0143 verifier checks the signatures in a packet when somebody supplies `trusted_issuers`; this new module specifically closes the **trust-on-first-use / packet-controlled key** failure mode. It does **not** provision, approve or contact an actual independent steward.

## Threat model and authority boundary

A hostile study packet can contain a perfectly coherent signed claim and a public key controlled by the developer. That is not independent custody. A standalone **host-owned trust policy file** must be provisioned outside public GitHub, with its complete exact raw-file SHA256 pinned *by a separately trusted host configuration*. The packet cannot supply the policy path, expected SHA256, active keys, role grants, independence groups or rotation state. An expected digest passed by the packet or generated dynamically from its accompanying policy file **does not establish trust**. A passed checksum proves bytes match the host's pin, **not** that a real institution or specimen is independently verified.

The policy binds one evaluation ID, external scope, development group, a shared witness log ID and exactly one **active** Ed25519 steward key and one **active** independent witness key. Keys cannot be reused across identities or registered twice. Policy can retain specifically **revoked** keys for audit, but none may authenticate current receipts; fail closed on missing active authorities or role/group overlap. Policy revisions are immutable; changes or rotation need a **new out-of-band host pin** and an independent approval trail. Merely changing a key's `status` from `REVOKED` to `ACTIVE` invalidates the old pin.

`authority_review_sha256` per registration is only a **pointer** to a missing or externally reviewed institutional qualification record: the field is NOT independently verified proof that the institution exists. An external institutional audit must separately confirm identities and legal authority and approve the pinned root.

## Implementation

- `rhombus/qualification/steward_trust_registry.py`: strict bounded JSON loader, raw-file SHA256 comparison, duplicate/NaN rejection, canonical registration schema and public-key independence/role/revocation checks.
- `review_pinned_external_steward_packet`: wraps existing `verify_steward_preregistration` using only the independently pinned active keyset; packet's claimed authority cannot replace the host trust store. Returns an **aggregate-only** report and permanently preserves all scientific NO-GO fields.
- `tests/test_phase3_steward_trust_registry.py`: synthetic Ed25519 test keys and adversarial pin swapping, key collision, role overlap, revocation/rotation, fake real-world independence, wrong scope/log and corrupt JSON. **No real trusted keys/identities are committed**.
- Test-only GitHub Actions never load real steward material, credential or actual institutional trust file; only synthetic verification summaries may be published.

## Required real-world handoff outside this repository

1. Institutionally independent steward + witness independently vetted by project governance, separate key custody, written consent and institutional source/measurement authority.
2. A host operator approves a policy file with the current Ed25519 public keys and source-review provenance. Store immutable exact raw SHA256 *out of band* in trusted host configuration, **not alongside an untrusted study packet**.
3. Authenticated real-new-cohort planning and private specimen/phase/measurement inventory; sealed identity/truth outside GitHub. Authorized reviewers observe locked predictions before truth release.
4. Independent full MACE-MPA-0 selected training-frame overlap audit (P0-02) and independent material-level experimental power/precision/replication (P0-03) are separate prerequisites.

**No Codex Cloud required:** bounded unit tests and synthetic GitHub Actions suffice. A real external human custodian and audited source data, not new AI compute, remain the blocking resource.
