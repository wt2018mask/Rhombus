"""All inputs are metadata; no energies and no physical model computation."""
from __future__ import annotations

from copy import deepcopy
import json

import pytest

from rhombus.benchmark.tier_a_power_envelope import (
    metadata_only_power_envelope, one_sided_zero_event_upper,
    required_zero_event_groups,
)
from tests.test_tier_a_budget_contract_0204 import fixtures
from scripts.benchmark.analyze_tier_a_power_envelope_0205 import run


def _registry():
    registry, _, _ = fixtures()
    return registry


def test_zero_event_one_sided_exact_upper_derived_from_binomial_tail():
    n = 4
    u = one_sided_zero_event_upper(n, confidence=.95)
    assert u == pytest.approx(1 - .05 ** .25)
    assert (1-u) ** n == pytest.approx(.05)
    assert one_sided_zero_event_upper(0, confidence=.95) is None
    assert one_sided_zero_event_upper(103, confidence=.95) < u


def test_minimum_required_independent_accepted_groups_avoids_roundoff():
    n = required_zero_event_groups(risk_target=.05, confidence=.95)
    assert n == 59
    assert one_sided_zero_event_upper(n, confidence=.95) <= .05
    assert one_sided_zero_event_upper(n-1, confidence=.95) > .05
    for risk in (.001, .005, .1, .2, .5):
        count = required_zero_event_groups(risk_target=risk, confidence=.95)
        assert one_sided_zero_event_upper(count, confidence=.95) <= risk
        if count > 1:
            assert one_sided_zero_event_upper(count-1, confidence=.95) > risk


def test_group_envelope_is_always_unqualified_not_test_result():
    r=metadata_only_power_envelope(_registry(),risk_target=.05,confidence=.95)
    assert r["hypothesis_only"]["minimum_accepted_groups_in_ideal_zero_failure_case"] == 59
    assert r["planned_train_pilot_four_groups"]["scientific_claim_allowed"] is False
    assert r["planned_train_pilot_four_groups"]["observed_risk"] is None
    assert r["data_access"] == "ALLOWLIST_METADATA_ONLY_NO_DFT_OR_MLIP_TARGET_VALUES"
    assert r["execution_authorized"] is False
    assert r["benchmark_status"] == "BENCHMARK_NOT_FROZEN"
    assert r["scientific_status"] == "SCIENTIFIC_NO_GO_ABSTAIN"
    assert not any("em_dft" in str(k) for k in r)


def test_four_group_pilot_cannot_support_five_percent_risk_even_in_idealization():
    report=metadata_only_power_envelope(_registry(),risk_target=.05,confidence=.95)
    row=report["planned_train_pilot_four_groups"]
    assert row["retained_chemsys_groups"] == 4
    assert row["optimistic_upper_risk_if_every_group_accepted_and_zero_failures"] > .52
    assert row["zero_failure_bound_attainable_with_available_groups_in_IID_idealization"] is False
    assert row["minimum_required_group_coverage_in_IID_zero_failure_idealization"] is None


def test_strict_alt_group_exclusion_and_candidates_consistent():
    r=metadata_only_power_envelope(_registry(),risk_target=.05,confidence=.95)
    assert r["retained_chemsys_candidate"]["test"]["retained_chemsys_groups"] == 1
    assert r["strict_exclusive_chemsys_sensitivity_only"]["test"]["retained_chemsys_groups"] == 1
    assert r["retained_chemsys_candidate"]["train"]["retained_chemsys_groups"] == 6
    assert r["hypothesis_only"]["IID_accepted_group_bernoulli_assumption"] == "UNPROVEN"
    assert "GROUP_COVERAGE_IS_NOT_EDGE_COVERAGE" in r["independence_limits"]


@pytest.mark.parametrize("field, value", [
    ("risk", 0), ("risk", 1), ("risk", True), ("risk", None),
    ("risk", float('nan')), ("risk", float('inf')),
    ("confidence", 0.5), ("confidence", 1), ("confidence", "0.95"),
    ("confidence", float('-inf')),
])
def test_invalid_numeric_assumptions_rejected(field, value):
    kwargs={"risk_target":.05,"confidence":.95}
    kwargs["risk_target" if field == "risk" else "confidence"] = value
    with pytest.raises(ValueError):
        metadata_only_power_envelope(_registry(),**kwargs)


@pytest.mark.parametrize("bad", [True, -1, 100001, 1.2, None])
def test_invalid_group_count_rejected(bad):
    with pytest.raises(ValueError, match="INVALID_GROUP_COUNT"):
        one_sided_zero_event_upper(bad,confidence=.95)


def test_registry_metadata_tamper_and_label_injection_rejected():
    r=_registry()
    for mode in ("groups", "rows_hash", "edge", "extra", "label"):
        x=deepcopy(r)
        if mode=="groups":
            x["counts"]["retained_groups"]["test"]+=1
        elif mode=="rows_hash":
            x["rows_sha256"]="0"*64
        elif mode=="edge":
            x["rows"][0]["group_id"]="CHEMSYS:OTHER"
        elif mode=="extra":
            x["rows"][0]["candidate_split"]="TEST"
        elif mode=="label":
            x["rows"][0]["em_dft"] = 0.3
        with pytest.raises(ValueError):
            metadata_only_power_envelope(x, risk_target=.05, confidence=.95)


def test_input_order_is_canonical_and_reproducible():
    a=_registry()
    b=deepcopy(a)
    assert metadata_only_power_envelope(a,risk_target=.05,confidence=.95)==metadata_only_power_envelope(b,risk_target=.05,confidence=.95)


def test_cli_new_file_only_duplicate_json_and_fail_closed(tmp_path):
    r=_registry()
    inp=tmp_path/'registry.json'
    out=tmp_path/'envelope.json'
    inp.write_text(json.dumps(r),encoding='utf-8')
    x=run(registry_file=inp,output=out,risk_target=.05,confidence=.95)
    assert json.loads(out.read_text())==x
    with pytest.raises(ValueError,match="OUTPUT_MUST_BE_NEW"):
        run(registry_file=inp,output=out,risk_target=.05,confidence=.95)
    with pytest.raises(ValueError,match="OUTPUT_MUST_BE_NEW"):
        run(registry_file=inp,output=inp,risk_target=.05,confidence=.95)
    inp.write_text('{"a":1,"a":2}')
    with pytest.raises(ValueError,match="REGISTRY_JSON_INVALID"):
        run(registry_file=inp,output=tmp_path/'unused.json',risk_target=.05,confidence=.95)


def test_cli_never_writes_on_invalid_input(tmp_path):
    p=tmp_path/'bad.json';q=tmp_path/'out.json'
    p.write_text('{"execution_authorized":true}')
    with pytest.raises(ValueError):
        run(registry_file=p,output=q,risk_target=.05,confidence=.95)
    assert not q.exists()
