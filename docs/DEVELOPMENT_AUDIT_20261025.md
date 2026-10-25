# Repository and integration audit — 2026-10-25

Observed canonical main: `1aaaa555a9a1ce2c9123845402fec4e664626708` (0192).
Recovered CURRENT first, passed continuity, resolved inherited a196/a197 and
read AGENTS, HANDOFF, README, naming, milestones and red-team contracts. Live
Issues #349/#368 were read through GitHub public HTML. Their roadmap is not an
execution receipt. The owner's newer scope revision supersedes permanent
O_ONLY-only future scope while preserving scientific qualification boundaries.

## Verified stack

| PR | Exact HEAD | Base PR | Checkpoint | Files changed from base | Commits | Public Checks success/failure |
| --- | --- | --- | ---: | ---: | ---: | --- |
| #363 | 3c2f42f6f5c3c88acfb55fcd6cdf7acab8b76802 | main | 193 | 8 | 5 | 56 / 0 |
| #364 | 03c1bd5b1ba37284d73577c8fd58e4382b0d4251 | #363 | 194 | 21 | 35 | 57 / 0 |
| #365 | e3547d9968ce44a39b1d084f5440082d9e982d66 | #364 | 195 | 59 | 22 | 56 / 2 |
| #367 | afbe238287b6321190af2e263f5afdf100c3ca0c | #365 | 196 | 16 | 3 | 49 / 3 |
| #369 | 87446af01baefa4b1dc5e4f592012dca591ef795 | #367 | 197 | 15 | 3 | 50 / 2 |

Every listed base is an actual Git ancestor of HEAD. Each diff adds exactly one
checkpoint event; none edits/removes a prior event or changes the immutable
0118 baseline. Public PR pages still show all five as Draft with the listed
target branches. Worker integration is not canonical main integration.

Scope review: #363 is the nonmonotonic admission gate. #364 includes source
authentication/recovery changes. #365 is a substantially larger literature and
source-audit/replay change, not merely a tiny adaptive allocation patch; review
those 59 files before integration. #367 adds the sensitivity falsification;
#369 adds real MCP protocol/computed-evidence integration and contains the normal
merge of #367. Distinct events remain owned by their original PRs.

Counts above are workflow entries on each exact-head Checks page, classified by
their rendered job-result labels. These are observations of those historical
heads, not results for this new local branch. No new Actions run was triggered.

## Failures and limits of diagnosis

#369 live original-source jobs fail:

- 0169 run [39940431382](https://github.com/wt2018mask/Rhombus/actions/runs/39940431382),
  job 120370228509: `Fetch two independent real primary sources and evaluate
  directional transfers`, exit 1.
- 0170 run [39940431932](https://github.com/wt2018mask/Rhombus/actions/runs/39940431932),
  job 120370230412: `Execute ACTUAL original university primary paper`, exit 1.

The public job pages say **Sign in to view logs**. GitHub API/GraphQL requests
are blocked by the environment proxy. The owner's earlier timeout diagnosis is
consistent with the failed acquisition stages, but full tracebacks and precise
remote causes were NOT independently verified. Do not claim a reproduced
scientific numerical failure or a confirmed timeout root cause.

#365 has the same 0169/0170 workflow failures (39927006343/39927006584).
#367 additionally fails 0175 full binary acquisition (39939590628), along with
0169/0170 (39939590510/39939590711). Its detailed cause also remains unverified.
All corresponding exact-head Fast CI, Wave 2 and continuity entries shown in
the #369 public Checks page succeeded. This does not erase live-source failures.

0169 uses pinned TU Delft accepted manuscript C9TA02126D plus original
PMC9064144 JATS; 0170 uses the TU Delft C7TA05031C institutional PDF. Reviewed
fetch code bounds size, validates final source URL/content/DOI/units and refuses
scientific promotion. These destination hosts are absent from current runtime
policy. No denied source endpoint was repeatedly queried or substituted with a
fixture. No new source acquisition is claimed.

The additive CI change exposes deterministic 0168/0169/0170 fixture/numerical
regressions as independent offline jobs. Original live job IDs, entire job
definitions, triggers, admission assertions and nonzero failure behavior are
unchanged (verified by parsed YAML comparison with the parent). Existing live
tests intentionally remain, so those checks still require both regression and
real source acquisition. This distinguishes the results; it does not repair
external availability, waive a required check or create authenticated evidence.
Branch protection settings remain unverified; no protection setting was changed.

## Development and AI capability

The new versioned research-context adapter and synthetic second-family tests
demonstrate represent/query/manifest/propose/reject with six existing MCP tools.
O_ONLY model claims are not transferred. A declaration match still abstains.
Local validation passed: 22 new pure contract tests plus one real SDK subprocess
context test; the existing full Fast CI selection passed 2,145 tests (8 warnings).
The new pure contract tests are now included in Fast CI; the context subprocess
test is registered in the existing optional MCP CI workflow.

Actual SDK subprocess verification of retained historical evidence: 38 calls,
15 successful calls and 23 expected rejection calls; 0197 integration: four
successful computed-evidence/manifest calls, six-tool discovery, closed session.
These are SDK-level process tests, not autonomous AI-selection measurements.

Codex CLI 0.163.0 reports an existing ChatGPT login. A bounded read-only MCP
research-client attempt initially could not initialize its runtime directory;
after approved sandbox escalation it started, but the model connection to
chatgpt.com failed with proxy HTTP CONNECT 403. The session was stopped without
a model response. Tool-selection accuracy, false-claim rate and real model
token/latency metrics remain UNVERIFIED; no bytes/4 token proxy is reported.

Required egress additions were saved in the environment draft: api.github.com,
pure.tudelft.nl, repository.tudelft.nl, www.ebi.ac.uk,
eutils.ncbi.nlm.nih.gov and chatgpt.com. Saving is not runtime application or
publication. Existing package-manager presets and setup instructions were
preserved. No secret value was requested or copied.

## Safe integration path

Do not merge. Review bottom-up #363 → #364 → #365 → #367 → #369, rechecking
each current HEAD, continuity against its actual base, canonical Wave 2 and the
applicable science workflows before each separately authorized canonical merge.
Recheck later PR bases after bottom-up integration. Authenticate unavailable
sources or record a separately approved claim-specific blocked outcome; an
offline regression pass cannot clear a live evidence requirement.

## Subsequent execution and integration update

Authenticated `gh` API operations subsequently succeeded: Draft #371 contains the
executed numerical fallback, its real 0198 event, compact CURRENT and generated
HANDOFF. Draft #370 is now based on #371, with a normal worker merge and one
distinct executed ENGINEERING event 0199 for actual multi-family SDK validation.
This follows the 0197 engineering-event precedent; it does not invent a science
verdict or attach artificial scientific evidence to a policy change. Both remain
Draft, with separate code/results and no main merge. The revised bottom-up tail
is #369 → #371 → #370. Independent source-qualified process-design science remains
the next frontier (0200); the fallback is exposed, one-source retrospective work.

The initial network/API observations above are historical, not universal CLI
capability claims. Current API evidence confirms 54 job check-runs at #369 HEAD:
52 succeeded and 2 failed. The table above counts 52 workflow entries (50/2).
The log-download redirect hostname remains proxy-blocked; branch-protection API
returns `Resource not accessible by integration` (403), so neither detailed
timeout tracebacks nor protection configuration were independently recovered.
The exact additional log hostname was saved to the network draft; saving still
does not establish runtime application/publication. Codex model selection remains
UNVERIFIED after the actual model connection returned proxy 403.

#370's initial head had Fast CI fail at `Validate compact continuity` and
Development Continuity fail at `Enforce per-PR checkpoint update`, confirming
the disclosed registration boundary rather than a unit-test regression. The new
real engineering event resolves that boundary without weakening either gate.
#371 head 072d0cc passes remote Fast CI, continuity and the new frozen offline
utility workflow; 0169/0170 acquisition checks still fail. Do not call the stack
fully green or merge it without required checks and separate owner authorization.
