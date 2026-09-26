"""MatterSim scientific-X transport execution protocol.

This module freezes the execution contract only. It does not run MD.
The protocol is intentionally explicit and must be bound to an admitted
MatterSimXExecutionSpec so that an independent-model transport comparison
cannot silently change temperature, species, estimator, or sampling scope.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from rudeus.science.contracts import Record, digest, require_hash
from rudeus.science.x_mattersim_scientific import MatterSimXExecutionSpec


@dataclass(frozen=True, kw_only=True)
class MatterSimXProtocol(Record):
    target_species: str
    temperature_K: float
    timestep_fs: float
    equilibration_steps: int
    production_steps: int
    sample_interval_steps: int
    thermostat: str
    ensemble: str
    cell_mode: str
    reference_frame: str
    lag_steps: tuple[int, ...]
    fit_window_ps: tuple[float, float]
    estimator_id: str
    seed: int
    source_p3_protocol_hash: str
    version: str = "mattersim-x-transport-v1"

    def validate(self):
        super().validate()
        require_hash(self.source_p3_protocol_hash)
        if self.version != "mattersim-x-transport-v1":
            raise ValueError("unsupported MatterSim X protocol version")
        if not self.target_species or not self.estimator_id:
            raise ValueError("MatterSim X protocol requires species and estimator")
        if self.temperature_K <= 0 or self.timestep_fs <= 0:
            raise ValueError("MatterSim X protocol requires positive temperature/timestep")
        if self.equilibration_steps < 0 or self.production_steps <= 0:
            raise ValueError("MatterSim X protocol requires positive production duration")
        if self.sample_interval_steps <= 0:
            raise ValueError("MatterSim X sample interval must be positive")
        if self.production_steps % self.sample_interval_steps != 0:
            raise ValueError("production steps must be divisible by sample interval")
        if self.thermostat != "langevin":
            raise ValueError("MatterSim X v1 supports only explicit Langevin thermostat")
        if self.ensemble != "NVT":
            raise ValueError("MatterSim X v1 supports only NVT")
        if self.cell_mode != "fixed":
            raise ValueError("MatterSim X v1 supports only fixed cell")
        if self.reference_frame != "simulation_cell":
            raise ValueError("MatterSim X v1 requires simulation_cell reference frame")
        if len(self.lag_steps) < 2 or any(
            isinstance(v, bool) or not isinstance(v, int) or v < 1
            for v in self.lag_steps
        ):
            raise ValueError("MatterSim X requires at least two positive integer lags")
        if any(a >= b for a, b in zip(self.lag_steps, self.lag_steps[1:])):
            raise ValueError("MatterSim X lag steps must be strictly increasing")
        if len(self.fit_window_ps) != 2 or not 0 <= self.fit_window_ps[0] < self.fit_window_ps[1]:
            raise ValueError("MatterSim X fit window is invalid")
        n_frames = self.production_steps // self.sample_interval_steps
        if max(self.lag_steps) >= n_frames:
            raise ValueError("MatterSim X lag exceeds available production frames")


def bind_protocol(
    admission: MatterSimXExecutionSpec,
    protocol: MatterSimXProtocol,
) -> dict:
    """Bind explicit transport protocol to an admitted scientific-X entrant."""
    if protocol.target_species != admission.target_species:
        raise ValueError("MatterSim X protocol target species mismatch")
    if protocol.temperature_K != admission.temperature_K:
        raise ValueError("MatterSim X protocol temperature mismatch")
    if protocol.source_p3_protocol_hash != admission.p3_protocol_hash:
        raise ValueError("MatterSim X protocol source P3 hash mismatch")

    return {
        "stage": "X",
        "purpose": "independent_transport_crosscheck",
        "admission_hash": admission.content_hash,
        "protocol_hash": protocol.content_hash,
        "candidate_id": admission.candidate_id,
        "batch_id": admission.batch_id,
        "trajectory_sha256": admission.trajectory_sha256,
        "model_identity": {
            "model_name": admission.model_name,
            "model_family": admission.model_family,
            "checkpoint_sha256": admission.checkpoint_sha256,
            "training_data_id": admission.training_data_id,
            "mattersim_version": admission.mattersim_version,
        },
        "protocol": protocol.to_dict(),
        "scientific_verdict_changed": False,
    }
