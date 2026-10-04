"""Append-only content-addressed storage for frozen G.1 calibration records.

Infrastructure/provenance only: bytes are written and verified, never
interpreted. No thresholds, coverage logic, uncertainty, validation of
held-out splits, verdicts, or qualification live here.

Mechanism reuse (no second storage abstraction):
- canonical bytes and identity: ``canonical_bytes`` / ``content_hash``
- atomic append-only writes: ``evidence.append_file``
- path confinement: ``evidence.inside``
- failure convention: ``integrity_errors`` (storage faults surface as
  ``ExecutionError`` with ``INTEGRITY`` — infrastructure, never scientific)

Layout: ``<directory>/<content-hash>.json`` where the directory names the
G.1 record type. Record type is additionally bound by the stored ``version``
field, which must equal the expected record class's version.
"""

from __future__ import annotations

import json
from pathlib import Path

from rudeus.science.calibration import (
    CalibrationDatasetManifest,
    CalibrationPlan,
    CalibrationReplicateManifest,
    CalibrationScope,
    GeneratorSpec,
    HeldoutEvaluationManifest,
    TruthRecord,
)
from rudeus.science.contracts import Record, canonical_bytes, require_hash
from rudeus.science.evidence import append_file, inside, integrity_errors, require


_DIRECTORIES = {
    "calibration_plans": CalibrationPlan,
    "generator_specs": GeneratorSpec,
    "truth_records": TruthRecord,
    "calibration_datasets": CalibrationDatasetManifest,
    "calibration_replicates": CalibrationReplicateManifest,
    "heldout_evaluations": HeldoutEvaluationManifest,
    "calibration_scopes": CalibrationScope,
}

_CLASSES = {cls: directory for directory, cls in _DIRECTORIES.items()}


def directory_for(record_type):
    """Storage directory for a G.1 record class (type binding, not identity)."""
    cls = _DIRECTORIES[record_type] if isinstance(record_type, str) else record_type
    if cls not in _CLASSES:
        raise ValueError("unsupported calibration record type")
    return _CLASSES[cls]


def class_for(directory):
    """G.1 record class stored under a directory name."""
    if directory not in _DIRECTORIES:
        raise ValueError("unsupported calibration record directory")
    return _DIRECTORIES[directory]


class CalibrationStore:
    """Content-addressed G.1 record archive rooted at one directory."""

    def __init__(self, root):
        self.root = Path(root).resolve()

    def path(self, relative):
        return inside(self.root, relative)

    def store(self, record: Record) -> str:
        """Persist a G.1 record append-only; returns its content hash.

        Identical re-storage is idempotent. Different bytes at an existing
        identity fail closed via the append-only primitive.
        """
        with integrity_errors():
            require(type(record) in _CLASSES, "only frozen G.1 records are stored")
            data = canonical_bytes(record)
            identity = record.content_hash
            append_file(self.path(f"{_CLASSES[type(record)]}/{identity}.json"), data)
            stored = self.path(f"{_CLASSES[type(record)]}/{identity}.json").read_bytes()
            require(stored == data, "stored bytes differ from canonical record")
            return identity

    def retrieve(self, record_type, identity: str) -> Record:
        """Load and verify a stored G.1 record by type and content hash."""
        with integrity_errors():
            cls = class_for(directory_for(record_type))
            require_hash(identity)
            data = self.path(f"{_CLASSES[cls]}/{identity}.json").read_bytes()
            record = cls.from_dict(json.loads(data))
            expected_version = cls.__dataclass_fields__["version"].default
            require(record.to_dict().get("version") == expected_version,
                    "stored record version mismatch")
            require(canonical_bytes(record) == data, "stored bytes are not canonical")
            require(record.content_hash == identity, "stored record hash mismatch")
            return record
