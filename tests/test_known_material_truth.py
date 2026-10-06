"""B1 source-bound truth contract tests; all identities are synthetic."""
from dataclasses import replace
import json
from pathlib import Path

import pytest

from rudeus.science.contracts import Verdict, digest
from rudeus.science.known_material_benchmark import STAGES, TruthClass, TruthEvidenceClass, build_known_material_benchmark_protocol
from rudeus.science.known_material_truth import (
    TRUTH_RECORD_VERSION,
    EvidenceAtom,
    EvidenceQuantityKind,
    KnownMaterialTruthBundle,
    ReferenceSource,
    ReferenceStructure,
    SourceKind,
    StageTruthRecord,
    TruthDisposition,
)


def h(value):
    return digest(value)


def source():
    return ReferenceSource(
        source_id="doi:synthetic/benchmark",
        source_kind=SourceKind.PEER_REVIEWED_ARTICLE.value,
        locator="doi:synthetic/benchmark",
        citation="Synthetic benchmark source",
        version_or_date="2026",
        retained_artifact_hashes=(h("source-metadata"),),
    )


def evidence(src, *, quantity=EvidenceQuantityKind.STRUCTURE.value,
             dimension="reference_structure", family="dataset-a"):
    return EvidenceAtom(
        source_hash=src.content_hash,
        evidence_class=TruthEvidenceClass.DIRECT_EXPERIMENTAL.value,
        evidence_family_id=family,
        quantity_kind=quantity,
        claim_dimension=dimension,
        phase_identity="phase-alpha",
        species=("Li",),
        conditions={"temperature_K": 300},
        reported_value=True,
        units="categorical",
        retained_artifact_hashes=(h([quantity, dimension]),),
        evidence_scope="synthetic scoped evidence",
    )


def reference(structure_evidence):
    return ReferenceStructure(
        material_identity="SEALED_SYNTHETIC_IDENTITY",
        composition="Li-X",
        phase_identity="phase-alpha",
        structure_hash=h("reference-structure-bytes"),
        structure_format="cif",
        source_evidence_hashes=(structure_evidence.content_hash,),
        mobile_species=("Li",),
        chemistry_family="synthetic-family",
        reference_conditions={"temperature_K": 300},
    )


def unresolved_truth(stage, ref):
    return StageTruthRecord(
        stage=stage,
        material_reference_hash=ref.content_hash,
        truth_statement=f"{stage} truth unresolved in synthetic fixture",
        truth_value=None,
        disposition=TruthDisposition.INSUFFICIENT.value,
        scope={"phase_identity": ref.phase_identity},
        evidence_hashes=(),
        required_quantity_kinds=(),
        permitted_pipeline_verdicts=(Verdict.UNKNOWN.value, Verdict.INDETERMINATE.value),
        falsifying_pipeline_verdicts=(),
        scorable=False,
        reason_codes=("fixture_insufficient",),
    )


def supported_truth(stage, ref, atom, required_kind):
    return StageTruthRecord(
        stage=stage,
        material_reference_hash=ref.content_hash,
        truth_statement=f"{stage} supported synthetic truth",
        truth_value=True,
        disposition=TruthDisposition.SUPPORTED.value,
        scope={"phase_identity": ref.phase_identity, "temperature_K": 300},
        evidence_hashes=(atom.content_hash,),
        required_quantity_kinds=(required_kind,),
        permitted_pipeline_verdicts=(Verdict.PASS.value,),
        falsifying_pipeline_verdicts=(Verdict.FAIL.value,),
        scorable=True,
    )


def bundle(*, transport_quantity=EvidenceQuantityKind.SELF_DIFFUSION.value):
    src = source()
    structure = evidence(src)
    transport = evidence(src, quantity=transport_quantity, dimension="self_diffusion", family="dataset-b")
    ref = reference(structure)
    truths = [unresolved_truth(stage, ref) for stage in STAGES]
    index = STAGES.index("P2.5")
    truths[index] = supported_truth(
        "P2.5", ref, transport, EvidenceQuantityKind.SELF_DIFFUSION.value
    )
    return KnownMaterialTruthBundle(
        truth_record_version=TRUTH_RECORD_VERSION,
        benchmark_protocol_hash=build_known_material_benchmark_protocol().content_hash,
        benchmark_role=TruthClass.POSITIVE.value,
        reference=ref,
        sources=(src,),
        evidence=(structure, transport),
        stage_truths=tuple(truths),
    )


def test_b1_bundle_is_content_addressed_immutable_and_roundtrips():
    first = bundle()
    second = bundle()
    assert first == second
    assert first.content_hash == second.content_hash == digest(first.to_dict())
    assert KnownMaterialTruthBundle.from_dict(first.to_dict()) == first
    with pytest.raises(TypeError):
        first.reference.reference_conditions["temperature_K"] = 500


def test_every_pipeline_stage_is_explicit_even_when_truth_is_insufficient():
    b = bundle()
    assert tuple(item.stage for item in b.stage_truths) == STAGES
    unresolved = [item for item in b.stage_truths if item.stage != "P2.5"]
    assert all(item.disposition == TruthDisposition.INSUFFICIENT.value for item in unresolved)
    assert all(not item.scorable for item in unresolved)


def test_supported_truth_requires_source_bound_evidence_and_falsification_rule():
    b = bundle()
    p25 = next(item for item in b.stage_truths if item.stage == "P2.5")
    with pytest.raises(ValueError, match="source-bound"):
        replace(p25, evidence_hashes=())
    with pytest.raises(ValueError, match="permitted and falsifying"):
        replace(p25, falsifying_pipeline_verdicts=())


def test_unresolved_truth_cannot_be_used_to_falsify_pipeline():
    b = bundle()
    p3 = next(item for item in b.stage_truths if item.stage == "P3")
    with pytest.raises(ValueError, match="cannot falsify"):
        replace(p3, falsifying_pipeline_verdicts=(Verdict.FAIL.value,))


def test_evidence_must_bind_to_retained_source_in_same_bundle():
    b = bundle()
    broken_atom = replace(b.evidence[1], source_hash=h("other-source"))
    with pytest.raises(ValueError, match="source outside"):
        replace(b, evidence=(b.evidence[0], broken_atom),
                stage_truths=tuple(
                    replace(t, evidence_hashes=(broken_atom.content_hash,))
                    if t.stage == "P2.5" else t for t in b.stage_truths
                ))


def test_reference_structure_must_bind_to_retained_evidence():
    b = bundle()
    broken_ref = replace(b.reference, source_evidence_hashes=(h("missing-evidence"),))
    truths = tuple(replace(t, material_reference_hash=broken_ref.content_hash) for t in b.stage_truths)
    with pytest.raises(ValueError, match="reference structure evidence"):
        replace(b, reference=broken_ref, stage_truths=truths)


def test_experimental_conductivity_cannot_satisfy_self_diffusion_truth_by_substitution():
    with pytest.raises(ValueError, match="required quantity kind"):
        bundle(transport_quantity=EvidenceQuantityKind.IONIC_CONDUCTIVITY.value)


def test_evidence_lineage_is_explicit_for_later_independence_accounting():
    src = source()
    with pytest.raises(ValueError, match="lineage"):
        evidence(src, family="")


def test_bundle_does_not_assign_dev_or_held_out_membership():
    b = bundle()
    serialized = b.to_dict()
    assert "split" not in serialized
    assert "benchmark_id" not in serialized
    assert b.curation_state == "DRAFT"


def test_canonical_li2s_bundle_is_curated_but_only_p0_is_scorable():
    path = Path(
        "data/benchmarks/known_material/truth_bundles/"
        "li2s-microcrystalline-v1.json"
    )
    canonical = KnownMaterialTruthBundle.from_dict(
        json.loads(path.read_text(encoding="utf-8"))
    )
    assert canonical.curation_state == "CURATED_FOR_B2"
    assert canonical.benchmark_role == TruthClass.NEGATIVE.value
    assert canonical.reference.structure_hash == (
        "ff1d7eeb11f6d91c3adb7af92c8b6cfc938f9c9f412e26bd4187a021de7470b0"
    )
    scorable = tuple(item.stage for item in canonical.stage_truths if item.scorable)
    assert scorable == ("P0",)
    p25 = next(item for item in canonical.stage_truths if item.stage == "P2.5")
    assert p25.scorable is False
    assert "no_direct_self_diffusion_truth" in p25.reason_codes


def test_canonical_gamma_lialo2_bundle_is_negative_and_p25_scorable():
    path = Path(
        "data/benchmarks/known_material/truth_bundles/"
        "lialo2-gamma-v1.json"
    )
    canonical = KnownMaterialTruthBundle.from_dict(
        json.loads(path.read_text(encoding="utf-8"))
    )
    assert canonical.curation_state == "CURATED_FOR_B2"
    assert canonical.benchmark_role == TruthClass.NEGATIVE.value
    assert canonical.reference.structure_hash == (
        "94aa55ef4b1a2aeb94c5c07ddd7cdc18201ac752546a283c8543cb8faa05f589"
    )
    scorable = tuple(
        item.stage for item in canonical.stage_truths if item.scorable
    )
    assert scorable == ("P0", "P2.5")
    p25 = next(item for item in canonical.stage_truths if item.stage == "P2.5")
    assert p25.required_quantity_kinds == (
        EvidenceQuantityKind.SELF_DIFFUSION.value,
    )
    assert p25.permitted_pipeline_verdicts == (Verdict.FAIL.value,)
    assert p25.falsifying_pipeline_verdicts == (Verdict.PASS.value,)
    assert "direct_tracer_self_diffusion_negative_control" in p25.reason_codes


def test_canonical_libh4_bundle_preserves_phase_pair_borderline_scope():
    path = Path(
        "data/benchmarks/known_material/truth_bundles/"
        "libh4-phase-transition-pair-v1.json"
    )
    canonical = KnownMaterialTruthBundle.from_dict(
        json.loads(path.read_text(encoding="utf-8"))
    )
    assert canonical.curation_state == "CURATED_FOR_B2"
    assert canonical.benchmark_role == TruthClass.BORDERLINE.value
    assert canonical.reference.structure_format == "CIF_PHASE_SET"
    assert canonical.reference.structure_hash == (
        "56af6e7b696a8a5cc8c20336485674fb50ab62343a06f05a1a57b1165e9b2538"
    )
    scorable = tuple(
        item.stage for item in canonical.stage_truths if item.scorable
    )
    assert scorable == ("P0",)

    p0 = next(item for item in canonical.stage_truths if item.stage == "P0")
    assert p0.required_quantity_kinds == (
        EvidenceQuantityKind.STRUCTURE.value,
    )
    assert p0.permitted_pipeline_verdicts == (Verdict.PASS.value,)
    assert p0.falsifying_pipeline_verdicts == (Verdict.FAIL.value,)

    p25 = next(item for item in canonical.stage_truths if item.stage == "P2.5")
    assert p25.disposition == TruthDisposition.INSUFFICIENT.value
    assert p25.scorable is False
    assert p25.permitted_pipeline_verdicts == (
        Verdict.UNKNOWN.value,
        Verdict.INDETERMINATE.value,
    )
    assert (
        "phase_scoped_self_diffusion_does_not_authorize_pair_level_verdict"
        in p25.reason_codes
    )
    assert any(
        atom.quantity_kind == EvidenceQuantityKind.SELF_DIFFUSION.value
        and atom.phase_identity == "high-temperature hexagonal LiBH4"
        for atom in canonical.evidence
    )
