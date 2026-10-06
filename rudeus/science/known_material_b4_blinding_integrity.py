"""B4 blinding-integrity audit for the frozen known-material cohort.

Executable structure readiness is not equivalent to blinding.  This audit fails
closed when repository-visible state lets an execution-visible identifier be
reassociated with frozen material identity or truth before blinded results freeze.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from rudeus.science.contracts import Record, require_hash
from rudeus.science.known_material_b3_split import B3SplitFreeze
from rudeus.science.known_material_b4_blind_package import visible_structure_hash
from rudeus.science.known_material_structure_resolution import StructureResolutionLedger
from rudeus.science.known_material_truth import KnownMaterialTruthBundle


B4_BLINDING_INTEGRITY_VERSION = "known-material-b4-blinding-integrity-v1"

PUBLIC_FROZEN_MATERIAL_IDENTITIES = "PUBLIC_FROZEN_MATERIAL_IDENTITIES"
PUBLIC_TRUTH_BUNDLE_BINDINGS = "PUBLIC_TRUTH_BUNDLE_BINDINGS"
PUBLIC_VISIBLE_STRUCTURE_HASH_BINDINGS = "PUBLIC_VISIBLE_STRUCTURE_HASH_BINDINGS"


@dataclass(frozen=True, kw_only=True)
class PublicStructureIdentityBinding(Record):
    material_key: str
    visible_structure_hash: str

    def validate(self):
        super().validate()
        if not self.material_key:
            raise ValueError("public structure identity binding requires material key")
        require_hash(self.visible_structure_hash)


@dataclass(frozen=True, kw_only=True)
class B4BlindingIntegrityAudit(Record):
    audit_version: str
    split_freeze_hash: str
    public_frozen_material_keys: tuple[str, ...]
    public_truth_material_keys: tuple[str, ...]
    public_structure_bindings: tuple[PublicStructureIdentityBinding, ...]
    contamination_codes: tuple[str, ...]
    strong_blind_qualification_authorized: bool
    production_blind_package_authorized: bool

    @classmethod
    def from_dict(cls, value):
        value = dict(value)
        value["public_structure_bindings"] = tuple(
            PublicStructureIdentityBinding.from_dict(item)
            for item in value["public_structure_bindings"]
        )
        return cls(**value)

    def validate(self):
        super().validate()
        require_hash(self.split_freeze_hash)
        expected_codes = []
        if self.public_frozen_material_keys:
            expected_codes.append(PUBLIC_FROZEN_MATERIAL_IDENTITIES)
        if self.public_truth_material_keys:
            expected_codes.append(PUBLIC_TRUTH_BUNDLE_BINDINGS)
        if self.public_structure_bindings:
            expected_codes.append(PUBLIC_VISIBLE_STRUCTURE_HASH_BINDINGS)
        if self.contamination_codes != tuple(expected_codes):
            raise ValueError("blinding contamination codes disagree with exposed state")
        authorized = not self.contamination_codes
        if self.strong_blind_qualification_authorized is not authorized:
            raise ValueError("strong blind qualification authorization disagrees with audit")
        if self.production_blind_package_authorized is not authorized:
            raise ValueError("production blind package authorization disagrees with audit")


def audit_b4_blinding_integrity(
    split_freeze: B3SplitFreeze,
    truth_bundles: Mapping[str, KnownMaterialTruthBundle],
    structure_ledger: StructureResolutionLedger,
) -> B4BlindingIntegrityAudit:
    """Audit whether the canonical cohort still supports strong blind qualification.

    The current v1 freeze stores legacy material keys directly.  If those keys,
    their truth bundles, or execution-visible structure hashes are repository
    visible, an opaque-id permutation cannot restore strong blinding.
    """
    frozen_keys = {member.benchmark_id for member in split_freeze.members}
    public_frozen = tuple(sorted(frozen_keys))

    public_truth = tuple(sorted(frozen_keys & set(truth_bundles)))

    case_by_material = {
        case.material_key: case
        for case in structure_ledger.cases
    }
    public_structure = tuple(
        PublicStructureIdentityBinding(
            material_key=material_key,
            visible_structure_hash=visible_structure_hash(case_by_material[material_key]),
        )
        for material_key in sorted(frozen_keys & set(case_by_material))
    )

    codes = []
    if public_frozen:
        codes.append(PUBLIC_FROZEN_MATERIAL_IDENTITIES)
    if public_truth:
        codes.append(PUBLIC_TRUTH_BUNDLE_BINDINGS)
    if public_structure:
        codes.append(PUBLIC_VISIBLE_STRUCTURE_HASH_BINDINGS)

    authorized = not codes
    audit = B4BlindingIntegrityAudit(
        audit_version=B4_BLINDING_INTEGRITY_VERSION,
        split_freeze_hash=split_freeze.content_hash,
        public_frozen_material_keys=public_frozen,
        public_truth_material_keys=public_truth,
        public_structure_bindings=public_structure,
        contamination_codes=tuple(codes),
        strong_blind_qualification_authorized=authorized,
        production_blind_package_authorized=authorized,
    )
    audit.validate()
    return audit
