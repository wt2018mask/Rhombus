"""Evidence-gated representation policies for known-material structure resolution.

Policies are material-agnostic data contracts. A structure case names a policy; the
policy declares which resolution modes it can govern and which evidence-backed inputs
must exist before scientific execution readiness can be claimed. Merely naming a
policy never satisfies it.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path
from typing import Any, Mapping

from rudeus.science.contracts import Record, require_hash


REPRESENTATION_POLICY_VERSION = "known-material-representation-policy-v1"
REPRESENTATION_EVIDENCE_LEDGER_VERSION = (
    "known-material-representation-evidence-ledger-v1"
)

SUPPORTED_RESOLUTION_MODES = frozenset({
    "DIRECT",
    "PHASE_SET",
    "ENSEMBLE",
})


class RepresentationPolicyKind(str, Enum):
    EXACT = "EXACT"
    FRACTIONAL_OCCUPANCY = "FRACTIONAL_OCCUPANCY"
    CONFIGURATION_ENSEMBLE = "CONFIGURATION_ENSEMBLE"
    PHASE_RESOLVED = "PHASE_RESOLVED"
    MICROSTRUCTURE = "MICROSTRUCTURE"


class RepresentationEvidenceDisposition(str, Enum):
    SATISFIED = "SATISFIED"
    REJECTED = "REJECTED"


class RepresentationPolicyStatus(str, Enum):
    SATISFIED = "SATISFIED"
    BLOCKED_MISSING_EVIDENCE = "BLOCKED_MISSING_EVIDENCE"
    BLOCKED_REJECTED_EVIDENCE = "BLOCKED_REJECTED_EVIDENCE"


@dataclass(frozen=True, kw_only=True)
class RepresentationPolicySpec(Record):
    policy_id: str
    policy_kind: str
    applicable_modes: tuple[str, ...]
    required_inputs: tuple[str, ...]
    optional_inputs: tuple[str, ...] = ()
    forbidden_shortcuts: tuple[str, ...] = ()
    rationale: tuple[str, ...] = ()

    def validate(self):
        super().validate()
        RepresentationPolicyKind(self.policy_kind)
        if not self.policy_id:
            raise ValueError("representation policy requires an id")
        if not self.applicable_modes:
            raise ValueError("representation policy requires applicable modes")
        if len(self.applicable_modes) != len(set(self.applicable_modes)):
            raise ValueError("representation policy contains duplicate modes")
        unknown_modes = set(self.applicable_modes) - SUPPORTED_RESOLUTION_MODES
        if unknown_modes:
            raise ValueError(
                "representation policy contains unsupported resolution modes: "
                + ", ".join(sorted(unknown_modes))
            )
        if len(self.required_inputs) != len(set(self.required_inputs)):
            raise ValueError("representation policy contains duplicate required inputs")
        if len(self.optional_inputs) != len(set(self.optional_inputs)):
            raise ValueError("representation policy contains duplicate optional inputs")
        if set(self.required_inputs) & set(self.optional_inputs):
            raise ValueError("representation policy input cannot be required and optional")
        if any(not item for item in self.required_inputs + self.optional_inputs):
            raise ValueError("representation policy input keys must be nonempty")


@dataclass(frozen=True, kw_only=True)
class RepresentationPolicyRegistry(Record):
    registry_version: str
    policies: tuple[RepresentationPolicySpec, ...]

    @classmethod
    def from_dict(cls, value):
        value = dict(value)
        value["policies"] = tuple(
            RepresentationPolicySpec.from_dict(item) for item in value["policies"]
        )
        return cls(**value)

    def validate(self):
        super().validate()
        if self.registry_version != REPRESENTATION_POLICY_VERSION:
            raise ValueError("unsupported representation policy registry version")
        ids = [policy.policy_id for policy in self.policies]
        if not ids or len(ids) != len(set(ids)):
            raise ValueError("representation policy registry requires unique policy ids")


@dataclass(frozen=True, kw_only=True)
class RepresentationPolicyEvidence(Record):
    policy_id: str
    input_key: str
    disposition: str
    provenance_hash: str
    evidence_refs: tuple[str, ...]
    payload: Mapping[str, Any]
    rationale: tuple[str, ...] = ()

    def validate(self):
        super().validate()
        disposition = RepresentationEvidenceDisposition(self.disposition)
        if not self.policy_id or not self.input_key:
            raise ValueError("representation policy evidence identity is incomplete")
        require_hash(self.provenance_hash)
        if disposition == RepresentationEvidenceDisposition.SATISFIED:
            if not self.evidence_refs or not self.payload:
                raise ValueError(
                    "satisfied representation evidence requires refs and payload"
                )
        elif not self.rationale:
            raise ValueError("rejected representation evidence requires rationale")


@dataclass(frozen=True, kw_only=True)
class RepresentationEvidenceLedger(Record):
    ledger_version: str
    entries: tuple[RepresentationPolicyEvidence, ...]

    @classmethod
    def from_dict(cls, value):
        value = dict(value)
        value["entries"] = tuple(
            RepresentationPolicyEvidence.from_dict(item) for item in value["entries"]
        )
        return cls(**value)

    def validate(self):
        super().validate()
        if self.ledger_version != REPRESENTATION_EVIDENCE_LEDGER_VERSION:
            raise ValueError("unsupported representation evidence ledger version")
        keys = [(entry.policy_id, entry.input_key) for entry in self.entries]
        if len(keys) != len(set(keys)):
            raise ValueError(
                "representation evidence ledger requires unique policy/input pairs"
            )


@dataclass(frozen=True, kw_only=True)
class RepresentationPolicyResolution(Record):
    policy_id: str
    status: str
    required_inputs: tuple[str, ...]
    satisfied_inputs: tuple[str, ...]
    missing_inputs: tuple[str, ...]
    rejected_inputs: tuple[str, ...]
    evidence_hashes: tuple[str, ...]

    def validate(self):
        super().validate()
        status = RepresentationPolicyStatus(self.status)
        if not self.policy_id:
            raise ValueError("representation policy resolution requires a policy id")
        groups = (
            self.required_inputs,
            self.satisfied_inputs,
            self.missing_inputs,
            self.rejected_inputs,
        )
        if any(len(group) != len(set(group)) for group in groups):
            raise ValueError("representation policy resolution contains duplicates")
        if set(self.satisfied_inputs) & set(self.missing_inputs):
            raise ValueError("policy input cannot be both satisfied and missing")
        if set(self.satisfied_inputs) & set(self.rejected_inputs):
            raise ValueError("policy input cannot be both satisfied and rejected")
        if set(self.missing_inputs) & set(self.rejected_inputs):
            raise ValueError("policy input cannot be both missing and rejected")
        if (
            set(self.satisfied_inputs)
            | set(self.missing_inputs)
            | set(self.rejected_inputs)
        ) != set(self.required_inputs):
            raise ValueError("policy resolution must partition required inputs")
        for digest in self.evidence_hashes:
            require_hash(digest)

        if status == RepresentationPolicyStatus.SATISFIED:
            if self.missing_inputs or self.rejected_inputs:
                raise ValueError("satisfied policy cannot retain blockers")
        elif status == RepresentationPolicyStatus.BLOCKED_MISSING_EVIDENCE:
            if not self.missing_inputs or self.rejected_inputs:
                raise ValueError(
                    "missing-evidence status requires only missing blockers"
                )
        elif status == RepresentationPolicyStatus.BLOCKED_REJECTED_EVIDENCE:
            if not self.rejected_inputs:
                raise ValueError(
                    "rejected-evidence status requires rejected policy evidence"
                )


def load_representation_policy_registry(path: Path) -> RepresentationPolicyRegistry:
    return RepresentationPolicyRegistry.from_dict(
        json.loads(path.read_text(encoding="utf-8"))
    )


def load_representation_evidence_ledger(path: Path) -> RepresentationEvidenceLedger:
    return RepresentationEvidenceLedger.from_dict(
        json.loads(path.read_text(encoding="utf-8"))
    )



def validate_representation_evidence_ledger(
    registry: RepresentationPolicyRegistry,
    evidence_ledger: RepresentationEvidenceLedger,
) -> None:
    by_id = {policy.policy_id: policy for policy in registry.policies}
    for entry in evidence_ledger.entries:
        policy = by_id.get(entry.policy_id)
        if policy is None:
            raise ValueError(
                "representation evidence references unknown policy: "
                + entry.policy_id
            )
        declared = set(policy.required_inputs) | set(policy.optional_inputs)
        if entry.input_key not in declared:
            raise ValueError(
                "representation evidence input is not declared by policy: "
                + entry.input_key
            )


def resolve_representation_policy(
    *,
    policy_id: str,
    resolution_mode: str,
    registry: RepresentationPolicyRegistry,
    evidence_ledger: RepresentationEvidenceLedger,
    additional_required_inputs: tuple[str, ...] = (),
) -> RepresentationPolicyResolution:
    by_id = {policy.policy_id: policy for policy in registry.policies}
    try:
        policy = by_id[policy_id]
    except KeyError as exc:
        raise ValueError(
            f"structure resolution references unknown representation policy: {policy_id}"
        ) from exc

    if resolution_mode not in policy.applicable_modes:
        raise ValueError(
            "representation policy is incompatible with structure resolution mode"
        )

    declared_inputs = set(policy.required_inputs) | set(policy.optional_inputs)
    undeclared = tuple(
        item for item in additional_required_inputs if item not in declared_inputs
    )
    if undeclared:
        raise ValueError(
            "structure resolution requires inputs not declared by policy: "
            + ", ".join(undeclared)
        )

    required = tuple(dict.fromkeys(
        tuple(policy.required_inputs) + tuple(additional_required_inputs)
    ))

    evidence_for_policy = {
        entry.input_key: entry
        for entry in evidence_ledger.entries
        if entry.policy_id == policy_id
    }
    unknown_evidence = tuple(
        key for key in evidence_for_policy if key not in declared_inputs
    )
    if unknown_evidence:
        raise ValueError(
            "representation evidence contains inputs not declared by policy: "
            + ", ".join(sorted(unknown_evidence))
        )

    satisfied = []
    missing = []
    rejected = []
    evidence_hashes = []
    for input_key in required:
        evidence = evidence_for_policy.get(input_key)
        if evidence is None:
            missing.append(input_key)
            continue
        evidence_hashes.append(evidence.content_hash)
        if (
            evidence.disposition
            == RepresentationEvidenceDisposition.SATISFIED.value
        ):
            satisfied.append(input_key)
        else:
            rejected.append(input_key)

    if rejected:
        status = RepresentationPolicyStatus.BLOCKED_REJECTED_EVIDENCE.value
    elif missing:
        status = RepresentationPolicyStatus.BLOCKED_MISSING_EVIDENCE.value
    else:
        status = RepresentationPolicyStatus.SATISFIED.value

    return RepresentationPolicyResolution(
        policy_id=policy_id,
        status=status,
        required_inputs=required,
        satisfied_inputs=tuple(satisfied),
        missing_inputs=tuple(missing),
        rejected_inputs=tuple(rejected),
        evidence_hashes=tuple(evidence_hashes),
    )
