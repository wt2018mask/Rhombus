# Evidence-gap acquisition attempt — checkpoint 0196 remains unconsumed

This is a blocked acquisition experiment, not a completed scientific checkpoint.
Starting GitHub head: `e3547d9968ce44a39b1d084f5440082d9e982d66` (#365).
Branch `worker/p3-0196-evidence-gap-utility` stacks on #365; main and checkpoint
0195 records remain unchanged. No merge or production authorization is requested.

## Pre-answer protocol and actual feedback

The four 0195 source pools were recovered. The bounded initial menu targets
DOI `10.1002/cssc.202300399`: direct rather than derived 25°C measurements,
complete formulas for all six series, defined conductivity uncertainty, and
physical EIS specimen relationships for all 18 Table 2 conditions. Each task
requires original-source bindings; retained table values and target temperatures
are already known. Public labels cannot support prospective blindness.

Exact protocol bytes were frozen before source requests. Frozen SHA-256 values:

- Initial: `ed56334148103c5e1729f469cfa983a16933519c27fa10a1d0acb20ceefad2d3`.
- Successor: `98948d74ecb4ee04828e61a49a471415c054bb147f30d3589934c8c8c5924886`.
- Publisher-route amendment: `fbdaa901adc299860d3a8ed157ec8362c088d78c67ebb7d3c38ef30408c6373d`.

The successor was frozen after observed source unavailability and before any SI
answers. It targets DOI `10.3390/ma14226809`, PMC8620275: defined uncertainty,
Table S1 pellet diameter/thickness, fitted bulk/grain-boundary resistances, and
EIS specimen/replicate relationships for SSR/SASSR/CP/SD. Partial mappings do not
resolve the full questions. Parent JATS SHA-256 remains
`0da4f7639daec04bf41c0a96e952a7ec8846eb5034ae531f60694e415d6350c3`.
The public publisher route amendment changes only the endpoint/request budget,
not task definitions, weights, selection rules, or success criteria.

| Policy | Initial selection | Successor selection |
| --- | --- | --- |
| Static | Direct 25°C | Uncertainty |
| Cheapest estimate | Uncertainty | Uncertainty |
| Fixed seeded order | Specimens | Geometry |
| Adaptive provisional value/cost | Complete formulas | Geometry |

Every policy starts from the same state within its episode. Weights are
provisional; processing costs are estimates. Source estimates are common to all
policies. The adaptive choice changes because the source failed, not because
scientific answers became visible. Full proposed orders are retained in JSON.

## Actual operations and costs

| Request | Actual result | Retained body bytes | Acquisition seconds |
| --- | --- | ---: | ---: |
| Fixed authenticated Unimore VOR URL | HTTP 403; unavailable | 0 | 1.904800 |
| Europe PMC exact-DOI metadata | HTTP 200; no PMC/OA text identified | 7340 metadata only | 1.469600 |
| Europe PMC supplementaryFiles archive | TimeoutError | 0 | 15.493354 |
| Public mdpi-res.com parent-linked SI filename | URLError; underlying reason not retained | 0 | 0.021342 |

Total: four distinct requests, zero identical-URL retries, 18.889096 measured
acquisition seconds, zero retained authenticated original-scientific bytes,
$0 monetary cost. Header/TLS bytes and CPU time were not measured. The PDF
receipt's `started_utc` was recorded after the operation; it is not reliable as a
request-start timestamp. Raw receipts and exact metadata response bytes are
retained in `data/development/evidence_gap_attempt_0196_v1.json`.
No original publisher documents are redistributed.

All four policies have zero observed resolved questions and zero new verified
fields. This is a tie on observed resolution, with **no evidence of adaptive
superiority**. Shared retrieval cost is counted once globally, with a common
cost basis in each policy comparison. Adjudications were not executed; their
answers, processing times, full action runtimes and the frozen full-cost yield
metric remain UNKNOWN. A separately labeled source-cost-only diagnostic is zero.
This is not four independent downloads or a demonstrated deployment cost saving.

Six unique typed EvidenceRecords retain source-acquisition errors, scientific
UNKNOWN, unqualified applicability, and eight policy references. Duplicate
policy selections reuse the same evidence IDs. No failure is scientific FAIL;
HTTP metadata success is not qualification or a negative scientific finding.
All eight questions remain UNKNOWN. STRICT DOI groups added: **0**. STRICT
manufacturing comparisons added: **0**. New exploratory comparisons: **0**.
Scientific outcome: **INCONCLUSIVE**. No applicability or scientific claim changed.

## Controls and retained provenance

`rhombus/tools/evidence_gap.py` reuses EvidenceRecord, SourceBinding, TaskSpec,
planning, and the existing no-redirect adapter. Network execution requires
explicit authorization, exact HTTPS URL/source allowlisting, inherited proxy/CA,
source-specific byte caps, and caller-enforced hard timeouts. Partial/oversized
files are removed, SHA-256 is recorded, and received bytes remain unverified
until original source identity/integrity is authenticated. Generic 8 MB intake
limits are unchanged; the frozen EBI supplementary archive allowance is 24 MB.
The original one-off acquisition helpers produced the retained receipts; unit
tests of the reusable module are not new live evidence acquisitions.

Prior hot-press original PDF SHA-256 is unchanged:
`871e6ff252cce27799e8e2bf5455667bdaf6dc639dde2875ad57a4ecce5fc58b`.
Prior authenticated receipt SHA-256:
`4cce0d4b9329e369d61db5116687c7297316fbda77be63fb96f1cbac6de18b75`.
Process feature audit SHA-256:
`8af20fd82153bf67db318d9e091610f7979d76df6689ae0de4a33ba1331d34c2`.
No old source receipts, baseline snapshots, checkpoint events or TEST121 labels
were modified. Existence and dynamic states remain UNKNOWN; transport evidence
is unchanged. O_ONLY, P0 BLOCKED, GO false, and production OFF remain in force.

Focused tests cover unauthorized I/O, URL/final-host identity, redirects,
oversized/truncated/empty bytes, raw-hash drift, frozen protocol drift, HTTP/
timeout/TLS failures, unknown/NaN costs, duplicate information/tasks, deterministic
selection, shared costs, missing answers and reproduction of the retained report.
Synthetic fixtures only test software contracts, not scientific acceptance.

## Access blocker and next experiment

Observed active custom allowed hosts were empty; network readiness was UNKNOWN.
The existing configuration draft already contained `iris.unimore.it` and
`www.ebi.ac.uk`; only `mdpi-res.com` was added. The saved draft requires user
review/publication and has **not** changed the active runtime. Publishing may
resolve environment policy restrictions; it does not guarantee publisher access
or eliminate EBI transfer timeouts. No proxy bypass, publisher-control bypass,
challenge execution, TLS weakening, or repeated denied request was attempted.
The publisher URLError cannot support a more precise diagnosis without retained
network evidence.

Smallest next configuration action: review and publish the saved environment
network draft containing those three source hosts, then verify runtime policy.
If access is restored, the highest-value next scientific experiment is the
already frozen Table S1 geometry action: authenticate the original 2021 SI,
verify article/file identity and archive integrity, and bind route-specific
pellet dimensions and units to SSR/SASSR/CP/SD. Do not infer independent specimens
or resolve uncertainty from parenthetical notation. This next experiment is
**NOT_EXECUTED**, and no automatic retry is authorized by a failed request.

Checkpoint 0196 acceptance is not met: no original evidence-gap answer was
acquired or adjudicated. CURRENT and the generated handoff remain at 0195.
A draft PR with these truthful blocked findings must not merge until substantive
0196 evidence and its required continuity event are supplied. CI success cannot
substitute for that scientific requirement.

## Local validation of this attempt

Focused acquisition/replay/supplement regression: 88 passed before the retained
report reproduction test was added; final acquisition suite: 21 passed.
Bounded Fast CI tier including that final test: 2133 passed, 8 existing warnings;
compile/import checks, development continuity and unchanged paired-power
planning assertions passed. These are local validation results, not a claim that
new-PR integration checks or original-source downloads passed.
