# Read-only evidence manifest tool v1

`build_evidence_manifest` extends the opt-in/local-stdio Rhombus AI
gateway with deterministic, bounded evidence ID indexing.

## Input

The trusted host selects the exact EvidenceRecord JSONL snapshot when
starting the MCP process; the AI caller supplies only `candidate_id`
and optional `max_evidence_ids` (1..25; default 10). Paths, external
URLs, provider credentials, shell commands and compute jobs are not valid.

## Output

- `manifest_id`: SHA256 of canonical JSON containing the candidate ID,
  entire trusted snapshot SHA256, and *all* candidate evidence IDs sorted;
- `snapshot_sha256`: SHA256 of every raw byte in the host-bound snapshot;
- `evidence_ids`: the first at most 25 IDs in deterministic order;
- `evidence_count`, `returned_count` and `truncated`: prevent consumers
  from misinterpreting a bounded partial list as complete;
- `operational_status=SUCCEEDED`, `scientific_verdict=UNKNOWN`,
  `domain_status=UNQUALIFIED`, `claim_authorized=false`.

The gateway verifies every underlying EvidenceRecord content hash, including
nonmatching candidates; rejects duplicate IDs, missing or corrupt lines, and
oversized source/records; and never modifies source bytes.

**Important:** deterministic evidence manifests are NOT scientifically
qualified, proof of provenance independence, a PASS verdict, or a statement
that the model did not train on the candidate. A truncated visible ID list
MUST NOT be interpreted as a complete claim source. The hash binds the
manifest to the snapshot bytes, not a signed external provenance authority.

No Kaggle polling, paid API, remote server, credential forwarding or
automatic experiment dispatch is added.

Focused tests:

    python -m pytest -q tests/test_r2_ai_manifest.py tests/test_r2_ai_manifest_mcp.py

Integration sequence: security PR #202 (checkpoint 0044) ->
AI preflight PR #206 (0045) -> this manifest PR (0046).
