"""CPU-only synthetic release rehearsal; no physical validity is asserted."""
from dataclasses import replace
import hashlib
import math

import pytest

from rudeus.execution.contracts import ArtifactManifest, ExecutionAttempt, ExecutionError, TaskSpec
from rudeus.execution.scheduler import plan_attempt
from rudeus.science.claims import QualificationRecord, evaluate_claim
from rudeus.science.contracts import (AcceptanceRegion, ClaimSpec, Observation, ObservableType,
                                      Uncertainty, Verdict, canonical_bytes, digest)
from rudeus.science.downstream import (
    ApplicationProfile, CrosscheckEvidence, CrosscheckTask, ModelIdentity, NoveltyEvidence,
    ProfileClaimEvidence, ReferenceCoverageQualification, SecondaryModelQualification,
    SynthesisCriterion, SynthesisEvidence, SYNTHESIS_CRITERIA, TrainingIndependenceEvidence,
    assess_application, assess_crosscheck, assess_novelty, assess_synthesis)
from rudeus.science.evidence import ingest_verified_artifact
from rudeus.science.followups import FollowupRequest, unresolved_followup
from rudeus.science.p3_series import analyze_p3_series
from rudeus.science.pipeline_release import (ReleaseRecord, RetainedOutput, RunIdentity, StageReceipt,
                                             assemble_release)

REV = "5de384508a953c788da77d181ac4db3053930590"
CANDIDATE = "synthetic-candidate"
EVIDENCE_VALUES = {}


def h(value):
    identity = digest(value)
    EVIDENCE_VALUES[identity] = value
    return identity


def remember(*records):
    for record in records:
        EVIDENCE_VALUES[record.content_hash] = record.to_dict()


def artifact(root, value, producer, parents=(), name="result.json"):
    data = canonical_bytes(value)
    manifest = ArtifactManifest(logical_hash=h(value), raw_hash=hashlib.sha256(data).hexdigest(),
        canonicalization_version="canonical-json-v1", format="json", format_version="synthetic-v1",
        size_bytes=len(data), durable_locator=f"synthetic/{name}", producer_attempt=producer,
        parent_artifact_hashes=tuple(parents), retrieval_verification={"fixture": True})
    return RetainedOutput(logical_name=name, manifest=manifest,
                          ingestion_receipt=ingest_verified_artifact(root, manifest, data))


def attempt(task, label, outputs=(), failure=None, backend="local-cpu"):
    status = "FAILED" if failure else "COMPLETED"
    return ExecutionAttempt(attempt_id=h(label), task_id=task.task_id,
        task_content_hash=task.content_hash, backend=backend, remote_session_id=None,
        started_at="synthetic", ended_at="synthetic", runtime_s=0,
        hardware={"cpu": True}, environment={}, precision=None,
        exit_status=1 if failure else 0, status=status,
        termination_reason="synthetic", failure_class=failure, logs=(),
        output_manifest={} if failure else {o.logical_name: o.manifest.content_hash for o in outputs})


def stage_chain(root, *, p25_state="DIFFUSIVE", omit=()):
    entries, report = p3_report(return_entries=True)
    source = artifact(root, {"candidate_id": CANDIDATE, "p0_state": "PLAUSIBLE"},
                      h("source-attempt"), name="candidate.json")
    run = RunIdentity(candidate_id=CANDIDATE, source_hash=source.manifest.logical_hash,
                      pipeline_protocol_hash=h("synthetic-pipeline-v1"), code_revision=REV)
    stages = {}

    def receipt(name, values, inputs, dependencies, label, temperature=None):
        task = TaskSpec(candidate_id=CANDIDATE, stage=name, protocol_hash=h([name, "protocol"]),
            config={"fixture_stage": name}, input_artifact_hashes=tuple(inputs),
            dependencies=tuple(dependencies), code_revision=REV,
            resource_requirements={"cpu": True}, expected_outputs=tuple(values),
            retry_policy={"infrastructure": "same_task"}, temperature=temperature,
            replica=label if name == "P3" else None)
        outputs = tuple(artifact(root, value, h([name, label, "success"]), inputs, filename)
                        for filename, value in values.items())
        failed = attempt(task, [name, label, "timeout"], failure="TIMEOUT") if name == "P1" else None
        return StageReceipt(task=task, attempts=tuple(a for a in (
            failed, attempt(task, [name, label, "success"], outputs)) if a), outputs=outputs)

    if "P1" in omit:
        return run, source, stages, report
    p1 = receipt("P1", {"p1.json": {"stage": "P1", "candidate_id": CANDIDATE,
                                    "synthetic": True}},
                 (source.manifest.logical_hash,), (), "one")
    stages["P1"] = (p1,)
    if "P2" in omit:
        return run, source, stages, report
    p2_receipts, p25_receipts, p3_receipts = [], [], []
    for entry in entries:
        point = entry["temperature_point_id"]
        temperature = entry["p3_result"]["temperature_K"]
        trajectory = [point, "trajectory"]
        p2 = receipt("P2", {"p2.json": {"stage": "P2", "point": point,
                                          "candidate_id": CANDIDATE, "synthetic": True},
                             "trajectory.json": trajectory},
                     (p1.outputs[0].manifest.logical_hash,), (p1.task.task_id,), point,
                     temperature)
        p2_receipts.append(p2)
        if "P2.5" in omit:
            continue
        p25 = receipt("P2.5", {"p25.json": {"stage": "P2.5", "point": point,
            "candidate_id": CANDIDATE, "synthetic": True,
            "result": {"transport_state": p25_state, "p25_verdict": p25_state}}},
            tuple(o.manifest.logical_hash for o in p2.outputs),
            (p2.task.task_id,), point, temperature)
        p25_receipts.append(p25)
        if "P3" in omit or p25_state != "DIFFUSIVE":
            continue
        p3 = receipt("P3", {"p3.json": entry["p3_result"]},
            (p25.outputs[0].manifest.logical_hash,) + tuple(
                o.manifest.logical_hash for o in p2.outputs),
            (p25.task.task_id,), point, temperature)
        p3_receipts.append(p3)
    stages["P2"] = tuple(p2_receipts)
    if p25_receipts:
        stages["P2.5"] = tuple(p25_receipts)
    if p3_receipts:
        stages["P3"] = tuple(p3_receipts)
    return run, source, stages, report


def upstream(value=True, *, missing=None, unresolved=None, evidence_hashes=None):
    names = ("existence", "structural_energetic_validity", "dynamic_stability",
             "diffusion", "transport_p3", "uncertainty_qualification")
    specs, assessments = {}, []
    for name in names:
        spec = ClaimSpec(claim_id=name, protocol_hash=h([name, "protocol"]), estimand=name,
            units="boolean", scope={"candidate_id": CANDIDATE},
            assumptions=("qualified",) if name == unresolved else (),
            applicability_requirements=(), sufficiency_requirements=(), independence_requirements=(),
            admissible_evidence=(ObservableType.SIMULATED.value,), provenance_identity=h(name),
            acceptance=AcceptanceRegion(kind="exact", expected=True,
                                        justification="synthetic rehearsal only"))
        specs[name] = spec
        if name == missing:
            continue
        observation = Observation(quantity=name, units="boolean",
            value=value if name == "existence" else True, species=("Li",),
            conditions={"candidate_id": CANDIDATE}, reference_frame="synthetic",
            data_support={"fixture": name}, estimator="explicit_synthetic_fixture",
            estimator_version="1", protocol_hash=spec.protocol_hash,
            artifact_hashes=((evidence_hashes or {}).get(name, h([name, "retained-evidence"])),),
            observable_type=ObservableType.SIMULATED)
        assessments.append(evaluate_claim(spec, observation))
    return specs, tuple(assessments)


def p3_report(*, return_entries=False):
    entries = []
    protocol = h("p3-series-protocol")
    for temperature in (500., 600., 700., 800.):
        point = f"T{temperature}"
        trajectory = h([point, "trajectory"])
        D = 1e-7 * math.exp(-.25 / (8.617333262145e-5 * temperature))
        source = {"candidate_material_id": CANDIDATE, "target_species": "Li",
                  "temperature_K": temperature, "transport_state": "DIFFUSIVE"}
        obs = Observation(quantity="D_self", units="m2/s", value=D, species=("Li",),
            conditions={"candidate_id": CANDIDATE, "temperature_K": temperature,
                        "reference_frame": "simulation_cell"}, reference_frame="simulation_cell",
            data_support={"trajectory_sha256": trajectory}, estimator="synthetic_D_self",
            estimator_version="1", protocol_hash=protocol, artifact_hashes=(trajectory,),
            observable_type=ObservableType.DERIVED)
        unc = Uncertainty(observation_hash=obs.content_hash,
                          unavailable_reasons=("temperature_point_interval_unqualified",))
        record = {"observation": obs.to_dict(), "uncertainty": unc.to_dict()}
        entries.append({"temperature_point_id": point, "replicate_id": "r1",
            "p3_result": {**source, "quantitative_transport": {
                "self_diffusion": {"D_m2_per_s": D},
                "conductivity_estimate": {"status": "estimate_only"},
                "collective_transport": {"status": "unresolved"}},
                "p3_scientific_record": record,
                "p3_provenance": {"scientific_record_hash": h(record),
                    "p25_result_hash": h(source), "p3_config_hash": protocol,
                    "trajectory_sha256": trajectory}}})
    preliminary = analyze_p3_series(entries)
    spec = replace(ClaimSpec.from_dict(preliminary["claim_spec"]),
        acceptance=AcceptanceRegion(kind="interval", lower=.1, upper=.4,
                                    justification="synthetic provisional window"),
        uncertainty_requirements={"held_out_coverage": "required"})
    observation = Observation.from_dict(preliminary["observation"])
    cert = QualificationRecord(protocol_hash=preliminary["series_hash"],
        estimator=observation.estimator, estimator_version=observation.estimator_version,
        uncertainty_method="synthetic_held_out", uncertainty_method_version="1",
        nominal_coverage=.9, scope=spec.scope, evidence_hashes=(h("synthetic-held-out"),),
        requirements_hash=h(spec.uncertainty_requirements), status="QUALIFIED")
    unc = Uncertainty(observation_hash=observation.content_hash, method="synthetic_held_out",
        method_version="1", nominal_coverage=.9, bounds=(.2, .3),
        calibration_reference=cert.content_hash, unavailable_reasons=())
    checks = {key: True for key in (spec.assumptions + spec.applicability_requirements +
                                    spec.sufficiency_requirements + spec.independence_requirements)}
    report = analyze_p3_series(entries, claim_spec=spec, activation_uncertainty=unc,
        qualification_registry={cert.content_hash: cert}, checks=checks)
    return (entries, report) if return_entries else report


def downstream(*, x_agreement=True, x_qualified=True, x_independent=True,
               novelty_coverage=True, rediscovery=False, synthesis_missing=None,
               synthesis_fail=None, application_applicable=True, application_missing=False):
    primary = ModelIdentity(model_id="primary", model_version="1", base_model_id="primary-base",
        training_provenance_hash=h("primary-training"), protocol_hash=h("primary-protocol"),
        training_family_id="primary-family")
    secondary = ModelIdentity(model_id="secondary", model_version="1", base_model_id="secondary-base",
        training_provenance_hash=h("secondary-training"), protocol_hash=h("secondary-protocol"),
        training_family_id="secondary-family")
    independence = TrainingIndependenceEvidence(
        primary_training_hash=primary.training_provenance_hash,
        secondary_training_hash=secondary.training_provenance_hash,
        primary_base_id=primary.base_model_id, secondary_base_id=secondary.base_model_id,
        evidence_hashes=(h("independence-review"),), status="INDEPENDENT")
    task = CrosscheckTask(candidate_id=CANDIDATE, species="Li", protocol_hash=h("x-protocol"),
        primary=primary, secondary=secondary, observable="transport",
        conditions={"temperature_K": 500}, agreement_rule_hash=h("agreement-rule"),
        input_artifact_hashes=(h("p3-result"),),
        independence_evidence_hashes=(independence.content_hash,) if x_independent else ())
    qualification = SecondaryModelQualification(model_hash=secondary.content_hash,
        task_protocol_hash=task.protocol_hash, species=("Li",),
        evidence_hashes=(h("secondary-qualification"),), status="QUALIFIED")
    remember(independence, qualification)
    evidence = CrosscheckEvidence(task_hash=task.content_hash,
        primary_artifact_hashes=(h("primary-result"),),
        secondary_artifact_hashes=(h("secondary-result"),),
        disagreement_artifact_hashes=(h("comparison"),), agreement=x_agreement,
        applicable=True, primary_supported=True, secondary_supported=True,
        qualification=qualification, qualification_reference=qualification.content_hash if x_qualified else None,
        independence=independence if x_independent else None)
    x = assess_crosscheck(task, evidence)
    coverage = ReferenceCoverageQualification(reference_sources={"database": h("reference-snapshot")},
        reference_versions={"database": "synthetic-v1"}, universe_hash=h("universe"),
        protocol_hash=h("n-protocol"), evidence_hashes=(h("coverage-review"),), status="QUALIFIED")
    remember(coverage)
    n = assess_novelty(NoveltyEvidence(candidate_id=CANDIDATE,
        reference_sources=coverage.reference_sources, reference_versions=coverage.reference_versions,
        coverage_complete=novelty_coverage, reference_universe_complete=novelty_coverage,
        coverage_evidence_hashes=(h("coverage"),), universe_hash=coverage.universe_hash,
        coverage_protocol_hash=coverage.protocol_hash,
        coverage_qualification_reference=coverage.content_hash, coverage_qualification=coverage,
        composition_novel=not rediscovery, structure_novel=not rediscovery,
        known_material_rediscovery=rediscovery, evidence_hashes=(h("novelty-match-review"),)))
    criteria = {k: SynthesisCriterion(verdict=Verdict.FAIL if k == synthesis_fail else Verdict.PASS,
                evidence_hashes=(h([k, "criterion-evidence"]),))
                for k in SYNTHESIS_CRITERIA if k != synthesis_missing}
    s = assess_synthesis(SynthesisEvidence(candidate_id=CANDIDATE,
        protocol_hash=h("s-protocol"), criteria=criteria))
    region = {"kind": "exact", "expected": True, "status": "PROVISIONAL",
              "justification": "synthetic application criterion"}
    profile = ApplicationProfile(profile_id="synthetic-profile", profile_version="1",
        protocol_hash=h("application-protocol"), target_species=("Li",),
        operating_constraints={"temperature_K": 500},
        electrochemical_constraints={"voltage_V": 4}, environment={"atmosphere": "dry"},
        mandatory_claims=("fit",), optional_claims=(), acceptance_regions={"fit": region},
        applicability_requirements=(), profile_requirements=())
    claim = ProfileClaimEvidence(candidate_id=CANDIDATE, profile_hash=profile.content_hash,
        protocol_hash=profile.protocol_hash, verdict=Verdict.PASS,
        acceptance_hash=h(region), applicable=True, evidence_hashes=(h("application-fit"),))
    a = assess_application(profile, {} if application_missing else {"fit": claim},
        candidate_id=CANDIDATE, species="Li", applicable=application_applicable,
        requirement_evidence={key: h(key) for key in (
            "operating_constraints", "electrochemical_constraints", "environment")})
    return {"X": x, "N": n, "S": s, "APPLICATION": a}


def retain_references(root, assessments, stages, report, known=()):
    refs = {h for assessment in assessments for h in assessment.supporting_evidence}
    refs.update(h for stage in stages.values() for h in stage.evidence_hashes)
    if report is not None:
        refs.update(p["trajectory_sha256"] for p in report["replicates"])
        refs.update(report["calibration_applicability"]["held_out_evidence_hashes"])
    refs.difference_update(known)
    return tuple(artifact(root, EVIDENCE_VALUES[identity], h(["reference-producer", identity]),
                          name="reference.json") for identity in sorted(refs))


def known_outputs(source, stages, series_output=None):
    return ((source.manifest.logical_hash,) if source else ()) + tuple(
        output.manifest.logical_hash for receipts in stages.values()
        for receipt in receipts for output in receipt.outputs) + (
        (series_output.manifest.logical_hash,) if series_output else ())


def release(root, *, source_present=True, stages=None, upstream_args=None,
            downstream_args=None, limitations=(), p25_state="DIFFUSIVE"):
    run, source, built, report = stage_chain(root, p25_state=p25_state)
    if stages is not None:
        built = {k: v for k, v in built.items() if k in stages}
    report = report if "P3" in built else None
    series_output = (artifact(root, report, h("series-producer"),
                              tuple(r.outputs[0].manifest.logical_hash for r in built["P3"]),
                              "p3-series.json")
                     if report is not None else None)
    bindings = {"existence": source.manifest.logical_hash} if source_present else {}
    for claim, stage in (("structural_energetic_validity", "P1"),
                         ("dynamic_stability", "P2"), ("diffusion", "P2.5")):
        if stage in built:
            bindings[claim] = built[stage][0].outputs[0].manifest.logical_hash
    if series_output is not None:
        bindings.update(transport_p3=series_output.manifest.logical_hash,
                        uncertainty_qualification=series_output.manifest.logical_hash)
    specs, assessments = upstream(evidence_hashes=bindings, **(upstream_args or {}))
    assessed = downstream(**(downstream_args or {})) if source_present else {}
    extra = retain_references(root, assessments, assessed, report,
                              known_outputs(source if source_present else None, built, series_output))
    record, out = assemble_release(run=run, source=source if source_present else None,
        stages=built, artifact_root=root, claim_specs=specs, assessments=assessments,
        downstream=assessed, p3_series=report, p3_series_output=series_output,
        retained_evidence=extra,
        software_regression_hashes=(h("software-regression"),),
        synthetic_e2e_hashes=(h("canonical-synthetic-e2e"),),
        production_evidence_hashes=(), limitations=limitations)
    return run, source, built, record, out


@pytest.mark.parametrize("scenario,kwargs,expected", [
    ("complete synthetic PASS", {}, "PASS"),
    ("mandatory FAIL", {"upstream_args": {"value": False}}, "FAIL"),
    ("mandatory UNKNOWN", {"upstream_args": {"missing": "existence"}}, "UNKNOWN"),
    ("mandatory INDETERMINATE", {"upstream_args": {"unresolved": "existence"}}, "INDETERMINATE"),
    ("P2.5 NONDIFFUSIVE no P3", {"stages": ("P1", "P2", "P2.5"),
                                  "p25_state": "NONDIFFUSIVE"}, "FAIL"),
    ("X disagreement", {"downstream_args": {"x_agreement": False}}, "FAIL"),
    ("X qualification unresolved", {"downstream_args": {"x_qualified": False}}, "INDETERMINATE"),
    ("X independence unresolved", {"downstream_args": {"x_independent": False}}, "INDETERMINATE"),
    ("novelty coverage incomplete", {"downstream_args": {"novelty_coverage": False}}, "UNKNOWN"),
    ("known-material rediscovery", {"downstream_args": {"rediscovery": True}}, "FAIL"),
    ("synthesizability criterion missing", {"downstream_args": {"synthesis_missing": "route_plausibility"}}, "UNKNOWN"),
    ("synthesizability criterion FAIL", {"downstream_args": {"synthesis_fail": "competing_phases"}}, "FAIL"),
    ("application incompatible", {"downstream_args": {"application_applicable": False}}, "INDETERMINATE"),
    ("application mandatory evidence missing", {"downstream_args": {"application_missing": True}}, "UNKNOWN"),
    ("provenance incomplete", {"limitations": ("unresolved_source_review",)}, "UNKNOWN"),
    ("no qualifying candidate", {"source_present": False, "stages": ()}, "UNKNOWN"),
])
def test_canonical_release_states(tmp_path, scenario, kwargs, expected):
    _, _, _, record, out = release(tmp_path, **kwargs)
    assert out.final_assessment == expected, scenario
    assert record.out_hash == out.content_hash
    assert len(out.claim_vector) == 11
    assert record.qualification["canonical_synthetic_e2e_reference_present"]
    assert not record.qualification["production_scientific_reference_present"]
    if scenario == "complete synthetic PASS":
        assert record.qualification["durable_artifacts_complete"]
        assert len(record.stage_receipts) == 4
        assert len(record.stage_receipts["P3"]) == 4
        assert {receipt.task.temperature for receipt in record.stage_receipts["P3"]} == {
            500., 600., 700., 800.}
        assert record.p3_series_hash
        assert h(record.to_dict()) == record.content_hash
        assert ReleaseRecord.from_dict(record.to_dict()) == record


@pytest.mark.parametrize("case", ["missing artifact", "corrupted artifact",
                                  "completed attempt without durable ingestion"])
def test_artifact_integrity_blocks_assessment(tmp_path, case):
    run, source, stages, report = stage_chain(tmp_path)
    output = stages["P3"][0].outputs[0]
    if case == "missing artifact":
        (tmp_path / "blobs" / output.manifest.raw_hash).unlink()
    elif case == "corrupted artifact":
        (tmp_path / "blobs" / output.manifest.raw_hash).write_bytes(b"corrupt")
    else:
        (tmp_path / "receipts" / f"{output.ingestion_receipt}.json").unlink()
    series_output = artifact(tmp_path, report, h("series-producer"),
                             tuple(r.outputs[0].manifest.logical_hash for r in stages["P3"]),
                             "p3-series.json")
    specs, assessments = upstream()
    assessed = downstream()
    extra = retain_references(tmp_path, assessments, assessed, report,
                              known_outputs(source, stages, series_output))
    with pytest.raises(ExecutionError) as error:
        assemble_release(run=run, source=source, stages=stages, artifact_root=tmp_path,
            claim_specs=specs, assessments=assessments, downstream=assessed,
            p3_series=report, p3_series_output=series_output, retained_evidence=extra)
    assert error.value.failure_class.value == "INTEGRITY"


def test_retry_followup_and_terminal_science(tmp_path):
    _, _, stages, _ = stage_chain(tmp_path)
    task = stages["P1"][0].task
    failed = stages["P1"][0].attempts[0]
    transient = plan_attempt(task, "local-cpu", prior_attempts=(failed,))
    assert transient["status"] == "PLANNED"
    assert transient["plan"].task_id == task.task_id
    assert transient["plan"].attempt_id != failed.attempt_id
    backend_failure = replace(failed, failure_class="RESOURCE")
    assert plan_attempt(task, "local-cpu", prior_attempts=(backend_failure,))["reason"] == "alternate_backend_required"
    alternate = plan_attempt(task, "other-cpu", prior_attempts=(backend_failure,))
    assert alternate["plan"].task_id == task.task_id
    assert alternate["plan"].backend == "other-cpu"
    assert plan_attempt(task, "local-cpu", prior_attempts=stages["P1"][0].attempts)["reason"] == "completed_attempt_not_retryable"
    assert plan_attempt(task, "local-cpu", scientific_verdict="FAIL")["reason"] == "scientific_fail_terminal"
    assert unresolved_followup("P3_TEMPERATURE_COVERAGE_INSUFFICIENT")["task"] is None
    new_task = replace(stages["P3"][0].task, temperature=700., seed=17)
    followup = FollowupRequest(scientific_record_hash=h("record"), assessment_hash=h("assessment"),
                               reason="new temperature evidence", task=new_task)
    assert followup.task.task_id != stages["P3"][0].task.task_id
    assert followup.task.stage == "P3"


def test_nondiffusive_cannot_smuggle_p3(tmp_path):
    run, source, stages, report = stage_chain(tmp_path, p25_state="NONDIFFUSIVE")
    # Bind an otherwise valid P3 attempt to a NONDIFFUSIVE parent.
    p25 = stages["P2.5"][0]
    p2 = stages["P2"][0]
    inputs = (p25.outputs[0].manifest.logical_hash,) + tuple(
        output.manifest.logical_hash for output in p2.outputs)
    task = replace(p25.task, stage="P3", expected_outputs=("p3.json",),
                   input_artifact_hashes=inputs, dependencies=(p25.task.task_id,))
    entries, _ = p3_report(return_entries=True)
    output = artifact(tmp_path, entries[0]["p3_result"], h("smuggled-p3"), inputs, "p3.json")
    stages["P3"] = (StageReceipt(task=task,
        attempts=(attempt(task, "smuggled-p3", (output,)),), outputs=(output,)),)
    series_output = artifact(tmp_path, report, h("series-producer"),
                             tuple(r.outputs[0].manifest.logical_hash for r in stages["P3"]),
                             "p3-series.json")
    specs, assessments = upstream()
    assessed = downstream()
    extra = retain_references(tmp_path, assessments, assessed, report,
                              known_outputs(source, stages, series_output))
    with pytest.raises(ExecutionError, match="did not admit P3"):
        assemble_release(run=run, source=source, stages=stages, artifact_root=tmp_path,
            claim_specs=specs, assessments=assessments, downstream=assessed,
            p3_series=report, p3_series_output=series_output, retained_evidence=extra)
