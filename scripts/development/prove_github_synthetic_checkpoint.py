"""Small synthetic GitHub Actions artifact upload/download proof.

No real sAlex/WBM/MPTrj, API secrets, GitHub writes or Kaggle. Source data are
eight deterministic artificial SQLite rows. Use exact existing independent
SHA256 part bundling without importing the scientific heavyweight package.
Local --verify checks bytes only; only the two-job GitHub Actions workflow
establishes a real artifact-service cross-runner transfer.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import runpy
import sqlite3
import sys
from tempfile import TemporaryDirectory

BUNDLE_ID = "phase3-synthetic-fixture"
ROW_COUNT = 8
PART_BYTES = 1024
MAX_FIXTURE_BYTES = 64 * 1024
MAX_FIXTURE_PARTS = 64
ROOT = Path(__file__).resolve().parents[2]


def _api():
    # Reuse the exact checked-in bounded bundle implementation. A dynamic
    # file-scoped import avoids costly rhombus.domain package-science imports,
    # while keeping the synthetic transfer workflow standard-library only.
    impl = runpy.run_path(str(ROOT / "rhombus/domain/checkpoint_bundle.py"))
    return impl["pack_checkpoint_parts"], impl["verify_checkpoint_parts"]


def _records():
    return [(n, f"synthetic-checkpoint-{n:02d}") for n in range(1, ROW_COUNT + 1)]


def make_fixture(root: Path) -> dict:
    """Produce exactly one fresh bounded local artifact bundle."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=False)
    source = root / "input.sqlite"
    with sqlite3.connect(source) as db:
        db.execute("CREATE TABLE diagnostic (serial INTEGER PRIMARY KEY, payload TEXT NOT NULL)")
        db.executemany("INSERT INTO diagnostic (serial,payload) VALUES (?,?)", _records())
        db.commit()
        if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("synthetic SQLite source invalid")
    if not 0 < source.stat().st_size <= MAX_FIXTURE_BYTES:
        raise ValueError("synthetic source exceeds resource budget")
    folder = root / "bundle"
    folder.mkdir(exist_ok=False)
    pack, _ = _api()
    receipt = pack(source=source, output_dir=folder, bundle_id=BUNDLE_ID, part_bytes=PART_BYTES)
    if (receipt["total_bytes"] > MAX_FIXTURE_BYTES
            or len(receipt["parts"]) > MAX_FIXTURE_PARTS
            or receipt["external_durability_verified"] is not False
            or receipt["claim_authorized"] is not False):
        raise ValueError("unsafe synthetic bundle claim")
    return {
        "status": "SYNTHETIC_LOCAL_CHECKPOINT_BUNDLE_CREATED",
        "bundle_dir": str(folder),
        "part_count": len(receipt["parts"]),
        "source_sha256": receipt["source_sha256"],
        "external_storage_verified": False,
        "training_membership_attested": False,
    }


def verify_fixture(folder: Path) -> dict:
    """Read downloaded or local parts, rehash, restore and verify known rows.

    This method alone does NOT attest upload/download; the Actions pipeline
    calls it only after actions/download-artifact in a different job.
    """
    folder = Path(folder)
    meta_path = folder / f"{BUNDLE_ID}.bundle.json"
    if meta_path.is_symlink() or not meta_path.is_file() or meta_path.stat().st_size > 32 * 1024:
        raise ValueError("missing or oversized synthetic bundle manifest")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if (not isinstance(meta, dict)
            or type(meta.get("total_bytes")) is not int
            or not 0 < meta["total_bytes"] <= MAX_FIXTURE_BYTES
            or not isinstance(meta.get("parts"), list)
            or not 1 <= len(meta["parts"]) <= MAX_FIXTURE_PARTS):
        raise ValueError("synthetic fixture exceeds resource budget")
    _, verify_parts = _api()
    checked = verify_parts(output_dir=folder, bundle_id=BUNDLE_ID)
    with TemporaryDirectory(prefix="rhombus-synthetic-check-") as temp:
        restored = Path(temp) / "restored.sqlite"
        h = sha256()
        with restored.open("xb") as out:
            for i in range(checked["verified_parts"]):
                part_path = folder / f"{BUNDLE_ID}.part-{i:05d}"
                with part_path.open("rb") as inp:
                    segment = inp.read(PART_BYTES + 1)
                if not 1 <= len(segment) <= PART_BYTES:
                    raise ValueError("part exceeds pinned small transfer size")
                h.update(segment)
                out.write(segment)
        if restored.stat().st_size != meta["total_bytes"] or h.hexdigest() != checked["source_sha256"]:
            raise ValueError("independently reassembled SHA256 mismatch")
        with sqlite3.connect(restored) as db:
            if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise ValueError("reconstructed SQLite integrity failed")
            rows = db.execute("SELECT serial,payload FROM diagnostic ORDER BY serial").fetchall()
        if rows != _records():
            raise ValueError("reconstructed synthetic fixture rows mismatch")
    return {
        "status": "SYNTHETIC_TRANSFER_BYTES_VALIDATED_OFFLINE_ONLY",
        "rows_verified": len(rows),
        "part_count": checked["verified_parts"],
        "restored_sha256": checked["source_sha256"],
        "source_lineage_verified": False,
        "external_durability_verified_by_local_verifier": False,
        "actual_kaggle_resume_verified": False,
        "scientific_verdict": "UNKNOWN",
        "claim_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--make", type=Path, help="new local synthetic source+bundle root")
    group.add_argument("--verify", type=Path, help="downloaded synthetic bundle directory")
    args = parser.parse_args(argv)
    try:
        result = make_fixture(args.make) if args.make is not None else verify_fixture(args.verify)
    except (ValueError, OSError, TypeError, sqlite3.DatabaseError) as exc:
        print(f"SYNTHETIC_CHECKPOINT_REJECTED: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
