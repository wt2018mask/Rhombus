"""AI scientific task proposals are never execution authorization."""
import pytest

from rhombus.tools.task_proposal import DenyByDefaultTaskPlanner, plan_task_tool_spec


ARGS = {
    "candidate_id": "test-candidate",
    "capability": "relax_structure",
    "evidence_manifest_id": "manifest:sha256:" + "a" * 64,
    "requested_backend": "KAGGLE_CPU",
    "max_walltime_seconds": 1800,
    "max_cpu_cores": 2,
    "max_memory_mib": 4096,
}


def test_plan_is_deterministic_and_denied_without_side_effect():
    planner = DenyByDefaultTaskPlanner()
    a = planner.call_tool("plan_scientific_task", ARGS)
    b = planner.call_tool("plan_scientific_task", dict(reversed(list(ARGS.items()))))
    assert a == b
    assert a["proposal_id"].startswith("task-proposal:sha256:")
    assert a["task_state"] == "PROPOSED_ONLY"
    assert a["approval_status"] == "REQUIRES_TRUSTED_HOST_APPROVAL"
    assert a["dispatch_status"] == "NOT_SUBMITTED"
    assert a["execution_authorized"] is False
    assert a["paid_service_authorized"] is False
    assert a["evidence_manifest_id_verified"] is False
    assert a["scientific_verdict"] == "UNKNOWN"
    assert a["claim_authorized"] is False
    assert "RESOURCE_BUDGET_IS_REQUESTED_NOT_RESERVED" in a["limitations"]
    adjusted = {**ARGS, "max_walltime_seconds": 1801}
    assert planner.call_tool("plan_scientific_task", adjusted)["proposal_id"] != a["proposal_id"]


def test_strict_tool_signature_never_includes_token_or_owner_approval():
    params = plan_task_tool_spec()["function"]["parameters"]
    assert params["additionalProperties"] is False
    assert "approve" not in str(params).lower()
    assert "kaggle_token" not in str(params).lower()
    assert "provider_api_key" not in str(params).lower()
    assert "path" not in params["properties"]


@pytest.mark.parametrize("changes", [
    {"candidate_id": ""},
    {"capability": "run_shell"},
    {"capability": "select_next_experiment"},
    {"requested_backend": "PAID_API"},
    {"evidence_manifest_id": "manifest:sha256:abc"},
    {"evidence_manifest_id": "../private-token"},
    {"max_walltime_seconds": 0},
    {"max_walltime_seconds": 21601},
    {"max_walltime_seconds": True},
    {"max_cpu_cores": 9},
    {"max_memory_mib": 128},
    {"max_memory_mib": 32768},
    {"approval": True},
    {"api_key": "secret"},
])
def test_bad_requests_fail_closed(changes):
    with pytest.raises(ValueError):
        DenyByDefaultTaskPlanner().call_tool("plan_scientific_task", {**ARGS, **changes})


def test_unsupported_tool_rejected():
    with pytest.raises(ValueError):
        DenyByDefaultTaskPlanner().call_tool("execute_scientific_task", ARGS)
    with pytest.raises(ValueError):
        DenyByDefaultTaskPlanner().call_tool("plan_scientific_task", {k:v for k,v in ARGS.items() if k!="max_cpu_cores"})
