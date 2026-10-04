"""Replicate-level bootstrap over verified calibration diagnostic observations.

Resampling infrastructure only: draws replicate-level (signed/absolute
error) observations with replacement and persists the resulting bootstrap
distributions of mean signed/absolute error. The output is a descriptive
resampling distribution, NOT a confidence interval, NOT coverage, NOT
qualification. No thresholds, no verdicts, no acceptance logic.

Resampling unit is the calibration replicate. Trajectory frames, atoms,
displacements, moments, and estimator internals are never resampled.
Determinism: explicit seed + explicit iteration count + NumPy PCG64 Generator.
"""

from __future__ import annotations

import json

import numpy as np

from rudeus.execution.contracts import ExecutionError
from rudeus.science.calibration import CalibrationDatasetManifest, CalibrationReplicateManifest
from rudeus.science.calibration_store import CalibrationStore
from rudeus.science.calibration_validation import VALID, validate_dataset
from rudeus.science.contracts import canonical_bytes, digest, require_hash
from rudeus.science.evidence import append_file, inside, integrity_errors, require


ESTIMATOR_NAME = "analyze_trajectory"
ESTIMATOR_MODULE = "rudeus.science.transport"
RESAMPLE_FORMAT = "calibration-bootstrap-v1"
RNG_ALGORITHM = "numpy.random.Generator(PCG64)"


def _fail(message, failure_class="INTEGRITY"):
    raise ExecutionError(message, failure_class)


def _read_verified_json(artifact_root, directory, filename):
    try:
        data = inside(artifact_root, f"{directory}/{filename}").read_bytes()
    except (OSError, ValueError) as exc:
        _fail(f"calibration record is unavailable: {type(exc).__name__}")
    try:
        decoded = json.loads(data)
    except ValueError:
        _fail("calibration record bytes are not JSON")
    if not isinstance(decoded, dict):
        _fail("calibration record must be a JSON object")
    try:
        require(digest(decoded) == filename.removesuffix(".json"),
                "calibration record filename does not match content")
        require(canonical_bytes(decoded) == data,
                "calibration record bytes are not canonical")
    except ExecutionError:
        _fail("calibration record failed verification")
    return decoded


def _finite_number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(f"calibration diagnostic {name} must be numeric")
    if not np.isfinite(value):
        _fail(f"calibration diagnostic {name} must be finite")
    return float(value)


def bootstrap_calibration_diagnostics(
    *,
    calibration_store: CalibrationStore,
    artifact_root,
    dataset_manifest_hash: str,
    diagnostic_hash: str,
    replicate_ids,
    species: str,
    estimator_config,
    code_revision: str,
    seed: int,
    n_bootstrap: int,
) -> dict:
    """Bootstrap mean signed/absolute error over replicate-level observations.

    Args:
        diagnostic_hash: content hash of the persisted diagnostic record
            (file ``calibration_diagnostics/{hash}.json``).
        replicate_ids: explicit non-empty selection of replicate IDs. All
            must share one parameter cell; nothing is inferred or mixed.
        species: scalar species whose diagnostic entries are consumed.
        estimator_config: exact estimator configuration; the diagnostic
            record must carry byte-identical canonical configuration.
        code_revision: required code revision recorded on the diagnostic.
        seed: explicit integer seed for the PCG64 generator.
        n_bootstrap: explicit positive integer iteration count.

    Returns ``{"bootstrap_hash", "diagnostic_hash", "dataset_manifest_hash",
    "n_observations", "n_bootstrap", "artifact_status": "RESAMPLED"}``.
    Every lineage, binding, or ambiguity failure raises ``ExecutionError``.
    """
    from pathlib import Path
    root = Path(artifact_root).resolve()
    if isinstance(seed, bool) or not isinstance(seed, int):
        _fail("calibration resampling seed must be an integer", "UNSUPPORTED_INPUT")
    if isinstance(n_bootstrap, bool) or not isinstance(n_bootstrap, int) \
            or n_bootstrap < 1:
        _fail("calibration bootstrap count must be a positive integer",
              "UNSUPPORTED_INPUT")
    if not isinstance(species, str) or not species:
        _fail("calibration resampling species must be a nonempty string")
    if not isinstance(code_revision, str) or not code_revision:
        _fail("calibration resampling code revision must be a nonempty string")
    if not isinstance(estimator_config, dict):
        _fail("calibration resampling estimator configuration must be a mapping")
    for label, identity in (("dataset", dataset_manifest_hash),
                            ("diagnostic", diagnostic_hash)):
        try:
            require_hash(identity)
        except ValueError:
            _fail(f"calibration {label} identity must be a content hash")
    try:
        expected_config = canonical_bytes(
            {**estimator_config, "charge_numbers": estimator_config.get("charge_numbers")})
    except (ValueError, TypeError):
        _fail("calibration resampling estimator configuration is not canonical")
    if not isinstance(replicate_ids, (list, tuple)) or not replicate_ids \
            or len(set(replicate_ids)) != len(replicate_ids) \
            or any(not isinstance(rep, str) or not rep for rep in replicate_ids):
        _fail("calibration resampling selection must be a nonempty unique ID list")

    if validate_dataset(calibration_store, dataset_manifest_hash).status != VALID:
        _fail("calibration dataset lineage is not valid")
    try:
        dataset = calibration_store.retrieve(
            CalibrationDatasetManifest, dataset_manifest_hash)
    except ExecutionError:
        _fail("calibration dataset lineage is not valid")
    diagnostic = _read_verified_json(root, "calibration_diagnostics",
                                     f"{diagnostic_hash}.json")
    if diagnostic.get("format") != "calibration-error-diagnostic-v1":
        _fail("calibration diagnostic has an unsupported format", "UNSUPPORTED_INPUT")
    if diagnostic.get("dataset_manifest_hash") != dataset_manifest_hash:
        _fail("calibration diagnostic does not belong to the dataset")
    if diagnostic.get("species") != species:
        _fail("calibration diagnostic species mismatch")
    if diagnostic.get("code_revision") != code_revision:
        _fail("calibration diagnostic code revision mismatch")
    try:
        require(canonical_bytes(diagnostic.get("estimator_config")) == expected_config,
                "calibration diagnostic estimator configuration mismatch")
    except ExecutionError:
        _fail("calibration diagnostic estimator configuration mismatch")
    if any(rep not in diagnostic.get("entries", {}) for rep in replicate_ids):
        _fail("calibration resampling selection has no diagnostic entry")

    try:
        manifests = {}
        for rep in replicate_ids:
            found = [path for path in
                     (calibration_store.root / "calibration_replicates").glob("*.json")
                     if json.loads(path.read_bytes())["replicate_id"] == rep]
            if len(found) != 1:
                _fail("calibration replicate manifest is ambiguous or missing")
            decoded = json.loads(found[0].read_bytes())
            require(digest(decoded) == found[0].stem,
                    "calibration replicate manifest failed verification")
            manifests[rep] = CalibrationReplicateManifest.from_dict(decoded)
    except ExecutionError:
        raise
    except (OSError, ValueError, KeyError) as exc:
        _fail(f"calibration replicate manifests are unavailable: {type(exc).__name__}")

    cells = set()
    signed, absolute = [], []
    for rep in replicate_ids:
        manifest = manifests[rep]
        if manifest.dataset_id != dataset.dataset_id:
            _fail("calibration replicate does not belong to the dataset")
        entry = diagnostic["entries"][rep]
        if entry["parameter_cell_id"] not in dataset.parameter_cell_ids:
            _fail("calibration parameter-cell mismatch")
        if manifest.parameter_cell_id != entry["parameter_cell_id"]:
            _fail("calibration parameter-cell mismatch")
        estimator_hash = entry.get("estimator_result_hash")
        try:
            require_hash(estimator_hash)
            estimator_path = inside(root, f"estimator_results/{estimator_hash}.json")
            estimator_bytes = estimator_path.read_bytes()
            estimator_decoded = json.loads(estimator_bytes)
            require(digest(estimator_decoded) == estimator_hash,
                    "calibration estimator result hash mismatch")
            require(canonical_bytes(estimator_decoded) == estimator_bytes,
                    "calibration estimator result bytes are not canonical")
        except (ExecutionError, ValueError, OSError):
            _fail("calibration estimator result failed verification")
        cells.add(entry["parameter_cell_id"])
        signed.append(_finite_number(entry.get("signed_error"), "signed_error"))
        absolute.append(_finite_number(entry.get("absolute_error"), "absolute_error"))
    if len(cells) > 1:
        _fail("calibration resampling population mixes parameter cells")
    cell = next(iter(cells))

    signed = np.asarray(signed, dtype=float)
    absolute = np.asarray(absolute, dtype=float)
    count = len(replicate_ids)
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, count, size=(n_bootstrap, count)).tolist()
    index_array = np.asarray(indices, dtype=int)
    signed_means = np.mean(signed[index_array], axis=1).tolist()
    absolute_means = np.mean(absolute[index_array], axis=1).tolist()
    result = {
        "format": RESAMPLE_FORMAT,
        "dataset_manifest_hash": dataset_manifest_hash,
        "diagnostic_hash": diagnostic_hash,
        "replicate_ids": sorted(replicate_ids),
        "parameter_cell_id": cell,
        "species": species,
        "estimator": ESTIMATOR_NAME,
        "estimator_module": ESTIMATOR_MODULE,
        "estimator_config": json.loads(expected_config.decode("utf-8")),
        "estimator_config_hash": digest(json.loads(expected_config.decode("utf-8"))),
        "source_signed_errors": signed.tolist(),
        "source_absolute_errors": absolute.tolist(),
        "rng": {"algorithm": RNG_ALGORITHM, "seed": seed,
                "numpy_version": np.__version__},
        "n_observations": count,
        "n_bootstrap": n_bootstrap,
        "bootstrap_indices": indices,
        "signed_error_means": signed_means,
        "absolute_error_means": absolute_means,
        "code_revision": code_revision,
        "numpy_version": np.__version__,
    }
    with integrity_errors():
        data = canonical_bytes(result)
        identity = digest(result)
        append_file(inside(root, f"calibration_resamples/{identity}.json"), data)
        stored = inside(root, f"calibration_resamples/{identity}.json").read_bytes()
        require(stored == data, "stored resample differs from canonical resample")
    return {"bootstrap_hash": identity,
            "diagnostic_hash": diagnostic_hash,
            "dataset_manifest_hash": dataset_manifest_hash,
            "n_observations": count,
            "n_bootstrap": n_bootstrap,
            "artifact_status": "RESAMPLED"}


__all__ = ["ESTIMATOR_NAME", "ESTIMATOR_MODULE", "RESAMPLE_FORMAT", "RNG_ALGORITHM",
           "bootstrap_calibration_diagnostics"]
