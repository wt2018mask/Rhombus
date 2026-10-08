"""Pure, fail-closed AI task proposals: NEVER dispatch compute or grant approval.

A plan ID is a content digest, not authorization. Agent-provided manifest IDs
have not been validated against the host's scientific evidence snapshot.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

PLAN_VERSION = "rhombus-ai-science-task-proposal-v1"
CAPABILITIES = frozenset({
    "relax_structure", "assess_finite_temperature_stability",
    "quantify_ionic_transport",
})
BACKENDS = frozenset({"LOCAL_CPU", "KAGGLE_CPU"})
_SHA_ID = re.compile(r"^manifest:sha256:[a-f0-9]{64}$")
MAX_WALL_SECONDS = 21600
MAX_CPU_CORES = 8
MAX_MEMORY_MIB = 16384

_SPEC = {
    "type": "function",
    "function": {
        "name": "plan_scientific_task",
        "description": (
            "Create an immutable proposal ID with explicit compute budget. "
            "Never queues, approves, or launches Kaggle/CPU jobs. "
            "A trusted human-controlled host must authorize any future execution."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "candidate_id": {"type": "string", "minLength": 1, "maxLength": 256},
                "capability": {"type": "string", "enum": sorted(CAPABILITIES)},
                "evidence_manifest_id": {
                    "type": "string", "pattern": "^manifest:sha256:[a-f0-9]{64}$",
                },
                "requested_backend": {"type": "string", "enum": sorted(BACKENDS)},
                "max_walltime_seconds": {
                    "type": "integer", "minimum": 1, "maximum": MAX_WALL_SECONDS,
                },
                "max_cpu_cores": {"type": "integer", "minimum": 1, "maximum": MAX_CPU_CORES},
                "max_memory_mib": {
                    "type": "integer", "minimum": 256, "maximum": MAX_MEMORY_MIB,
                },
            },
            "required": [
                "candidate_id", "capability", "evidence_manifest_id", "requested_backend",
                "max_walltime_seconds", "max_cpu_cores", "max_memory_mib",
            ],
            "additionalProperties": False,
        },
    },
}


def plan_task_tool_spec() -> dict[str, Any]:
    return json.loads(json.dumps(_SPEC))


class DenyByDefaultTaskPlanner:
    """Unprivileged CPU-only planner, not a task executor or approval service."""

    def call_tool(self, name: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
        if name != "plan_scientific_task":
            raise ValueError("task planning tool is not registered")
        if not isinstance(arguments, Mapping):
            raise ValueError("tool arguments must be a JSON object")
        schema = _SPEC["function"]["parameters"]
        if set(arguments) != set(schema["required"]):
            raise ValueError("task proposal requires exact allowlisted arguments")
        candidate = arguments["candidate_id"]
        if not isinstance(candidate, str) or not candidate.strip() or len(candidate) > 256:
            raise ValueError("invalid candidate_id")
        capability = arguments["capability"]
        if not isinstance(capability, str) or capability not in CAPABILITIES:
            raise ValueError("unsupported capability")
        manifest = arguments["evidence_manifest_id"]
        if not isinstance(manifest, str) or not _SHA_ID.fullmatch(manifest):
            raise ValueError("invalid manifest identity")
        backend = arguments["requested_backend"]
        if not isinstance(backend, str) or backend not in BACKENDS:
            raise ValueError("unsupported execution backend")
        bounds = (
            ("max_walltime_seconds", 1, MAX_WALL_SECONDS),
            ("max_cpu_cores", 1, MAX_CPU_CORES),
            ("max_memory_mib", 256, MAX_MEMORY_MIB),
        )
        for key, lower, upper in bounds:
            value = arguments[key]
            if type(value) is not int or not lower <= value <= upper:
                raise ValueError(f"{key} is outside bounded integer budget")

        proposal = {
            "schema_version": PLAN_VERSION,
            "candidate_id": candidate,
            "capability": capability,
            "evidence_manifest_id": manifest,
            "requested_backend": backend,
            "resource_budget": {key: arguments[key] for key, _, _ in bounds},
        }
        canonical = json.dumps(
            proposal, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
        if len(canonical) > 4096:
            raise ValueError("task proposal exceeds size budget")
        proposal_id = "task-proposal:sha256:" + hashlib.sha256(canonical).hexdigest()
        return {
            **proposal,
            "tool_name": name,
            "proposal_id": proposal_id,
            "operational_status": "SUCCEEDED",
            "task_state": "PROPOSED_ONLY",
            "execution_authorized": False,
            "approval_status": "REQUIRES_TRUSTED_HOST_APPROVAL",
            "dispatch_status": "NOT_SUBMITTED",
            "scientific_verdict": "UNKNOWN",
            "domain_status": "UNQUALIFIED",
            "claim_authorized": False,
            "evidence_manifest_id_verified": False,
            "paid_service_authorized": False,
            "limitations": [
                "PROPOSAL_ID_IS_NOT_APPROVAL_OR_EXECUTION_RECEIPT",
                "AGENT_SUPPLIED_MANIFEST_ID_NOT_SOURCE_VERIFIED",
                "NO_EXECUTION_BACKEND_OR_CREDENTIALS_EXPOSED",
                "RESOURCE_BUDGET_IS_REQUESTED_NOT_RESERVED",
                "NO_SCIENTIFIC_CLAIM_AUTHORIZATION",
            ],
        }


__all__ = ["DenyByDefaultTaskPlanner", "plan_task_tool_spec"]
