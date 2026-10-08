# Rhombus AI Tool — local MCP stdio bridge

The official MCP Python SDK **v2** exposes the existing read-only
`get_candidate_evidence` as an MCP tool that desktop apps and coding
agents can discover and call. This adapter starts a **local stdio server**;
it does not listen on a network port, execute simulations, or authorize claims.

## Windows PowerShell install and launch

From the Rhombus repository root, using Python 3.11:

```powershell
py -3.11 -m pip install -e ".[ai-mcp]"
py -3.11 -m rhombus.tools.mcp_server --evidence-jsonl "C:\\trusted-data\\evidence-v1.jsonl"
```

The host must supply a real, trusted `rhombus-evidence-record-v1` JSONL export.
This repository **does not ship** a full sAlex production index or an
automatic export. Missing input blocks startup rather than fabricating data.

To configure a local MCP-capable desktop host, provide this stdio command:

```json
{
  "mcpServers": {
    "rhombus-evidence": {
      "command": "python",
      "args": [
        "-m",
        "rhombus.tools.mcp_server",
        "--evidence-jsonl",
        "C:/trusted-data/evidence-v1.jsonl"
      ]
    }
  }
}
```

Choose a Python interpreter with the optional `ai-mcp` extra installed.
The model controls only `candidate_id` and `max_records` (1–25).
The path is bound by a trusted local host. The gateway verifies every
record's content SHA256 and rejects missing, damaged or oversized inputs.
Individual evidence verdicts remain distinct; the tool response is
always `scientific_verdict=UNKNOWN`, `domain_status=UNQUALIFIED`,
`claim_authorized=false` until separate scientific qualification.

Run the in-memory integration tests with the official MCP v2 SDK:

```powershell
py -3.11 -m pytest -q tests/test_r2_ai_mcp_stdio.py
```

No change to Kaggle runs, frozen science, or public networking.
This does not install a ChatGPT plugin or deploy a hosted MCP endpoint.


## Optional structure/domain preflights

Host opt-in adds get_domain_assessment and validate_candidate_structure without changing the default single-tool catalog. See docs/AI_TOOLS_PREFLIGHT_V1.md for the exact frozen snapshot and safety caveats.
