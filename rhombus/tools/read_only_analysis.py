"""Bounded, read-only structure-input and model-domain preflight tools.

No scheduler, Kaggle secrets, shell, model inference, structure relaxation,
or scientific PASS claim is reachable from this module. Host controls the
only model-domain snapshot path. Input geometry is checked syntactically and
for exact duplicate sites, NOT scientifically qualified for stability.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

DOMAIN_SHA256 = "51bd681f03d5873b1add0b1765ea1865881776bcfc0fb188c730daf0e2f1b1e5"
DOMAIN_MODEL = "medium-mpa-0"
DOMAIN_CHECKPOINT = "75428afe3a1d7d8062e19bcaabd5c433623cabf308242ec9fb493e38604fb638"
MAX_SITES = 128
MAX_INPUT_BYTES = 128 * 1024
CLAIM_KINDS = (
    "finite_temperature_stability", "ionic_transport", "structural_relaxation"
)


def list_analysis_tool_specs() -> list[dict[str, Any]]:
    """Stable, strict function schemas that cannot select paths or run compute."""
    names = {
        "get_domain_assessment": {
            "description": (
                "Conservative, read-only element-coverage preflight against the "
                "exact host-pinned medium-mpa-0 snapshot. Element coverage "
                "NEVER proves IN_DOMAIN; no calibration or simulation is performed."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "candidate_id": {"type": "string", "minLength": 1, "maxLength": 256},
                    "model_id": {"type": "string", "enum": [DOMAIN_MODEL]},
                    "claim_kind": {"type": "string", "enum": list(CLAIM_KINDS)},
                    "atomic_numbers": {
                        "type": "array", "minItems": 1, "maxItems": MAX_SITES,
                        "items": {"type": "integer", "minimum": 1, "maximum": 118},
                    },
                },
                "required": ["candidate_id", "model_id", "claim_kind", "atomic_numbers"],
                "additionalProperties": False,
            },
        },
        "validate_candidate_structure": {
            "description": (
                "Bounded, local geometric representation preflight only. "
                "Checks lattice, integer atomic numbers, fractional coordinates "
                "and coincident periodic sites. VALID_REPRESENTATION is NOT "
                "scientific stability, synthesizability, novelty or PASS."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "candidate_id": {"type": "string", "minLength": 1, "maxLength": 256},
                    "structure": {
                        "type": "object",
                        "properties": {
                            "lattice_vectors_angstrom": {
                                "type": "array", "minItems": 3, "maxItems": 3,
                                "items": {
                                    "type": "array", "minItems": 3, "maxItems": 3,
                                    "items": {"type": "number"},
                                },
                            },
                            "atomic_numbers": {
                                "type": "array", "minItems": 1, "maxItems": MAX_SITES,
                                "items": {"type": "integer", "minimum": 1, "maximum": 118},
                            },
                            "fractional_coords": {
                                "type": "array", "minItems": 1, "maxItems": MAX_SITES,
                                "items": {
                                    "type": "array", "minItems": 3, "maxItems": 3,
                                    "items": {"type": "number"},
                                },
                            },
                        },
                        "required": [
                            "lattice_vectors_angstrom", "atomic_numbers", "fractional_coords"
                        ],
                        "additionalProperties": False,
                    },
                },
                "required": ["candidate_id", "structure"],
                "additionalProperties": False,
            },
        },
    }
    return json.loads(json.dumps([
        {"type": "function", "function": {"name": name, **body}}
        for name, body in names.items()
    ]))


def _bounded_json(value: Any) -> bytes:
    try:
        encoded = json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("non-JSON or non-finite tool input") from exc
    if len(encoded) > MAX_INPUT_BYTES:
        raise ValueError("tool input exceeds safe size budget")
    return encoded


def _validate_candidate_id(candidate_id: Any) -> str:
    if not isinstance(candidate_id, str) or not candidate_id.strip() or len(candidate_id) > 256:
        raise ValueError("candidate_id must be a nonempty bounded identifier")
    return candidate_id


def _validate_atomic_numbers(value: Any) -> list[int]:
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_SITES:
        raise ValueError("atomic_numbers length outside supported bound")
    if any(type(z) is not int or not 1 <= z <= 118 for z in value):
        raise ValueError("atomic_numbers must be integer elements in [1, 118]")
    return value


def _matrix3(value: Any, *, field: str, limit: float) -> list[list[float]]:
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError(f"{field} requires three vectors")
    if any(not isinstance(row, list) or len(row) != 3 for row in value):
        raise ValueError(f"{field} requires 3x3 numeric matrix")
    for row in value:
        for component in row:
            if type(component) not in (float, int) or not math.isfinite(component):
                raise ValueError(f"{field} contains nonfinite or nonnumeric data")
            if abs(component) > limit:
                raise ValueError(f"{field} exceeds bounded numeric range")
    return value


def _volume(v: list[list[float]]) -> float:
    a, b, c = v
    return abs(
        a[0] * (b[1] * c[2] - b[2] * c[1])
        - a[1] * (b[0] * c[2] - b[2] * c[0])
        + a[2] * (b[0] * c[1] - b[1] * c[0])
    )


def _base(name: str, candidate_id: str) -> dict[str, Any]:
    return {
        "schema_version": "rhombus-ai-tool-result-v1",
        "tool_name": name,
        "candidate_id": candidate_id,
        "operational_status": "SUCCEEDED",
        "scientific_verdict": "UNKNOWN",
        "claim_authorized": False,
    }


class ReadOnlyAnalysisTools:
    """Host-pinned bounded source for model-domain and representation preflights."""

    def __init__(self, model_domain_snapshot: Path | None = None):
        self._model_domain_snapshot = (
            Path(model_domain_snapshot) if model_domain_snapshot is not None else None
        )

    def call_tool(self, name: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
        schemas = {s["function"]["name"]: s["function"] for s in list_analysis_tool_specs()}
        if name not in schemas:
            raise ValueError("unavailable analysis tool")
        if not isinstance(arguments, dict):
            raise ValueError("tool arguments must be an object")
        allowed = set(schemas[name]["parameters"]["properties"])
        if set(arguments) - allowed:
            raise ValueError("unexpected tool arguments")
        _bounded_json(arguments)
        candidate_id = _validate_candidate_id(arguments.get("candidate_id"))
        if name == "get_domain_assessment":
            if set(arguments) != allowed:
                raise ValueError("domain preflight requires model, claim and composition")
            return self._domain(candidate_id, arguments)
        if set(arguments) != allowed:
            raise ValueError("structure preflight requires candidate_id and structure")
        return self._structure(candidate_id, arguments["structure"])

    def _domain(self, candidate_id: str, args: Mapping[str, Any]) -> dict[str, Any]:
        if args["model_id"] != DOMAIN_MODEL or args["claim_kind"] not in CLAIM_KINDS:
            raise ValueError("model or claim kind is not authorized")
        atomic_numbers = _validate_atomic_numbers(args["atomic_numbers"])
        if self._model_domain_snapshot is None or not self._model_domain_snapshot.is_file():
            raise ValueError("trusted model-domain snapshot is not configured")
        if self._model_domain_snapshot.stat().st_size > 1024 * 1024:
            raise ValueError("model-domain snapshot too large")
        blob = self._model_domain_snapshot.read_bytes()
        if hashlib.sha256(blob).hexdigest() != DOMAIN_SHA256:
            raise ValueError("model-domain source identity mismatch")
        try:
            snapshot = json.loads(blob)
        except (ValueError, UnicodeError) as exc:
            raise ValueError("model-domain snapshot is invalid") from exc
        # Do not conflate this inexpensive preflight with calibrated coverage.
        from rhombus.domain.applicability import ModelElementDomain, assess_element_coverage
        from rhombus.domain.descriptors import CompositionDescriptor

        domain = ModelElementDomain.from_snapshot(
            snapshot, snapshot_content_hash=DOMAIN_SHA256,
        )
        if domain.model_id != DOMAIN_MODEL or domain.checkpoint_sha256 != DOMAIN_CHECKPOINT:
            raise ValueError("frozen model-domain identity mismatch")
        assessment = assess_element_coverage(
            descriptor=CompositionDescriptor.from_atomic_numbers(atomic_numbers),
            domain=domain,
            claim_kind=args["claim_kind"],
        )
        return {
            **_base("get_domain_assessment", candidate_id),
            "model_id": DOMAIN_MODEL,
            "model_checkpoint_sha256": DOMAIN_CHECKPOINT,
            "domain_snapshot_sha256": DOMAIN_SHA256,
            "assessment_level": "ELEMENT_COVERAGE_PREFLIGHT",
            "domain_status": assessment.domain_status.value,
            "claim_kind": args["claim_kind"],
            "unsupported_atomic_numbers": list(assessment.unsupported_atomic_numbers),
            "limitations": list(assessment.applicability.limitations) + [
                "NOT_STRUCTURAL_DISTANCE_CALIBRATION",
                "NOT_TRAINING_EXPOSURE_AUDIT",
                "NO_UNSEEN_GENERALIZATION_CLAIM",
            ],
        }

    def _structure(self, candidate_id: str, structure: Any) -> dict[str, Any]:
        if not isinstance(structure, dict) or set(structure) != {
            "lattice_vectors_angstrom", "atomic_numbers", "fractional_coords"
        }:
            raise ValueError("structure representation has invalid fields")
        atomic_numbers = _validate_atomic_numbers(structure["atomic_numbers"])
        vectors = _matrix3(
            structure["lattice_vectors_angstrom"],
            field="lattice_vectors_angstrom", limit=1e5,
        )
        coords = structure["fractional_coords"]
        if not isinstance(coords, list) or len(coords) != len(atomic_numbers):
            raise ValueError("fractional_coords must match atomic_numbers length")
        if any(not isinstance(c, list) or len(c) != 3 for c in coords):
            raise ValueError("fractional_coords must be 3 component arrays")
        for coord in coords:
            if any(
                type(v) not in (float, int) or not math.isfinite(v) or abs(v) > 1e6
                for v in coord
            ):
                raise ValueError("fractional_coords contains invalid numeric values")
        vol = _volume(vectors)
        if not math.isfinite(vol) or vol <= 1e-9:
            raise ValueError("lattice volume is zero or degenerate")
        # Only exact periodic site collisions are flagged. No scientific
        # bond threshold or stable-structure inference is implemented here.
        sites = [tuple(float(v) % 1.0 for v in coord) for coord in coords]
        collided = any(
            all(min(abs(a-b), 1.0 - abs(a-b)) < 1e-10 for a, b in zip(sites[i], sites[j]))
            for i in range(len(sites)) for j in range(i + 1, len(sites))
        )
        digest = hashlib.sha256(_bounded_json(structure)).hexdigest()
        return {
            **_base("validate_candidate_structure", candidate_id),
            "representation_status": (
                "INVALID_COINCIDENT_PERIODIC_SITES" if collided
                else "VALID_REPRESENTATION"
            ),
            "input_structure_sha256": digest,
            "site_count": len(atomic_numbers),
            "cell_volume_angstrom3": round(vol, 12),
            "domain_status": "UNQUALIFIED",
            "limitations": [
                "REPRESENTATION_PREFLIGHT_ONLY",
                "VALID_REPRESENTATION_IS_NOT_SCIENTIFIC_PASS",
                "NO_RELAXATION_OR_FINITE_TEMPERATURE_CALCULATION",
                "NO_SCIENTIFIC_CLAIM_AUTHORIZATION",
            ],
        }
