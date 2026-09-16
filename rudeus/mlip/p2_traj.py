"""P2 trajectory artifact: canonical persistence + deterministic hashing.

Persistence only — no science. This module closes the dangling
``trajectory_sha256`` problem: previously ``build_p2_result`` hashed
rounded in-memory positions and discarded the frames, leaving a hash
with no verifiable bytes behind it. Now the sampled production
trajectory is written atomically to
``data/batches/p2_traj/<batch_id>.npz`` and the P2 JSON binds to the
SHA256 of a canonical byte serialization of that artifact.

Design decisions (see task spec, P2 -> P2.5 handoff increment):

- WRAPPED Cartesian positions + cell are persisted, never unwrapped-only.
  The future P2.5 consumer re-unwraps with the single canonical
  ``rudeus.mlip.p2.unwrap_trajectory``. No second unwrapping convention
  is introduced here.
- Production frames only. The in-memory record mixes equilibration and
  production samples; the artifact slices to ``phase == "production"``
  and records the exact per-frame MD step indices, so the consumer never
  has to guess where production starts.
- Atom order is preserved exactly as sampled (ASE order inherited from
  ``Structure.from_dict(job["relaxed_structure_dict"])``). No reordering,
  no sorting, no new atom-ID scheme. The species vector is persisted
  explicitly so the artifact is self-describing.
- Fixed NVT cell: one canonical 3x3 matrix with
  ``cell_mode == "fixed"``. P2 runs fixed-cell Langevin NVT (no
  barostat), so repeating the cell per frame would be redundant bytes
  with no information.
- Deterministic hash (Option B): ``trajectory_sha256`` is SHA256 over a
  canonical byte stream (magic + canonical-JSON metadata + fixed-dtype,
  big-endian, C-order array bytes + length-prefixed UTF-8 species), NOT
  over raw NPZ file bytes (ZIP container metadata is not guaranteed
  deterministic). Same logical trajectory + same metadata -> identical
  hash across runs, machines, and temporary filenames. No timestamps, no
  filesystem paths, no hostnames, no wall-clock values enter the hash.
- Atomic write: temp file in the same directory -> flush/close ->
  reload + rehash verification -> atomic os.replace -> post-replace
  re-verification. Only then may the P2 JSON reference the artifact. A
  failed write raises and never touches a pre-existing valid artifact;
  no locks, no database, no service.
"""

from __future__ import annotations

import hashlib
import json
import os
import struct
from pathlib import Path
from typing import Any, Dict, List, Union

import numpy as np

#: Artifact format version, recorded in every artifact and P2 JSON binding.
P2_TRAJ_FORMAT_VERSION = "p2-traj-v1"

#: Default repository-relative directory for trajectory artifacts.
DEFAULT_P2_TRAJ_DIR = "data/batches/p2_traj"

#: Magic prefix of the canonical byte stream (domain separation).
_CANONICAL_MAGIC = b"P2TRAJ-v1\x00"

#: NPZ member names (storage convenience; the hash does NOT cover ZIP bytes).
_NPZ_POSITIONS = "positions"
_NPZ_CELL = "cell"
_NPZ_FRAME_STEPS = "frame_steps"
_NPZ_SPECIES = "species"
_NPZ_META = "meta_json"


class TrajectoryArtifactError(RuntimeError):
    """Raised when a trajectory artifact cannot be built, written, or verified.

    Fail-closed: callers must not produce an artifact-bound P2 result when
    this is raised, and must never silently fall back to the legacy
    dangling-hash behavior.
    """


# ---------------------------------------------------------------------------
# Logical payload construction (production-frame slice of a sampled record).
# ---------------------------------------------------------------------------

def build_traj_payload(record: Dict[str, Any], job: Dict[str, Any]) -> Dict[str, Any]:
    """Slice the production trajectory out of a sampled P2 record.

    Args:
        record: Sampled trajectory record as produced by
            ``_run_nvt_segments`` / ``run_nvt`` / ``run_nvt_adaptive``
            (``species``, ``cell``, ``frames`` with ``phase``/``positions``
            /``md_step``, ``timestep_fs``, ``sample_interval_steps``,
            ``equil_steps``, ``production_steps``, ``seed``).
        job: P2 job dict (``batch_id``, ``p2_config_hash``,
            ``p2_protocol`` carrying ``p2_protocol_version``).

    Returns:
        Logical payload dict with wrapped production-frame positions,
        the fixed cell, the explicit species vector, production-relative
        frame step indices, and identity metadata. No frame is invented:
        an empty production slice yields ``n_production_frames == 0``.

    Raises:
        TrajectoryArtifactError: on any structural defect or ordering
            violation (missing ``md_step``, non-monotonic steps,
            shape mismatches). Fail closed, never guess.
    """
    try:
        batch_id = job["batch_id"]
        config_hash = job["p2_config_hash"]
        protocol = job["p2_protocol"]
        species_all = [str(s) for s in record["species"]]
        cell = np.asarray(record["cell"], dtype=np.float64)
        interval = int(record["sample_interval_steps"])
        equil_steps = int(record["equil_steps"])
        prod_completed = int(record["production_steps"])
        timestep_fs = float(record["timestep_fs"])
        seed = int(record["seed"])
    except (KeyError, TypeError, ValueError) as e:
        raise TrajectoryArtifactError(
            f"trajectory payload: missing or invalid record/job field: {e}")

    if cell.shape != (3, 3):
        raise TrajectoryArtifactError(
            f"trajectory payload: cell must be 3x3, got shape {cell.shape}")
    if not np.all(np.isfinite(cell)):
        raise TrajectoryArtifactError(
            "trajectory payload: cell contains non-finite values")
    if interval <= 0:
        raise TrajectoryArtifactError(
            f"trajectory payload: invalid sample_interval_steps={interval}")
    if equil_steps < 0 or prod_completed < 0:
        raise TrajectoryArtifactError(
            "trajectory payload: negative equil/production step counts")

    protocol_version = str(protocol.get("p2_protocol_version",
                                        "p2-unversioned"))
    n_atoms = len(species_all)

    prod_frames = [f for f in record.get("frames", [])
                   if f.get("phase") == "production"]
    positions_list: List[np.ndarray] = []
    md_steps: List[int] = []
    for f in prod_frames:
        if "md_step" not in f:
            raise TrajectoryArtifactError(
                "trajectory payload: production frame lacks 'md_step'; "
                "refusing to reconstruct frame indices from array position")
        try:
            step = int(f["md_step"])
        except (TypeError, ValueError):
            raise TrajectoryArtifactError(
                "trajectory payload: non-integer frame 'md_step'")
        pos = np.asarray(f["positions"], dtype=np.float64)
        if pos.shape != (n_atoms, 3):
            raise TrajectoryArtifactError(
                f"trajectory payload: frame positions shape {pos.shape} "
                f"does not match (n_atoms, 3)={(n_atoms, 3)}")
        if not np.all(np.isfinite(pos)):
            raise TrajectoryArtifactError(
                "trajectory payload: frame positions contain non-finite "
                "values; refusing to persist a corrupt trajectory")
        positions_list.append(np.ascontiguousarray(pos, dtype=np.float64))
        md_steps.append(step)

    # Production-relative 1-based MD step indices (total steps minus equil).
    frame_steps = np.array([s - equil_steps for s in md_steps], dtype=np.int64)
    if len(frame_steps):
        if bool((frame_steps <= 0).any()):
            raise TrajectoryArtifactError(
                "trajectory payload: production frame step indices must be "
                "positive (frame sampled at or before equil end)")
        if bool((np.diff(frame_steps) <= 0).any()):
            raise TrajectoryArtifactError(
                "trajectory payload: production frame steps not strictly "
                "increasing; atom/frame ordering cannot be trusted")
        raw = np.array(md_steps, dtype=np.int64)
        if bool((raw % interval != 0).any()):
            raise TrajectoryArtifactError(
                "trajectory payload: frame md_steps violate the sampling "
                "cadence (not multiples of sample_interval_steps)")

    positions = (np.stack(positions_list, axis=0)
                 if positions_list
                 else np.zeros((0, n_atoms, 3), dtype=np.float64))

    return {
        "format_version": P2_TRAJ_FORMAT_VERSION,
        "batch_id": str(batch_id),
        "species": species_all,
        "cell": np.ascontiguousarray(cell, dtype=np.float64),
        "cell_mode": "fixed",
        "positions": positions,
        "frame_steps": np.ascontiguousarray(frame_steps, dtype=np.int64),
        "n_production_frames": int(len(frame_steps)),
        "n_atoms": int(n_atoms),
        "timestep_fs": timestep_fs,
        "sample_interval_steps": int(interval),
        "equil_steps": int(equil_steps),
        "production_steps_completed": int(prod_completed),
        "seed": int(seed),
        "p2_config_hash": str(config_hash),
        "p2_protocol_version": str(protocol_version),
    }


# ---------------------------------------------------------------------------
# Canonical byte serialization + deterministic SHA256 (hash contract).
# ---------------------------------------------------------------------------

def _canonical_meta(payload: Dict[str, Any]) -> Dict[str, Any]:
    """JSON-safe metadata subset covered by the canonical hash."""
    return {
        "format_version": payload["format_version"],
        "batch_id": payload["batch_id"],
        "cell_mode": payload["cell_mode"],
        "n_production_frames": payload["n_production_frames"],
        "n_atoms": payload["n_atoms"],
        "timestep_fs": payload["timestep_fs"],
        "sample_interval_steps": payload["sample_interval_steps"],
        "equil_steps": payload["equil_steps"],
        "production_steps_completed": payload["production_steps_completed"],
        "seed": payload["seed"],
        "p2_config_hash": payload["p2_config_hash"],
        "p2_protocol_version": payload["p2_protocol_version"],
    }


def canonical_traj_bytes(payload: Dict[str, Any]) -> bytes:
    """Deterministic byte serialization of a logical trajectory payload.

    Layout (all integers big-endian, all floats big-endian IEEE 754):

    - magic ``b"P2TRAJ-v1\\x00"``
    - u32 length + canonical-JSON metadata (sort_keys, compact
      separators, ASCII) covering format version, batch identity,
      shapes, sampling parameters, seed, config hash, protocol version
    - u64 n_production_frames + u64 n_atoms
    - positions as big-endian float64, C order
      (n_frames, n_atoms, 3), wrapped Cartesian Angstrom
    - cell as big-endian float64, C order (3, 3)
    - frame_steps as big-endian int64, C order (production-relative
      1-based MD step indices)
    - u32 species count, then per species u32 length + UTF-8 bytes
      (exact ASE order; no reordering)

    Same logical payload -> identical bytes on any machine. Timestamps,
    paths, hostnames, and ZIP container metadata are never included.
    """
    meta_json = json.dumps(_canonical_meta(payload), sort_keys=True,
                           separators=(",", ":"), ensure_ascii=True)
    meta_raw = meta_json.encode("ascii")
    n_frames = int(payload["n_production_frames"])
    n_atoms = int(payload["n_atoms"])
    pos = np.ascontiguousarray(payload["positions"], dtype=">f8")
    cell = np.ascontiguousarray(payload["cell"], dtype=">f8")
    steps = np.ascontiguousarray(payload["frame_steps"], dtype=">i8")
    if pos.shape != (n_frames, n_atoms, 3):
        raise TrajectoryArtifactError(
            f"canonical bytes: positions shape {pos.shape} inconsistent "
            f"with ({n_frames}, {n_atoms}, 3)")
    if cell.shape != (3, 3):
        raise TrajectoryArtifactError(
            f"canonical bytes: cell shape {cell.shape} != (3, 3)")
    if steps.shape != (n_frames,):
        raise TrajectoryArtifactError(
            "canonical bytes: frame_steps length inconsistent with "
            "n_production_frames")

    out = bytearray()
    out += _CANONICAL_MAGIC
    out += struct.pack(">I", len(meta_raw))
    out += meta_raw
    out += struct.pack(">Q", n_frames)
    out += struct.pack(">Q", n_atoms)
    out += pos.tobytes(order="C")
    out += cell.tobytes(order="C")
    out += steps.tobytes(order="C")
    species = [str(s) for s in payload["species"]]
    if len(species) != n_atoms:
        raise TrajectoryArtifactError(
            "canonical bytes: species count inconsistent with n_atoms")
    out += struct.pack(">I", len(species))
    for s in species:
        raw = s.encode("utf-8")
        out += struct.pack(">I", len(raw))
        out += raw
    return bytes(out)


def traj_sha256(payload: Dict[str, Any]) -> str:
    """SHA256 hex digest of the canonical trajectory serialization."""
    return hashlib.sha256(canonical_traj_bytes(payload)).hexdigest()


# ---------------------------------------------------------------------------
# NPZ storage (convenience container; the hash covers canonical bytes).
# ---------------------------------------------------------------------------

def _payload_to_npz_arrays(payload: Dict[str, Any]) -> Dict[str, np.ndarray]:
    meta_json = json.dumps(_canonical_meta(payload), sort_keys=True,
                           separators=(",", ":"), ensure_ascii=True)
    return {
        _NPZ_POSITIONS: np.ascontiguousarray(payload["positions"],
                                             dtype=np.float64),
        _NPZ_CELL: np.ascontiguousarray(payload["cell"], dtype=np.float64),
        _NPZ_FRAME_STEPS: np.ascontiguousarray(payload["frame_steps"],
                                               dtype=np.int64),
        _NPZ_SPECIES: np.array([str(s) for s in payload["species"]],
                               dtype=str),
        _NPZ_META: np.array(meta_json),
    }


def load_traj_artifact(path: Union[str, Path]) -> Dict[str, Any]:
    """Load a persisted artifact back into a logical payload dict.

    Raises:
        TrajectoryArtifactError: file missing, unreadable, or structurally
            invalid (wrong members, shapes, dtypes, format version).
    """
    path = Path(path)
    if not path.is_file():
        raise TrajectoryArtifactError(
            f"trajectory artifact missing: {path}")
    try:
        with np.load(str(path), allow_pickle=False) as z:
            names = set(z.files)
            missing = {_NPZ_POSITIONS, _NPZ_CELL, _NPZ_FRAME_STEPS,
                       _NPZ_SPECIES, _NPZ_META} - names
            if missing:
                raise TrajectoryArtifactError(
                    f"trajectory artifact {path.name}: missing members "
                    f"{sorted(missing)}")
            positions = np.ascontiguousarray(z[_NPZ_POSITIONS],
                                             dtype=np.float64)
            cell = np.ascontiguousarray(z[_NPZ_CELL], dtype=np.float64)
            frame_steps = np.ascontiguousarray(z[_NPZ_FRAME_STEPS],
                                               dtype=np.int64)
            species = [str(s) for s in z[_NPZ_SPECIES].tolist()]
            meta = json.loads(str(z[_NPZ_META].item()))
    except TrajectoryArtifactError:
        raise
    except Exception as e:
        raise TrajectoryArtifactError(
            f"trajectory artifact {path.name} unreadable: "
            f"{type(e).__name__}: {e}")

    if not isinstance(meta, dict):
        raise TrajectoryArtifactError(
            f"trajectory artifact {path.name}: corrupt metadata member")
    if meta.get("format_version") != P2_TRAJ_FORMAT_VERSION:
        raise TrajectoryArtifactError(
            f"trajectory artifact {path.name}: unsupported format_version "
            f"{meta.get('format_version')!r} "
            f"(expected {P2_TRAJ_FORMAT_VERSION!r})")
    if meta.get("cell_mode") != "fixed":
        raise TrajectoryArtifactError(
            f"trajectory artifact {path.name}: unsupported cell_mode "
            f"{meta.get('cell_mode')!r}")
    if positions.ndim != 3 or positions.shape[1:] != (meta.get("n_atoms"), 3):
        raise TrajectoryArtifactError(
            f"trajectory artifact {path.name}: positions shape "
            f"{positions.shape} inconsistent with metadata")
    if cell.shape != (3, 3):
        raise TrajectoryArtifactError(
            f"trajectory artifact {path.name}: cell shape {cell.shape}")
    if frame_steps.shape != (positions.shape[0],):
        raise TrajectoryArtifactError(
            f"trajectory artifact {path.name}: frame_steps length "
            f"inconsistent with positions")
    if len(species) != meta.get("n_atoms"):
        raise TrajectoryArtifactError(
            f"trajectory artifact {path.name}: species count inconsistent "
            f"with metadata")

    payload = dict(meta)
    payload.update({
        "species": species,
        "cell": cell,
        "cell_mode": "fixed",
        "positions": positions,
        "frame_steps": frame_steps,
    })
    return payload


def verify_traj_artifact(path: Union[str, Path],
                         expected_sha256: str) -> Dict[str, Any]:
    """Load an artifact and verify it against the recorded SHA256.

    Returns the logical payload on success. Raises
    TrajectoryArtifactError when the file is missing, malformed, or its
    canonical hash differs (corruption, truncation, or wrong trajectory).
    """
    payload = load_traj_artifact(path)
    actual = traj_sha256(payload)
    if actual != str(expected_sha256):
        raise TrajectoryArtifactError(
            f"trajectory artifact {Path(path).name}: SHA256 mismatch: "
            f"file={actual} expected={expected_sha256}")
    return payload


def write_traj_artifact(path: Union[str, Path],
                        payload: Dict[str, Any]) -> str:
    """Atomically write a trajectory artifact; return its canonical SHA256.

    Protocol: serialize NPZ to a temp file in the SAME directory, reload
    and rehash-verify the temp file, atomically replace the target via
    os.replace, then re-verify the final file. Only a verified file is
    ever referenced by P2 JSON.

    A failure raises TrajectoryArtifactError, cleans up the temp file
    (best effort), and never modifies or deletes a pre-existing valid
    target. No locks, no database, no service.
    """
    path = Path(path)
    expected = traj_sha256(payload)  # validates logical payload eagerly
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        raise TrajectoryArtifactError(
            f"trajectory artifact: cannot create directory "
            f"{path.parent}: {e}")

    tmp = path.parent / f"{path.name}.tmp-{os.getpid()}"
    try:
        with open(tmp, "wb") as f:
            np.savez_compressed(f, **_payload_to_npz_arrays(payload))
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass  # best effort; atomicity comes from os.replace
        # Verify the temp file BEFORE it becomes visible at the target.
        verify_traj_artifact(tmp, expected)
        os.replace(tmp, path)
        # Verify the final file AFTER the replace; only then may the
        # caller bind the P2 JSON to `expected`.
        verify_traj_artifact(path, expected)
    except TrajectoryArtifactError:
        raise
    except Exception as e:
        raise TrajectoryArtifactError(
            f"trajectory artifact write failed for {path.name}: "
            f"{type(e).__name__}: {e}")
    finally:
        try:
            if tmp.exists():
                if tmp.resolve() != path.resolve():
                    tmp.unlink()
                # else: tmp IS the target (pathological); leave it.
        except OSError:
            pass
    return expected
