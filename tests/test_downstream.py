"""Synthetic contract fixtures; no scientific threshold or model is qualified here."""
from dataclasses import replace

import pytest

from rudeus.science.contracts import ClaimAssessment, ClaimSpec, Verdict, digest
from rudeus.science.downstream import (
    CLAIM_IDS, ApplicationProfile, CrosscheckEvidence, CrosscheckTask,
    FinalDiscoveryManifest, ModelIdentity, NoveltyEvidence, ProfileClaimEvidence, StageAssessment,
    SynthesisCriterion, SynthesisEvidence, SYNTHESIS_CRITERIA,
    assess_application, assess_crosscheck, assess_novelty, assess_synthesis,
    make_out, qualified_upstream_claims,
)


def h(value):
    return digest(value)


def stage(name, verdict="PASS"):
    return StageAssessment(stage=name, verdict=Verdict(verdict), applicability="APPLICABLE",
                           reason_codes=("synthetic",), evidence_hashes=(h(name),))


def out(claims=None, stages=None, **changes):
    values = dict(candidate_id="synthetic", claims={k: "PASS" for k in CLAIM_IDS},
                  stages={k: stage(k) for k in ("X", "N", "S", "APPLICATION")},
                  applicability={k: "APPLICABLE" for k in ("X", "N", "S", "APPLICATION")},
                  protocol_hashes={"pipeline": h("protocol")}, config_hashes={"pipeline": h("config")},
                  input_artifact_hashes=(h("input"),), output_artifact_hashes=(h("output"),),
                  execution_references=(h("execution"),), provenance_references=(h("provenance"),))
    if claims is not None:
        values["claims"] = claims
    if stages is not None:
        values["stages"] = stages
    values.update(changes)
    return make_out(**values)


@pytest.mark.parametrize("override,expected", [({}, "PASS"),
    ({"existence": "FAIL"}, "FAIL"), ({"diffusion": "UNKNOWN"}, "UNKNOWN"),
    ({"transport_p3": "INDETERMINATE"}, "INDETERMINATE"),
    ({"existence": "FAIL", "diffusion": "UNKNOWN"}, "FAIL"),
    ({"existence": "INDETERMINATE", "diffusion": "UNKNOWN"}, "UNKNOWN")])
def test_final_conjunction(override, expected):
    claims = {k: "PASS" for k in CLAIM_IDS}
    claims.update(override)
    manifest = out(claims=claims)
    assert manifest.final_assessment == expected
    assert set(manifest.claim_vector) == set(CLAIM_IDS)
    assert digest(manifest.to_dict()) == manifest.content_hash
    assert FinalDiscoveryManifest.from_dict(manifest.to_dict()) == manifest
    with pytest.raises(TypeError):
        manifest.claim_vector["existence"] = "FAIL"


@pytest.mark.parametrize("missing", ["X", "N", "S", "APPLICATION"])
def test_missing_downstream_evidence_cannot_pass(missing):
    stages = {k: stage(k) for k in ("X", "N", "S", "APPLICATION") if k != missing}
    result = out(stages=stages)
    assert result.final_assessment == "UNKNOWN"
    assert result.stage_assessments[missing].verdict == "UNKNOWN"


def test_provenance_and_no_qualifying_candidate():
    assert out(provenance_references=()).final_assessment == "UNKNOWN"
    assert out(candidate_id=None).final_assessment == "UNKNOWN"
    with pytest.raises(ValueError, match="conjunction"):
        replace(out(), final_assessment=Verdict.FAIL)


def test_crosscheck_independent_models_and_artifacts():
    primary = ModelIdentity(model_id="p", model_version="1", base_model_id="base-p",
                            training_provenance_hash=h("train-p"), protocol_hash=h("p"))
    secondary = ModelIdentity(model_id="s", model_version="1", base_model_id="base-s",
                              training_provenance_hash=h("train-s"), protocol_hash=h("s"))
    task = CrosscheckTask(candidate_id="c", primary=primary, secondary=secondary,
                          observable="structural_stability", conditions={"temperature_K": 500},
                          agreement_rule_hash=h("rule"), input_artifact_hashes=(h("input"),),
                          independence_evidence_hashes=(h("independence"),))
    assert assess_crosscheck(task, None).verdict == "UNKNOWN"
    assert CrosscheckTask.from_dict(task.to_dict()) == task
    evidence = CrosscheckEvidence(task_hash=task.content_hash,
        primary_artifact_hashes=(h("primary-result"),), secondary_artifact_hashes=(h("secondary-result"),),
        disagreement_artifact_hashes=(h("comparison"),), agreement=True, applicable=True,
        qualification_reference=h("qualification"))
    assert assess_crosscheck(task, evidence).verdict == "PASS"
    assert assess_crosscheck(task, replace(evidence, agreement=False)).verdict == "FAIL"
    assert assess_crosscheck(task, replace(evidence, qualification_reference=None)).verdict == "INDETERMINATE"
    same_base = replace(task, secondary=replace(secondary, base_model_id="base-p"))
    assert assess_crosscheck(same_base, replace(evidence, task_hash=same_base.content_hash)).verdict == "INDETERMINATE"


def test_final_novelty_coverage_and_rediscovery():
    evidence = NoveltyEvidence(candidate_id="c", reference_sources={"database-v": h("db")},
        coverage_complete=False, composition_novel=True, structure_novel=True,
        known_material_rediscovery=False, evidence_hashes=(h("matches"),),
        unresolved_coverage=("unindexed_sources",))
    assert assess_novelty(evidence).verdict == "UNKNOWN"
    assert assess_novelty(replace(evidence, coverage_complete=True, unresolved_coverage=())).verdict == "PASS"
    assert assess_novelty(replace(evidence, known_material_rediscovery=True)).verdict == "FAIL"


def test_synthesis_unknowns_and_no_scalar():
    criteria = {k: SynthesisCriterion(verdict=Verdict.PASS, evidence_hashes=(h(k),)) for k in SYNTHESIS_CRITERIA}
    evidence = SynthesisEvidence(candidate_id="c", protocol_hash=h("s-protocol"), criteria=criteria)
    assert SynthesisEvidence.from_dict(evidence.to_dict()) == evidence
    assert assess_synthesis(evidence).verdict == "PASS"
    assert assess_synthesis(replace(evidence, criteria={k: v for k, v in criteria.items() if k != "synthesis_route"})).verdict == "UNKNOWN"
    assert assess_synthesis(replace(evidence, criteria={**criteria, "competing_phases":
        SynthesisCriterion(verdict=Verdict.FAIL, evidence_hashes=(h("phase"),))})).verdict == "FAIL"


def test_application_profile_mandatory_optional_and_acceptance_binding():
    region = {"kind": "exact", "expected": True, "status": "PROVISIONAL", "justification": "fixture"}
    profile = ApplicationProfile(profile_id="test-profile", profile_version="1", protocol_hash=h("profile"),
        mandatory_claims=("a",), optional_claims=("b",), acceptance_regions={"a": region, "b": region},
        applicability_requirements=("species_supported",), profile_requirements=("environment_defined",))
    good = ProfileClaimEvidence(verdict=Verdict.PASS, acceptance_hash=digest(region), applicable=True,
                                evidence_hashes=(h("profile-evidence"),))
    checks = ("species_supported", "environment_defined")
    assert assess_application(profile, {"a": good}, applicable=True, satisfied_requirements=checks).verdict == "PASS"
    assert assess_application(profile, {"b": good}, applicable=True, satisfied_requirements=checks).verdict == "UNKNOWN"
    assert assess_application(profile, {"a": replace(good, acceptance_hash=h("wrong"))},
                              applicable=True, satisfied_requirements=checks).verdict == "UNKNOWN"
    assert assess_application(profile, {"a": good}, applicable=True).verdict == "UNKNOWN"
    assert assess_application(profile, {"a": good}, applicable=False, satisfied_requirements=checks).verdict == "INDETERMINATE"


def test_upstream_assessment_exact_binding():
    spec = ClaimSpec(claim_id="diffusion", protocol_hash=h("protocol"), estimand="D",
        units="m2/s", scope={"temperature_K": 500}, assumptions=(), applicability_requirements=(),
        sufficiency_requirements=(), admissible_evidence=("derived_quantity",),
        independence_requirements=(), provenance_identity=h("source"))
    assessment = ClaimAssessment(claim_id="diffusion", claim_hash=spec.content_hash,
        protocol_hash=spec.protocol_hash, verdict=Verdict.PASS, assumptions={}, applicability={},
        statistical_sufficiency={}, reason_codes=("synthetic",), supporting_evidence=(h("artifact"),))
    assert qualified_upstream_claims({"diffusion": spec}, (assessment,)) == {"diffusion": "PASS"}
    assert qualified_upstream_claims({"diffusion": spec}, (replace(assessment, claim_hash=h("wrong")),)) == {"diffusion": "UNKNOWN"}
