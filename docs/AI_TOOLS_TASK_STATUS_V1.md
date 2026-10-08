# Read-only task execution status snapshot tool v1

`get_task_status` reads an **optional trusted host-selected** JSONL snapshot
of scientific task status receipts. It makes no provider API call and does
not query live Kaggle/CPU runners. The AI caller supplies only a
`task-proposal:sha256:<64-hex>` ID.

Host-side MCP configuration:

    python -m rhombus.tools.mcp_server --evidence-jsonl /trusted/evidence.jsonl --task-status-jsonl /trusted/task-status.jsonl

Without the trusted task status file, tool calls fail closed. The AI cannot
supply a path, token, status, provider run ID, approval or cancellation
argument. It cannot start, cancel, or update a job.

The host snapshot is a bounded, single-current-status-per-proposal JSONL
record stream (up to 8 MiB/10,000 rows/16 KiB each). Each row has exactly:

- `schema_version: rhombus-ai-task-status-snapshot-v1`
- `proposal_id`
- `task_state`: PROPOSED, PENDING_APPROVAL, AUTHORIZED, QUEUED, RUNNING,
  SUCCEEDED, ERROR, or CANCELLED
- `backend_identity`: LOCAL_CPU or KAGGLE_CPU
- `observed_at_utc`: strict UTC timestamp (YYYY-MM-DDTHH:MM:SSZ)
- `provider_run_id`: optional bounded provider-defined identifier
- `record_id`: `task-status:sha256:` plus SHA256 of the remaining canonical
  JSON fields (`sort_keys=True, separators=(',', ':'), ensure_ascii=False`)

All entries are independently content-hash verified, including those for
unrelated IDs. Duplicate proposal IDs, corrupted rows, invalid timestamps,
unsupported values and oversized sources fail closed. This is an **integrity
check**, not proof that a provider signed/attested the status. A malicious
creator of the trusted file can also recompute hashes.

Tool outputs include the latest recorded task state, timestamp, snapshot
SHA256 and `status_freshness=HOST_SNAPSHOT_ONLY_NOT_LIVE`. A missing ID
returns `task_state=UNKNOWN`, not a fabricated success. Even if a task
state says SUCCEEDED, the scientific verdict remains UNKNOWN and
`claim_authorized=false`.

**Not yet implemented:** producer of real provider-signed status snapshots,
authenticated human approval, token-isolated dispatch/cancel gateway,
live polling, and completed scientific evidence qualification. The tool is
an interface for future trusted-host orchestration, not live job tracking.

Focused tests:

    python -m pytest -q tests/test_r2_ai_task_status.py tests/test_r2_ai_task_status_mcp.py

Stack order: security #202 (0044), AI preflight #206 (0045),
evidence manifest #208 (0046), task proposal #209 (0047),
this read-only status adapter (0048).
