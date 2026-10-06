from rudeus.science.known_material_b5_p0_semantics import (
    NeutralityApplicability,
    classify_exact_member_neutrality,
)


def test_weighted_marginal_ensemble_does_not_turn_member_neutrality_into_material_fail():
    result = classify_exact_member_neutrality(
        material_key="generic-disordered-material",
        representation_mode="ENSEMBLE",
        member_neutrality=(False, False),
        member_geometry=(True, True),
        member_pauling=(True, True),
        weighted_ensemble=True,
        source_marginals_only=True,
    )
    assert result.exact_member_neutrality_applicability == (
        NeutralityApplicability.MODEL_DOMAIN_UNSUPPORTED.value
    )
    assert result.material_verdict_authorized is False
    assert result.member_neutrality_false_count == 2


def test_direct_representation_keeps_exact_neutrality_applicable():
    result = classify_exact_member_neutrality(
        material_key="generic-ordered-material",
        representation_mode="DIRECT",
        member_neutrality=(False,),
        member_geometry=(True,),
        member_pauling=(True,),
        weighted_ensemble=False,
        source_marginals_only=False,
    )
    assert result.exact_member_neutrality_applicability == (
        NeutralityApplicability.APPLICABLE.value
    )
