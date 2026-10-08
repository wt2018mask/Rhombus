"""Optional, local-only MCP v2 stdio wrapper for verified Rhombus evidence."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Annotated, Any

from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from .evidence_query import MAX_RECORDS, ReadOnlyEvidenceTools
from .preflight import ReadOnlyPreflightTools


def create_mcp_server(
    evidence_jsonl: Path,
    *,
    enable_preflight_tools: bool = False,
    model_domain_snapshot: Path | None = None,
    model_domain_snapshot_sha256: str | None = None,
) -> MCPServer:
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

    if enable_preflight_tools:
        if model_domain_snapshot is None or model_domain_snapshot_sha256 is None:
            raise ValueError("preflight tools require a host-pinned model-domain snapshot and SHA256")
        preflight = ReadOnlyPreflightTools(
            model_domain_snapshot=model_domain_snapshot,
            model_domain_snapshot_sha256=model_domain_snapshot_sha256,
        )

        @server.tool(
            name="get_domain_assessment",
            title="Get conservative model element-domain assessment",
            annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False),
        )
        def get_domain_assessment(
            candidate_id: Annotated[str, Field(min_length=1, max_length=256)],
            atomic_numbers: Annotated[list[int], Field(min_length=1, max_length=256)],
            claim_kind: Annotated[str, Field(min_length=1, max_length=256)],
        ) -> dict[str, Any]:
            """Preflight model element support, not an IN_DOMAIN or scientific PASS claim."""
            return preflight.call_tool("get_domain_assessment", {
                "candidate_id": candidate_id, "atomic_numbers": atomic_numbers,
                "claim_kind": claim_kind,
            })

        @server.tool(
            name="validate_candidate_structure",
            title="Validate periodic structure representation",
            annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False),
        )
        def validate_candidate_structure(
            candidate_id: Annotated[str, Field(min_length=1, max_length=256)],
            atomic_numbers: Annotated[list[int], Field(min_length=1, max_length=256)],
            cell_lengths_angstrom: Annotated[list[float], Field(min_length=3, max_length=3)],
            cell_angles_degrees: Annotated[list[float], Field(min_length=3, max_length=3)],
            fractional_coordinates: Annotated[list[list[float]], Field(min_length=1, max_length=256)],
        ) -> dict[str, Any]:
            """Check periodic representation only; do not infer physical viability."""
            return preflight.call_tool("validate_candidate_structure", {
                "candidate_id": candidate_id, "atomic_numbers": atomic_numbers,
                "cell_lengths_angstrom": cell_lengths_angstrom,
                "cell_angles_degrees": cell_angles_degrees,
                "fractional_coordinates": fractional_coordinates,
            })

    return server


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Start a read-only Rhombus MCP server over local stdio"
    )
    parser.add_argument(
        "--evidence-jsonl", required=True, type=Path,
        help="Trusted host-bound EvidenceRecord JSONL snapshot",
    )
    parser.add_argument(
        "--enable-preflight-tools", action="store_true",
        help="Opt in to read-only structure/domain preflight tools",
    )
    parser.add_argument("--model-domain-snapshot", type=Path)
    parser.add_argument("--model-domain-snapshot-sha256", type=str)
    args = parser.parse_args(argv)
    if not args.evidence_jsonl.is_file():
        parser.error("trusted evidence snapshot does not exist")
    if args.evidence_jsonl.stat().st_size > 64 * 1024 * 1024:
        parser.error("trusted evidence snapshot exceeds the size budget")
    if args.enable_preflight_tools and (
        not args.model_domain_snapshot or not args.model_domain_snapshot_sha256
    ):
        parser.error("preflight opt-in requires host-selected snapshot path and SHA256")
    if not args.enable_preflight_tools and (
        args.model_domain_snapshot or args.model_domain_snapshot_sha256
    ):
        parser.error("preflight snapshot options require --enable-preflight-tools")
    # MCP protocol on stdout; do not emit banners or arbitrary log text.
    create_mcp_server(
        args.evidence_jsonl,
        enable_preflight_tools=args.enable_preflight_tools,
        model_domain_snapshot=args.model_domain_snapshot,
        model_domain_snapshot_sha256=args.model_domain_snapshot_sha256,
    ).run(transport="stdio")


if __name__ == "__main__":
    main()
