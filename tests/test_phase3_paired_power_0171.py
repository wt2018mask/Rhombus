"""0171 exact paired power, multiplicity and no sample promotion."""
import math
import pytest
from scripts.science import paired_power_0171 as m


def test_exact_unconditional_sample_targets_and_multiplicity():
    result=m.plan()
    assert result["scientific_GO"] is False
    assert result["sealed_roster_truth_or_individual_sample_IDs_accessed"] is False
    assert result["sample_independence_actually_attested"] is False
    assert all(result[k]=="BLOCKED" for k in ("P0_01","P0_02","P0_03"))
    expected=[246,148,138,83,342,205,191,114]
    rows=result["power_scenarios"]
    assert [r["minimum_independent_enrolled_materials_assuming_IID"] for r in rows]==expected
    assert rows[0]["prospective_recruitment_if_20pct_pre_enrollment_nonacquisition"]==308
    assert rows[4]["prospective_recruitment_if_20pct_pre_enrollment_nonacquisition"]==428
    assert all(r["exact_unconditional_power"]>=0.7999999 for r in rows)
    assert all(r["power_at_preceding_count"]<0.8 for r in rows)
    assert all(r["minimum_independent_enrolled_materials_assuming_IID"]>93 for r in rows[4:7])


def test_exact_integer_null_rejection_and_unequal_powers():
    assert m._exact_critical(0,1)==1
    assert m._exact_critical(1,1)==2
    for arms in (1,3):
        for d in range(1,150):
            k=m._exact_critical(d,arms)
            if k<=d:
                assert 20*arms*sum(math.comb(d,j) for j in range(k,d+1))<=2**d
                if k>0:
                    assert 20*arms*sum(math.comb(d,j) for j in range(k-1,d+1))>2**d
    for n in (5,6,25,50,100):
        assert m.unconditional_power(n,.7,.3,3) <= m.unconditional_power(n,.7,.3,1)+1e-10


@pytest.mark.parametrize("bad", [
    (float("nan"),.3,1),(.5,.3,1),(.99,.3,1),
    (.65,0.0,1),(.65,1.0,1),(.65,.3,2),(.65,.3,True),
    (True,.3,1),(.65,True,1),(.65,.3,0)
])
def test_invalid_assumptions_and_unapproved_multiple_tests_rejected(bad):
    with pytest.raises(ValueError):
        m.minimum_independent_materials(*bad,maximum=80)


def test_no_fake_six_material_sufficiency_and_max_bound():
    assert m.unconditional_power(6,.7,.3,1) < .8
    with pytest.raises(ValueError):
        m.minimum_independent_materials(.65,.3,3,maximum=10)
    with pytest.raises(ValueError):
        m.unconditional_power(0,.65,.3,1)
    with pytest.raises(ValueError):
        m.minimum_independent_materials(.65,.3,1,maximum=0)


def test_output_no_individual_records_and_no_overwrite(tmp_path, monkeypatch):
    target=tmp_path/"out"
    monkeypatch.setattr("sys.argv",["paired_power_0171","--output-dir",str(target)])
    m.main()
    text=(target/"power_plan_0171.json").read_text()
    assert "formula" not in text and "private_material_id" not in text
    assert '"scientific_GO":false' in text
    with pytest.raises(SystemExit):
        m.main()
