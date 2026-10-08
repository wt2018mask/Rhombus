# Rhombus local MCP stdio adapter — v1

This adapter makes the existing hash-verified, read-only
`get_candidate_evidence` function available to MCP-compatible local AI hosts.
It is **not** a remote HTTP service, a publicly hosted ChatGPT integration,
or an autonomous compute agent.

## Local setup

The host must first supply a legitimate, exported
`rhombus-evidence-record-v1` JSONL snapshot. No full Phase 3 Kaggle production
snapshot or live remote evidence feed is included in this change.

With Python 3.11+ and Rhombus available on your Python path (for example,
`python -m pip install --no-deps -e .` inside the repository), configure your
MCP-capable local host to launch:

```text
command: python
args: -m rhombus.tools.mcp_stdio --evidence-jsonl /trusted/absolute/path/evidence.jsonl
transport: stdio
```

Example on Windows (replace the Python executable and path as needed):

```json
{
  "mcpServers": {
    "rhombus-evidence": {
      "command": "python",
      "args": [
        "-m", "rhombus.tools.mcp_stdio",
        "--evidence-jsonl", "C:\\Rhombus\\trusted\\evidence.jsonl"
      ]
    }
  }
}
```

The model is allowed to supply only `candidate_id` and `max_records` for
`get_candidate_evidence`. The evidence path is specified by the **trusted
host**, not by the model, and snapshot integrity is verified before any result
is returned.

## Supported protocol subset

- MCP **2026-07-28**: stateless stdio `server/discover`, `tools/list`
  and `tools/call` with per-request protocol version metadata.
- MCP **2025-11-25**: legacy `initialize` and
  `notifications/initialized` handshake, `ping`,
  `tools/list` and `tools/call`.
- JSON-RPC messages use newline-delimited stdin/stdout. Protocol stdout
  contains only JSON; user-visible diagnostics are tool result objects.
- Requests are limited to 1 MiB. No HTTP port, daemon, background worker,
  paid API, or extra runtime dependency is introduced.
- Advertises only one tool with read-only annotations. No
  `relax_structure`, shell execution, unqualified claim resolution or
  automatic Kaggle dispatch is exposed.
- Successful lookup **does not mean the science passed**:
  `operational_status: SUCCEEDED` is the tool lookup status; the aggregate
  `scientific_verdict` is always `UNKNOWN`, and
  `claim_authorized` remains `false`.
- Corrupt/missing evidence returns `isError: true`, an operational
  `ERROR` and scientific `UNKNOWN`, without exposing raw paths.

## Limitations

This is a minimal local stdio compatibility adapter, not a general-purpose
MCP framework. It does not provide HTTP transport, resources, prompts,
sampling, elicitation, task scheduling or indexing large evidence datasets.
No claim of interoperability with every host is made until external client
integration tests are performed.

The upstream 2026 revision introduced `server/discover` and per-request
metadata in place of the 2025 `initialize` handshake. Both entry paths are
explicitly covered by repository unit and subprocess tests.

Authoritative state: `data/development/CURRENT.json`.
