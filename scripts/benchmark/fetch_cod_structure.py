#!/usr/bin/env python3
"""Fetch one approved COD structure, verify exact bytes, and update B2 retention records."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import urllib.request

from rudeus.science.known_material_structure_binding import StructureBindingLedger
from rudeus.science.known_material_structure_import import (
    CodArtifactSpec,
    apply_cod_retention_receipt,
    retain_cod_cif_payload,
)


REGISTRY_VERSION = "known-material-cod-registry-v1"
MAX_CIF_BYTES = 10 * 1024 * 1024


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    temp = path.with_name(f".{path.name}.tmp")
    temp.write_text(payload, encoding="utf-8")
    temp.replace(path)


def _download(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Rhombus-known-material-curation/1",
            "Accept": "chemical/x-cif,text/plain;q=0.9,*/*;q=0.1",
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        status = getattr(response, "status", 200)
        if status != 200:
            raise RuntimeError(f"COD download returned HTTP {status}")
        payload = response.read(MAX_CIF_BYTES + 1)
    if len(payload) > MAX_CIF_BYTES:
        raise RuntimeError("COD CIF exceeds bounded download size")
    return payload


def curate(repo_root: Path, material_key: str):
    registry_path = repo_root / "data/benchmarks/known_material/cod_structure_registry_v1.json"
    ledger_path = repo_root / "data/benchmarks/known_material/b2_structure_binding_v1.json"

    registry = _load_json(registry_path)
    if registry.get("registry_version") != REGISTRY_VERSION:
        raise ValueError("unsupported COD structure registry version")
    try:
        item = registry["entries"][material_key]
    except KeyError as exc:
        raise ValueError(f"material is not approved for COD curation: {material_key}") from exc

    spec = CodArtifactSpec(
        material_key=item["material_key"],
        cod_id=item["cod_id"],
        revision=item["revision"],
        expected_formula=item["expected_formula"],
        expected_space_group_number=item["expected_space_group_number"],
    )
    if material_key != spec.material_key:
        raise ValueError("registry key and material key disagree")

    retained_path = Path(item["retained_path"])
    receipt_path = Path(item["receipt_path"])
    if retained_path.is_absolute() or receipt_path.is_absolute():
        raise ValueError("curation output paths must be repository-relative")

    payload = _download(spec.pinned_locator)

    previous_cwd = Path.cwd()
    try:
        # Keep receipt paths repository-relative and deterministic.
        import os
        os.chdir(repo_root)
        receipt = retain_cod_cif_payload(payload, spec, retained_path)
    finally:
        os.chdir(previous_cwd)

    ledger = StructureBindingLedger.from_dict(_load_json(ledger_path))
    updated = apply_cod_retention_receipt(ledger, receipt)

    _write_json(repo_root / receipt_path, receipt.to_dict())
    _write_json(ledger_path, updated.to_dict())

    summary = {
        "material_key": material_key,
        "source_id": receipt.source_id,
        "pinned_locator": receipt.pinned_locator,
        "artifact_sha256": receipt.artifact_sha256,
        "byte_count": receipt.byte_count,
        "retained_path": receipt.retained_path,
        "receipt_path": receipt_path.as_posix(),
        "ledger_state": next(
            entry.artifact_state
            for entry in updated.entries
            if entry.material_key == material_key
        ),
    }
    print(json.dumps(summary, sort_keys=True))


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--material-key", required=True)
    parser.add_argument(
        "--repo-root",
        default=Path(__file__).resolve().parents[2],
        type=Path,
    )
    args = parser.parse_args(argv)
    curate(args.repo_root.resolve(), args.material_key)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"COD_CURATION_FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
