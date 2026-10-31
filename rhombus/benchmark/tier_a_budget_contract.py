"""0204 Tier-A *non-executable* equal-budget, paired telemetry contract.

No target energies, MLIP/DFT/NEB/MD calls, IO or execution side effects.
An internally consistent telemetry receipt is not provider authentication,
model accuracy, independent generalization, or permission to run anything.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
import math
import re
from typing import Any, Mapping, Sequence

from .tier_a_preflight import (ZIP_SHA256, SCHEMA as REGISTRY_SCHEMA,
                               readiness_blockers, select_train_only_pilot)

SCHEMA = "rhombus-0204-tier-a-paired-cost-draft-v1"
RECEIPT_SCHEMA = "rhombus-0204-tier-a-paired-cost-receipt-v1"
MODES = ("CONVERGED", "NONCONVERGED", "TIMEOUT", "OUT_OF_MEMORY", "MODEL_ERROR", "INPUT_INVALID")
PHASES = ("input_read", "model_load", "endpoint_relax", "neb_optimize", "other_overhead")
CAP_FIELDS = ("wall_seconds", "cpu_seconds", "energy_requests", "force_requests",
              "model_evaluations", "peak_rss_mib")
TOTAL_CAP_FIELDS = ("wall_seconds", "cpu_seconds")
MACE_MEDIUM_SHA256 = "75428afe3a1d7d8062e19bcaabd5c433623cabf308242ec9fb493e38604fb638"
REQUIRED_MODEL_IDS = frozenset({"MACE_MP_0_SMALL_PUBLISHER_EXAMPLE", "MACE_MPA_0_MEDIUM_RHOMBUS"})
SHA_RE = re.compile(r"[a-f0-9]{64}\Z")


def _sha(data: Any) -> str:
    return sha256(json.dumps(data, sort_keys=True, separators=(",", ":"),
                             allow_nan=False, ensure_ascii=True).encode("ascii")).hexdigest()


def _shape(x: Any, keys: Sequence[str], where: str) -> None:
    if type(x) is not dict or set(x) != set(keys):
        raise ValueError(f"{where}: EXACT_FIELDS_REQUIRED")


def _sha_check(value: Any, where: str, *, missing_ok: bool = False) -> bool:
    if value is None and missing_ok:
        return False
    if type(value) is not str or SHA_RE.fullmatch(value) is None:
        raise ValueError(f"{where}: PINNED_SHA256_REQUIRED")
    return True


def _numeric(value: Any, where: str, *, positive: bool = False, integer: bool = False,
             missing_ok: bool = False) -> bool:
    if value is None and missing_ok:
        return False
    if (type(value) is not int if integer else type(value) not in (int, float)):
        raise ValueError(f"{where}: INVALID_NUMBER")
    if not math.isfinite(value) or value < 0 or (positive and value <= 0) or value > 1e12:
        raise ValueError(f"{where}: INVALID_NUMBER")
    return True


def _model_specs(protocol: Mapping[str, Any]) -> list[dict[str, Any]]:
    draft_arms = protocol["candidate_experiment_protocol"]["model_arms"]
    specs = []
    for arm in draft_arms:
        if arm.get("type") == "reference strong MLIP candidate":
            if not isinstance(arm.get("id"), str) or not arm["id"]:
                raise ValueError("MODEL_ID_REQUIRED")
            chk = arm.get("checkpoint_sha256")
            _sha_check(chk, "MODEL_IDENTITY", missing_ok=True)
            specs.append({"arm_id": arm["id"], "checkpoint_sha256": chk,
                          "training_overlap": "UNKNOWN_TRAINING_OVERLAP"})
    if len(specs) < 2 or len({x["arm_id"] for x in specs}) != len(specs):
        raise ValueError("TWO_DISTINCT_PINNABLE_MLIP_ARMS_REQUIRED")
    return specs


def make_execution_disabled_budget_draft(
    registry: Mapping[str, Any], pilot: Mapping[str, Any], protocol: Mapping[str, Any]
) -> dict[str, Any]:
    """Build reproducible run *design* only. No run can be authorized here."""
    readiness = readiness_blockers(protocol)
    if readiness["execution_authorized"] is not False:
        raise ValueError("PREVIOUS_GATE_PROMOTED")
    if registry.get("schema_version") != REGISTRY_SCHEMA:
        raise ValueError("INVALID_REGISTRY_SCHEMA")
    actual_pilot = select_train_only_pilot(registry)
    if pilot != actual_pilot:
        raise ValueError("PILOT_NOT_BOUND_TO_REGISTRY")
    if len(pilot["selected"]) != 4 or any(p["published_split"] != "train" for p in pilot["selected"]):
        raise ValueError("NO_HELDOUT_PILOT")
    model_specs = _model_specs(protocol)
    return {
        "schema_version": SCHEMA,
        "scope": "TIER_A_RETROSPECTIVE_LI_HOP_DISCRETE_NEB_ENERGY_SPAN",
        "observable": "max(E_images)-min(E_images); NONDIRECTIONAL; NO_TARGET_ACCESS",
        "scientific_status": "SCIENTIFIC_NO_GO_ABSTAIN",
        "benchmark_status": "BENCHMARK_NOT_FROZEN",
        "execution_authorized": False,
        "precomputed_bvse_cost": "UNATTESTED_EXCLUDED_FROM_POST_PRECONDITIONING_COMPARISON",
        "source_sha256": ZIP_SHA256,
        "registry_rows_sha256": registry["rows_sha256"],
        "pilot_selection_sha256": pilot["selection_sha256"],
        "edges": [{"edge_id": p["edge_id"], "group_id": p["group_id"],
                   "initial_images_sha256": None} for p in pilot["selected"]],
        "model_arms": model_specs,
        "runtime": {"device": "cpu", "threads_per_arm": 2, "precision": "float64",
                    "schedule": "SEQUENTIAL_NO_OVERLAP"},
        "neb": {"initialization": "EXACT_SHARED_BVSE_PRECONDITIONED_PATH",
                "endpoint_policy": "RELAX_BOTH_ENDPOINTS_SAME_METHOD",
                "optimizer": "FIRE", "method": "improvedtangent", "climbing": True,
                "endpoint_fmax_ev_ang": None, "neb_fmax_ev_ang": None,
                "endpoint_max_steps": None, "neb_max_steps": None,
                "spring_eV_ang2": None},
        "per_arm_edge_caps": {key: None for key in CAP_FIELDS},
        "total_pilot_caps": {key: None for key in TOTAL_CAP_FIELDS},
        "telemetry_policy": "ALL_EDGE_ARM_PAIRS_AND_FAILURES_REQUIRED; NONE_ARE_SCORING",
    }


def inspect_budget_draft(draft: Mapping[str, Any]) -> dict[str, Any]:
    """Strict field/provenance checks. This returns blockers, never authorization."""
    _shape(draft, ("schema_version", "scope", "observable", "scientific_status",
                   "benchmark_status", "execution_authorized", "precomputed_bvse_cost",
                   "source_sha256", "registry_rows_sha256", "pilot_selection_sha256", "edges",
                   "model_arms", "runtime", "neb", "per_arm_edge_caps", "total_pilot_caps",
                   "telemetry_policy"), "CONTRACT")
    if draft["schema_version"] != SCHEMA or draft["scope"] != "TIER_A_RETROSPECTIVE_LI_HOP_DISCRETE_NEB_ENERGY_SPAN":
        raise ValueError("INVALID_SCOPE")
    if draft["observable"] != "max(E_images)-min(E_images); NONDIRECTIONAL; NO_TARGET_ACCESS":
        raise ValueError("OBSERVABLE_OR_HELDOUT_TAMPERING")
    if (draft["scientific_status"] != "SCIENTIFIC_NO_GO_ABSTAIN"
            or draft["benchmark_status"] != "BENCHMARK_NOT_FROZEN"
            or draft["execution_authorized"] is not False):
        raise ValueError("UNAUTHORIZED_SCIENTIFIC_PROMOTION")
    if draft["precomputed_bvse_cost"] != "UNATTESTED_EXCLUDED_FROM_POST_PRECONDITIONING_COMPARISON":
        raise ValueError("HIDDEN_INITIALIZATION_COST")
    if draft["source_sha256"] != ZIP_SHA256:
        raise ValueError("SOURCE_IDENTITY_MISMATCH")
    _sha_check(draft["registry_rows_sha256"], "REGISTRY")
    _sha_check(draft["pilot_selection_sha256"], "PILOT")
    edges = draft["edges"]
    if type(edges) is not list or len(edges) != 4:
        raise ValueError("EXACT_FOUR_TRAIN_EDGES_REQUIRED")
    ids, groups = set(), set()
    blockers: list[str] = []
    for item in edges:
        _shape(item, ("edge_id", "group_id", "initial_images_sha256"), "EDGE")
        if (type(item["edge_id"]) is not str or not re.fullmatch(r"mp-\d+_[0-9_-]+", item["edge_id"])
                or type(item["group_id"]) is not str or not item["group_id"].startswith("CHEMSYS:")
                or item["edge_id"] in ids or item["group_id"] in groups):
            raise ValueError("EDGE_GROUP_DUPLICATION_OR_INVALID")
        ids.add(item["edge_id"])
        groups.add(item["group_id"])
        if not _sha_check(item["initial_images_sha256"], "INITIAL_IMAGES", missing_ok=True):
            blockers.append("INITIAL_IMAGE_HASHES_MISSING")
    arms = draft["model_arms"]
    if type(arms) is not list or len(arms) < 2 or len(arms) > 8:
        raise ValueError("MODEL_ARMS_COUNT_INVALID")
    names = set()
    pinned = set()
    for arm in arms:
        _shape(arm, ("arm_id", "checkpoint_sha256", "training_overlap"), "MODEL_ARM")
        if type(arm["arm_id"]) is not str or not arm["arm_id"] or arm["arm_id"] in names:
            raise ValueError("DUPLICATE_MODEL_ARM")
        if arm["training_overlap"] != "UNKNOWN_TRAINING_OVERLAP":
            raise ValueError("UNATTESTED_TRAINING_OVERLAP_PROMOTED")
        names.add(arm["arm_id"])
        if not _sha_check(arm["checkpoint_sha256"], "MODEL", missing_ok=True):
            blockers.append("MODEL_CHECKPOINT_UNPINNED")
        elif arm["checkpoint_sha256"] in pinned:
            raise ValueError("SAME_WEIGHTS_CANNOT_DEFINE_DISTINCT_BASELINES")
        else:
            pinned.add(arm["checkpoint_sha256"])
    if set(names) != REQUIRED_MODEL_IDS:
        raise ValueError("REQUIRED_PUBLISHER_SMALL_AND_RHOMBUS_MEDIUM_MISSING")
    if next(a["checkpoint_sha256"] for a in arms if a["arm_id"] == "MACE_MPA_0_MEDIUM_RHOMBUS") != MACE_MEDIUM_SHA256:
        raise ValueError("RHOMBUS_MEDIUM_CHECKPOINT_CHANGED")
    runtime = draft["runtime"]
    _shape(runtime, ("device", "threads_per_arm", "precision", "schedule"), "RUNTIME")
    if (runtime["device"] != "cpu" or runtime["precision"] != "float64"
            or runtime["schedule"] != "SEQUENTIAL_NO_OVERLAP"
            or type(runtime["threads_per_arm"]) is not int or runtime["threads_per_arm"] != 2):
        raise ValueError("INCOMPARABLE_EXECUTION_ENVIRONMENT")
    neb = draft["neb"]
    _shape(neb, ("initialization", "endpoint_policy", "optimizer", "method", "climbing",
                 "endpoint_fmax_ev_ang", "neb_fmax_ev_ang", "endpoint_max_steps", "neb_max_steps",
                 "spring_eV_ang2"), "NEB")
    if (neb["initialization"] != "EXACT_SHARED_BVSE_PRECONDITIONED_PATH"
            or neb["endpoint_policy"] != "RELAX_BOTH_ENDPOINTS_SAME_METHOD"
            or neb["optimizer"] != "FIRE" or neb["method"] != "improvedtangent"
            or neb["climbing"] is not True):
        raise ValueError("INCOMPARABLE_NEB_PROTOCOL")
    for key in ("endpoint_fmax_ev_ang", "neb_fmax_ev_ang", "spring_eV_ang2"):
        if not _numeric(neb[key], key, positive=True, missing_ok=True):
            blockers.append("NEB_NUMERIC_SETTINGS_MISSING")
    for key in ("endpoint_max_steps", "neb_max_steps"):
        if not _numeric(neb[key], key, positive=True, integer=True, missing_ok=True):
            blockers.append("NEB_NUMERIC_SETTINGS_MISSING")
    caps = draft["per_arm_edge_caps"]
    _shape(caps, CAP_FIELDS, "CAPS")
    for key in CAP_FIELDS:
        if not _numeric(caps[key], key, positive=True, integer=key.endswith("requests") or key == "model_evaluations", missing_ok=True):
            blockers.append("PER_ARM_PER_EDGE_CAPS_MISSING")
    total = draft["total_pilot_caps"]
    _shape(total, TOTAL_CAP_FIELDS, "TOTAL_CAPS")
    for key in TOTAL_CAP_FIELDS:
        if not _numeric(total[key], key, positive=True, missing_ok=True):
            blockers.append("TOTAL_PILOT_CAPS_MISSING")
    if draft["telemetry_policy"] != "ALL_EDGE_ARM_PAIRS_AND_FAILURES_REQUIRED; NONE_ARE_SCORING":
        raise ValueError("FAILURE_ACCOUNTING_POLICY_TAMPERED")
    return {"schema_version": SCHEMA, "protocol_draft_valid": True,
            "execution_authorized": False,
            "benchmark": "BENCHMARK_NOT_FROZEN",
            "blockers": sorted(set(blockers + ["OWNER_RUN_AUTHORIZATION_MISSING",
                                               "TRAINING_OVERLAP_UNKNOWN", "REFERENCE_TARGETS_SEALED"])),
            "paired_rows_required": len(edges) * len(arms),
            "draft_sha256": _sha(draft)}


def _strict_receipt(rec: Any, draft: Mapping[str, Any]) -> None:
    _shape(rec, ("schema_version", "contract_sha256", "arm_id", "edge_id", "group_id",
                 "checkpoint_sha256", "initial_images_sha256", "reported_status",
                 "exception_code", "phases", "total", "observed_forces_ev_ang"), "RECEIPT")
    if rec["schema_version"] != RECEIPT_SCHEMA or rec["contract_sha256"] != _sha(draft):
        raise ValueError("RECEIPT_PROTOCOL_CONTEXT_MISMATCH")
    arms = {a["arm_id"]: a for a in draft["model_arms"]}
    edges = {e["edge_id"]: e for e in draft["edges"]}
    if rec["arm_id"] not in arms or rec["edge_id"] not in edges:
        raise ValueError("UNEXPECTED_ARM_OR_EDGE")
    arm, edge = arms[rec["arm_id"]], edges[rec["edge_id"]]
    if (rec["checkpoint_sha256"] != arm["checkpoint_sha256"]
            or rec["initial_images_sha256"] != edge["initial_images_sha256"]
            or rec["group_id"] != edge["group_id"]):
        raise ValueError("RECEIPT_IDENTITY_OR_GROUP_MISMATCH")
    if rec["reported_status"] not in MODES:
        raise ValueError("INVALID_REPORTED_STATUS")
    if rec["reported_status"] in ("CONVERGED", "NONCONVERGED"):
        if rec["exception_code"] is not None:
            raise ValueError("INCONSISTENT_EXCEPTION")
    elif rec["exception_code"] != rec["reported_status"]:
        raise ValueError("MISSING_FAILURE_REASON")
    phase = rec["phases"]
    _shape(phase, PHASES, "PHASES")
    for name in PHASES:
        _shape(phase[name], ("wall_seconds", "cpu_seconds"), f"PHASE_{name}")
        for k in ("wall_seconds", "cpu_seconds"):
            _numeric(phase[name][k], "PHASE_TIME")
    summary = rec["total"]
    _shape(summary, CAP_FIELDS, "TOTAL")
    for key in CAP_FIELDS:
        _numeric(summary[key], f"TOTAL_{key}", integer=key.endswith("requests") or key == "model_evaluations")
    for kind in ("wall_seconds", "cpu_seconds"):
        part_sum = sum(phase[p][kind] for p in PHASES)
        if abs(part_sum - summary[kind]) > 1e-5 * max(1.0, summary[kind]):
            raise ValueError("UNACCOUNTED_PHASE_TIME")
    forces = rec["observed_forces_ev_ang"]
    _shape(forces, ("endpoint_max", "neb_max"), "OBSERVED_FORCES")
    for val in forces.values():
        _numeric(val, "OBSERVED_FORCE", missing_ok=True)
    if rec["reported_status"] == "CONVERGED":
        if (summary["force_requests"] == 0 or summary["model_evaluations"] == 0
                or phase["neb_optimize"]["wall_seconds"] <= 0):
            raise ValueError("CLAIMED_CONVERGENCE_WITHOUT_MODEL_WORK")
        if any(v is None for v in forces.values()):
            raise ValueError("CONVERGENCE_EVIDENCE_MISSING")
        if (forces["endpoint_max"] >= draft["neb"]["endpoint_fmax_ev_ang"]
                or forces["neb_max"] >= draft["neb"]["neb_fmax_ev_ang"]):
            raise ValueError("CONVERGENCE_CONTRADICTS_FIXED_FMAX")


def audit_paired_receipts(draft: Mapping[str, Any], receipts: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Audit observed telemetry structure; NEVER authenticate the measurements.

    All attempted edge/arm pairs are counted, including failures. Cap overruns
    are retained as budget violations, not dropped from the denominator.
    No energy predictions or target values are accepted in any input schema.
    """
    readiness = inspect_budget_draft(draft)
    if any(x in readiness["blockers"] for x in (
            "INITIAL_IMAGE_HASHES_MISSING", "MODEL_CHECKPOINT_UNPINNED",
            "NEB_NUMERIC_SETTINGS_MISSING", "PER_ARM_PER_EDGE_CAPS_MISSING",
            "TOTAL_PILOT_CAPS_MISSING")):
        raise ValueError("INCOMPLETE_DRAFT_CANNOT_VALIDATE_RUN_TELEMETRY")
    if not isinstance(receipts, (list, tuple)):
        raise ValueError("RECEIPTS_MUST_BE_LIST")
    required = {(e["edge_id"], a["arm_id"]) for e in draft["edges"] for a in draft["model_arms"]}
    if len(receipts) != len(required):
        raise ValueError("UNREPORTED_OR_EXTRA_PAIRED_ROWS")
    found = set()
    statuses = Counter()
    effective = Counter()
    totals = {"wall_seconds": 0.0, "cpu_seconds": 0.0,
              "energy_requests": 0, "force_requests": 0, "model_evaluations": 0}
    overruns = []
    for rec in receipts:
        _strict_receipt(rec, draft)
        pair = (rec["edge_id"], rec["arm_id"])
        if pair in found:
            raise ValueError("DUPLICATE_PAIR_OR_MISSING_OTHER_PAIR")
        found.add(pair)
        status = rec["reported_status"]
        statuses[status] += 1
        reasons = []
        for key in CAP_FIELDS:
            if rec["total"][key] > draft["per_arm_edge_caps"][key]:
                reasons.append(f"{key.upper()}_CAP_EXCEEDED")
        if reasons:
            overruns.append({"edge_id": rec["edge_id"], "arm_id": rec["arm_id"],
                             "reasons": reasons})
            effective["BUDGET_VIOLATION"] += 1
        else:
            effective[status] += 1
        for key in totals:
            totals[key] += rec["total"][key]
    if found != required:
        raise ValueError("PAIRED_DENOMINATOR_MISMATCH")
    total_cap_violations = [k for k in TOTAL_CAP_FIELDS
                            if totals[k] > draft["total_pilot_caps"][k]]
    # Global budget overruns are flagged separately and MUST NOT add cases
    # to the paired denominator or effective per-pair status counts.
    return {
        "schema_version": "rhombus-0204-tier-a-cost-telemetry-audit-v1",
        "claim": "INTERNAL_CONSISTENCY_ONLY; NO_EXTERNAL_RUNTIME_ATTESTATION",
        "benchmark_status": "BENCHMARK_NOT_FROZEN",
        "execution_authorized": False,
        "scientific_status": "SCIENTIFIC_NO_GO_ABSTAIN",
        "recorded_pairs": len(receipts),
        "required_pairs": len(required),
        "recorded_status_counts": dict(sorted(statuses.items())),
        "effective_status_counts": dict(sorted(effective.items())),
        "budget_overruns": sorted(overruns, key=lambda x: (x["edge_id"], x["arm_id"])),
        "total_cap_violations": total_cap_violations,
        "total_observed": totals,
        "all_within_budget": not overruns and not total_cap_violations,
        "energy_target_access": "NONE",
        "performance_evaluation": "NOT_PERFORMED",
        "no_claim_of_equal_end_to_end_cost": True,
        "contract_sha256": readiness["draft_sha256"],
    }
