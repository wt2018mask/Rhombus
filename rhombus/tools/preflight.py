"""Conservative AI-visible structure and model-domain preflights.

These model-supplied inputs are not source-bound scientific evidence.
Valid periodic representation and element coverage never authorize stability,
simulation, training-exposure, or IN_DOMAIN claims.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Mapping

from .evidence_query import TOOL_SCHEMA_VERSION

MAX_SITES = 256
MAX_SNAPSHOT_BYTES = 128 * 1024
_SHA = re.compile(r"^[a-f0-9]{64}$")


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not 0 < len(value.strip()) <= 256:
        raise ValueError(f"{name} must be nonempty text, at most 256 characters")
    return value


def _atomic_numbers(raw: Any) -> list[int]:
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_SITES:
        raise ValueError("atomic_numbers must have 1..256 entries")
    if any(type(z) is not int or not 1 <= z <= 118 for z in raw):
        raise ValueError("atomic_numbers must contain integers in [1, 118]")
    return raw


def _finite_triple(value: Any, name: str, *, lower: float, upper: float | None = None) -> tuple[float, float, float]:
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError(f"{name} must contain exactly three numbers")
    if any(type(x) not in (float, int) for x in value):
        raise ValueError(f"{name} values must be numeric (bool forbidden)")
    result = tuple(float(x) for x in value)
    if any(not math.isfinite(x) or x <= lower or (upper is not None and x >= upper) for x in result):
        raise ValueError(f"{name} values outside valid bounds")
    return result  # type: ignore[return-value]


def _arguments(args: Mapping[str, Any], expected: set[str]) -> None:
    if not isinstance(args, Mapping) or set(args) != expected:
        raise ValueError("invalid or unexpected tool arguments")


def _base_result(name: str, candidate_id: str) -> dict[str, Any]:
    return {
        "schema_version": TOOL_SCHEMA_VERSION,
        "tool_name": name,
        "candidate_id": candidate_id,
        "operational_status": "SUCCEEDED",
        "scientific_verdict": "UNKNOWN",
        "domain_status": "UNQUALIFIED",
        "claim_authorized": False,
        "input_binding": "MODEL_SUPPLIED_NOT_SOURCE_VERIFIED",
        "evidence_ids": [],
        "limitations": [
            "INPUT_NOT_BOUND_TO_SOURCE_VERIFIED_EVIDENCE",
            "NO_SCIENTIFIC_STABILITY_OR_GENERALIZATION_AUTHORIZATION",
        ],
    }


class ReadOnlyPreflightTools:
    """Trusted host binds an exact model-domain file and expected raw SHA256."""

    def __init__(self, *, model_domain_snapshot: Path, model_domain_snapshot_sha256: str):
        if not isinstance(model_domain_snapshot_sha256, str) or not _SHA.fullmatch(model_domain_snapshot_sha256):
            raise ValueError("host must bind an exact lowercase snapshot SHA256")
        self._snapshot = Path(model_domain_snapshot)
        self._expected_sha256 = model_domain_snapshot_sha256

    def _verified_snapshot(self) -> dict[str, Any]:
        if not self._snapshot.is_file() or self._snapshot.stat().st_size > MAX_SNAPSHOT_BYTES:
            raise ValueError("trusted model domain snapshot missing or oversized")
        raw = self._snapshot.read_bytes()
        if hashlib.sha256(raw).hexdigest() != self._expected_sha256:
            raise ValueError("model domain snapshot SHA256 mismatch")
        try:
            record = json.loads(raw)
        except (UnicodeError, ValueError) as exc:
            raise ValueError("invalid model domain snapshot") from exc
        if not isinstance(record, dict):
            raise ValueError("invalid model domain snapshot object")
        if record.get("schema_version") != "scientific-freeze-v1":
            raise ValueError("unsupported model domain snapshot")
        return record

    def call_tool(self, name: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
        if name == "get_domain_assessment":
            _arguments(arguments, {"candidate_id", "atomic_numbers", "claim_kind"})
            candidate_id = _text(arguments["candidate_id"], "candidate_id")
            numbers = _atomic_numbers(arguments["atomic_numbers"])
            claim_kind = _text(arguments["claim_kind"], "claim_kind")
            # Import existing validated science contracts lazily so the
            # base MCP evidence tool stays lightweight and optional.
            from rhombus.domain.applicability import ModelElementDomain, assess_element_coverage
            from rhombus.domain.descriptors import CompositionDescriptor
            snapshot = self._verified_snapshot()
            model_domain = ModelElementDomain.from_snapshot(
                snapshot, snapshot_content_hash=None,
            )
            result = assess_element_coverage(
                descriptor=CompositionDescriptor.from_atomic_numbers(numbers),
                domain=model_domain,
                claim_kind=claim_kind,
            )
            output = _base_result(name, candidate_id)
            output.update({
                "domain_status": result.domain_status.value,
                "assessment_level": "ELEMENT_COVERAGE_PREFLIGHT",
                "claim_kind": claim_kind,
                "model_id": result.model_id,
                "model_checkpoint_sha256": result.checkpoint_sha256,
                "domain_key": result.domain_key,
                "snapshot_file_sha256": self._expected_sha256,
                "unsupported_atomic_numbers": list(result.unsupported_atomic_numbers),
                "limitations": output["limitations"] + list(result.applicability.limitations),
            })
            return output

        if name == "validate_candidate_structure":
            _arguments(arguments, {
                "candidate_id", "atomic_numbers", "cell_lengths_angstrom",
                "cell_angles_degrees", "fractional_coordinates",
            })
            candidate_id = _text(arguments["candidate_id"], "candidate_id")
            atomic_numbers = _atomic_numbers(arguments["atomic_numbers"])
            lengths = _finite_triple(arguments["cell_lengths_angstrom"], "cell_lengths_angstrom", lower=0)
            angles = _finite_triple(arguments["cell_angles_degrees"], "cell_angles_degrees", lower=0, upper=180)
            positions = arguments["fractional_coordinates"]
            if not isinstance(positions, list) or len(positions) != len(atomic_numbers):
                raise ValueError("fractional_coordinates must match atomic_numbers count")
            if any(not isinstance(pos, list) or len(pos) != 3 or any(
                type(x) not in (float, int) or not math.isfinite(float(x)) or abs(float(x)) > 1e6 for x in pos
            ) for pos in positions):
                raise ValueError("fractional_coordinates must be finite numeric triples")

            from pymatgen.core import Lattice, Structure
            from rhombus.domain.structure_protocols import (
                CANDIDATE_FINGERPRINT_PROTOCOL_ID,
                structure_candidate_fingerprint_sha256,
            )
            lattice = Lattice.from_parameters(*lengths, *angles)
            if not math.isfinite(lattice.volume) or lattice.volume <= 1e-8:
                raise ValueError("degenerate periodic lattice")
            structure = Structure(
                lattice, atomic_numbers, positions, coords_are_cartesian=False,
                validate_proximity=True,
            )
            fingerprint = structure_candidate_fingerprint_sha256(structure)
            output = _base_result(name, candidate_id)
            output.update({
                "representation_status": "WELL_FORMED_PERIODIC_STRUCTURE",
                "assessment_level": "PERIODIC_REPRESENTATION_PREFLIGHT",
                "site_count": len(structure),
                "formula": structure.composition.reduced_formula,
                "cell_volume_angstrom3": float(lattice.volume),
                "candidate_fingerprint_sha256": fingerprint,
                "fingerprint_protocol_id": CANDIDATE_FINGERPRINT_PROTOCOL_ID,
                "limitations": output["limitations"] + [
                    "GEOMETRY_PREFLIGHT_NOT_ENERGY_OR_STABILITY_VERDICT",
                    "COARSE_FINGERPRINT_NOT_EXACT_STRUCTURE_MEMBERSHIP",
                    "ATOMIC_STRUCTURE_NOT_PERSISTED_OR_SOURCE_VERIFIED",
                ],
            })
            return output
        raise ValueError("preflight tool is not registered")


__all__ = ["ReadOnlyPreflightTools"]
