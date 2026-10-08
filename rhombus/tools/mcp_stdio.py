"""Fail-closed local MCP stdio adapter for Rhombus evidence queries.

A trusted host configures the EvidenceRecord JSONL snapshot path. Exposes
only get_candidate_evidence. Implements the 2026-07-28 stateless and
2025-11-25 legacy initialize tool-list/call subset, without extra deps.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, TextIO

from rhombus.tools.evidence_query import ReadOnlyEvidenceTools, list_tool_specs

MODERN = "2026-07-28"
LEGACY = "2025-11-25"
SERVER_INFO = {"name": "rhombus-evidence", "version": "0.1.0"}
MAX_REQUEST_BYTES = 1024 * 1024
VERSION_KEY = "io.modelcontextprotocol/protocolVersion"
SERVER_KEY = "io.modelcontextprotocol/serverInfo"


def rpc_error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id,
            "error": {"code": code, "message": message}}


def rpc_result(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


class EvidenceMcpServer:
    """In-process JSON-RPC handler, with a strict one-tool allowlist."""

    def __init__(self, evidence_jsonl: Path):
        self._gateway = ReadOnlyEvidenceTools(evidence_jsonl)
        self._legacy_initialized = False

    @staticmethod
    def modern_result(payload: dict[str, Any]) -> dict[str, Any]:
        return {"resultType": "complete", **payload, "_meta": {SERVER_KEY: SERVER_INFO}}

    @staticmethod
    def tools() -> list[dict[str, Any]]:
        return [
            {
                "name": spec["function"]["name"],
                "description": spec["function"]["description"],
                "inputSchema": spec["function"]["parameters"],
                "annotations": {
                    "readOnlyHint": True,
                    "destructiveHint": False,
                    "idempotentHint": True,
                    "openWorldHint": False,
                },
            }
            for spec in list_tool_specs()
        ]

    def handle(self, message: Any) -> dict[str, Any] | None:
        if not isinstance(message, dict):
            return rpc_error(None, -32600, "Invalid Request")
        request_id = message.get("id")
        if message.get("jsonrpc") != "2.0" or not isinstance(message.get("method"), str):
            return rpc_error(None, -32600, "Invalid Request")
        if "id" not in message:
            return None  # JSON-RPC notifications never receive responses
        if isinstance(request_id, bool) or not isinstance(request_id, (str, int)):
            return rpc_error(None, -32600, "Invalid Request")
        params = message.get("params", {})
        if not isinstance(params, dict):
            return rpc_error(request_id, -32602, "Invalid params")
        method = message["method"]

        if method == "initialize":
            if not isinstance(params.get("protocolVersion"), str):
                return rpc_error(request_id, -32602, "Missing protocolVersion")
            self._legacy_initialized = True
            return rpc_result(request_id, {
                "protocolVersion": LEGACY,
                "capabilities": {"tools": {}},
                "serverInfo": SERVER_INFO,
                "instructions": "Only read-only evidence lookup; no scientific claim authority.",
            })

        metadata = params.get("_meta", {})
        if not isinstance(metadata, dict):
            return rpc_error(request_id, -32602, "Invalid request metadata")
        version = metadata.get(VERSION_KEY)
        if version == MODERN:
            modern = True
        elif self._legacy_initialized and version in (None, LEGACY):
            modern = False
        else:
            return rpc_error(request_id, -32022, "Unsupported MCP protocol version")

        if method == "server/discover":
            if not modern:
                return rpc_error(request_id, -32601, "Method not found")
            return rpc_result(request_id, self.modern_result({
                "supportedVersions": [MODERN, LEGACY],
                "capabilities": {"tools": {}},
                "instructions": "Read-only hash-verified Rhombus evidence; no simulations.",
                "ttlMs": 300000, "cacheScope": "private",
            }))
        if method == "ping" and not modern:
            return rpc_result(request_id, {})
        if method == "tools/list":
            payload = {"tools": self.tools()}
            if modern:
                payload.update({"ttlMs": 300000, "cacheScope": "private"})
            return rpc_result(request_id, self.modern_result(payload) if modern else payload)
        if method == "tools/call":
            name = params.get("name")
            args = params.get("arguments", {})
            if name != "get_candidate_evidence":
                return rpc_error(request_id, -32602, "Tool not registered")
            if not isinstance(args, dict):
                return rpc_error(request_id, -32602, "Tool arguments must be an object")
            try:
                result = self._gateway.call_tool(name, args)
            except (ValueError, OSError, TypeError):
                # Do not leak trusted file paths or arbitrary raw input.
                result = {"error_code": "EVIDENCE_LOOKUP_FAILED_CLOSED",
                          "operational_status": "ERROR",
                          "scientific_verdict": "UNKNOWN",
                          "claim_authorized": False,
                          "limitations": ["NO_SCIENTIFIC_RESULT_RETURNED"]}
                is_error = True
            else:
                is_error = False
            payload = {
                "content": [{"type": "text", "text": json.dumps(result, sort_keys=True)}],
                "structuredContent": result,
                "isError": is_error,
            }
            return rpc_result(request_id, self.modern_result(payload) if modern else payload)
        return rpc_error(request_id, -32601, "Method not found")


def serve_stdio(server: EvidenceMcpServer, *,
                input_stream: TextIO, output_stream: TextIO) -> None:
    """Newline-delimited JSON-RPC. No non-protocol stdout or network listener."""
    while True:
        raw = input_stream.readline(MAX_REQUEST_BYTES + 1)
        if not raw:
            return
        if len(raw.encode("utf-8")) > MAX_REQUEST_BYTES or not raw.endswith("\n"):
            output_stream.write(json.dumps(rpc_error(None, -32600, "Request too large")) + "\n")
            output_stream.flush()
            return  # never parse the remainder of an oversized message
        try:
            message = json.loads(raw)
        except json.JSONDecodeError:
            reply = rpc_error(None, -32700, "Parse error")
        else:
            try:
                reply = server.handle(message)
            except Exception:
                reply = rpc_error(None, -32603, "Internal error")
        if reply is not None:
            output_stream.write(json.dumps(reply, ensure_ascii=False,
                                           separators=(",", ":")) + "\n")
            output_stream.flush()


def main() -> int:
    parser = argparse.ArgumentParser(description="Rhombus read-only MCP stdio server")
    parser.add_argument("--evidence-jsonl", type=Path, required=True,
                        help="Host-controlled EvidenceRecord JSONL snapshot")
    args = parser.parse_args()
    serve_stdio(EvidenceMcpServer(args.evidence_jsonl),
                input_stream=sys.stdin, output_stream=sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
