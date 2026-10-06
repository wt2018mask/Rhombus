"""B4 executable-readiness gate for frozen known-material benchmark members.

Provenance retention and scientific executability are intentionally separate.  This
module summarizes the existing structure-resolution ledger and fails closed whenever
any frozen member is not READY; it never manufactures a representation to clear a
scientific blocker.
"""
from __future__ import annotations

from dataclasses import dataclass

from rudeus.science.contracts import Record
from rudeus.science.known_material_structure_resolution import (
    ResolutionStatus,
    StructureResolutionLedger,
)


B4_EXECUTABLE_READINESS_VERSION = "known-material-b4-executable-readiness-v1"


@dataclass(frozen=True, kw_only=True)
class B4ExecutableReadinessAudit(Record):
    audit_version: str
    structure_resolution_ledger_hash: str
    ready_material_keys: tuple[str, ...]
    blocked_material_keys: tuple[str, ...]
    blind_execution_authorized: bool

    def validate(self):
        super().validate()
        if self.audit_version != B4_EXECUTABLE_READINESS_VERSION:
            raise ValueError("unsupported B4 executable-readiness version")
        if set(self.ready_material_keys) & set(self.blocked_material_keys):
            raise ValueError("material cannot be both ready and blocked")
        if self.blind_execution_authorized is not (not self.blocked_material_keys):
            raise ValueError("blind execution authorization must follow readiness closure")


def audit_b4_executable_readiness(
    ledger: StructureResolutionLedger,
) -> B4ExecutableReadinessAudit:
    ready = tuple(sorted(
        case.material_key
        for case in ledger.cases
        if case.status == ResolutionStatus.READY.value
    ))
    blocked = tuple(sorted(
        case.material_key
        for case in ledger.cases
        if case.status != ResolutionStatus.READY.value
    ))
    return B4ExecutableReadinessAudit(
        audit_version=B4_EXECUTABLE_READINESS_VERSION,
        structure_resolution_ledger_hash=ledger.content_hash,
        ready_material_keys=ready,
        blocked_material_keys=blocked,
        blind_execution_authorized=not blocked,
    )
