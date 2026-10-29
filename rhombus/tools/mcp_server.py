"""Optional local stdio MCP v2 adapter for Rhombus read-only preflight tools."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Annotated, Any

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from jsonschema import Draft202012Validator
from pydantic import Field

from .evidence_query import MAX_RECORDS, ReadOnlyEvidenceTools, list_tool_specs
from .evidence_manifest import ReadOnlyEvidenceManifestTools
from .task_proposal import DenyByDefaultTaskPlanner
from .task_status import ReadOnlyTaskStatusTools
from .read_only_analysis import (
    DOMAIN_MODEL, MAX_SITES, ReadOnlyAnalysisTools,
)

MAX_MCP_INPUT_BYTES = 128 * 1024
MAX_MCP_RESULT_BYTES = 128 * 1024


class _ValidatedMCPServer(MCPServer):
    """Validate raw JSON before SDK coercion; publish the existing exact schemas."""

    additional_tool_specs: tuple = ()

    def _specs(self):
        return {spec['function']['name']: spec['function']
                for spec in (*list_tool_specs(), *self.additional_tool_specs)}

    async def list_tools(self):
        specs = self._specs()
        return [tool.model_copy(update={'input_schema': specs[tool.name]['parameters']})
                for tool in await super().list_tools()]

    async def call_tool(self, name, arguments, context=None):
        specs = self._specs()
        if name not in specs:
            raise ToolError('Unavailable Rhombus tool; use tools/list.')
        try:
            raw = json.dumps(arguments, allow_nan=False).encode('utf-8')
        except (TypeError, ValueError) as exc:
            raise ToolError('Tool arguments must be finite JSON.') from exc
        if len(raw) > MAX_MCP_INPUT_BYTES:
            raise ToolError('Tool arguments exceed the 128 KiB input budget.')
        error = next(Draft202012Validator(specs[name]['parameters']).iter_errors(arguments), None)
        if error is not None:
            # Do not echo malicious values, extra property names or sensitive paths.
            field = '.'.join(str(p) for p in error.absolute_schema_path if p != 'properties')
            raise ToolError(f'Invalid {name} arguments at {field}; follow tools/list schema.')
        result = await super().call_tool(name, arguments, context)
        if len(result.model_dump_json(by_alias=True).encode('utf-8')) > MAX_MCP_RESULT_BYTES:
            raise ToolError('Tool result exceeds the 128 KiB output budget; request fewer records.')
        return result


def create_mcp_server(
    evidence_jsonl: Path,
    *,
    model_domain_snapshot: Path | None = None,
    task_status_jsonl: Path | None = None,
    additional_tool_specs: tuple = (),
) -> MCPServer:
    """Expose only explicitly allowlisted queries with host-controlled sources."""
    evidence = ReadOnlyEvidenceTools(Path(evidence_jsonl))
    manifest = ReadOnlyEvidenceManifestTools(Path(evidence_jsonl))
    planner = DenyByDefaultTaskPlanner()
    task_status = ReadOnlyTaskStatusTools(task_status_jsonl)
    analysis = ReadOnlyAnalysisTools(model_domain_snapshot)
    server = _ValidatedMCPServer("Rhombus Evidence")
    existing = {spec['function']['name'] for spec in list_tool_specs()}
    added = [spec['function']['name'] for spec in additional_tool_specs]
    if existing.intersection(added) or len(added) != len(set(added)):
        raise ValueError('Additional tools cannot replace existing tools')
    server.additional_tool_specs = additional_tool_specs
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

    @server.tool(
        name="build_evidence_manifest",
        title="Build deterministic evidence ID manifest",
        annotations=readonly,
    )
    def build_evidence_manifest(
        candidate_id: Annotated[str, Field(min_length=1, max_length=256)],
        max_evidence_ids: Annotated[int, Field(ge=1, le=MAX_RECORDS)] = 10,
    ) -> dict[str, Any]:
        """Read-only SHA256-bound index, never a scientific qualification."""
        return manifest.call_tool(
            "build_evidence_manifest",
            {"candidate_id": candidate_id, "max_evidence_ids": max_evidence_ids},
        )

    @server.tool(
        name="plan_scientific_task",
        title="Propose scientific compute without executing",
        annotations=readonly,
    )
    def plan_scientific_task(
        candidate_id: Annotated[str, Field(min_length=1, max_length=256)],
        capability: Annotated[str, Field(description="Fixed scientific capability")],
        evidence_manifest_id: Annotated[str, Field(description="Agent-reported manifest ID; unverified")],
        requested_backend: Annotated[str, Field(description="LOCAL_CPU or KAGGLE_CPU")],
        max_walltime_seconds: Annotated[int, Field(ge=1, le=21600)],
        max_cpu_cores: Annotated[int, Field(ge=1, le=8)],
        max_memory_mib: Annotated[int, Field(ge=256, le=16384)],
    ) -> dict[str, Any]:
        """Unprivileged proposal ONLY: no approval, scheduler or Kaggle access."""
        return planner.call_tool("plan_scientific_task", {
            "candidate_id": candidate_id,
            "capability": capability,
            "evidence_manifest_id": evidence_manifest_id,
            "requested_backend": requested_backend,
            "max_walltime_seconds": max_walltime_seconds,
            "max_cpu_cores": max_cpu_cores,
            "max_memory_mib": max_memory_mib,
        })

    @server.tool(
        name="get_task_status",
        title="Get host snapshot of scientific task status",
        annotations=readonly,
    )
    def get_task_status(
        proposal_id: Annotated[str, Field(description="Exact task proposal SHA256 identifier")],
    ) -> dict[str, Any]:
        """Status from a host-bound receipt snapshot, never live provider polling."""
        return task_status.call_tool("get_task_status", {"proposal_id": proposal_id})

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
    parser.add_argument(
        "--task-status-jsonl", type=Path,
        help="Optional trusted host-controlled task-status snapshot (not live)",
    )
    args = parser.parse_args(argv)
    if not args.evidence_jsonl.is_file():
        parser.error("trusted evidence snapshot does not exist")
    if args.evidence_jsonl.stat().st_size > 64 * 1024 * 1024:
        parser.error("trusted evidence snapshot exceeds size budget")
    if args.model_domain_snapshot is not None and not args.model_domain_snapshot.is_file():
        parser.error("trusted model-domain snapshot does not exist")
    # No banner on stdout; it carries JSON-RPC only.
    if args.task_status_jsonl is not None and not args.task_status_jsonl.is_file():
        parser.error("trusted task-status snapshot does not exist")
    create_mcp_server(
        args.evidence_jsonl,
        model_domain_snapshot=args.model_domain_snapshot,
        task_status_jsonl=args.task_status_jsonl,
    ).run(transport="stdio")


if __name__ == "__main__":
    main()
