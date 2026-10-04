"""Synthetic contract fixtures; no scientific threshold or model is qualified here."""
from dataclasses import replace

import pytest

from rudeus.science.contracts import ClaimAssessment, ClaimSpec, Verdict, digest
from rudeus.science.downstream import (
    CLAIM_IDS, ApplicationProfile, CrosscheckEvidence, CrosscheckTask,
    FinalDiscoveryManifest, ModelIdentity, NoveltyEvidence, ProfileClaimEvidence, StageAssessment,
    ReferenceCoverageQualification, SecondaryModelQualification, TrainingIndependenceEvidence,
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
                            training_provenance_hash=h("train-p"), protocol_hash=h("p"), training_family_id="family-p")
    secondary = ModelIdentity(model_id="s", model_version="1", base_model_id="base-s",
                              training_provenance_hash=h("train-s"), protocol_hash=h("s"), training_family_id="family-s")
    independence = TrainingIndependenceEvidence(primary_training_hash=primary.training_provenance_hash,
        secondary_training_hash=secondary.training_provenance_hash,
        primary_base_id=primary.base_model_id, secondary_base_id=secondary.base_model_id,
        evidence_hashes=(h("training-distribution-review"),), status="INDEPENDENT")
    task = CrosscheckTask(candidate_id="c", species="Li", protocol_hash=h("crosscheck-protocol"),
                          primary=primary, secondary=secondary,
                          observable="structural_stability", conditions={"temperature_K": 500},
                          agreement_rule_hash=h("rule"), input_artifact_hashes=(h("input"),),
                          independence_evidence_hashes=(independence.content_hash,))
    assert assess_crosscheck(task, None).verdict == "UNKNOWN"
    assert CrosscheckTask.from_dict(task.to_dict()) == task
    qualification = SecondaryModelQualification(model_hash=secondary.content_hash,
        task_protocol_hash=task.protocol_hash, species=("Li",), evidence_hashes=(h("qualification-evidence"),),
        status="QUALIFIED")
    evidence = CrosscheckEvidence(task_hash=task.content_hash,
        primary_artifact_hashes=(h("primary-result"),), secondary_artifact_hashes=(h("secondary-result"),),
        disagreement_artifact_hashes=(h("comparison"),), agreement=True, applicable=True,
        primary_supported=True, secondary_supported=True, qualification=qualification,
        qualification_reference=qualification.content_hash, independence=independence)
    assert CrosscheckEvidence.from_dict(evidence.to_dict()) == evidence
    assert assess_crosscheck(task, evidence).verdict == "PASS"
    assert assess_crosscheck(task, replace(evidence, agreement=False)).verdict == "FAIL"
    assert assess_crosscheck(task, replace(evidence, qualification_reference=None)).verdict == "INDETERMINATE"
    same_base = replace(task, secondary=replace(secondary, base_model_id="base-p"))
    assert assess_crosscheck(same_base, replace(evidence, task_hash=same_base.content_hash)).verdict == "INDETERMINATE"
    same_family = replace(task, secondary=replace(secondary, training_family_id="family-p"))
    assert assess_crosscheck(same_family, replace(evidence, task_hash=same_family.content_hash)).verdict == "INDETERMINATE"
    missing_independence = replace(task, independence_evidence_hashes=())
    assert assess_crosscheck(missing_independence, replace(evidence, task_hash=missing_independence.content_hash)).verdict == "INDETERMINATE"
    absent = replace(task, secondary=None)
    assert assess_crosscheck(absent, replace(evidence, task_hash=absent.content_hash)).verdict == "INDETERMINATE"
    assert assess_crosscheck(task, replace(evidence, secondary_supported=False)).verdict == "INDETERMINATE"
    assert assess_crosscheck(task, replace(evidence, secondary_supported=False)).applicability == "INAPPLICABLE"
    assert assess_crosscheck(task, replace(evidence, secondary_supported=None)).verdict == "INDETERMINATE"
    assert assess_crosscheck(task, replace(evidence, independence=None)).verdict == "INDETERMINATE"
    assert assess_crosscheck(task, replace(evidence, independence=replace(independence,
        status="NOT_INDEPENDENT"))).verdict == "INDETERMINATE"
    wrong_scope = replace(qualification, species=("Na",))
    assert assess_crosscheck(task, replace(evidence, qualification=wrong_scope,
                                           qualification_reference=wrong_scope.content_hash)).verdict == "INDETERMINATE"
    with pytest.raises(ValueError, match="task mismatch"):
        assess_crosscheck(task, replace(evidence, task_hash=h("other-task")))


def test_final_novelty_coverage_and_rediscovery():
    qualification = ReferenceCoverageQualification(reference_sources={"database": h("db")},
        reference_versions={"database": "2026-01"}, universe_hash=h("universe"),
        protocol_hash=h("coverage-protocol"), evidence_hashes=(h("review"),), status="QUALIFIED")
    evidence = NoveltyEvidence(candidate_id="c", reference_sources={"database": h("db")},
        reference_versions={"database": "2026-01"}, coverage_complete=False,
        reference_universe_complete=False, coverage_evidence_hashes=(h("coverage"),),
        universe_hash=h("universe"), coverage_protocol_hash=h("coverage-protocol"),
        coverage_qualification_reference=qualification.content_hash, coverage_qualification=qualification,
        composition_novel=True, structure_novel=True,
        known_material_rediscovery=False, evidence_hashes=(h("matches"),),
        unresolved_coverage=("unindexed_sources",))
    assert NoveltyEvidence.from_dict(evidence.to_dict()) == evidence
    assert assess_novelty(evidence).verdict == "UNKNOWN"
    assert assess_novelty(replace(evidence, coverage_complete=True, unresolved_coverage=())).verdict == "UNKNOWN"
    complete = replace(evidence, coverage_complete=True, reference_universe_complete=True, unresolved_coverage=())
    assert assess_novelty(complete).verdict == "PASS"
    assert assess_novelty(replace(complete, coverage_evidence_hashes=())).verdict == "UNKNOWN"
    assert assess_novelty(replace(complete, coverage_qualification_reference=h("wrong"))).verdict == "UNKNOWN"
    assert assess_novelty(replace(complete, universe_hash=h("other-universe"))).verdict == "UNKNOWN"
    assert assess_novelty(replace(evidence, known_material_rediscovery=True)).verdict == "FAIL"
    with pytest.raises(ValueError, match="version"):
        replace(evidence, reference_versions={})


def test_synthesis_unknowns_and_no_scalar():
    criteria = {k: SynthesisCriterion(verdict=Verdict.PASS, evidence_hashes=(h(k),)) for k in SYNTHESIS_CRITERIA}
    evidence = SynthesisEvidence(candidate_id="c", protocol_hash=h("s-protocol"), criteria=criteria)
    assert SynthesisEvidence.from_dict(evidence.to_dict()) == evidence
    assert assess_synthesis(evidence).verdict == "PASS"
    assert assess_synthesis(replace(evidence, criteria={k: v for k, v in criteria.items() if k != "route_plausibility"})).verdict == "UNKNOWN"
    assert assess_synthesis(replace(evidence, criteria={**criteria, "competing_phases":
        SynthesisCriterion(verdict=Verdict.FAIL, evidence_hashes=(h("phase"),))})).verdict == "FAIL"


def test_application_profile_mandatory_optional_and_acceptance_binding():
    region = {"kind": "exact", "expected": True, "status": "PROVISIONAL", "justification": "fixture"}
    profile = ApplicationProfile(profile_id="test-profile", profile_version="1", protocol_hash=h("profile"),
        target_species=("Li",), operating_constraints={"temperature_K": [280, 330]},
        electrochemical_constraints={"voltage_window_V": [0, 5]}, environment={"atmosphere": "dry"},
        mandatory_claims=("a",), optional_claims=("b",), acceptance_regions={"a": region, "b": region},
        applicability_requirements=("species_supported",), profile_requirements=("environment_defined",))
    good = ProfileClaimEvidence(candidate_id="c", profile_hash=profile.content_hash,
                                protocol_hash=profile.protocol_hash, verdict=Verdict.PASS,
                                acceptance_hash=digest(region), applicable=True,
                                evidence_hashes=(h("profile-evidence"),))
    checks = {"species_supported": h("species"), "environment_defined": h("environment-defined"),
              "operating_constraints": h("operating"), "electrochemical_constraints": h("electrochemical"),
              "environment": h("environment")}
    kwargs = dict(candidate_id="c", species="Li", applicable=True, requirement_evidence=checks)
    assert assess_application(profile, {"a": good}, **kwargs).verdict == "PASS"
    assert assess_application(profile, {"b": good}, **kwargs).verdict == "UNKNOWN"
    assert assess_application(profile, {"a": replace(good, acceptance_hash=h("wrong"))},
                              **kwargs).verdict == "UNKNOWN"
    assert assess_application(profile, {"a": replace(good, profile_hash=h("wrong"))}, **kwargs).verdict == "UNKNOWN"
    assert assess_application(profile, {"a": good}, candidate_id="other", species="Li",
                              applicable=True, requirement_evidence=checks).verdict == "UNKNOWN"
    assert assess_application(profile, {"a": good}, candidate_id="c", species="Li", applicable=True).verdict == "UNKNOWN"
    assert assess_application(profile, {"a": good}, candidate_id="c", species="Na",
                              applicable=True, requirement_evidence=checks).verdict == "INDETERMINATE"
    assert assess_application(profile, {"a": good}, **{**kwargs, "applicable": False}).verdict == "INDETERMINATE"
    failed = replace(good, verdict=Verdict.FAIL)
    assert assess_application(profile, {"a": failed}, **kwargs).verdict == "FAIL"


def test_downstream_out_precedence():
    stages = {k: stage(k) for k in ("X", "N", "S", "APPLICATION")}
    stages["N"] = StageAssessment(stage="N", verdict=Verdict.UNKNOWN, applicability="APPLICABLE",
                                  reason_codes=("coverage_missing",), unresolved=("coverage",))
    assert out(stages=stages).final_assessment == "UNKNOWN"
    stages["S"] = stage("S", "FAIL")
    assert out(stages=stages).final_assessment == "FAIL"


def test_complete_synthetic_downstream_path():
    primary = ModelIdentity(model_id="p", model_version="1", base_model_id="p-base",
                            training_provenance_hash=h("p-train"), protocol_hash=h("p-protocol"),
                            training_family_id="p-family")
    secondary = ModelIdentity(model_id="s", model_version="1", base_model_id="s-base",
                              training_provenance_hash=h("s-train"), protocol_hash=h("s-protocol"),
                              training_family_id="s-family")
    independence = TrainingIndependenceEvidence(primary_training_hash=primary.training_provenance_hash,
        secondary_training_hash=secondary.training_provenance_hash,
        primary_base_id=primary.base_model_id, secondary_base_id=secondary.base_model_id,
        evidence_hashes=(h("independence-review"),), status="INDEPENDENT")
    task = CrosscheckTask(candidate_id="c", species="Li", protocol_hash=h("x-protocol"),
        primary=primary, secondary=secondary, observable="transport", conditions={"temperature_K": 300},
        agreement_rule_hash=h("agreement-rule"), input_artifact_hashes=(h("p3-input"),),
        independence_evidence_hashes=(independence.content_hash,))
    qualification = SecondaryModelQualification(model_hash=secondary.content_hash,
        task_protocol_hash=task.protocol_hash, species=("Li",), evidence_hashes=(h("model-review"),),
        status="QUALIFIED")
    x = assess_crosscheck(task, CrosscheckEvidence(task_hash=task.content_hash,
        primary_artifact_hashes=(h("p-result"),), secondary_artifact_hashes=(h("s-result"),),
        disagreement_artifact_hashes=(h("comparison"),), agreement=True, applicable=True,
        qualification_reference=qualification.content_hash, qualification=qualification,
        independence=independence, primary_supported=True, secondary_supported=True))
    coverage = ReferenceCoverageQualification(reference_sources={"db": h("db")},
        reference_versions={"db": "1"}, universe_hash=h("universe"), protocol_hash=h("n-protocol"),
        evidence_hashes=(h("coverage-review"),), status="QUALIFIED")
    n = assess_novelty(NoveltyEvidence(candidate_id="c", reference_sources={"db": h("db")},
        reference_versions={"db": "1"}, coverage_complete=True, reference_universe_complete=True,
        coverage_evidence_hashes=(h("coverage"),), universe_hash=coverage.universe_hash,
        coverage_protocol_hash=coverage.protocol_hash, coverage_qualification_reference=coverage.content_hash,
        coverage_qualification=coverage, composition_novel=True, structure_novel=True,
        known_material_rediscovery=False, evidence_hashes=(h("novelty"),)))
    s = assess_synthesis(SynthesisEvidence(candidate_id="c", protocol_hash=h("synthesis-protocol"),
        criteria={k: SynthesisCriterion(verdict=Verdict.PASS, evidence_hashes=(h(k),))
                  for k in SYNTHESIS_CRITERIA}))
    region = {"kind": "exact", "expected": True, "status": "PROVISIONAL", "justification": "fixture"}
    profile = ApplicationProfile(profile_id="synthetic", profile_version="1", protocol_hash=h("a-protocol"),
        target_species=("Li",), operating_constraints={"temperature_K": 300},
        electrochemical_constraints={"voltage_V": 4}, environment={"atmosphere": "dry"},
        mandatory_claims=("fit",), optional_claims=(), acceptance_regions={"fit": region},
        applicability_requirements=(), profile_requirements=())
    claim = ProfileClaimEvidence(candidate_id="c", profile_hash=profile.content_hash,
        protocol_hash=profile.protocol_hash, verdict=Verdict.PASS, acceptance_hash=digest(region),
        applicable=True, evidence_hashes=(h("fit-evidence"),))
    a = assess_application(profile, {"fit": claim}, candidate_id="c", species="Li", applicable=True,
        requirement_evidence={k: h(k) for k in ("operating_constraints", "electrochemical_constraints", "environment")})
    result = out(stages={"X": x, "N": n, "S": s, "APPLICATION": a})
    assert result.final_assessment == "PASS"
    assert FinalDiscoveryManifest.from_dict(result.to_dict()) == result


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
