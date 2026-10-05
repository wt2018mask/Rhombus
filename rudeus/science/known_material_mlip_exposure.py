"""B2 MLIP pretraining-exposure accounting.

This layer records what is publicly known about foundation-model training provenance
without treating unavailable exact membership information as evidence of non-exposure.
It is independent of B3 DEV/HELD_OUT assignment.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path
from typing import Mapping

from rudeus.science.contracts import Record, require_hash
from rudeus.science.known_material_universe import MaterialUniverseIntake


MLIP_EXPOSURE_LEDGER_VERSION = "known-material-mlip-exposure-v1"


class ExposureDisposition(str, Enum):
    CONFIRMED_EXPOSED = "CONFIRMED_EXPOSED"
    UNRESOLVED_EXACT_MEMBERSHIP = "UNRESOLVED_EXACT_MEMBERSHIP"
    NO_PUBLIC_MATCH = "NO_PUBLIC_MATCH"


@dataclass(frozen=True, kw_only=True)
class MaterialExposureRecord(Record):
    material_key: str
    disposition: str
    training_dataset_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    rationale: tuple[str, ...]

    def validate(self):
        super().validate()
        ExposureDisposition(self.disposition)
        if not self.material_key:
            raise ValueError("exposure record requires material key")
        if not self.training_dataset_refs:
            raise ValueError("exposure record requires training-dataset refs")
        if not self.evidence_refs:
            raise ValueError("exposure record requires evidence refs")
        if not self.rationale:
            raise ValueError("exposure record requires rationale")


@dataclass(frozen=True, kw_only=True)
class MlipExposureLedger(Record):
    ledger_version: str
    model_id: str
    checkpoint_sha256: str
    training_datasets: tuple[str, ...]
    provenance_refs: tuple[str, ...]
    material_records: tuple[MaterialExposureRecord, ...]
    interpretation_constraints: tuple[str, ...]

    @classmethod
    def from_dict(cls, value):
        value = dict(value)
        value["training_datasets"] = tuple(value["training_datasets"])
        value["provenance_refs"] = tuple(value["provenance_refs"])
        value["material_records"] = tuple(
            MaterialExposureRecord.from_dict(item)
            for item in value["material_records"]
        )
        value["interpretation_constraints"] = tuple(
            value["interpretation_constraints"]
        )
        return cls(**value)

    def validate(self):
        super().validate()
        if self.ledger_version != MLIP_EXPOSURE_LEDGER_VERSION:
            raise ValueError("unsupported MLIP exposure ledger version")
        if not self.model_id:
            raise ValueError("exposure ledger requires model id")
        require_hash(self.checkpoint_sha256)
        if not self.training_datasets:
            raise ValueError("exposure ledger requires training datasets")
        if not self.provenance_refs:
            raise ValueError("exposure ledger requires provenance refs")
        keys = [item.material_key for item in self.material_records]
        if not keys or len(keys) != len(set(keys)):
            raise ValueError("exposure ledger requires unique material records")
        if not self.interpretation_constraints:
            raise ValueError("exposure ledger requires interpretation constraints")


def load_mlip_exposure_ledger(path: Path) -> MlipExposureLedger:
    return MlipExposureLedger.from_dict(
        json.loads(path.read_text(encoding="utf-8"))
    )


def validate_exposure_coverage(
    ledger: MlipExposureLedger,
    universe: MaterialUniverseIntake,
) -> Mapping[str, str]:
    expected = {entry.material_key for entry in universe.entries}
    observed = {entry.material_key for entry in ledger.material_records}
    missing = sorted(expected - observed)
    extra = sorted(observed - expected)
    if missing or extra:
        raise ValueError(
            "MLIP exposure ledger does not match B2 universe "
            f"(missing={missing}, extra={extra})"
        )
    return {
        item.material_key: item.disposition
        for item in ledger.material_records
    }
