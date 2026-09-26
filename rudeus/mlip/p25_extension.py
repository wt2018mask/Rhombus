"""P2.5 transport-evidence extension authorization.

This is an operational bridge for P2 PASS candidates whose P2.5 verdict is
INDETERMINATE because the adaptive P2 trajectory was too short or its
uncertainty interval did not resolve the provisional F3 gate.

It never changes P2/P2.5 verdicts. It freezes an exact subset for a separate
longer-trajectory rerun from the original P1 relaxed structure.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List

from rudeus.mlip.sharding import write_json_atomic

EXTENSION_AUTH_VERSION = "p25-extension-authorization-v1"


def _load(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _identity(rows: List[Dict[str, Any]]) -> str:
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_extension_manifest(
    p1_dir: str | Path,
    p2_dir: str | Path,
    p25_dir: str | Path,
) -> Dict[str, Any]:
    p1_dir, p2_dir, p25_dir = map(Path, (p1_dir, p2_dir, p25_dir))
    rows: List[Dict[str, Any]] = []

    for p25_path in sorted(p25_dir.glob("*.json")):
        p25 = _load(p25_path)
        bid = p25_path.stem
        if p25.get("batch_id") != bid:
            raise ValueError(f"P2.5 batch_id/filename mismatch: {bid}")
        r25 = p25.get("result") or {}
        if r25.get("transport_state") != "INDETERMINATE":
            continue

        p2_path = p2_dir / f"{bid}.json"
        p1_path = p1_dir / f"{bid}.json"
        if not p2_path.is_file() or not p1_path.is_file():
            raise ValueError(f"missing P1/P2 source for {bid}")

        p2 = _load(p2_path)
        p1 = _load(p1_path)
        r2 = p2.get("result") or {}
        r1 = p1.get("result") or {}

        if r2.get("p2_verdict") != "PASS":
            raise ValueError(f"P2.5 INDETERMINATE source is not P2 PASS: {bid}")
        if r1.get("p1_verdict") != "KEEP_FOR_P2":
            raise ValueError(f"extension source is not P1 KEEP_FOR_P2: {bid}")

        relaxed_sha = r1.get("relaxed_structure_sha256")
        if not relaxed_sha or r2.get("p2_input_relaxed_sha256") != relaxed_sha:
            raise ValueError(f"P1/P2 relaxed structure binding mismatch: {bid}")

        p2_art = r2.get("trajectory_artifact") or {}
        p25_prov = r25.get("provenance") or {}
        if p25_prov.get("trajectory_artifact_sha256") != p2_art.get("sha256"):
            raise ValueError(f"P2/P2.5 trajectory binding mismatch: {bid}")

        rows.append({
            "batch_id": bid,
            "relaxed_structure_sha256": relaxed_sha,
            "source_p2_trajectory_sha256": p2_art.get("sha256"),
            "source_p2_config_hash": r2.get("p2_config_hash"),
            "source_p25_config_hash": p25_prov.get("p25_config_hash"),
            "source_p25_transport_state": "INDETERMINATE",
        })

    rows.sort(key=lambda x: x["batch_id"])
    return {
        "authorization_version": EXTENSION_AUTH_VERSION,
        "purpose": "p25_transport_evidence_extension",
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
        raise ValueError("unsupported P2.5 extension authorization version")

    actual = build_extension_manifest(p1_dir, p2_dir, p25_dir)
    rows = manifest.get("candidates")
    if not isinstance(rows, list):
        raise ValueError("extension authorization candidates must be a list")
    if rows != actual["candidates"]:
        raise ValueError("extension authorization does not exactly bind current sources")
    if manifest.get("n_authorized") != len(rows):
        raise ValueError("extension authorization count mismatch")
    if manifest.get("cohort_identity") != _identity(rows):
        raise ValueError("extension authorization cohort identity mismatch")
    if manifest.get("cohort_identity") != actual["cohort_identity"]:
        raise ValueError("extension authorization current cohort mismatch")
    return {r["batch_id"] for r in rows}
