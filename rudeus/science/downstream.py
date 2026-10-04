"""Deterministic X/N/S/application evidence and final discovery sidecar.

These contracts do not select scientific thresholds or grant qualification.
Callers provide explicit, versioned criteria and retained evidence identities.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping

from rudeus.science.contracts import ClaimAssessment, ClaimSpec, Record, Verdict, digest, require_hash
from rudeus.science.claims import final_claim_vector


CLAIM_IDS = (
    "existence", "structural_energetic_validity", "dynamic_stability",
    "diffusion", "transport_p3", "uncertainty_qualification",
    "independent_crosscheck", "novelty", "synthesizability",
    "application_compatibility", "provenance_sufficiency",
)


def _hashes(values):
    for value in values:
        require_hash(value)


def _verdict(value):
    return Verdict(value).value


def conjunction(mandatory: Mapping[str, str | Verdict]) -> str:
    """FAIL > UNKNOWN > INDETERMINATE > PASS; empty set is UNKNOWN."""
    states = {_verdict(v) for v in mandatory.values()}
    return next(v for v in ("FAIL", "UNKNOWN", "INDETERMINATE", "PASS") if v in states) if states else "UNKNOWN"


def qualified_upstream_claims(specs: Mapping[str, ClaimSpec],
                              assessments: tuple[ClaimAssessment, ...]) -> dict[str, str]:
    """Bind existing scientific assessments by exact ClaimSpec hash and protocol."""
    downstream = {"independent_crosscheck", "novelty", "synthesizability", "application_compatibility"}
    if set(specs) - (set(CLAIM_IDS) - downstream):
        raise ValueError("unknown or downstream claim supplied as upstream")
    if any(spec.claim_id != name for name, spec in specs.items()):
        raise ValueError("claim identity mismatch")
    rows = final_claim_vector(tuple(specs.values()), assessments)["claims"]
    return {row["claim_id"]: row["verdict"] for row in rows}


@dataclass(frozen=True, kw_only=True)
class StageAssessment(Record):
    stage: str
    verdict: Verdict
    applicability: str
    reason_codes: tuple[str, ...]
    evidence_hashes: tuple[str, ...] = ()
    unresolved: tuple[str, ...] = ()

    def validate(self):
        super().validate()
        _verdict(self.verdict)
        if self.stage not in ("X", "N", "S", "APPLICATION"):
            raise ValueError("invalid downstream stage")
        if self.applicability not in ("APPLICABLE", "INAPPLICABLE", "UNKNOWN"):
            raise ValueError("invalid applicability")
        _hashes(self.evidence_hashes)
        if self.verdict in (Verdict.PASS, Verdict.FAIL) and not self.evidence_hashes:
            raise ValueError("resolved stage verdict requires retained evidence")
        if self.verdict == Verdict.PASS and (self.applicability != "APPLICABLE" or self.unresolved):
            raise ValueError("PASS requires applicable, resolved evidence")


@dataclass(frozen=True, kw_only=True)
class ModelIdentity(Record):
    model_id: str
    model_version: str
    base_model_id: str
    training_provenance_hash: str
    protocol_hash: str

    def validate(self):
        super().validate()
        if not all((self.model_id, self.model_version, self.base_model_id)):
            raise ValueError("model identity incomplete")
        _hashes((self.training_provenance_hash, self.protocol_hash))


@dataclass(frozen=True, kw_only=True)
class CrosscheckTask(Record):
    candidate_id: str
    primary: ModelIdentity
    secondary: ModelIdentity | None
    observable: str
    conditions: Mapping
    agreement_rule_hash: str | None
    input_artifact_hashes: tuple[str, ...]
    independence_evidence_hashes: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, value):
        value = dict(value)
        value["primary"] = ModelIdentity.from_dict(value["primary"])
        if value.get("secondary") is not None:
            value["secondary"] = ModelIdentity.from_dict(value["secondary"])
        return cls(**value)

    def validate(self):
        super().validate()
        if not self.candidate_id or not self.observable or not self.conditions:
            raise ValueError("cross-check target incomplete")
        if not isinstance(self.primary, ModelIdentity) or (self.secondary is not None and not isinstance(self.secondary, ModelIdentity)):
            raise ValueError("typed model identities required")
        _hashes(self.input_artifact_hashes + self.independence_evidence_hashes)
        if self.agreement_rule_hash is not None:
            require_hash(self.agreement_rule_hash)


@dataclass(frozen=True, kw_only=True)
class CrosscheckEvidence(Record):
    task_hash: str
    primary_artifact_hashes: tuple[str, ...]
    secondary_artifact_hashes: tuple[str, ...]
    disagreement_artifact_hashes: tuple[str, ...]
    agreement: bool | None
    applicable: bool | None
    qualification_reference: str | None = None

    def validate(self):
        super().validate()
        require_hash(self.task_hash)
        _hashes(self.primary_artifact_hashes + self.secondary_artifact_hashes + self.disagreement_artifact_hashes)
        if self.qualification_reference is not None:
            require_hash(self.qualification_reference)


def assess_crosscheck(task: CrosscheckTask, evidence: CrosscheckEvidence | None) -> StageAssessment:
    missing = []
    if task.secondary is None:
        missing.append("secondary_model_selection")
    elif task.primary.base_model_id == task.secondary.base_model_id:
        missing.append("independent_base_model")
    if not task.independence_evidence_hashes:
        missing.append("independence_evidence")
    if not task.input_artifact_hashes:
        missing.append("input_artifacts")
    if task.agreement_rule_hash is None:
        missing.append("agreement_rule")
    if evidence is None:
        missing.append("crosscheck_evidence")
        return StageAssessment(stage="X", verdict=Verdict.UNKNOWN, applicability="UNKNOWN",
                               reason_codes=("evidence_unavailable",), unresolved=tuple(missing))
    if evidence.task_hash != task.content_hash:
        raise ValueError("cross-check evidence task mismatch")
    if not evidence.primary_artifact_hashes or not evidence.secondary_artifact_hashes or not evidence.disagreement_artifact_hashes:
        missing.append("model_and_disagreement_artifacts")
    if evidence.applicable is not True:
        return StageAssessment(stage="X", verdict=Verdict.INDETERMINATE if evidence.applicable is False else Verdict.UNKNOWN,
                               applicability="INAPPLICABLE" if evidence.applicable is False else "UNKNOWN",
                               reason_codes=("model_applicability_unresolved",), unresolved=tuple(missing + ["applicability"]))
    if missing or evidence.qualification_reference is None or evidence.agreement is None:
        return StageAssessment(stage="X", verdict=Verdict.INDETERMINATE, applicability="APPLICABLE",
                               reason_codes=("crosscheck_not_qualified",), unresolved=tuple(missing + ([] if evidence.qualification_reference else ["qualification"])))
    return StageAssessment(stage="X", verdict=Verdict.PASS if evidence.agreement else Verdict.FAIL,
                           applicability="APPLICABLE", reason_codes=("qualified_agreement" if evidence.agreement else "qualified_disagreement",),
                           evidence_hashes=evidence.primary_artifact_hashes + evidence.secondary_artifact_hashes + evidence.disagreement_artifact_hashes + (evidence.qualification_reference,))


@dataclass(frozen=True, kw_only=True)
class NoveltyEvidence(Record):
    candidate_id: str
    reference_sources: Mapping[str, str]
    coverage_complete: bool | None
    composition_novel: bool | None
    structure_novel: bool | None
    known_material_rediscovery: bool | None
    evidence_hashes: tuple[str, ...]
    unresolved_coverage: tuple[str, ...] = ()

    def validate(self):
        super().validate()
        if not self.candidate_id:
            raise ValueError("candidate identity required")
        _hashes(tuple(self.reference_sources.values()) + self.evidence_hashes)


def assess_novelty(e: NoveltyEvidence | None) -> StageAssessment:
    if e is None:
        return StageAssessment(stage="N", verdict=Verdict.UNKNOWN, applicability="UNKNOWN",
                               reason_codes=("evidence_unavailable",), unresolved=("final_novelty",))
    support = e.evidence_hashes + tuple(e.reference_sources.values())
    if not e.evidence_hashes or not e.reference_sources:
        return StageAssessment(stage="N", verdict=Verdict.UNKNOWN, applicability="UNKNOWN",
                               reason_codes=("reference_evidence_unavailable",), unresolved=("reference_sources",))
    if e.known_material_rediscovery is True or e.composition_novel is False or e.structure_novel is False:
        return StageAssessment(stage="N", verdict=Verdict.FAIL, applicability="APPLICABLE",
                               reason_codes=("known_or_matching_material",), evidence_hashes=support)
    if e.coverage_complete is not True or e.unresolved_coverage or e.known_material_rediscovery is None or e.composition_novel is None or e.structure_novel is None:
        return StageAssessment(stage="N", verdict=Verdict.UNKNOWN, applicability="APPLICABLE",
                               reason_codes=("reference_coverage_or_novelty_unresolved",), evidence_hashes=support,
                               unresolved=e.unresolved_coverage or ("reference_coverage_or_novelty",))
    return StageAssessment(stage="N", verdict=Verdict.PASS, applicability="APPLICABLE",
                           reason_codes=("qualified_final_novelty",), evidence_hashes=support)


SYNTHESIS_CRITERIA = ("precursor_availability", "compositional_feasibility", "chemical_plausibility",
                      "competing_phases", "synthesis_route")


@dataclass(frozen=True, kw_only=True)
class SynthesisCriterion(Record):
    verdict: Verdict
    evidence_hashes: tuple[str, ...] = ()
    limitation: str | None = None

    def validate(self):
        super().validate()
        _verdict(self.verdict)
        _hashes(self.evidence_hashes)
        if self.verdict in (Verdict.PASS, Verdict.FAIL) and not self.evidence_hashes:
            raise ValueError("resolved synthesis criterion requires evidence")


@dataclass(frozen=True, kw_only=True)
class SynthesisEvidence(Record):
    candidate_id: str
    protocol_hash: str
    criteria: Mapping[str, SynthesisCriterion]

    @classmethod
    def from_dict(cls, value):
        value = dict(value)
        value["criteria"] = {k: SynthesisCriterion.from_dict(v) for k, v in value["criteria"].items()}
        return cls(**value)

    def validate(self):
        super().validate()
        if not self.candidate_id:
            raise ValueError("candidate identity required")
        require_hash(self.protocol_hash)
        if set(self.criteria) - set(SYNTHESIS_CRITERIA) or any(not isinstance(v, SynthesisCriterion) for v in self.criteria.values()):
            raise ValueError("invalid synthesis criteria")


def assess_synthesis(e: SynthesisEvidence | None) -> StageAssessment:
    if e is None:
        return StageAssessment(stage="S", verdict=Verdict.UNKNOWN, applicability="UNKNOWN",
                               reason_codes=("evidence_unavailable",), unresolved=SYNTHESIS_CRITERIA)
    missing = tuple(k for k in SYNTHESIS_CRITERIA if k not in e.criteria)
    states = {k: e.criteria[k].verdict for k in e.criteria}
    states.update({k: Verdict.UNKNOWN for k in missing})
    hashes = tuple(h for criterion in e.criteria.values() for h in criterion.evidence_hashes)
    return StageAssessment(stage="S", verdict=Verdict(conjunction(states)), applicability="APPLICABLE",
                           reason_codes=("criterion_conjunction",), evidence_hashes=hashes,
                           unresolved=missing + tuple(k for k, v in states.items() if v in (Verdict.UNKNOWN, Verdict.INDETERMINATE)))


@dataclass(frozen=True, kw_only=True)
class ApplicationProfile(Record):
    profile_id: str
    profile_version: str
    protocol_hash: str
    mandatory_claims: tuple[str, ...]
    optional_claims: tuple[str, ...]
    acceptance_regions: Mapping[str, Mapping]
    applicability_requirements: tuple[str, ...]
    profile_requirements: tuple[str, ...]

    def validate(self):
        super().validate()
        require_hash(self.protocol_hash)
        if not self.profile_id or not self.profile_version or not self.mandatory_claims:
            raise ValueError("profile identity and mandatory claims required")
        if len(set(self.mandatory_claims + self.optional_claims)) != len(self.mandatory_claims + self.optional_claims):
            raise ValueError("duplicate profile claim")
        if set(self.acceptance_regions) != set(self.mandatory_claims + self.optional_claims):
            raise ValueError("explicit acceptance region required for each profile claim")
        if any(not region or region.get("status") != "PROVISIONAL" or not region.get("justification")
               for region in self.acceptance_regions.values()):
            raise ValueError("profile acceptance must be explicit and provisional")


@dataclass(frozen=True, kw_only=True)
class ProfileClaimEvidence(Record):
    verdict: Verdict
    acceptance_hash: str
    applicable: bool | None
    evidence_hashes: tuple[str, ...] = ()
    unresolved: tuple[str, ...] = ()

    def validate(self):
        super().validate()
        _verdict(self.verdict)
        require_hash(self.acceptance_hash)
        _hashes(self.evidence_hashes)
        if self.verdict in (Verdict.PASS, Verdict.FAIL) and not self.evidence_hashes:
            raise ValueError("resolved profile verdict requires retained evidence")
        if self.verdict == Verdict.PASS and (self.applicable is not True or self.unresolved):
            raise ValueError("profile PASS needs applicable resolved evidence")


def assess_application(profile: ApplicationProfile, claims: Mapping[str, ProfileClaimEvidence],
                       *, applicable: bool | None, satisfied_requirements: tuple[str, ...] = ()) -> StageAssessment:
    missing = tuple(k for k in profile.mandatory_claims if k not in claims)
    unmet = tuple(k for k in profile.applicability_requirements + profile.profile_requirements if k not in satisfied_requirements)
    if applicable is not True:
        return StageAssessment(stage="APPLICATION", verdict=Verdict.INDETERMINATE if applicable is False else Verdict.UNKNOWN,
                               applicability="INAPPLICABLE" if applicable is False else "UNKNOWN",
                               reason_codes=("profile_applicability_unresolved",), unresolved=missing + unmet)
    states = {}
    for k in profile.mandatory_claims:
        item = claims.get(k)
        states[k] = (item.verdict if item and item.acceptance_hash == digest(profile.acceptance_regions[k])
                     and item.applicable is True else Verdict.UNKNOWN)
    if unmet:
        states.update({k: Verdict.UNKNOWN for k in unmet})
    hashes = tuple(h for k in profile.mandatory_claims if k in claims for h in claims[k].evidence_hashes)
    verdict = Verdict(conjunction(states))
    if verdict == Verdict.PASS and not hashes:
        verdict = Verdict.UNKNOWN
    return StageAssessment(stage="APPLICATION", verdict=verdict, applicability="APPLICABLE",
                           reason_codes=("profile_claim_conjunction",), evidence_hashes=hashes,
                           unresolved=missing + unmet)


@dataclass(frozen=True, kw_only=True)
class FinalDiscoveryManifest(Record):
    candidate_id: str | None
    claim_vector: Mapping[str, str]
    stage_assessments: Mapping[str, StageAssessment]
    applicability: Mapping[str, str]
    unresolved_claims: tuple[str, ...]
    protocol_hashes: Mapping[str, str]
    config_hashes: Mapping[str, str]
    input_artifact_hashes: tuple[str, ...]
    output_artifact_hashes: tuple[str, ...]
    execution_references: tuple[str, ...]
    provenance_references: tuple[str, ...]
    scientific_limitations: tuple[str, ...]
    final_assessment: Verdict

    @classmethod
    def from_dict(cls, value):
        value = dict(value)
        value["stage_assessments"] = {k: StageAssessment.from_dict(v)
                                      for k, v in value["stage_assessments"].items()}
        return cls(**value)

    def validate(self):
        super().validate()
        if set(self.claim_vector) != set(CLAIM_IDS):
            raise ValueError("complete canonical claim vector required")
        if any(k not in self.stage_assessments for k in ("X", "N", "S", "APPLICATION")):
            raise ValueError("all downstream assessments required")
        if any(not isinstance(v, StageAssessment) or v.stage != k for k, v in self.stage_assessments.items()):
            raise ValueError("stage assessment mismatch")
        if any(self.applicability.get(k) != v.applicability for k, v in self.stage_assessments.items()):
            raise ValueError("stage applicability mismatch")
        _hashes(tuple(self.protocol_hashes.values()) + tuple(self.config_hashes.values()) +
                self.input_artifact_hashes + self.output_artifact_hashes + self.execution_references + self.provenance_references)
        expected = conjunction(self.claim_vector)
        if self.final_assessment != expected:
            raise ValueError("final assessment differs from mandatory conjunction")
        binding = {"X": "independent_crosscheck", "N": "novelty", "S": "synthesizability", "APPLICATION": "application_compatibility"}
        if any(self.claim_vector[claim] != self.stage_assessments[stage].verdict for stage, claim in binding.items()):
            raise ValueError("downstream assessment binding mismatch")
        if set(self.unresolved_claims) != {k for k, v in self.claim_vector.items() if v in ("UNKNOWN", "INDETERMINATE")}:
            raise ValueError("unresolved claims mismatch")
        if self.final_assessment == Verdict.PASS and (not self.candidate_id or not self.protocol_hashes or not self.config_hashes
                or not self.input_artifact_hashes or not self.output_artifact_hashes or not self.execution_references
                or not self.provenance_references or self.scientific_limitations):
            raise ValueError("PASS requires complete candidate and provenance bindings")


def make_out(*, candidate_id: str | None, claims: Mapping[str, str | Verdict],
             stages: Mapping[str, StageAssessment], applicability: Mapping[str, str],
             protocol_hashes: Mapping[str, str], config_hashes: Mapping[str, str],
             input_artifact_hashes: tuple[str, ...], output_artifact_hashes: tuple[str, ...],
             execution_references: tuple[str, ...], provenance_references: tuple[str, ...],
             scientific_limitations: tuple[str, ...] = ()) -> FinalDiscoveryManifest:
    stages = dict(stages)
    for stage in ("X", "N", "S", "APPLICATION"):
        stages.setdefault(stage, StageAssessment(stage=stage, verdict=Verdict.UNKNOWN,
            applicability="UNKNOWN", reason_codes=("stage_evidence_unavailable",),
            unresolved=("stage_evidence",)))
    vector = {k: _verdict(claims.get(k, Verdict.UNKNOWN)) for k in CLAIM_IDS}
    binding = {"X": "independent_crosscheck", "N": "novelty", "S": "synthesizability", "APPLICATION": "application_compatibility"}
    for stage, claim in binding.items():
        vector[claim] = _verdict(stages[stage].verdict) if stage in stages else Verdict.UNKNOWN.value
    # Provenance insufficiency is a scientific claim, never a successful-output flag.
    if (not candidate_id or scientific_limitations or not all((protocol_hashes, config_hashes, input_artifact_hashes,
                output_artifact_hashes, execution_references, provenance_references))) and vector["provenance_sufficiency"] == "PASS":
        vector["provenance_sufficiency"] = "UNKNOWN"
    applicability = {**applicability, **{k: v.applicability for k, v in stages.items()}}
    return FinalDiscoveryManifest(candidate_id=candidate_id, claim_vector=vector,
        stage_assessments=stages, applicability=applicability,
        unresolved_claims=tuple(k for k in CLAIM_IDS if vector[k] in ("UNKNOWN", "INDETERMINATE")),
        protocol_hashes=protocol_hashes, config_hashes=config_hashes,
        input_artifact_hashes=input_artifact_hashes, output_artifact_hashes=output_artifact_hashes,
        execution_references=execution_references, provenance_references=provenance_references,
        scientific_limitations=scientific_limitations, final_assessment=Verdict(conjunction(vector)))
