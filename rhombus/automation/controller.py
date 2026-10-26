"""Single approved thermal task, one submission, resumable provider observation."""
from __future__ import annotations

import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import uuid

from rhombus.automation.ledger import ControlError, canonical, digest

SOURCE = "474df8faa7484b87f19e5679336192939598e1f7"
MODEL = "75428afe3a1d7d8062e19bcaabd5c433623cabf308242ec9fb493e38604fb638"
PROTOCOL = "a436923971add5c32a0937deb0f4aa3960c2b416a6e2c7d833d191ed1bd141b0"


def build_request(root=None):
    raw = Path(__file__).with_name("request.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != "988a3b29cd99ae492e5c95e1802b89c419180de674ed6dd76524009d4e2b8c3f":
        raise ControlError("FROZEN_REQUEST_CHANGED")
    return json.loads(raw)


def validate_policy(policy, request, approved_digest):
    if not approved_digest or digest(policy) != approved_digest:
        raise ControlError("POLICY_NOT_INDEPENDENTLY_APPROVED")
    expected = {
        "schema_version": "rhombus-kaggle-policy-v1", "policy_id": "thermal-0201-cpu-once-v1",
        "source_commit": SOURCE, "model_sha256": MODEL, "protocol_sha256": PROTOCOL,
        "task_type": "assess_finite_temperature_stability",
        "candidate_ids": ["lialo2-gamma", "li2s-microcrystalline"],
        "resource": "KAGGLE_CPU", "gpu_enabled": False, "money_usd": 0,
        "wall_seconds": 10800, "memory_mib": 4096, "output_bytes": 134217728,
        "max_concurrent_jobs": 1, "max_submissions": 1, "submission_period": "POLICY_LIFETIME",
        "automatic_submission_retries": 0, "polls_per_invocation": 1,
        "unknown_cpu_quota": "BOUNDED_FREE_CPU_REQUEST_ONLY",
        "protocol_family": "thermal-study-0201-v1", "fail_closed": True,
    }
    if policy != expected:
        raise ControlError("UNSUPPORTED_POLICY")
    task, protocol = request["task"], request["protocol"]
    if (task["code_revision"] != SOURCE or task["protocol_hash"] != PROTOCOL
            or protocol["model_sha256"] != MODEL or request["device"] != "cpu"
            or protocol["candidate_ids"] != policy["candidate_ids"]
            or task["stage"] != policy["task_type"]):
        raise ControlError("TASK_NOT_ALLOWED")
    if request != build_request(Path(__file__).resolve().parents[2]):
        raise ControlError("REQUEST_SOURCE_OR_PROTOCOL_CHANGED")
    budget = protocol["resource_budget"]
    if any(budget[key] != policy[key] for key in ("wall_seconds", "memory_mib", "output_bytes", "money_usd", "max_submissions")):
        raise ControlError("RESOURCE_NOT_ALLOWED")


def provider_identity(username, request):
    if not re.fullmatch(r"[a-zA-Z0-9_-]{3,40}", username):
        raise ControlError("INVALID_KAGGLE_USERNAME")
    return username + "/rhombus-0201-" + request["task_id"][:40]


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def reconcile(ledger, provider, policy, request, approved_digest, staging, *, allow_submit=True):
    validate_policy(policy, request, approved_digest)
    readiness = provider.authenticate()
    identity = provider_identity(readiness["username"], request)
    revision, old = ledger.read()
    if old is not None:
        if (old["request_sha256"] != digest(request) or old["policy_sha256"] != digest(policy)
                or old["provider_identity"] != identity):
            raise ControlError("LEDGER_IDENTITY_MISMATCH")
        if old["state"] in ("VERIFIED", "SCIENTIFICALLY_INDETERMINATE", "SCIENTIFIC_VERIFICATION_FAILED"):
            return old
        state = copy.deepcopy(old)
    else:
        if not allow_submit:
            return {"state": "AUTHENTICATED_NOT_SUBMITTED", "readiness": readiness}
        provider.ensure_absent(identity)
        provider.prepare(staging, request, identity)
        state = {"schema_version": "rhombus-automation-state-v1", "task_id": request["task_id"],
                 "policy_sha256": digest(policy), "request_sha256": digest(request),
                 "provider_identity": identity, "provider_run_id": identity + "/1",
                 "state": "SUBMISSION_PENDING", "submission_attempts": 1,
                 "claim_nonce": uuid.uuid4().hex,
                 "claimed_at": now(), "readiness": readiness,
                 "script_sha256": hashlib.sha256((Path(staging) / "kernel.py").read_bytes()).hexdigest(),
                 "provider_origin_binding": "NOT_YET_OBSERVED"}
        revision = ledger.compare_and_swap(None, state)
        if revision is None:
            return {"state": "CLAIM_LOST_NO_SUBMISSION"}
        try:
            receipt = provider.submit(staging, identity, policy["wall_seconds"])
            state.update(state="ACCEPTED", receipt=receipt)
        except Exception:
            state["state"] = "SUBMISSION_OUTCOME_UNCERTAIN"
        state["observed_at"] = now()
        if ledger.compare_and_swap(revision, state) is None:
            raise ControlError("STATE_WRITE_CONFLICT_RECONCILE_ONLY")
        return state
    try:
        observation = provider.observe(state["provider_run_id"], state["script_sha256"])
        state["observation"] = observation
        observed = observation["state"]
        if old["state"] in ("RETRIEVAL_PENDING", "COMPLETE", "ERROR") and observed in ("RUNNING", "ACCEPTED", "UNKNOWN"):
            state["last_poll"] = "STALE_PROVIDER_STATUS"
        else:
            state["state"] = observed
        state["provider_origin_binding"] = observation["origin_binding"]
    except Exception:
        state["last_poll"] = "PROVIDER_OBSERVATION_UNAVAILABLE"
        if state["state"] in ("SUBMISSION_PENDING", "SUBMISSION_OUTCOME_UNCERTAIN"):
            state["state"] = "SUBMISSION_OUTCOME_UNCERTAIN"
    state["observed_at"] = now()
    if ledger.compare_and_swap(revision, state) is None:
        raise ControlError("STATE_WRITE_CONFLICT_RECONCILE_ONLY")
    return state
