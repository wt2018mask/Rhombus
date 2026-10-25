"""Verify actual computed pilot evidence through the existing local MCP tools."""
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

from rhombus.qualification.pilot_artifacts import verify_pilot_artifacts

ROOT = Path(__file__).resolve().parents[2]


async def verify():
    summary = json.loads((ROOT / "data/development/0200.json").read_text())
    directory = ROOT / summary["retained_final_directory"]
    integrity = verify_pilot_artifacts(directory, expected_report_sha256=summary["final_report_sha256"])
    report = json.loads((directory / "report.json").read_text())
    observations = []
    params = StdioServerParameters(command=sys.executable, cwd=ROOT,
        args=["-m", "rhombus.tools.mcp_server", "--evidence-jsonl", str(directory / "evidence.jsonl")])
    before = (directory / "evidence.jsonl").read_bytes()
    with tempfile.TemporaryDirectory(prefix="rhombus-physical-pilot-mcp-") as temp:
        with (Path(temp) / "stderr.log").open("w") as err:
            async with stdio_client(params, errlog=err) as streams:
                async with ClientSession(*streams, read_timeout_seconds=20) as client:
                    await client.initialize()
                    assert len((await client.list_tools()).tools) == 6
                    for row in report["evidence_records"]:
                        for tool in ("get_candidate_evidence", "build_evidence_manifest"):
                            started = time.perf_counter()
                            response = await client.call_tool(tool, {"candidate_id": row["candidate_id"]})
                            seconds = time.perf_counter() - started
                            normalized = response.model_dump(mode="json", by_alias=True)
                            assert not normalized["isError"]
                            result = normalized["structuredContent"]
                            assert result["claim_authorized"] is False and result["scientific_verdict"] == "UNKNOWN"
                            if tool == "get_candidate_evidence":
                                delivered = result["evidence_records"][0]
                                for key in ("evidence_id", "model_identity", "source_bindings", "uncertainty"):
                                    assert delivered[key] == row[key]
                                assert delivered["scientific_verdict"] == "INDETERMINATE"
                                assert delivered["applicability"]["domain_status"] == "UNQUALIFIED"
                            else:
                                assert result["evidence_ids"] == [row["evidence_id"]]
                            observations.append({"tool": tool, "candidate_id": row["candidate_id"],
                                "latency_seconds": seconds, "response_bytes": len(response.model_dump_json(by_alias=True).encode()),
                                "response": normalized})
    assert (directory / "evidence.jsonl").read_bytes() == before
    return {"schema_version": "rhombus-digital-pilot-mcp-verification-v1",
        "source_report_sha256": summary["final_report_sha256"], "integrity": integrity,
        "producer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "call_count": len(observations), "calls": observations, "session_closed": True,
        "autonomous_model_selection": "UNVERIFIED", "actual_model_token_usage": None,
        "scientific_GO": False, "new_computations_dispatched_by_MCP": 0}


def main():
    p = argparse.ArgumentParser(description=__doc__);p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    if args.output.exists():p.error("preserve existing observations")
    report = asyncio.run(verify())
    with args.output.open("x") as f:json.dump(report, f, indent=2);f.write("\n")
    print(json.dumps({"call_count": report["call_count"], "integrity": report["integrity"]}))


if __name__ == "__main__":main()
