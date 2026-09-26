"""MatterSim X trajectory persistence and D_self extraction.

This module owns X-only trajectory artifacts. It never emits a scientific
agreement/disagreement verdict. It persists the MatterSim MD execution record,
verifies byte identity, reconstructs wrapped coordinates, and derives a scalar
D_self observation candidate under the frozen X protocol.
"""

from __future__ import annotations

import hashlib
import json
import os
import struct
import tempfile
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from rudeus.mlip.p2 import unwrap_trajectory
from rudeus.mlip.p3_transport import fit_self_diffusion
from rudeus.science.contracts import digest
from rudeus.science.x_mattersim_protocol import MatterSimXProtocol
from rudeus.science.x_mattersim_scientific import MatterSimXExecutionSpec

X_TRAJ_FORMAT_VERSION = "x-mattersim-traj-v1"
_MAGIC = b"XMATTERSIMTRAJ-v1\x00"


class MatterSimXArtifactError(RuntimeError):
    pass


def _production_frames(record: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [f for f in record.get("frames", []) if f.get("phase") == "production"]


def build_x_traj_payload(
    execution: Mapping[str, Any],
    admission: MatterSimXExecutionSpec,
    protocol: MatterSimXProtocol,
) -> dict:
    if execution.get("scientific_x_evidence") is not False:
        raise MatterSimXArtifactError("execution payload must remain non-scientific")
    if execution.get("start_structure_sha256") != admission.start_structure_sha256:
        raise MatterSimXArtifactError("execution start-structure binding mismatch")
    if execution.get("model_checkpoint_sha256") != admission.checkpoint_sha256:
        raise MatterSimXArtifactError("execution checkpoint binding mismatch")
    record = execution.get("record")
    if not isinstance(record, Mapping):
        raise MatterSimXArtifactError("execution record missing")
    if not record.get("completed"):
        raise MatterSimXArtifactError("incomplete X MD cannot yield trajectory evidence")

    species = [str(s) for s in record.get("species", [])]
    cell = np.asarray(record.get("cell"), dtype=np.float64)
    if cell.shape != (3, 3) or not np.all(np.isfinite(cell)):
        raise MatterSimXArtifactError("invalid fixed cell")
    n_atoms = len(species)

    frames = _production_frames(record)
    positions = []
    steps = []
    for frame in frames:
        if "md_step" not in frame:
            raise MatterSimXArtifactError("X production frame missing md_step")
        pos = np.asarray(frame.get("positions"), dtype=np.float64)
        if pos.shape != (n_atoms, 3) or not np.all(np.isfinite(pos)):
            raise MatterSimXArtifactError("invalid X production positions")
        positions.append(pos)
        steps.append(int(frame["md_step"]) - int(protocol.equilibration_steps))

    step_arr = np.asarray(steps, dtype=np.int64)
    if len(step_arr):
        if np.any(step_arr <= 0) or np.any(np.diff(step_arr) <= 0):
            raise MatterSimXArtifactError("invalid X production frame ordering")
    pos_arr = np.stack(positions) if positions else np.zeros((0, n_atoms, 3), dtype=np.float64)

    return {
        "format_version": X_TRAJ_FORMAT_VERSION,
        "candidate_id": admission.candidate_id,
        "batch_id": admission.batch_id,
        "species": species,
        "cell": cell,
        "cell_mode": "fixed",
        "positions": pos_arr,
        "frame_steps": step_arr,
        "n_atoms": n_atoms,
        "n_production_frames": int(len(step_arr)),
        "timestep_fs": float(protocol.timestep_fs),
        "sample_interval_steps": int(protocol.sample_interval_steps),
        "equilibration_steps": int(protocol.equilibration_steps),
        "production_steps": int(protocol.production_steps),
        "seed": int(protocol.seed),
        "target_species": protocol.target_species,
        "temperature_K": float(protocol.temperature_K),
        "protocol_hash": protocol.content_hash,
        "admission_hash": admission.content_hash,
        "start_structure_sha256": admission.start_structure_sha256,
        "model_checkpoint_sha256": admission.checkpoint_sha256,
    }


def _meta(payload: Mapping[str, Any]) -> dict:
    return {k: payload[k] for k in (
        "format_version", "candidate_id", "batch_id", "cell_mode", "n_atoms",
        "n_production_frames", "timestep_fs", "sample_interval_steps",
        "equilibration_steps", "production_steps", "seed", "target_species",
        "temperature_K", "protocol_hash", "admission_hash",
        "start_structure_sha256", "model_checkpoint_sha256",
    )}


def canonical_x_traj_bytes(payload: Mapping[str, Any]) -> bytes:
    meta = json.dumps(_meta(payload), sort_keys=True, separators=(",", ":")).encode("ascii")
    pos = np.ascontiguousarray(payload["positions"], dtype=">f8")
    cell = np.ascontiguousarray(payload["cell"], dtype=">f8")
    steps = np.ascontiguousarray(payload["frame_steps"], dtype=">i8")
    species = [str(s) for s in payload["species"]]

    if pos.shape != (int(payload["n_production_frames"]), int(payload["n_atoms"]), 3):
        raise MatterSimXArtifactError("X positions shape mismatch")
    if cell.shape != (3, 3):
        raise MatterSimXArtifactError("X cell shape mismatch")
    if steps.shape != (int(payload["n_production_frames"]),):
        raise MatterSimXArtifactError("X frame step shape mismatch")
    if len(species) != int(payload["n_atoms"]):
        raise MatterSimXArtifactError("X species count mismatch")

    out = bytearray(_MAGIC)
    out += struct.pack(">I", len(meta)) + meta
    out += pos.tobytes(order="C")
    out += cell.tobytes(order="C")
    out += steps.tobytes(order="C")
    out += struct.pack(">I", len(species))
    for s in species:
        raw = s.encode("utf-8")
        out += struct.pack(">I", len(raw)) + raw
    return bytes(out)


def x_traj_sha256(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_x_traj_bytes(payload)).hexdigest()


def write_x_traj_artifact(path: str | Path, payload: Mapping[str, Any]) -> str:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sha = x_traj_sha256(payload)
    arrays = {
        "positions": np.asarray(payload["positions"], dtype=np.float64),
        "cell": np.asarray(payload["cell"], dtype=np.float64),
        "frame_steps": np.asarray(payload["frame_steps"], dtype=np.int64),
        "species": np.asarray(payload["species"], dtype=str),
        "meta_json": np.array(json.dumps(_meta(payload), sort_keys=True, separators=(",", ":"))),
    }
    fd, tmp = tempfile.mkstemp(prefix=".xtraj-", suffix=".npz", dir=path.parent)
    os.close(fd)
    try:
        np.savez_compressed(tmp, **arrays)
        loaded = load_x_traj_artifact(tmp)
        if x_traj_sha256(loaded) != sha:
            raise MatterSimXArtifactError("X trajectory write verification failed")
        if path.exists():
            prior = load_x_traj_artifact(path)
            if x_traj_sha256(prior) != sha:
                raise MatterSimXArtifactError("refusing to overwrite different X trajectory")
            return sha
        os.replace(tmp, path)
        tmp = None
    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)
    return sha


def load_x_traj_artifact(path: str | Path) -> dict:
    path = Path(path)
    if not path.is_file():
        raise MatterSimXArtifactError("X trajectory artifact missing")
    try:
        with np.load(path, allow_pickle=False) as z:
            meta = json.loads(str(z["meta_json"].item()))
            payload = dict(meta)
            payload["positions"] = np.asarray(z["positions"], dtype=np.float64)
            payload["cell"] = np.asarray(z["cell"], dtype=np.float64)
            payload["frame_steps"] = np.asarray(z["frame_steps"], dtype=np.int64)
            payload["species"] = [str(x) for x in z["species"].tolist()]
    except Exception as exc:
        raise MatterSimXArtifactError(f"unreadable X trajectory: {type(exc).__name__}") from exc
    if payload.get("format_version") != X_TRAJ_FORMAT_VERSION:
        raise MatterSimXArtifactError("unsupported X trajectory format")
    canonical_x_traj_bytes(payload)
    return payload


def estimate_x_d_self(payload: Mapping[str, Any], protocol: MatterSimXProtocol) -> dict:
    if payload.get("protocol_hash") != protocol.content_hash:
        raise MatterSimXArtifactError("X trajectory protocol mismatch")
    if payload.get("target_species") != protocol.target_species:
        raise MatterSimXArtifactError("X trajectory target species mismatch")
    positions = np.asarray(payload["positions"], dtype=float)
    if len(positions) < 3:
        raise MatterSimXArtifactError("insufficient X production frames")

    idx = [i for i, s in enumerate(payload["species"]) if s == protocol.target_species]
    if not idx:
        raise MatterSimXArtifactError("target species absent from X trajectory")

    unwrapped = unwrap_trajectory(positions, np.asarray(payload["cell"], dtype=float))
    mobile = unwrapped[:, idx, :]
    frame_steps = np.asarray(payload["frame_steps"], dtype=int)

    lag_times = []
    msd = []
    for lag in protocol.lag_steps:
        if lag >= len(mobile):
            raise MatterSimXArtifactError("protocol lag exceeds X trajectory")
        disp = mobile[lag:] - mobile[:-lag]
        msd.append(float(np.mean(np.sum(disp * disp, axis=-1))))
        lag_times.append(
            float(lag * protocol.sample_interval_steps * protocol.timestep_fs / 1000.0)
        )

    selected_t, selected_msd = zip(*[
        (t, m) for t, m in zip(lag_times, msd)
        if protocol.fit_window_ps[0] <= t <= protocol.fit_window_ps[1]
    ])
    if len(selected_t) < 2:
        raise MatterSimXArtifactError("fewer than two X lags in fit window")

    fit = fit_self_diffusion(time_ps=selected_t, msd_A2=selected_msd)
    return {
        "quantity": "D_self",
        "units": "m2/s",
        "value": float(fit["D_m2_per_s"]),
        "estimator_id": protocol.estimator_id,
        "trajectory_sha256": x_traj_sha256(payload),
        "n_mobile_ions": len(idx),
        "lag_times_ps": lag_times,
        "msd_A2": msd,
        "fit": fit,
        "scientific_verdict_changed": False,
    }
