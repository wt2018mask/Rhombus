"""Local process telemetry adapter. No engine, imports, dispatch or inference.

Embedding this meter in a separately owner-authorized runner is a FUTURE task.
Until then, only synthetic callbacks / counters may be tested. It observes
monotonic wall time, process CPU time and process-wide RSS high-water; it cannot
verify MLIP calculator internals, subprocesses, independent provenance or physics.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from hashlib import sha256
import json
import math
import sys
import time
from typing import Any

from .tier_a_budget_contract import (
    PHASES, RECEIPT_SCHEMA, _sha, inspect_budget_draft,
)

SCHEMA = "rhombus-0204-tier-a-local-process-meter-envelope-v1"
REQUEST_KINDS = frozenset(("energy", "force", "model_calculation"))
MAX_LOCAL_EVENTS = 20_000
_MEASURED_PHASES = PHASES[:-1]  # the fifth 'other_overhead' is computed as residual
VALID_EVENTS = frozenset(f"{p}:{k}" for p in ("endpoint_relax", "neb_optimize") for k in REQUEST_KINDS)


def _process_high_water_mib() -> float:
    """Conservative process high-water (not per-NEB phase or child processes)."""
    try:
        import resource
        max_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        mib = max_rss / (1024 * 1024 if sys.platform == "darwin" else 1024)
        if not math.isfinite(mib) or mib <= 0:
            raise ValueError("RSS_UNAVAILABLE")
        return mib
    except (ImportError, AttributeError, OSError) as exc:
        try:
            import psutil  # Optional on Windows: use peak working-set, not sampled RSS
            p = psutil.Process().memory_info()
            peak = getattr(p, "peak_wset", None)
            if peak is None or peak <= 0:
                raise ValueError("WINDOWS_PEAK_WSET_UNAVAILABLE")
            return peak / (1024 * 1024)
        except (ImportError, AttributeError, OSError, ValueError) as win_exc:
            raise ValueError("PROCESS_HIGH_WATER_RSS_UNAVAILABLE") from win_exc


class LocalProcessMeter:
    """Nonexecuting measurement hooks for an eventual trusted runner.

    No method invokes a scientific model or invokes passed callables. Future
    integration MUST wrap the real underlying calculator to ensure that actual
    calls, including failed attempts, are captured at the calculator boundary.
    """

    def __init__(self, draft: dict, *, arm_id: str, edge_id: str):
        self._draft = deepcopy(draft)
        state = inspect_budget_draft(self._draft)
        self._contract_sha256 = state["draft_sha256"]
        self._arm = next((a for a in self._draft["model_arms"] if a["arm_id"] == arm_id), None)
        self._edge = next((e for e in self._draft["edges"] if e["edge_id"] == edge_id), None)
        if self._arm is None or self._edge is None:
            raise ValueError("ARM_EDGE_NOT_IN_FROZEN_CANDIDATE")
        if self._arm["checkpoint_sha256"] is None or self._edge["initial_images_sha256"] is None:
            raise ValueError("METER_IDENTITY_NOT_PINNED")
        self._start_wall = time.perf_counter_ns()
        self._start_cpu = time.process_time_ns()
        self._observed_rss_mib = _process_high_water_mib()
        self._phases: dict[str, dict[str, float]] = {}
        self._active: str | None = None
        self._last_phase_index = -1
        self._calls = {"energy_requests": 0, "force_requests": 0, "model_evaluations": 0}
        self._events: list[str] = []
        self._fault_seen = False
        self._closed = False

    def _ensure_open(self) -> None:
        if self._closed:
            raise ValueError("METER_ALREADY_FINALIZED")

    @contextmanager
    def phase(self, name: str):
        self._ensure_open()
        if name not in _MEASURED_PHASES:
            raise ValueError("INVALID_EXPLICIT_PHASE")
        index = _MEASURED_PHASES.index(name)
        if self._active is not None or name in self._phases or index <= self._last_phase_index:
            raise ValueError("OVERLAPPING_REPEATED_OR_REORDERED_PHASE")
        self._last_phase_index = index
        self._active = name
        w0, c0 = time.perf_counter_ns(), time.process_time_ns()
        try:
            yield self
        except BaseException:
            self._fault_seen = True
            raise
        finally:
            dw = max(0, time.perf_counter_ns() - w0) / 1e9
            dc = max(0, time.process_time_ns() - c0) / 1e9
            self._phases[name] = {"wall_seconds": dw, "cpu_seconds": dc}
            self._observed_rss_mib = max(self._observed_rss_mib, _process_high_water_mib())
            self._active = None

    def record_call(self, kind: str) -> None:
        """Hook for caller-controlled boundaries; NEVER claims MLIP forward-pass attestation."""
        self._ensure_open()
        if kind not in REQUEST_KINDS or self._active not in ("endpoint_relax", "neb_optimize"):
            # Swallowed accounting errors must never become scientific success.
            self._fault_seen = True
            raise ValueError("CALCULATOR_EVENT_OUTSIDE_ALLOWED_PHASE")
        key = {"energy": "energy_requests", "force": "force_requests",
               "model_calculation": "model_evaluations"}[kind]
        if len(self._events) >= MAX_LOCAL_EVENTS:
            self._fault_seen = True
            raise ValueError("LOCAL_EVENT_BUDGET_EXCEEDED")
        self._calls[key] += 1
        self._events.append(f"{self._active}:{kind}")
        self._observed_rss_mib = max(self._observed_rss_mib, _process_high_water_mib())

    def mark_calculator_fault(self) -> None:
        """A swallowed calculator error must taint the final receipt."""
        self._ensure_open()
        if self._active not in ("endpoint_relax", "neb_optimize"):
            raise ValueError("CALCULATOR_FAULT_OUTSIDE_ALLOWED_PHASE")
        self._fault_seen = True

    def finish(self, *, status: str, exception_code: str | None = None,
               endpoint_max_force: float | None = None,
               neb_max_force: float | None = None) -> dict[str, Any]:
        self._ensure_open()
        if self._active is not None:
            raise ValueError("FINALIZATION_DURING_ACTIVE_PHASE")
        # Explicit caller status is untrusted. The receipt validator will test
        # claimed convergence against force thresholds and work counters.
        if status not in ("CONVERGED", "NONCONVERGED", "TIMEOUT", "OUT_OF_MEMORY",
                          "MODEL_ERROR", "INPUT_INVALID"):
            raise ValueError("INVALID_COMPLETION_STATUS")
        if self._fault_seen and status in ("CONVERGED", "NONCONVERGED"):
            raise ValueError("INSTRUMENTED_EXCEPTION_CANNOT_BECOME_SUCCESS")
        if status in ("CONVERGED", "NONCONVERGED") and exception_code is not None:
            raise ValueError("UNEXPECTED_EXCEPTION_CODE")
        if status not in ("CONVERGED", "NONCONVERGED") and exception_code != status:
            raise ValueError("FAILURE_CODE_REQUIRED")
        for key, val in (("endpoint_max", endpoint_max_force), ("neb_max", neb_max_force)):
            if val is not None and (type(val) not in (float, int) or
                                    not math.isfinite(val) or val < 0):
                raise ValueError("INVALID_FORCE_DIAGNOSTIC")
        if status == "CONVERGED" and (endpoint_max_force is None or neb_max_force is None):
            raise ValueError("CONVERGENCE_REQUIRES_RECORDED_FORCES")
        wall = max(0, time.perf_counter_ns() - self._start_wall) / 1e9
        cpu = max(0, time.process_time_ns() - self._start_cpu) / 1e9
        durations = {name: self._phases.get(name, {"wall_seconds": 0.0,
                                                   "cpu_seconds": 0.0})
                     for name in _MEASURED_PHASES}
        durations["other_overhead"] = {
            "wall_seconds": max(0.0, wall - sum(x["wall_seconds"] for x in durations.values())),
            "cpu_seconds": max(0.0, cpu - sum(x["cpu_seconds"] for x in durations.values())),
        }
        self._observed_rss_mib = max(self._observed_rss_mib, _process_high_water_mib())
        receipt = {
            "schema_version": RECEIPT_SCHEMA,
            "contract_sha256": self._contract_sha256,
            "arm_id": self._arm["arm_id"], "edge_id": self._edge["edge_id"],
            "group_id": self._edge["group_id"],
            "checkpoint_sha256": self._arm["checkpoint_sha256"],
            "initial_images_sha256": self._edge["initial_images_sha256"],
            "reported_status": status, "exception_code": exception_code,
            "phases": durations,
            "total": {"wall_seconds": wall, "cpu_seconds": cpu,
                      **self._calls, "peak_rss_mib": self._observed_rss_mib},
            "observed_forces_ev_ang": {"endpoint_max": endpoint_max_force,
                                       "neb_max": neb_max_force},
        }
        self._closed = True
        return {
            "schema_version": SCHEMA,
            "measurement_provenance": "LOCAL_PROCESS_SELF_REPORTED_NOT_INDEPENDENT_RUNTIME_ATTESTATION",
            "model_call_semantics": "CALLER_INSTRUMENTED_CALCULATOR_BOUNDARY_NOT_VERIFIED_FORWARD_PASSES",
            "wall_clock": "PERF_COUNTER_NS_MONOTONIC",
            "cpu_clock": "PROCESS_TIME_NS_EXCLUDES_CHILD_PROCESS_CPU",
            "rss_semantics": "PROCESS_WIDE_HIGH_WATER_MARK_INCLUDES_PREEXISTING_MEMORY",
            "event_count": len(self._events),
            "event_log": list(self._events),
            "event_order_sha256": sha256(json.dumps(self._events, separators=(",", ":"),
                                                   ensure_ascii=True).encode("ascii")).hexdigest(),
            "raw_energy_values_saved": False,
            "model_executed_by_meter": False,
            "execution_authorized_by_meter": False,
            "receipt": receipt,
        }


def audit_local_meter_envelopes(draft: dict, envelopes: list[dict]) -> dict[str, Any]:
    """Cross-check caller-generated event order and counts; never attest a model.

    This does not prove events occurred in the physical calculator. Replays can
    reproduce recorded JSON, not independently authenticate the underlying run.
    """
    from .tier_a_budget_contract import audit_paired_receipts

    if type(envelopes) is not list or len(envelopes) != (
        len(draft["edges"]) * len(draft["model_arms"])
    ):
        raise ValueError("COMPLETE_PAIRED_ENVELOPES_REQUIRED")
    receipts = []
    for env in envelopes:
        if type(env) is not dict or set(env) != {
            "schema_version", "measurement_provenance", "model_call_semantics",
            "wall_clock", "cpu_clock", "rss_semantics", "event_count",
            "event_log", "event_order_sha256", "raw_energy_values_saved",
            "model_executed_by_meter", "execution_authorized_by_meter", "receipt"
        }:
            raise ValueError("UNKNOWN_METER_ENVELOPE_FIELDS")
        if (env["schema_version"] != SCHEMA
                or env["measurement_provenance"] != "LOCAL_PROCESS_SELF_REPORTED_NOT_INDEPENDENT_RUNTIME_ATTESTATION"
                or env["model_call_semantics"] != "CALLER_INSTRUMENTED_CALCULATOR_BOUNDARY_NOT_VERIFIED_FORWARD_PASSES"
                or env["wall_clock"] != "PERF_COUNTER_NS_MONOTONIC"
                or env["cpu_clock"] != "PROCESS_TIME_NS_EXCLUDES_CHILD_PROCESS_CPU"
                or env["rss_semantics"] != "PROCESS_WIDE_HIGH_WATER_MARK_INCLUDES_PREEXISTING_MEMORY"
                or env["raw_energy_values_saved"] is not False
                or env["model_executed_by_meter"] is not False
                or env["execution_authorized_by_meter"] is not False):
            raise ValueError("UNATTESTED_METER_PROMOTED")
        events = env["event_log"]
        if (type(events) is not list or len(events) > MAX_LOCAL_EVENTS or
                type(env["event_count"]) is not int or env["event_count"] != len(events)
                or not all(type(x) is str and x in VALID_EVENTS for x in events)):
            raise ValueError("INVALID_EVENT_SEQUENCE")
        if env["event_order_sha256"] != sha256(json.dumps(events, separators=(",", ":"),
                                             ensure_ascii=True).encode("ascii")).hexdigest():
            raise ValueError("EVENT_HASH_MISMATCH")
        # Calculator events must obey the declared phase progression.
        labels = [x.split(":", 1)[0] for x in events]
        if "endpoint_relax" in labels and "neb_optimize" in labels:
            if max(i for i, x in enumerate(labels) if x == "endpoint_relax") > min(
                i for i, x in enumerate(labels) if x == "neb_optimize"
            ):
                raise ValueError("EVENT_PHASE_ORDER_CONTRADICTION")
        rec = env["receipt"]
        if type(rec) is not dict:
            raise ValueError("INVALID_METER_RECEIPT")
        counter = {
            "energy_requests": sum(x.endswith(":energy") for x in events),
            "force_requests": sum(x.endswith(":force") for x in events),
            "model_evaluations": sum(x.endswith(":model_calculation") for x in events),
        }
        if rec.get("total", {}).get("energy_requests") != counter["energy_requests"] or \
           rec.get("total", {}).get("force_requests") != counter["force_requests"] or \
           rec.get("total", {}).get("model_evaluations") != counter["model_evaluations"]:
            raise ValueError("METER_EVENT_COUNTER_MISMATCH")
        receipts.append(rec)
    out = audit_paired_receipts(draft, receipts)
    out["meter_envelopes_checked"] = len(envelopes)
    out["meter_source_authenticity"] = "NOT_INDEPENDENTLY_ATTESTED"
    out["meter_events_cross_checked"] = sum(e["event_count"] for e in envelopes)
    return out
