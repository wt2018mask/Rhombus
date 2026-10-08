# AI tool surface: read-only evidence lookup v1

The first AI-callable Rhombus v2 capability is `get_candidate_evidence`. It is
deliberately **read-only**, bounded, and useful before Phase 3 sAlex/Kaggle
production evidence is ready. This is a Python function-calling adapter, **not
yet an MCP/HTTP server**; model transports may wrap it later without modifying
scientific semantics.

A trusted application configures the location of an existing, exported
`rhombus-evidence-record-v1` JSONL snapshot; the AI never chooses the path.

```python
from pathlib import Path
from rhombus.tools import ReadOnlyEvidenceTools, list_tool_specs

model_function_specs = list_tool_specs()
tools = ReadOnlyEvidenceTools(Path("trusted-data/evidence-v1.jsonl"))
result = tools.call_tool("get_candidate_evidence", {
    "candidate_id": "exact-source-bound-candidate-id",
    "max_records": 10,
})
```

- Read-only; no network, new evidence publication, compute dispatch or fees.
- Exact content-addressed `evidence_id` is recomputed for every JSONL row;
  corrupted, duplicate, malformed or oversized snapshots fail **closed**.
- A result with `operational_status: SUCCEEDED` means **the lookup succeeded**.
  The top-level `scientific_verdict` remains `UNKNOWN`, `domain_status`
  remains `UNQUALIFIED`, and `claim_authorized` is always `false`.
  Individual record verdicts, provenance pointers, model identity, uncertainty
  and limitations remain separate. Missing records never mean `PASS`.
- Returned records are bounded (`max_records` 1..25), include stable IDs
  and are intentionally not an unbounded dump of scientific payloads. This
  first adapter accepts **at most 64 MiB** of JSONL input for safe, bounded
  read-only use; large archives need a separately qualified indexed store.
- Only the trusted host supplies `evidence_jsonl`. Tools offered to a
  model expose only `candidate_id` and `max_records`.
- Snapshot files must be created by an authorized evidence exporter; no
  canonical Phase 3 production archive is supplied or claimed by this change.

## Next independent AI milestones

1. Qualify an indexed Evidence Ledger backing store and `get_domain_assessment`
   for independently calibrated model-domain evidence.
2. Expose `list_candidate_evidence` or pagination only once row-level
   verification and bounded-read semantics are proven for large archives.
3. Add an explicit transport adapter (MCP or other tool-calling integration)
   with allowlisted tools and no default scientific execution permissions.
4. Promote simulation/claim tools only after matching evidence, protocol,
   resource-budget and authorization contracts are qualified.

The Kaggle CPU sAlex/WBM run and MPTrj training-exposure blockers continue
independently. See `data/development/CURRENT.json` for the live frontier.


### Expanded read-only preflights (checkpoint 0045)

The original `get_candidate_evidence` integrity and scientific semantics remain unchanged. The new `get_domain_assessment` and `validate_candidate_structure` are separately bounded, explicitly non-authoritative preflights; see `docs/AI_TOOLS_ANALYSIS_V1.md`. No Kaggle, remote user execution, or unseen-generalization claims are exposed.
