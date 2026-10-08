"""Optional local stdio MCP v2 adapter for Rhombus read-only preflight tools."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Annotated, Any

from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from .evidence_query import MAX_RECORDS, ReadOnlyEvidenceTools
from .read_only_analysis import (
    DOMAIN_MODEL, MAX_SITES, ReadOnlyAnalysisTools,
)


def create_mcp_server(
    evidence_jsonl: Path,
    *,
    model_domain_snapshot: Path | None = None,
) -> MCPServer:
    """Expose only explicitly allowlisted queries with host-controlled sources."""
    evidence = ReadOnlyEvidenceTools(Path(evidence_jsonl))
    analysis = ReadOnlyAnalysisTools(model_domain_snapshot)
    server = MCPServer("Rhombus Evidence")
    readonly = ToolAnnotations(read_only_hint=True, open_world_hint=False)

    @server.tool(
        name="get_candidate_evidence",
        title="Get candidate evidence",
        annotations=readonly,
    )
    def get_candidate_evidence(
        candidate_id: Annotated[
            str, Field(min_length=1, max_length=256, description="Exact candidate ID"),
        ],
        max_records: Annotated[
            int, Field(ge=1, le=MAX_RECORDS, description="Maximum returned records"),
        ] = 10,
    ) -> dict[str, Any]:
        """Query content-hash-verified evidence, without authorizing scientific claims."""
        return evidence.call_tool(
            "get_candidate_evidence",
            {"candidate_id": candidate_id, "max_records": max_records},
        )

    @server.tool(
        name="get_domain_assessment",
        title="Get conservative model domain preflight",
        annotations=readonly,
    )
    def get_domain_assessment(
        candidate_id: Annotated[str, Field(min_length=1, max_length=256)],
        model_id: Annotated[str, Field(description="Pinned model identity")],
        claim_kind: Annotated[str, Field(description="Exact domain-specific claim kind")],
        atomic_numbers: Annotated[list[int], Field(min_length=1, max_length=MAX_SITES)],
    ) -> dict[str, Any]:
        """Check exact pinned model element coverage; never infer IN_DOMAIN from it."""
        return analysis.call_tool("get_domain_assessment", {
            "candidate_id": candidate_id,
            "model_id": model_id,
            "claim_kind": claim_kind,
            "atomic_numbers": atomic_numbers,
        })

    @server.tool(
        name="validate_candidate_structure",
        title="Validate a candidate structure representation",
        annotations=readonly,
    )
    def validate_candidate_structure(
        candidate_id: Annotated[str, Field(min_length=1, max_length=256)],
        structure: Annotated[dict[str, Any], Field(
            description=(
                "Explicit 3x3 lattice_vectors_angstrom, bounded atomic_numbers, "
                "and per-site fractional_coords, no file path"
            ),
        )],
    ) -> dict[str, Any]:
        """Validate bounded periodic input shape, not physics, stability or novelty."""
        return analysis.call_tool("validate_candidate_structure", {
            "candidate_id": candidate_id, "structure": structure,
        })

    return server


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Start local read-only Rhombus MCP server over stdio",
    )
    parser.add_argument(
        "--evidence-jsonl", required=True, type=Path,
        help="Trusted host-bound EvidenceRecord JSONL snapshot",
    )
    parser.add_argument(
        "--model-domain-snapshot", type=Path,
        help="Optional trusted frozen medium-mpa-0 domain snapshot (SHA256 pinned)",
    )
    args = parser.parse_args(argv)
    if not args.evidence_jsonl.is_file():
        parser.error("trusted evidence snapshot does not exist")
    if args.evidence_jsonl.stat().st_size > 64 * 1024 * 1024:
        parser.error("trusted evidence snapshot exceeds size budget")
    if args.model_domain_snapshot is not None and not args.model_domain_snapshot.is_file():
        parser.error("trusted model-domain snapshot does not exist")
    # No banner on stdout; it carries JSON-RPC only.
    create_mcp_server(
        args.evidence_jsonl,
        model_domain_snapshot=args.model_domain_snapshot,
    ).run(transport="stdio")


if __name__ == "__main__":
    main()
