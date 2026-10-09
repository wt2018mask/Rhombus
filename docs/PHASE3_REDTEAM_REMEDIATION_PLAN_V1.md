# Phase 3 Red-team remediation roadmap — checkpoint 0118

**Decision: scientific release NO-GO.** Rhombus remains a diagnostic research
prototype. The attached independent **2026-10-09 critical red-team review**
identified three **P0 scientific validity blockers**, four operational **P1
risks**, and numerical/reproducibility **P2 defects**. This document is an
actionable acceptance-test plan, *not* a declaration that findings were fixed.
The authoritative machine-readable register is
[`data/development/phase3_redteam_remediation_register_v1.json`](../data/development/phase3_redteam_remediation_register_v1.json).

## Reconciliation with live canonical GitHub main

The report assessed `79a2a329e67927a370c8e44531f75d4dd4c1b340` and
PR #281 at an **older** head `951b629d`. On main
`e1e6317f18bd27b00b0a0fa08a91d450dcc3bbc5` / checkpoint **0117**, PR #281 has **merged** after exact-head
Development Continuity, R2 Fast CI, Wave 2 and a real **two-job synthetic**
GitHub artifact upload/download. The old CI FAIL is therefore **historical,
resolved**, not an open issue. The synthetic roundtrip **does not establish
Kaggle cross-session or real-source safe resumption**.

The branch-protection query returned **403** from the available GitHub
integration, while accessible rulesets list returned `[]`. This is **not
proof that server-side required CI is disabled or enabled**. Admin must verify
effective protection and test that a deliberately failing PR cannot merge.

The report's code observations reconfirmed on this later main include:
`p3_transport.fit_arrhenius()` missing inverse-T rank/conditioning checks,
`int(charge_number)` silently coercing fractional input, the outgoing
scanner treating `.zip/.gz/.zst/.sqlite` as opaque, and the existing
`armed=true, launch_once=true` request without a consumed-run guarantee.
These are not to be relabeled fixed just because other CI passes.

## Non-negotiable scientific P0 — gate first

| ID | Existing evidence or flaw | Remediation / independent PASS requirement |
| --- | --- | --- |
| RT-P0-01 | Existing B3 HELD_OUT identities + truth references are publicly visible; blinding integrity already rejects strong blind qualification | **Never rehabilitate the old split**. A separate independent steward creates new sealed truth and identities; preregister protocol and freeze predictions **before** opening truth; red-team must fail to recover identity/answer |
| RT-P0-02 | Upstream MACE-MPA-0 medium reported SHA + declared MPTrj/sAlex families ≠ selected training frame membership | Independently hash exact model bytes and obtain checkpoint-selected frames, source SHA256, preprocessing and energy labels; audit overlap from immutable manifests; otherwise training exposure remains UNKNOWN |
| RT-P0-03 | 2 scoreable materials per POSITIVE/NEGATIVE/BORDERLINE; minimum split feasibility only | Pre-register independent **material-level** sample size, precision, inclusion/exclusion and negative reporting; compute confidence intervals and abstention/failure rates; never infer statistical generalization from repeated trajectories |

No P0 is resolved by rerunning Wave 2, adding more MD time for the same
material, obtaining a first-MiB MPTrj prefix, or fetching the 12.2GB original
without model-selected frame manifests.

## P1 / P2 stop-line operational controls

| ID | Severity | Attack/failure simulation required before PASS |
| --- | --- | --- |
| RT-P1-01 | P1 | Admin confirms effective branch-protection/ruleset settings, required CI & reviews, tests intentional failing PR is **unmergeable**; never actually bypass or merge red test |
| RT-P1-02 | P1 | Stop Kaggle **after** an independent externally stored source-shard checkpoint, then retrieve/check byte hashes + SQLite + source lineage and deterministically resume without loss or double-counting |
| RT-P1-03 | P1 | Fake token hidden inside bounded ZIP/GZ/ZST/SQLite cannot leave export scanner: **detect or reject** if uninspectable; prevent decompression-bomb tricks |
| RT-P1-04 | P1 | Replay/retry/concurrency of same `armed` sAlex launch request does **not** submit twice; prove durable consumed identifier, default-deny and explicit fresh operator opt-in |
| RT-P1-05 | P1 | Material-level analyses record **all** FAILED/UNKNOWN/NONDIFFUSIVE results; no correlated ensemble marketed as independent; no unqualified extrapolation from 550K short MD |
| RT-P2-01 | P2 | Identical and near-identical temperatures, rank-deficient and ill-conditioned inverse-T fits reject rather than `SUPPORTED_BY_DATA`; valid cases remain valid |
| RT-P2-02 | P2 | `charge_number=1.9`, `True`, `"1"`, 0 all rejected; finite true nonzero integers only, no silent coercion |
| RT-P2-03 | P2 | Python/Kaggle libraries, containers, GitHub Actions SHA, hardware/precision, random seeds, dataset+model hash pinned/logged; independent rerun variability explicitly recorded |

**Urgency:** RT-P1-04 and RT-P1-03 should be handled as immediate
no-side-effect safety PRs, along with RT-P1-01 admin review. Physical
numerical guards RT-P2-01/02 should be a small next PR, without postponing
the P0 blind-study design and exact lineage investigation.

## Execution order and acceptance gates

1. **R0 — Immediate claims freeze / controls (next small PRs).** Keep
   all scientific PASS/generalization and autonomous release gates false.
   Triage `armed` Kaggle dispatch, require real PR branch rule
   enforcement confirmation, and refuse claim promotion.
2. **R1 — Correctable engineering hazards.** Add the secret-in-archive
   rejection tests, launch nonce/consumed-run replay defense, invalid
   Arrhenius/charge guards, and source/runtime lock inventory. No new long job.
3. **R2 — Pre-registered external blinded study design.** External
   steward holds new HELD_OUT identities and truth **outside this public
   repository**. Freeze source/model/protocol IDs and all evaluation rules
   before any new prediction. Determine independent material count from a
   justified confidence/power calculation rather than declaring 2 per role
   adequate.
4. **R3 — Exact MACE lineage.** Independently hash the model binary,
   obtain selected MPTrj/sAlex frame, preprocessing and energy-label
   lineage; if unobtainable, keep `UNATTESTED` and constrain conclusions.
5. **R4 — Kaggle external recovery proof.** Advance the synthetic
   two-job Github proof to **separately completed real source-bound shard**
   upload/download, injected failure, no-gap/no-double-count resume; no
   12GB source or sAlex full computation until an approved resource gate.
6. **R5 — Material-level blinded science trial.** Run only after frozen
   predictions and all appropriate provenance, independent verification,
   full negative/failure retention, transport-sampling validity, material-
   level confidence intervals and provenance-bound published limitations.
   Independent replication is needed for an external science PASS.

R2/R3 can be investigated in parallel with the quick R0/R1 engineering
fixes. R4 must precede any new multi-hour Kaggle/MPTrj job. R5 is gated
by appropriate evidence, not an automatic project-phase increment.

## Evidence required to close a red-team issue

Every PR cites its `RT-...` ID; carries an **adversarial regression that
fails before the fix**, an independent successful verification, a
machine-readable SHA/source/permission record, and an explicit decision
on whether scientific authorizations remain false. Update this register
only to `RESOLVED` with qualifying evidence, reviewer and links. **Do not
weaken safeguards to satisfy a test.**

The **administrator** must apply effective GitHub protection settings (the
connected integration receives 403 for that setting). The **independent
blinded-data steward** must remain distinct from development agents and
public repo reviewers. The program should not automatically do either
without those external roles' deliberate action.

## Explicit NO-GO until independent evidence

- Scientific model qualification, unseen generalization, autonomous
  discovery approval and empirical calibration remain **denied**.
- The old public B3 held-out remains **contaminated** for strong blind claims.
- Source-family overlap, CI PASS or SHA256 of a partial artifact never proves
  checkpoint-selected training membership, full population validity,
  security of uninspected archives or durable Kaggle crash recovery.
- The staged GitHub synthetic roundtrip proves provider transport only
  for a tiny artificial SQLite fixture; it is **not** a Kaggle recovery
  completion certificate.
