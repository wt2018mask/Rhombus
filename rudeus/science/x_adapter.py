"""Production adapter for external stage-X model results.

The external model runner is intentionally out of scope here. This adapter
ingests one already-produced scalar result, binds it to explicit X model/input
identities, hashes the exact raw result bytes, and emits a canonical
XObservation. It never executes a model and never changes scientific verdicts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping

from rudeus.science.contracts import canonical_bytes
from rudeus.science.xcheck import XInputBinding, XModelIdentity, XObservation


_RESULT_FIELDS = {"quantity", "units", "value", "estimator_id"}


def _read_json(path: Path) -> tuple[bytes, Mapping[str, Any]]:
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return raw, value


def adapt_x_result(
    *,
    model: XModelIdentity,
    binding: XInputBinding,
    raw_result_bytes: bytes,
    result: Mapping[str, Any],
) -> XObservation:
    """Bind one exact raw external-model result to an X observation."""
    if set(result) != _RESULT_FIELDS:
        raise ValueError("X raw result schema mismatch")
    if result["quantity"] != binding.quantity or result["units"] != binding.units:
        raise ValueError("X raw result quantity/units mismatch")
    estimator_id = result["estimator_id"]
    if not isinstance(estimator_id, str) or not estimator_id:
        raise ValueError("X raw result requires estimator_id")

    value = result["value"]
    if value is not None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("X raw result value must be numeric or null")
        value = float(value)
        if not __import__("math").isfinite(value):
            raise ValueError("X raw result value must be finite")

    return XObservation(
        model_hash=model.content_hash,
        input_binding_hash=binding.content_hash,
        quantity=binding.quantity,
        units=binding.units,
        value=value,
        evidence_hash=hashlib.sha256(raw_result_bytes).hexdigest(),
        estimator_id=estimator_id,
    )


def adapt_files(*, model_path: Path, binding_path: Path, result_path: Path) -> XObservation:
    _, model_payload = _read_json(model_path)
    _, binding_payload = _read_json(binding_path)
    result_raw, result_payload = _read_json(result_path)
    model = XModelIdentity.from_dict(model_payload)
    binding = XInputBinding.from_dict(binding_payload)
    return adapt_x_result(
        model=model,
        binding=binding,
        raw_result_bytes=result_raw,
        result=result_payload,
    )


def write_observation(path: Path, observation: XObservation) -> None:
    """Append-only atomic publication of one canonical X observation."""
    data = canonical_bytes(observation)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != data:
            raise FileExistsError("refusing to overwrite different X observation")
        return

    fd, temporary = tempfile.mkstemp(prefix=".x-observation-pending-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            if path.read_bytes() != data:
                raise FileExistsError("refusing to overwrite different X observation")
    finally:
        Path(temporary).unlink(missing_ok=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Bind an external model result to stage-X evidence")
    parser.add_argument("--model", required=True)
    parser.add_argument("--binding", required=True)
    parser.add_argument("--result", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    try:
        observation = adapt_files(
            model_path=Path(args.model),
            binding_path=Path(args.binding),
            result_path=Path(args.result),
        )
        write_observation(Path(args.output), observation)
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({"status": "ERROR", "error": str(exc)}, sort_keys=True))
        return 1

    print(json.dumps({
        "status": "BOUND",
        "observation_hash": observation.content_hash,
        "evidence_hash": observation.evidence_hash,
        "model_hash": observation.model_hash,
        "input_binding_hash": observation.input_binding_hash,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
