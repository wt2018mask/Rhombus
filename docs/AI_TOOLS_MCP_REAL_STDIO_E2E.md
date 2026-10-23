# Real MCP stdio verification on historical O_ONLY evidence

Engineering base: PR #365, `e3547d9968ce44a39b1d084f5440082d9e982d66`.
Initial workspace/source-work branch was PR #367 at
`df7506c67643b9a9dc8abd9b0c3b3fffbec95ad3`; it remains separate and unchanged.
This branch, `worker/ai-mcp-real-stdio-e2e`, implements Issue #368's local
engineering acceptance criterion. It does not consume checkpoint 0196.

## Reproduced defects and scoped correction

A real SDK client launched `python -m rhombus.tools.mcp_server` as a subprocess,
initialized protocol `2025-11-25`, discovered six tools, and queried a genuine
0195 EvidenceRecord. Before correction, `max_records=true`, `max_records="1"`
and an unknown `command` argument all returned successful tool results. The SDK
coerced values or ignored extra keys before the existing strict Python adapters
could inspect them. No command execution is asserted. The initial stdout
observations are retained; the initial raw RPC result was not retained before a
follow-up probe overwrote its temporary file. No before/after latency claim is made.

The existing MCPServer and six tools remain. A small boundary adapter validates
raw finite JSON against the already existing canonical tool schemas before SDK
conversion, and publishes those same schemas during discovery. The schemas now
expose the real nested structure fields, enums, ranges, manifest/status ID
patterns, and `additionalProperties=false`. Errors identify the tool/schema
location without echoing malicious values or filesystem paths. Input and
serialized result budgets are 128 KiB each; oversized results fail explicitly.
Underlying evidence, domain, structure, proposal and status semantics are unchanged.

Two existing client tests also failed before exercising the tool because several
tool names had accidentally become positional arguments to one `call_tool`.
Both positive and negative calls were corrected without weakening assertions.
Malformed concatenated workflow path filters were split, and all six tools'
contract suites plus the real subprocess test now run in the MCP workflow.

## Actual client, inputs, lifecycle and performance

Runtime: Python 3.11.17; official `mcp==2.3.0`, `ClientSession` and
`mcp.client.stdio.stdio_client`. This is stdio JSON-RPC across a real process,
not an in-memory server wrapped as E2E. Initialize, initialized notification,
list/discover, call, errors, and context-managed process/session close completed.

The host exported three **unchanged historical** 0195 EvidenceRecords after
verifying their content IDs, source-binding hashes and receipt-file SHA-256.
Historical artifact hash:
`5605d2f604fc2a44c0409d0f8b1dd4bdff7ad1f600f439fddd7c7ccdcc10e73c`.
No fresh original-source authentication or new measurement is claimed.

Successful structure validation used the retained CC0 gamma-LiAlO2 COD 1008166
reference (16 sites), with bytes checked against its existing receipt:
`94aa55ef4b1a2aeb94c5c07ddd7cdc18201ac752546a283c8543cb8faa05f589`.
It is a separate reference candidate, not a specimen or phase mapping for any
source-paper replay candidate. No occupancy rounding or oversized-LLZO truncation
was used to create a smaller structure. No TEST121 data were inspected.

| Tool | Verified behavior |
| --- | --- |
| `get_candidate_evidence` | Exact retained evidence ID; missing candidate returns no evidence and no claim authorization |
| `get_domain_assessment` | Element coverage remains UNQUALIFIED, never calibrated model applicability |
| `validate_candidate_structure` | Valid retained representation, scientific UNKNOWN; no stability or novelty claim |
| `build_evidence_manifest` | Deterministic ID and exact historical evidence linkage |
| `plan_scientific_task` | PROPOSED_ONLY, NOT_SUBMITTED, manifest unverified, execution unauthorized even for forged well-formed IDs |
| `get_task_status` | Host snapshot only; no invented execution receipt, missing proposal UNKNOWN, no live backend polling |

The retained session contains **38 calls: 15 valid and 23 expected errors**.
Each tool has a successful call, exact deterministic repeat, missing input,
wrong type and forbidden-extra argument case. Additional cases cover numeric
coercion, unknown execution tools, excessive input, forged manifests, and
hash-corrupted evidence followed by host restoration. Synthetic hash-valid
oversized metadata is used only in a negative output-budget test.

Measured retained-session invocation range: **0.002468–1.420891 seconds**.
Maximum SDK-normalized response: **3,593 UTF-8 bytes**. These sizes include text
and structured content but exclude JSON-RPC framing; they are not packet captures.
Request argument sizes, catalog size, individual responses and latencies are in
`data/development/mcp_stdio_e2e_20261023_v1.json`. Bytes/4 token counts are explicitly
heuristic, not tokenizer measurements. One sequential local session, import/cold
costs and warm repeats do not establish latency or token savings.

Seven fixed research requests are mapped manually to invocation cases. No model
chooses tools or arguments in this experiment. Agent selection accuracy is UNKNOWN.

Codex CLI **0.163.0** was available and additionally tested via its real app-server
JSON-RPC interface with ephemeral Rhombus MCP configuration. It exited **1** with
`Read-only file system (os error 30)` before initialization. No model turn or paid
API request was started. Codex invocation compatibility remains **NOT VERIFIED**;
OpenCode is not installed. SDK verification is independently successful.

## Authorization and hostile inputs

The real child process is instrumented with a Python audit hook denying outbound
socket connections/DNS, child process dispatch, filesystem path writes and
filesystem mutations. Existing stdio descriptors and `/dev/null` remain usable.
An initial overly broad hook blocked SDK stdout `fdopen`; the corrected harness
permits transport descriptors and then completes all calls. This is test
instrumentation, not an OS sandbox or security certification. The parent host
alone creates the bounded snapshots and deliberately corrupts/restores one
negative fixture. No tool supplies file paths, commands, provider credentials,
trusted approvals or writable snapshots. The planner's requested resource budget
is not reserved compute. A source-level DOI proposal does not establish a
crystal/specimen binding or an executable physical input.

## Independent scientific-access assessment

Active runtime observations were current, but custom allowed hosts were empty and
network policy state was `unknown`. Saved draft revision 9 contains
`iris.unimore.it`, `www.ebi.ac.uk`, and `mdpi-res.com`; none is in the observed
effective runtime host list. Publication globally is not independently attested;
the new source policy is **not applied to this runtime**. No configuration was
changed in this workstream, and no denied publisher request was repeated.

This execution made **zero original-source requests**, acquired **zero original
bytes**, and resolved **zero new scientific questions**. Acquisition/processing
costs for the unexecuted source action remain UNKNOWN, not zero-duration success.
The four earlier requests and 18.889096 seconds remain bound to #367's exact
commit/artifacts; they are not reclassified as current work. Its inherited 0169
and 0170 original-source Actions failures were inspected: both ended in timeout/
URLError, not scientific FAIL. Its Fast CI and continuity failures came from
missing per-PR checkpoint state. No bulk workflow rerun was requested.

Next scientific action remains the frozen 2021 DOI `10.3390/ma14226809`
supplementary Table S1 geometry question for SSR/SASSR/CP/SD. Review/publish the
saved environment network configuration, verify active source access, then
acquire and authenticate complete original SI bytes before adjudicating dimensions
and units. Publishing does not guarantee publisher availability. Do not infer
specimen identities, independent replicates or uncertainty meanings.

New STRICT DOI groups: **0**; original manufacturing comparisons: **0**;
new EXPLORATORY comparisons: **0**. Scientific acquisition INCONCLUSIVE/BLOCKED.
P0-01/02/03 BLOCKED; GO false; production OFF; $0; O_ONLY focus unchanged.

## Reproduction, validation and integration boundary

From the repository root, using the supported Python with the optional `ai-mcp`
extra installed (the complete science environment already supplies ASE):

```sh
python -m scripts.tools.verify_mcp_stdio --output /tmp/new-mcp-stdio-observation.json
python -m pytest -q tests/test_r2_ai_mcp_process.py
```

The verifier refuses to overwrite a prior output file. It records implementation
hashes so its observations remain bound to exact code bytes. The MCP workflow
retains the same report as an Actions artifact.

Local focused tool/security/provenance plus adaptive-replay regression: **81
passed**. Local bounded Fast CI tier: **2112 passed, 8 existing warnings**;
compile/import, compact continuity and unchanged paired-power assertions passed.
These checks do not establish scientific model quality or new-PR merge readiness.

No checkpoint, CURRENT, handoff or historical scientific artifact was modified.
The separate MCP draft PR must retain the mandatory per-PR continuity failure
until a legitimate integration sequence supplies an authorized substantive science
checkpoint. Do not manufacture 0196, duplicate 0195, disable checks, force-push, or
merge into main to make standalone engineering appear integrated.
