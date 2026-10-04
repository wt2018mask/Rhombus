"""Canonical P2.5 evidence-sufficiency transition.

This module defines a pipeline rule, not a candidate-specific rescue path.

Any candidate is admitted iff the frozen upstream records satisfy the same
structured predicate:
  * P1 KEEP_FOR_P2 with a hash-bound relaxed structure;
  * P2 PASS with a verified trajectory binding;
  * P2.5 INDETERMINATE;
  * enough target ions for a transport claim (trajectory length/statistical
    ambiguity is extendable; composition insufficiency is not);
  * the source is not itself an evidence-extension result.

The transition is one-shot.  It restarts from the frozen P1 relaxed structure
with a code-versioned, fixed 550 K / 1 fs / FixCom Langevin protocol and the
same deterministic batch-derived seed.  Early structural FAIL remains
terminal; early PASS does not stop the trajectory because P2.5 needs adequate
transport evidence.

The authorization manifest binds every admitted candidate to upstream hashes,
the MLIP checkpoint hash, the admission basis, and the exact transition
protocol hash.  Candidate names/IDs never participate in scientific selection
except as deterministic identifiers and RNG seed inputs already frozen by P2.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from rudeus.mlip.p2 import (
    P2_PROTOCOL_DEFAULTS,
    p2_job_seed,
    protocol_config_hash,
)
from rudeus.mlip.sharding import write_json_atomic

TRANSITION_VERSION = "p25-evidence-sufficiency-transition-v1"
ADMISSION_POLICY = "p25-indeterminate-with-sufficient-mobile-count-v1"
EXTENSION_AUTH_VERSION = "p25-evidence-transition-authorization-v2"
EXTENSION_PROTOCOL_VERSION = (
    "p2-p25-evidence-extension-v1-fixcom-constraint-provisional"
)
EXTENSION_POLICY = "p25-evidence-extension-1000-3000-8000-v1"
CANONICAL_BASE_SEED = 550
CANONICAL_TIERS = [1000, 3000, 8000]


def _load(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _identity(rows: List[Dict[str, Any]]) -> str:
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_extension_protocol() -> Dict[str, Any]:
    """Return the fixed, code-versioned one-shot evidence extension protocol.

    Deliberately does not read config.yaml P2 overrides.  Scientific protocol
    values are therefore fixed by this source revision rather than mutable
    runtime configuration.
    """
    protocol = dict(P2_PROTOCOL_DEFAULTS)
    protocol.update({
        "temperature_K": 550,
        "timestep_fs": 1.0,
        "equil_steps": 2000,
        "production_tier_schedule_provisional": list(CANONICAL_TIERS),
        "production_steps": 8000,
        "sample_interval_steps": 10,
        "thermostat": "langevin",
        "friction_fs_inv_provisional": 0.02,
        "fix_center_of_mass": True,
        "base_seed": CANONICAL_BASE_SEED,
        "p2_protocol_version": EXTENSION_PROTOCOL_VERSION,
        "trajectory_policy": EXTENSION_POLICY,
        "force_full_production_for_transport": True,
    })
    return protocol


def extension_protocol_hash() -> str:
    return protocol_config_hash(build_extension_protocol())


def _admission_basis(r25: Dict[str, Any]) -> Tuple[bool, str]:
    """ID-independent P2.5 transition predicate.

    Longer sampling can resolve trajectory/statistical ambiguity, but it
    cannot repair a composition with too few target ions.  Thus every
    INDETERMINATE record with the configured minimum mobile-ion count is
    admitted exactly once, regardless of material identity or point estimate.
    """
    if r25.get("transport_state") != "INDETERMINATE":
        return False, "p25_not_indeterminate"

    suff = r25.get("sufficiency") or {}
    try:
        n_mobile = int(suff["n_mobile_ions"])
        min_mobile = int(suff["min_mobile_ions"])
    except Exception:
        return False, "missing_structured_mobile_sufficiency"

    if n_mobile < min_mobile:
        return False, "nonextendable_mobile_count_insufficiency"

    prov = r25.get("provenance") or {}
    if str(prov.get("p2_protocol_version", "")).startswith(
        "p2-p25-evidence-extension-"
    ):
        return False, "extension_is_one_shot"

    unc = (r25.get("transport") or {}).get("uncertainty") or {}
    reasons = list((r25.get("diagnostics") or {}).get("reasons") or [])
    if unc.get("status") != "sufficient":
        basis = "trajectory_statistical_sufficiency"
    elif any(str(r).startswith("uncertainty_") for r in reasons):
        basis = "uncertainty_gate_ambiguity"
    elif r25.get("point_transport_state") == "INDETERMINATE":
        basis = "point_regime_ambiguity"
    else:
        # Defensive fallback: the final state is INDETERMINATE with enough
        # ions but the diagnostic vocabulary is newer than this code.
        basis = "other_transport_evidence_ambiguity"
    return True, basis


def build_extension_manifest(
    p1_dir: str | Path,
    p2_dir: str | Path,
    p25_dir: str | Path,
) -> Dict[str, Any]:
    p1_dir, p2_dir, p25_dir = map(Path, (p1_dir, p2_dir, p25_dir))
    rows: List[Dict[str, Any]] = []
    protocol = build_extension_protocol()
    proto_hash = protocol_config_hash(protocol)

    for p25_path in sorted(p25_dir.glob("*.json")):
        p25 = _load(p25_path)
        bid = p25_path.stem
        if p25.get("batch_id") != bid:
            raise ValueError(f"P2.5 batch_id/filename mismatch: {bid}")
        r25 = p25.get("result") or {}
        admitted, basis = _admission_basis(r25)
        if not admitted:
            continue

        p2_path = p2_dir / f"{bid}.json"
        p1_path = p1_dir / f"{bid}.json"
        if not p2_path.is_file() or not p1_path.is_file():
            raise ValueError(f"missing P1/P2 source for admitted candidate {bid}")

        p2 = _load(p2_path)
        p1 = _load(p1_path)
        r2 = p2.get("result") or {}
        r1 = p1.get("result") or {}

        if r2.get("p2_verdict") != "PASS":
            raise ValueError(f"P2.5 admitted source is not P2 PASS: {bid}")
        if r1.get("p1_verdict") != "KEEP_FOR_P2":
            raise ValueError(f"transition source is not P1 KEEP_FOR_P2: {bid}")

        relaxed_sha = r1.get("relaxed_structure_sha256")
        if not relaxed_sha or r2.get("p2_input_relaxed_sha256") != relaxed_sha:
            raise ValueError(f"P1/P2 relaxed structure binding mismatch: {bid}")

        p2_art = r2.get("trajectory_artifact") or {}
        p25_prov = r25.get("provenance") or {}
        if p25_prov.get("trajectory_artifact_sha256") != p2_art.get("sha256"):
            raise ValueError(f"P2/P2.5 trajectory binding mismatch: {bid}")

        source_seed = r2.get("seed")
        expected_seed = p2_job_seed(CANONICAL_BASE_SEED, bid)
        if source_seed != expected_seed:
            raise ValueError(
                f"source P2 seed is not canonical batch-derived seed: {bid}"
            )

        calc = (r2.get("provenance") or {}).get("calc") or {}
        checkpoint_sha = calc.get("sha256")
        if not checkpoint_sha:
            raise ValueError(f"source P2 lacks checkpoint SHA binding: {bid}")
        calc_dtype = calc.get("dtype")
        if not calc_dtype:
            raise ValueError(f"source P2 lacks calculator dtype binding: {bid}")

        rows.append({
            "batch_id": bid,
            "admission_policy": ADMISSION_POLICY,
            "admission_basis": basis,
            "relaxed_structure_sha256": relaxed_sha,
            "source_p2_trajectory_sha256": p2_art.get("sha256"),
            "source_p2_config_hash": r2.get("p2_config_hash"),
            "source_p2_protocol_version": r2.get("p2_protocol_version"),
            "source_p2_seed": source_seed,
            "source_p2_checkpoint_sha256": checkpoint_sha,
            "source_p2_calc_dtype": calc_dtype,
            "source_p25_config_hash": p25_prov.get("p25_config_hash"),
            "source_p25_version": p25_prov.get("p25_version"),
            "source_p25_transport_state": "INDETERMINATE",
            "transition_protocol_hash": proto_hash,
        })

    rows.sort(key=lambda x: x["batch_id"])
    return {
        "authorization_version": EXTENSION_AUTH_VERSION,
        "transition_version": TRANSITION_VERSION,
        "admission_policy": ADMISSION_POLICY,
        "purpose": "canonical_p25_evidence_sufficiency_transition",
        "one_shot": True,
        "transition_protocol_version": EXTENSION_PROTOCOL_VERSION,
        "transition_policy": EXTENSION_POLICY,
        "transition_protocol_hash": proto_hash,
        "transition_protocol": protocol,
        "n_authorized": len(rows),
        "candidates": rows,
        "cohort_identity": _identity(rows),
    }


def write_extension_manifest(
    p1_dir: str | Path,
    p2_dir: str | Path,
    p25_dir: str | Path,
    out_path: str | Path,
) -> Dict[str, Any]:
    manifest = build_extension_manifest(p1_dir, p2_dir, p25_dir)
    write_json_atomic(Path(out_path), manifest)
    return manifest


def load_extension_manifest(
    manifest_path: str | Path,
    p1_dir: str | Path,
    p2_dir: str | Path,
    p25_dir: str | Path,
) -> set[str]:
    manifest = _load(Path(manifest_path))
    if manifest.get("authorization_version") != EXTENSION_AUTH_VERSION:
        raise ValueError("unsupported canonical P2.5 transition authorization")
    if manifest.get("transition_version") != TRANSITION_VERSION:
        raise ValueError("canonical P2.5 transition version mismatch")
    if manifest.get("one_shot") is not True:
        raise ValueError("canonical P2.5 transition must be one-shot")

    actual = build_extension_manifest(p1_dir, p2_dir, p25_dir)
    rows = manifest.get("candidates")
    if not isinstance(rows, list):
        raise ValueError("transition authorization candidates must be a list")
    if rows != actual["candidates"]:
        raise ValueError("transition authorization does not exactly bind sources")
    if manifest.get("n_authorized") != len(rows):
        raise ValueError("transition authorization count mismatch")
    if manifest.get("cohort_identity") != _identity(rows):
        raise ValueError("transition authorization cohort identity mismatch")
    for key in (
        "admission_policy",
        "transition_protocol_version",
        "transition_policy",
        "transition_protocol_hash",
        "transition_protocol",
    ):
        if manifest.get(key) != actual.get(key):
            raise ValueError(f"transition contract mismatch: {key}")
    if manifest.get("cohort_identity") != actual["cohort_identity"]:
        raise ValueError("transition authorization current cohort mismatch")
    return {r["batch_id"] for r in rows}


def validated_manifest(
    manifest_path: str | Path,
    p1_dir: str | Path,
    p2_dir: str | Path,
    p25_dir: str | Path,
) -> Dict[str, Any]:
    """Return the validated frozen manifest after full source re-derivation."""
    load_extension_manifest(manifest_path, p1_dir, p2_dir, p25_dir)
    return _load(Path(manifest_path))
