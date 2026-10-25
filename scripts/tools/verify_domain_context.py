"""Measure real stdio transport of synthetic multi-family context; no model call."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from rhombus.domain.context import CapabilityDeclaration, ResearchContext, assess_declared_capability
from rhombus.evidence.identity import SourceBinding

ROOT = Path(__file__).resolve().parents[2]


async def verify():
    declaration = CapabilityDeclaration("quantify_ionic_transport", "solid_ionic_conductors",
        "O_ONLY", "total_ionic_conductivity", "S/cm", "fixture:oxide-model", "fixture:v1")
    contexts = [ResearchContext("solid_ionic_conductors", family, "fixture:" + family,
        "total_ionic_conductivity", "S/cm", measurement_temperature_K=298.15)
        for family in ("O_ONLY", "S_ONLY")]
    records = [assess_declared_capability(c, declaration, source_bindings=(
        SourceBinding("SYNTHETIC_FIXTURE", "fixture:architecture-validation"),)) for c in contexts]
    observations = []
    with tempfile.TemporaryDirectory(prefix="rhombus-domain-context-") as directory:
        snapshot = Path(directory) / "synthetic.jsonl"
        snapshot.write_text("".join(json.dumps(r.to_dict()) + "\n" for r in records))
        original = snapshot.read_bytes()
        params = StdioServerParameters(command=sys.executable, cwd=ROOT,
            args=["-m", "rhombus.tools.mcp_server", "--evidence-jsonl", str(snapshot)])
        with (Path(directory) / "stderr.log").open("w") as err:
            async with stdio_client(params, errlog=err) as streams:
                async with ClientSession(*streams, read_timeout_seconds=20) as client:
                    await client.initialize()
                    tools = (await client.list_tools()).tools
                    assert len(tools) == 6
                    for record in records:
                        manifest_id = None
                        for tool in ("get_candidate_evidence", "build_evidence_manifest", "plan_scientific_task"):
                            arguments = {"candidate_id": record.candidate_id}
                            if tool == "plan_scientific_task":
                                arguments.update(capability="quantify_ionic_transport",
                                    evidence_manifest_id=manifest_id, requested_backend="LOCAL_CPU",
                                    max_walltime_seconds=60, max_cpu_cores=1, max_memory_mib=256)
                            start = time.perf_counter()
                            response = await client.call_tool(tool, arguments)
                            seconds = time.perf_counter() - start
                            normalized = response.model_dump(mode="json", by_alias=True)
                            assert not normalized["isError"]
                            result = normalized["structuredContent"]
                            assert result["claim_authorized"] is False
                            if tool == "get_candidate_evidence":
                                row = result["evidence_records"][0]
                                assert row["evidence_id"] == record.evidence_id
                                assert row["research_context"] == record.payload["research_context"]
                                assert row["scientific_verdict"] == record.scientific_verdict.value
                            elif tool == "build_evidence_manifest":
                                assert result["evidence_ids"] == [record.evidence_id]
                                manifest_id = result["manifest_id"]
                            else:
                                assert not result["execution_authorized"]
                                assert result["dispatch_status"] == "NOT_SUBMITTED"
                            observations.append({"tool": tool, "candidate_id": record.candidate_id,
                                "invocation_seconds": seconds,
                                "response_bytes": len(response.model_dump_json(by_alias=True).encode()),
                                "response": normalized})
        assert snapshot.read_bytes() == original
    return {
        "schema_version": "rhombus-domain-context-stdio-validation-v1",
        "input_kind": "SYNTHETIC_ARCHITECTURE_FIXTURE_NOT_SCIENTIFIC_SOURCE",
        "code_sha256": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in (
            "rhombus/domain/context.py", "rhombus/tools/evidence_query.py",
            "scripts/tools/verify_domain_context.py")},
        "tool_count": 6, "call_count": len(observations), "session_closed": True,
        "evidence_records": [r.to_dict() for r in records], "calls": observations,
        "autonomous_AI_selection_accuracy": None, "actual_model_token_usage": None,
        "scientific_generalization_verified": False, "new_experimental_measurements": 0,
        "scientific_GO": False, "production_enabled": False, "TEST121_accessed": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists; preserve prior observations")
    report = asyncio.run(verify())
    with args.output.open("x", encoding="utf-8") as out:
        json.dump(report, out, indent=2, allow_nan=False)
        out.write("\n")
    print(json.dumps({k: report[k] for k in ("tool_count", "call_count", "session_closed")}))


if __name__ == "__main__":
    main()
