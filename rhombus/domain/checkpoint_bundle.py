"""Bounded immutable part bundle for independently finalized checkpoint files.

Local-only; an external storage uploader/reader must be explicitly supplied by
trusted host software in a future change. No network, Kaggle, or science PASS.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
from typing import Any

MAX_PARTS = 4096
MAX_PART_BYTES = 128 * 1024 * 1024
MAX_TOTAL_BYTES = 2 * 1024 * 1024 * 1024


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            h.update(block)
    return h.hexdigest()


def pack_checkpoint_parts(*, source: Path, output_dir: Path, bundle_id: str,
                          part_bytes: int = 8 * 1024 * 1024) -> dict[str, Any]:
    """Write no-overwrite numbered parts; publish manifest last on success."""
    if type(source) is not Path or type(output_dir) is not Path:
        raise ValueError("host-bound Path required")
    if source.is_symlink() or output_dir.is_symlink():
        raise ValueError("symlink paths forbidden")
    if not isinstance(bundle_id, str) or not 1 <= len(bundle_id) <= 64 or any(
        x not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for x in bundle_id
    ):
        raise ValueError("invalid bundle_id")
    if type(part_bytes) is not int or not 1 <= part_bytes <= MAX_PART_BYTES:
        raise ValueError("invalid part_bytes")
    src, root = source.resolve(strict=True), output_dir.resolve(strict=True)
    if not src.is_file() or not root.is_dir() or src.parent == root:
        raise ValueError("invalid source/destination")
    if Path(str(src) + "-wal").exists() or Path(str(src) + "-shm").exists():
        raise ValueError("source SQLite is not finalized")
    size = src.stat().st_size
    if not 0 < size <= MAX_TOTAL_BYTES or (size + part_bytes - 1) // part_bytes > MAX_PARTS:
        raise ValueError("bundle exceeds budget")
    prefix = bundle_id + ".part-"
    manifest_path = root / (bundle_id + ".bundle.json")
    if manifest_path.exists() or list(root.glob(prefix + "*")):
        raise FileExistsError("bundle identifier already occupied")
    parts = []
    created: list[Path] = []
    whole = hashlib.sha256()
    try:
        with src.open("rb") as stream:
            for i in range((size + part_bytes - 1) // part_bytes):
                blob = stream.read(part_bytes)
                if not blob:
                    raise ValueError("unexpected source truncation")
                whole.update(blob)
                name = f"{prefix}{i:05d}"
                path = root / name
                with path.open("xb") as out:
                    created.append(path)
                    out.write(blob)
                    out.flush()
                    os.fsync(out.fileno())
                parts.append({"name": name, "bytes": len(blob),
                              "sha256": hashlib.sha256(blob).hexdigest()})
            if stream.read(1):
                raise ValueError("source grew during packaging")
        if sum(p["bytes"] for p in parts) != size or _digest(src) != whole.hexdigest():
            raise ValueError("source changed during packaging")
        result = {"schema_version": "rhombus-checkpoint-part-bundle-v1",
                  "bundle_id": bundle_id, "total_bytes": size,
                  "source_sha256": whole.hexdigest(), "parts": parts,
                  "external_durability_verified": False,
                  "scientific_verdict": "UNKNOWN", "claim_authorized": False}
        with manifest_path.open("xb") as out:
            created.append(manifest_path)
            out.write((json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n").encode())
            out.flush()
            os.fsync(out.fileno())
        return result
    except Exception:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        raise


def verify_checkpoint_parts(*, output_dir: Path, bundle_id: str) -> dict[str, Any]:
    """Validate complete ordered bundle bytes, without trusting manifest claims."""
    if type(output_dir) is not Path or output_dir.is_symlink():
        raise ValueError("host-bound non-symlink directory required")
    if not isinstance(bundle_id, str) or not 1 <= len(bundle_id) <= 64 or any(
        x not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for x in bundle_id
    ):
        raise ValueError("invalid bundle_id")
    root = output_dir.resolve(strict=True)
    path = root / (bundle_id + ".bundle.json")
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 1024 * 1024:
        raise ValueError("bundle manifest missing or oversized")
    try:
        meta = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError) as exc:
        raise ValueError("invalid bundle manifest") from exc
    if not isinstance(meta, dict) or set(meta) != {
        "schema_version", "bundle_id", "total_bytes", "source_sha256",
        "parts", "external_durability_verified", "scientific_verdict", "claim_authorized"
    } or meta["schema_version"] != "rhombus-checkpoint-part-bundle-v1" or meta["bundle_id"] != bundle_id:
        raise ValueError("bundle manifest schema mismatch")
    if (meta["external_durability_verified"] is not False or
        meta["scientific_verdict"] != "UNKNOWN" or meta["claim_authorized"] is not False):
        raise ValueError("unauthorized manifest claims")
    parts = meta["parts"]
    if not isinstance(parts, list) or not 1 <= len(parts) <= MAX_PARTS:
        raise ValueError("invalid part list")
    hasher = hashlib.sha256()
    count = 0
    for i, part in enumerate(parts):
        expected_name = f"{bundle_id}.part-{i:05d}"
        if not isinstance(part, dict) or set(part) != {"name", "bytes", "sha256"} or part["name"] != expected_name:
            raise ValueError("part identity mismatch")
        if type(part["bytes"]) is not int or not 1 <= part["bytes"] <= MAX_PART_BYTES:
            raise ValueError("invalid part size")
        name = root / expected_name
        if name.is_symlink() or not name.is_file() or name.stat().st_size != part["bytes"]:
            raise ValueError("part missing or size mismatch")
        with name.open("rb") as stream:
            blob = stream.read(MAX_PART_BYTES + 1)
        digest = hashlib.sha256(blob).hexdigest()
        if digest != part["sha256"]:
            raise ValueError("part checksum mismatch")
        hasher.update(blob)
        count += len(blob)
    if type(meta["total_bytes"]) is not int or count != meta["total_bytes"] or count > MAX_TOTAL_BYTES:
        raise ValueError("bundle total size mismatch")
    if hasher.hexdigest() != meta["source_sha256"]:
        raise ValueError("bundle source SHA mismatch")
    return {"schema_version": "rhombus-checkpoint-part-bundle-verification-v1",
            "bundle_id": bundle_id, "source_sha256": hasher.hexdigest(),
            "verified_bytes": count, "verified_parts": len(parts),
            "artifact_bytes_verified": True, "external_durability_verified": False,
            "execution_authorized": False, "scientific_verdict": "UNKNOWN",
            "claim_authorized": False}
