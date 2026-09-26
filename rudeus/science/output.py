"""Final research-output contract (stage OUT).

OUT is a presentation layer over an already-verified SynthesisAssessment.
It must preserve scientific status exactly, surface conflicts and unresolved
requirements, and never rewrite uncertainty into stronger language.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from rudeus.science.contracts import Record, Verdict, digest, require_hash
from rudeus.science.synthesis import SStatus, SynthesisAssessment


class OUTDisposition(str, Enum):
    SUPPORTED = "SUPPORTED"
    NOT_SUPPORTED = "NOT_SUPPORTED"
    UNRESOLVED = "UNRESOLVED"
    CONFLICTED = "CONFLICTED"


@dataclass(frozen=True, kw_only=True)
class ResearchOutput(Record):
    synthesis_hash: str
    synthesis_status: SStatus
    claim_verdict: Verdict
    disposition: OUTDisposition
    headline: str
    summary: str
    supporting_evidence: tuple[str, ...]
    conflicting_evidence: tuple[str, ...]
    unresolved_requirements: tuple[str, ...]
    caveats: tuple[str, ...]
    machine_readable: Mapping[str, Any]

    def validate(self):
        super().validate()
        require_hash(self.synthesis_hash)
        SStatus(self.synthesis_status)
        Verdict(self.claim_verdict)
        OUTDisposition(self.disposition)
        for value in self.supporting_evidence + self.conflicting_evidence:
            require_hash(value)
        if not self.headline or not self.summary:
            raise ValueError("OUT requires a nonempty headline and summary")
        if self.synthesis_status == SStatus.CONFLICT and self.disposition != OUTDisposition.CONFLICTED:
            raise ValueError("conflicted synthesis must remain CONFLICTED in OUT")
        if self.claim_verdict in (Verdict.UNKNOWN, Verdict.INDETERMINATE) and self.disposition == OUTDisposition.SUPPORTED:
            raise ValueError("unresolved claim cannot be presented as supported")
        if self.claim_verdict == Verdict.FAIL and self.disposition != OUTDisposition.NOT_SUPPORTED:
            raise ValueError("FAIL claim must remain NOT_SUPPORTED in OUT")
        if self.conflicting_evidence and self.disposition != OUTDisposition.CONFLICTED:
            raise ValueError("conflicting evidence must remain visible in OUT")


def _disposition(synthesis: SynthesisAssessment) -> OUTDisposition:
    if synthesis.status == SStatus.CONFLICT or synthesis.conflicting_evidence:
        return OUTDisposition.CONFLICTED
    if synthesis.final_claim_verdict == Verdict.FAIL:
        return OUTDisposition.NOT_SUPPORTED
    if synthesis.final_claim_verdict == Verdict.PASS:
        return OUTDisposition.SUPPORTED
    return OUTDisposition.UNRESOLVED


def build_output(synthesis: SynthesisAssessment) -> ResearchOutput:
    """Convert S to a conservative, deterministic research output."""
    disposition = _disposition(synthesis)

    if disposition == OUTDisposition.CONFLICTED:
        headline = "Evidence conflict remains unresolved"
        summary = (
            "The available evidence contains unresolved conflict. "
            "No positive scientific conclusion is authorized."
        )
    elif disposition == OUTDisposition.NOT_SUPPORTED:
        headline = "Claim not supported by the current evidence"
        summary = (
            "The synthesized evidence does not support the claim under the "
            "registered scope and criteria."
        )
    elif disposition == OUTDisposition.SUPPORTED:
        headline = "Claim supported within the registered scope"
        summary = (
            "The synthesized evidence supports the claim only within the "
            "registered scope, assumptions, and qualification limits."
        )
    else:
        headline = "Scientific conclusion remains unresolved"
        summary = (
            "The available evidence is insufficient for a decisive conclusion. "
            "Unknown or indeterminate requirements remain explicit."
        )

    caveats = []
    if synthesis.x_assessment_hashes:
        caveats.append("independent-model cross-check evidence is included")
    if synthesis.n_assessment_hashes:
        caveats.append("negative-control evidence is included")
    if synthesis.conflicting_evidence:
        caveats.append("conflicting evidence requires resolution")
    if synthesis.unresolved_requirements:
        caveats.append("unresolved scientific requirements remain")
    caveats.append("OUT does not recompute or upgrade upstream scientific assessments")

    machine = {
        "synthesis_status": synthesis.status.value,
        "claim_verdict": synthesis.final_claim_verdict.value,
        "disposition": disposition.value,
        "primary_claim_hash": synthesis.primary_claim_hash,
        "primary_assessment_hash": synthesis.primary_assessment_hash,
        "x_assessment_hashes": list(synthesis.x_assessment_hashes),
        "n_assessment_hashes": list(synthesis.n_assessment_hashes),
        "reason_codes": list(synthesis.reason_codes),
    }

    return ResearchOutput(
        synthesis_hash=synthesis.content_hash,
        synthesis_status=synthesis.status,
        claim_verdict=synthesis.final_claim_verdict,
        disposition=disposition,
        headline=headline,
        summary=summary,
        supporting_evidence=synthesis.supporting_evidence,
        conflicting_evidence=synthesis.conflicting_evidence,
        unresolved_requirements=synthesis.unresolved_requirements,
        caveats=tuple(caveats),
        machine_readable=machine,
    )


def out_record(synthesis: SynthesisAssessment) -> dict[str, Any]:
    output = build_output(synthesis)
    return {
        "stage": "OUT",
        "synthesis": synthesis.to_dict(),
        "output": output.to_dict(),
    }


def verify_out_record(record: Mapping[str, Any]) -> dict[str, Any]:
    required = {"stage", "synthesis", "output"}
    if set(record) != required or record.get("stage") != "OUT":
        raise ValueError("invalid OUT record schema")

    synthesis = SynthesisAssessment.from_dict(record["synthesis"])
    stored = ResearchOutput.from_dict(record["output"])
    replayed = build_output(synthesis)
    if stored != replayed:
        raise ValueError("OUT replay mismatch")

    return {
        "record": dict(record),
        "record_hash": digest(record),
        "disposition": replayed.disposition.value,
        "claim_verdict": replayed.claim_verdict.value,
        "synthesis_status": replayed.synthesis_status.value,
    }
