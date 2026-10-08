"""Optional, local-only MCP v2 stdio wrapper for verified Rhombus evidence."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Annotated, Any

from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from .evidence_query import MAX_RECORDS, ReadOnlyEvidenceTools


def create_mcp_server(evidence_jsonl: Path) -> MCPServer:
    """Bind a trusted host-selected JSONL snapshot; expose exactly one tool."""
    gateway = ReadOnlyEvidenceTools(Path(evidence_jsonl))
    server = MCPServer("Rhombus Evidence")

    @server.tool(
        name="get_candidate_evidence",
        title="Get candidate evidence",
        annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False),
    )
    def get_candidate_evidence(
        candidate_id: Annotated[
            str,
            Field(min_length=1, max_length=256, description="Exact candidate ID"),
        ],
        max_records: Annotated[
            int,
            Field(ge=1, le=MAX_RECORDS, description="Maximum returned records"),
        ] = 10,
    ) -> dict[str, Any]:
        """Read SHA256-verified evidence without authorizing any scientific claim.

        No computation, network access, or scientific PASS inference is offered.
        """
        return gateway.call_tool(
            "get_candidate_evidence",
            {"candidate_id": candidate_id, "max_records": max_records},
        )

    return server


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Start a read-only Rhombus MCP server over local stdio"
    )
    parser.add_argument(
        "--evidence-jsonl", required=True, type=Path,
        help="Trusted host-bound EvidenceRecord JSONL snapshot",
    )
    args = parser.parse_args(argv)
    if not args.evidence_jsonl.is_file():
        parser.error("trusted evidence snapshot does not exist")
    if args.evidence_jsonl.stat().st_size > 64 * 1024 * 1024:
        parser.error("trusted evidence snapshot exceeds the size budget")
    # Do not write a banner to stdout: it carries the MCP wire protocol.
    create_mcp_server(args.evidence_jsonl).run(transport="stdio")


if __name__ == "__main__":
    main()
