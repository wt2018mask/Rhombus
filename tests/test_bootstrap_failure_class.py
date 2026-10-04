"""B3 regression: bootstrap standalone failure classification must follow the canonical taxonomy."""
import subprocess
import sys

from rudeus.execution.bootstrap import _failure_class_name
from rudeus.execution.contracts import ExecutionError


def test_timeout_maps_to_timeout():
    assert _failure_class_name(TimeoutError("timed out")) == "TIMEOUT"
    assert _failure_class_name(subprocess.TimeoutExpired("cmd", 1)) == "TIMEOUT"


def test_connection_error_maps_to_network():
    assert _failure_class_name(ConnectionError("refused")) == "NETWORK"


def test_floating_point_and_overflow_map_to_numerical():
    assert _failure_class_name(FloatingPointError("invalid")) == "NUMERICAL"
    assert _failure_class_name(OverflowError("too large")) == "NUMERICAL"


def test_file_not_found_maps_to_integrity():
    assert _failure_class_name(FileNotFoundError("missing")) == "INTEGRITY"


def test_arbitrary_value_error_follows_canonical_classifier():
    # Canonical classify_failure falls through to SOFTWARE; it must not be
    # hard-coded to INTEGRITY in the bootstrap reporting path.
    assert _failure_class_name(ValueError("bad value")) == "SOFTWARE"
    assert _failure_class_name(RuntimeError("boom")) == "SOFTWARE"


def test_resource_preserved():
    assert _failure_class_name(MemoryError("oom")) == "RESOURCE"


def test_execution_error_passthrough_preserved():
    assert _failure_class_name(ExecutionError("preempted", "INFRASTRUCTURE")) == "INFRASTRUCTURE"
    assert _failure_class_name(ExecutionError("unsupported", "UNSUPPORTED_INPUT")) == "UNSUPPORTED_INPUT"
    assert _failure_class_name(ExecutionError("unknown")) == "UNKNOWN"


def test_fallback_when_canonical_import_unavailable(monkeypatch):
    monkeypatch.setitem(sys.modules, "rudeus.execution.contracts", None)
    assert _failure_class_name(ValueError("bad value")) == "INTEGRITY"
    assert _failure_class_name(MemoryError("oom")) == "RESOURCE"
    assert _failure_class_name(TimeoutError("timed out")) == "SOFTWARE"
    assert _failure_class_name(
        ExecutionError("preempted", "INFRASTRUCTURE")) == "INFRASTRUCTURE"
