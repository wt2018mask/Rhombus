"""B4 provenance-closure audit for frozen benchmark split members."""
from __future__ import annotations

from dataclasses import dataclass

from rudeus.science.contracts import Record
from rudeus.science.known_material_b3_split import B3SplitFreeze
from rudeus.science.known_material_artifact_curation import ArtifactRetentionIndex


B4_PROVENANCE_AUDIT_VERSION = "known-material-b4-provenance-audit-v1"


@dataclass(frozen=True, kw_only=True)
class B4ProvenanceAudit(Record):
    audit_version: str
    split_freeze_hash: str
    retained_material_keys: tuple[str, ...]
    missing_material_keys: tuple[str, ...]
    ingress_materialization_authorized: bool

    def validate(self):
        super().validate()
        if self.audit_version != B4_PROVENANCE_AUDIT_VERSION:
            raise ValueError("unsupported B4 provenance-audit version")
        if set(self.retained_material_keys) & set(self.missing_material_keys):
            raise ValueError("material cannot be both retained and missing")
        expected = not self.missing_material_keys
        if self.ingress_materialization_authorized is not expected:
            raise ValueError("B4 ingress authorization must follow provenance closure")


def audit_b4_provenance(
    split_freeze: B3SplitFreeze,
    retention_index: ArtifactRetentionIndex,
) -> B4ProvenanceAudit:
    """Require at least one retained reference-structure artifact per split member.

    A missing artifact blocks B4 materialization; it is not a physical-material
    failure and does not mutate the frozen B3 split.
    """
    split_keys = {member.benchmark_id for member in split_freeze.members}
    retained_keys = {
        receipt.material_key
        for receipt in retention_index.receipts
        if receipt.artifact_kind == "REFERENCE_STRUCTURE"
    }
    present = tuple(sorted(split_keys & retained_keys))
    missing = tuple(sorted(split_keys - retained_keys))
    return B4ProvenanceAudit(
        audit_version=B4_PROVENANCE_AUDIT_VERSION,
        split_freeze_hash=split_freeze.content_hash,
        retained_material_keys=present,
        missing_material_keys=missing,
        ingress_materialization_authorized=not missing,
    )
