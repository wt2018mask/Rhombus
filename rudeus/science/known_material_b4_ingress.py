"""B4 blind benchmark ingress contract.

Execution receives only the B0-visible identity fields.  Scientific identity,
truth class, literature evidence, and expected outcomes remain outside this
record and therefore cannot leak through the execution payload.
"""
from __future__ import annotations

from dataclasses import dataclass

from rudeus.science.contracts import Record, require_hash


BLIND_INGRESS_VERSION = "known-material-blind-ingress-v1"
VISIBLE_FIELDS = (
    "benchmark_id",
    "split",
    "structure_hash",
    "benchmark_protocol_hash",
)


@dataclass(frozen=True, kw_only=True)
class BlindBenchmarkIngress(Record):
    ingress_version: str
    benchmark_id: str
    split: str
    structure_hash: str
    benchmark_protocol_hash: str

    def validate(self):
        super().validate()
        if self.ingress_version != BLIND_INGRESS_VERSION:
            raise ValueError("unsupported blind-ingress version")
        if not self.benchmark_id:
            raise ValueError("blind ingress requires benchmark id")
        if self.split not in {"DEV", "HELD_OUT"}:
            raise ValueError("blind ingress split must be DEV or HELD_OUT")
        require_hash(self.structure_hash)
        require_hash(self.benchmark_protocol_hash)

    @property
    def execution_payload(self):
        return {
            "benchmark_id": self.benchmark_id,
            "split": self.split,
            "structure_hash": self.structure_hash,
            "benchmark_protocol_hash": self.benchmark_protocol_hash,
        }
