# 0195 — bounded adaptive evidence replay, not material discovery

This completed control-plane experiment uses four authenticated historical O_ONLY
source pools, 32 reported process conditions, and no new experimental labels.
It closes one loop: source-backed candidates → coverage/applicability → bounded
allocation → host-authorized offline replay → typed EvidenceRecord → updated
coverage → an unexecuted next proposal. It is not a general scheduler or a new
predictive model. Original TEST121 fields and structures are not read.

## Inputs and independent scientific axes

Pinned process audit SHA256:
`8af20fd82153bf67db318d9e091610f7979d76df6689ae0de4a33ba1331d34c2`.
Pinned historical institutional VOR receipt SHA256:
`4cce0d4b9329e369d61db5116687c7297316fbda77be63fb96f1cbac6de18b75`.
The latter's actual source-verification run39357927381 was independently checked
through GitHub API: SUCCESS on1fd36ff2b7594fdc0e186fdd693941ede0cba417.
No new live PDF authentication is claimed; raw source hashes remain in records.

| Candidate pool / DOI | Conditions | Separate processing regime |
| --- | ---: | --- |
| 10.1039/c8ra01329b | 5 | frozen2018 conventional support; training-source overlap |
| 10.3390/ma13030560 | 5 | shorter-dwell conventional; old model OOD |
| 10.3390/ma14226809 | 4 | categorical powder recipes; shared2018 formula,1800min |
| 10.1002/cssc.202300399 | 18 | 56MPa hot press;600/650/700C,six reported series |

A source, process row, formula series and physical replicate are distinct units.
Source authenticity does not establish exact individual-pellet composition,
direct25C EIS, numeric uncertainty, physical independence or model applicability.
Hot-press complete per-condition formulas/overlap remain unresolved. All sources
remain useful exploratory evidence for their own regimes; none is rejected as
scientifically worthless because the conventional2018 Ridge cannot apply.

The existing process-support screen is reused. Source/formula overlap is an
additional independent blocker. Numeric temperature/time descriptors cannot
identify categorical route changes. Missing uncertainty, physical specimen
identity and model disagreement (not assessed without applicable predictions)
remain explicit. Existence/dynamic/transport states are never collapsed into a
single fitness. No separate-domain model is justified by one hot-press DOI or
one categorical-route DOI; conventional sources have only two formula components.

## Frozen allocation and actual replay

Each policy has ONE replay and at most18 target-pool conditions. All controls
use the same preavailable source cache; timing includes common provenance
reconstruction as well as the selected applicability replay. Estimated cost is
input-row work units, NOT calibrated CPU seconds. Adaptive allocation maximizes
answerable applicability condition coverage within that cap, with deterministic
identity ties. Controls are fixed regime order, cheapest eligible replay, and
one fixed-seed hash permutation. All policies share cost, capability, failure,
retry and authorization gates. Completed coverage is excluded from the next
proposal. Unknown cost and scientific failure do not grant execution.

The legacy local backend explicitly supports control-plane work only. We reuse
its capability report, TaskSpec, plan_attempt/order_plans and v2 EvidenceRecord
with SourceBinding. No LocalBackend.submit or remote scientific task is called.
A proposal remains NOT_SUBMITTED; the CLI separately authorizes OFFLINE replay.
This is newly executed diagnostic replay of historical authenticated evidence,
not a new physical calculation or model prediction. Each policy's selected
replay is actually executed separately; no counterfactual runtime is invented.

| Policy | Pool | Conditions with explicit applicability decision | Source-pool decisions |
| --- | --- | ---: | ---: |
| Static | 2018 | 5 | 1 |
| Cheapest | categorical2021 | 4 | 1 |
| Seeded control | hot press | 18 | 1 |
| Adaptive | hot press | 18 | 1 |

All four return ABSTAIN/REQUEST_MORE_EVIDENCE, no manufacturing winner. Adaptive
ties the seeded control and has the same ONE source-pool decision as all others.
Higher row coverage is not calibrated information gain, independent specimen
coverage, prediction accuracy, material utility or demonstrated scientific
superiority. Shared seeded/adaptive output has the SAME evidence ID: three
unique records, not four new discoveries. Costs are measured per replay, with
import/cache/order/host effects disclosed; no speedup or cost saving is claimed.
Unexecuted physical tasks have UNKNOWN cost/outcome. Physical abstention
correctness and ranking/regret utility are UNKNOWN, not fabricated positives.

## Reproduction and limits

`python -m rhombus.tools.adaptive_replay --output NEW.json --authorize-offline-replay`

The flag authorizes this bounded offline diagnostic only. Without it, no inputs
are read. Output creation is exclusive. Selection/evidence IDs are deterministic;
wall-clock observations are separate and need not reproduce bit-for-bit.
Run `python -m pytest -q tests/test_adaptive_evidence_replay.py` for missing
provenance/cost, source overlap, OOD, failure/retry, duplicate identities,
unauthorized execution, scientific dispatch and misleading PASS adversaries.

Append-only correction: earlier Nb-source narrative said its Nb0.6 formula
matched2020training. The actual shared formula is Li6.6La3Zr1.6Nb0.4O12 (Nb0.4).
The prior code already embargoed all target-source pools on ANY formula match,
so its three quarantined attempts are unchanged. Historical reports stay intact;
the misleading test comment is corrected.

0195 records this executed comparative adaptive diagnostic, not another failed
DOI search or scientific GO. STRICT additions0, physical experiments0, new model
fits0, paid cost$0. P0-01/02/03 BLOCKED, production OFF, TEST121 untouched.
PR365 remains draft until all canonical checks and explicit merge authorization.
Next: freeze one evidence-gap action with independently verifiable success/failure
and real cost, then test whether allocation improves qualified evidence yield;
current condition-count coverage alone cannot establish that benefit.

Validation:105focused tests passed; local Fast CI2,112passed with8warnings.
Compilation, compact continuity (CURRENT3991bytes), and exact0171conditional
power checks passed. Full-source historical events/baseline bytes are unchanged.
