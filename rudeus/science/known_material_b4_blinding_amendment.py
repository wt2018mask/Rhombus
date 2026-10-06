"""B4 blinding amendment over the immutable B3 split.

The B3 freeze is historical and must not be rewritten even though its benchmark_id
values are material keys.  This amendment binds the frozen membership to caller-
supplied opaque execution ids plus one common benchmark protocol hash.  The sealed
legacy-to-opaque mapping is not part of the blind execution payload.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping

from rudeus.science.contracts import Record, require_hash
from rudeus.science.known_material_b3_split import B3SplitFreeze


B4_BLIND_IDENTITY_AMENDMENT_VERSION = "known-material-b4-blind-identity-amendment-v1"
OPAQUE_ID_RE = re.compile(r"km-[a-z0-9]{8}")


@dataclass(frozen=True, kw_only=True)
class B4BlindIdentityBinding(Record):
    legacy_benchmark_id: str
    opaque_benchmark_id: str
    split: str
    truth_bundle_hash: str

    def validate(self):
        super().validate()
        if not self.legacy_benchmark_id:
            raise ValueError("blind identity binding requires legacy benchmark id")
        if not OPAQUE_ID_RE.fullmatch(self.opaque_benchmark_id):
            raise ValueError("opaque benchmark id must match km-[a-z0-9]{8}")
        if self.split not in {"DEV", "HELD_OUT"}:
            raise ValueError("blind identity binding split must be DEV or HELD_OUT")
        require_hash(self.truth_bundle_hash)


@dataclass(frozen=True, kw_only=True)
class B4BlindIdentityAmendment(Record):
    amendment_version: str
    split_freeze_hash: str
    benchmark_protocol_hash: str
    bindings: tuple[B4BlindIdentityBinding, ...]

    def validate(self):
        super().validate()
        if self.amendment_version != B4_BLIND_IDENTITY_AMENDMENT_VERSION:
            raise ValueError("unsupported B4 blind-identity amendment version")
        require_hash(self.split_freeze_hash)
        require_hash(self.benchmark_protocol_hash)
        if not self.bindings:
            raise ValueError("blind identity amendment requires bindings")
        legacy_ids = tuple(item.legacy_benchmark_id for item in self.bindings)
        opaque_ids = tuple(item.opaque_benchmark_id for item in self.bindings)
        if len(set(legacy_ids)) != len(legacy_ids):
            raise ValueError("legacy benchmark ids must be unique")
        if len(set(opaque_ids)) != len(opaque_ids):
            raise ValueError("opaque benchmark ids must be unique")


def build_b4_blind_identity_amendment(
    split_freeze: B3SplitFreeze,
    *,
    opaque_ids_by_legacy_id: Mapping[str, str],
    protocol_hash_by_truth_bundle_hash: Mapping[str, str],
) -> B4BlindIdentityAmendment:
    frozen_ids = {member.benchmark_id for member in split_freeze.members}
    if set(opaque_ids_by_legacy_id) != frozen_ids:
        raise ValueError("opaque-id mapping must cover exactly the frozen B3 membership")

    protocol_hashes = set()
    bindings = []
    for member in split_freeze.members:
        try:
            protocol_hash = protocol_hash_by_truth_bundle_hash[member.truth_bundle_hash]
        except KeyError as exc:
            raise ValueError(
                "protocol binding missing frozen truth-bundle hash"
            ) from exc
        require_hash(protocol_hash)
        protocol_hashes.add(protocol_hash)
        bindings.append(
            B4BlindIdentityBinding(
                legacy_benchmark_id=member.benchmark_id,
                opaque_benchmark_id=opaque_ids_by_legacy_id[member.benchmark_id],
                split=member.split,
                truth_bundle_hash=member.truth_bundle_hash,
            )
        )

    if len(protocol_hashes) != 1:
        raise ValueError("all frozen B3 members must share one benchmark protocol hash")

    amendment = B4BlindIdentityAmendment(
        amendment_version=B4_BLIND_IDENTITY_AMENDMENT_VERSION,
        split_freeze_hash=split_freeze.content_hash,
        benchmark_protocol_hash=next(iter(protocol_hashes)),
        bindings=tuple(bindings),
    )
    amendment.validate()
    return amendment
