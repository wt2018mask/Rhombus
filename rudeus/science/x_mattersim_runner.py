"""MatterSim scientific-X MD execution layer.

Execution only: verifies the admitted P1-relaxed start structure, constructs
the byte-pinned MatterSim calculator on CUDA, and delegates dynamics to the
existing deterministic ASE Langevin engine. It does not classify transport,
compute D_self, or write scientific X observations.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping

from rudeus.mlip.p2 import run_nvt
from rudeus.mlip.sharding import structure_dict_sha256
from rudeus.science.x_mattersim_preflight import (
    CHECKPOINT_LABEL,
    EXPECTED_CHECKPOINT_SHA256,
    EXPECTED_MATTERSIM_VERSION,
    _require_runtime,
    _verified_checkpoint,
)
from rudeus.science.x_mattersim_protocol import MatterSimXProtocol, bind_protocol
from rudeus.science.x_mattersim_scientific import MatterSimXExecutionSpec


class MatterSimXExecutionError(RuntimeError):
    pass


def _relaxed_structure(
    p1_payload: Mapping[str, Any],
    admission: MatterSimXExecutionSpec,
) -> dict:
    result = p1_payload.get("result")
    if not isinstance(result, Mapping):
        raise MatterSimXExecutionError("P1 payload missing result mapping")
    structure = result.get("relaxed_structure_dict")
    if not isinstance(structure, dict):
        raise MatterSimXExecutionError("P1 relaxed structure missing")
    recorded_sha = result.get("relaxed_structure_sha256")
    actual_sha = structure_dict_sha256(structure)
    if recorded_sha != admission.start_structure_sha256:
        raise MatterSimXExecutionError("P1 recorded relaxed-structure SHA disagrees with admission")
    if actual_sha != admission.start_structure_sha256:
        raise MatterSimXExecutionError("P1 relaxed-structure bytes disagree with admission")
    return structure


def _default_calculator():
    torch, MatterSimCalculator = _require_runtime()
    if not bool(torch.cuda.is_available()):
        raise MatterSimXExecutionError("MatterSim scientific X requires CUDA")
    try:
        import importlib.metadata
        version = importlib.metadata.version("mattersim")
    except Exception as exc:
        raise MatterSimXExecutionError("cannot resolve MatterSim package version") from exc
    if version != EXPECTED_MATTERSIM_VERSION:
        raise MatterSimXExecutionError(
            f"MatterSim version mismatch: expected {EXPECTED_MATTERSIM_VERSION}, got {version}"
        )
    calc = MatterSimCalculator(load_path=CHECKPOINT_LABEL, device="cuda")
    _, checkpoint_sha = _verified_checkpoint()
    if checkpoint_sha != EXPECTED_CHECKPOINT_SHA256:
        raise MatterSimXExecutionError("MatterSim checkpoint identity mismatch")
    return calc


def _p2_engine_protocol(protocol: MatterSimXProtocol) -> dict:
    """Adapter only; no P2 scientific thresholds or adaptive policy are used."""
    return {
        "temperature_K": protocol.temperature_K,
        "timestep_fs": protocol.timestep_fs,
        "equil_steps": protocol.equilibration_steps,
        "production_steps": protocol.production_steps,
        "sample_interval_steps": protocol.sample_interval_steps,
        "thermostat": protocol.thermostat,
        "friction_fs_inv_provisional": protocol.friction_fs_inv,
        "fix_center_of_mass": protocol.fix_center_of_mass,
        # run_nvt's sampling abort guard expects this key. This is an
        # execution-safety bound, not an X scientific acceptance threshold.
        "explosion_abort_A_provisional": 3.0,
    }


def execute_mattersim_x_md(
    *,
    p1_payload: Mapping[str, Any],
    admission: MatterSimXExecutionSpec,
    protocol: MatterSimXProtocol,
    calculator_factory: Callable[[], Any] = _default_calculator,
    md_engine: Callable[..., dict] = run_nvt,
) -> dict:
    """Execute admitted MatterSim X MD without producing a scientific verdict."""
    binding = bind_protocol(admission, protocol)
    structure = _relaxed_structure(p1_payload, admission)

    calc = calculator_factory()
    record = md_engine(
        structure,
        calc,
        _p2_engine_protocol(protocol),
        protocol.seed,
        batch_id=admission.batch_id,
    )
    if not isinstance(record, dict):
        raise MatterSimXExecutionError("MD engine returned non-mapping record")

    return {
        "schema_version": "mattersim-x-md-execution-v1",
        "status": "EXECUTED" if record.get("completed") else "INCOMPLETE",
        "scientific_x_evidence": False,
        "scientific_verdict_changed": False,
        "binding": binding,
        "start_structure_sha256": admission.start_structure_sha256,
        "model_checkpoint_sha256": admission.checkpoint_sha256,
        "record": record,
    }
