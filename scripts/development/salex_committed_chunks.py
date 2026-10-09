"""Diagnostic sAlex chunks from records AFTER successful SQLite batch COMMIT.

Chunks contain full MembershipIndexRecord metadata, never raw ASE/LMDB source.
Each complete gzip and its hash-bound JSON receipt are independent evidence
units. Full sAlex archive SHA256 is NOT verified until the complete stream
finishes; no chunk is a scientifically qualified exposure or training claim.
Files under Kaggle /working are NOT guaranteed remotely available mid-run.
"""
from __future__ import annotations

from dataclasses import asdict
import gzip
import hashlib
import json
import os
from pathlib import Path
from typing import BinaryIO

from rhombus.domain.membership import MembershipIndexRecord

RECORDS_PER_CHUNK = 50_000
MAX_JSONL_RECORD_BYTES = 16 * 1024
CHUNK_SCHEMA = "rhombus-phase3-salex-postcommit-diagnostic-chunk-v1"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while data := source.read(1024 * 1024):
            digest.update(data)
    return digest.hexdigest()


class CommittedSalexChunkWriter:
    """Bounded append-only pieces, published only after a complete gzip closes.

    A crash during the current .inflight file cannot invalidate older complete
    chunks. Never infer that a Kaggle notebook version persisted those files.
    """

    def __init__(self, root: Path, *, chunk_records: int = RECORDS_PER_CHUNK):
        if type(chunk_records) is not int or chunk_records < 1 or chunk_records > RECORDS_PER_CHUNK:
            raise ValueError("invalid partial chunk records budget")
        self.root = Path(root)
        if self.root.exists():
            raise FileExistsError("partial evidence destination must be new")
        self.root.mkdir(parents=True, exist_ok=False)
        self.chunk_records = chunk_records
        self.committed = 0
        self.last_complete = 0
        self.index = 0
        self.current = 0
        self._output: BinaryIO | None = None
        self._gzip = None
        self._previous_digest: str | None = None

    def _paths(self):
        stem = f"salex-committed-{self.index:04d}"
        return self.root / (stem + ".jsonl.gz"), self.root / (stem + ".json")

    def _open(self):
        if self._gzip is not None:
            return
        final, _ = self._paths()
        self._output = (self.root / (final.name + ".inflight")).open("xb")
        self._gzip = gzip.GzipFile(filename="", mode="wb", fileobj=self._output, mtime=0)

    def __call__(self, batch: list[MembershipIndexRecord], committed_rows: int):
        if type(committed_rows) is not int or committed_rows != self.committed + len(batch) or not batch:
            raise ValueError("nonmonotonic or empty SQLite committed batch")
        for record in batch:
            if record.dataset_id != "sAlex":
                raise ValueError("non-sAlex record in checkpoint")
            self._open()
            payload = (json.dumps(asdict(record), sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
            if len(payload) > MAX_JSONL_RECORD_BYTES:
                raise ValueError("diagnostic record exceeds bounded size")
            self._gzip.write(payload)
            self.current += 1
            self.committed += 1
            if self.current == self.chunk_records:
                self._seal()
        if self.committed != committed_rows:
            raise AssertionError("postcommit callback inconsistent with inserted SQLite count")

    def _seal(self):
        if self.current != self.chunk_records:
            raise ValueError("only complete committed chunks can be sealed")
        assert self._gzip is not None and self._output is not None
        self._gzip.close()
        self._output.flush()
        os.fsync(self._output.fileno())
        self._output.close()
        self._gzip = None
        self._output = None
        archive, receipt = self._paths()
        os.replace(str(archive) + ".inflight", archive)
        digest = _sha256(archive)
        prior = self.last_complete
        manifest = {
            "schema_version": CHUNK_SCHEMA,
            "status": "SQLITE_BATCH_COMMITTED_PARTIAL_SOURCE_UNVERIFIED",
            "archive": archive.name,
            "sha256": digest,
            "size_bytes": archive.stat().st_size,
            "chunk_index": self.index,
            "first_record_ordinal": prior,
            "last_record_ordinal_exclusive": self.committed,
            "committed_records_in_chunk": self.current,
            "prior_chunk_sha256": self._previous_digest,
            "full_salex_archive_sha256_verified": False,
            "source_complete": False,
            "training_membership_attested": False,
            "unseen_generalization_authorized": False,
        }
        temp = Path(str(receipt) + ".inflight")
        with temp.open("x", encoding="utf-8") as out:
            json.dump(manifest, out, sort_keys=True, separators=(",", ":"))
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, receipt)
        self._previous_digest = digest
        self.last_complete = self.committed
        self.index += 1
        self.current = 0
        print("SALEX_COMMITTED_DIAGNOSTIC_CHUNK " + json.dumps({
            "records_committed": self.committed,
            "chunk_index": manifest["chunk_index"],
            "sha256": digest,
            "source_sha256_verified": False,
        }, sort_keys=True), flush=True)


def verify_committed_chunk(archive: Path, manifest_path: Path) -> dict:
    """Offline integrity and count check; does not authenticate total source."""
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    if (manifest.get("schema_version") != CHUNK_SCHEMA
            or manifest.get("status") != "SQLITE_BATCH_COMMITTED_PARTIAL_SOURCE_UNVERIFIED"
            or any(manifest.get(key) is not False for key in (
                "full_salex_archive_sha256_verified", "source_complete",
                "training_membership_attested", "unseen_generalization_authorized",
            ))
            or manifest.get("archive") != Path(archive).name
            or type(manifest.get("size_bytes")) is not int
            or manifest["size_bytes"] != Path(archive).stat().st_size
            or _sha256(Path(archive)) != manifest.get("sha256")):
        raise ValueError("tampered or promoted sAlex diagnostic evidence")
    count = 0
    with gzip.open(archive, "rb") as source:
        while raw := source.readline(MAX_JSONL_RECORD_BYTES + 1):
            if len(raw) > MAX_JSONL_RECORD_BYTES or not raw.endswith(b"\n"):
                raise ValueError("invalid bounded record")
            item = json.loads(raw)
            if item.get("dataset_id") != "sAlex":
                raise ValueError("wrong dataset in committed record")
            count += 1
    if (count != manifest.get("committed_records_in_chunk")
            or type(manifest.get("first_record_ordinal")) is not int
            or manifest.get("last_record_ordinal_exclusive")
            != manifest["first_record_ordinal"] + count):
        raise ValueError("noncontiguous or incomplete committed records")
    return manifest
