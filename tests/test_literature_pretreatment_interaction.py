"""Exposed-table arithmetic tests, not original-source authentication."""
import copy
import json
from pathlib import Path
import pytest
from rhombus.literature.pretreatment_interaction import evaluate_exposed_processing_interaction, run_lead

LEAD = Path(__file__).resolve().parents[1]/'data/development/rosen_2021_surface_storage_lead_v1.json'


def sample():
    return json.loads(LEAD.read_text())


def test_matched_treatment_interaction_and_missingness():
    r = run_lead(LEAD)
    assert r['table_rows'] == 11 and r['numerical_total25C_rows'] == 9
    assert r['explicit_missing_conductivity_rows'] == ['Air1,7', 'Argon1,7']
    assert r['matched_air_storage_change_S_cm']['7']['ARGON'] == pytest.approx(8.6e-5)
    assert r['matched_air_storage_change_S_cm']['7']['AIR'] == pytest.approx(-3.8213e-4)
    assert r['pretreatment_by_storage_interactions']['7']['difference_in_differences_air_minus_argon_S_cm'] == pytest.approx(-4.6813e-4)
    assert r['pretreatment_by_storage_interactions']['1']['difference_in_differences_air_minus_argon_S_cm'] == pytest.approx(-3.48e-4)
    assert all(v['sign_reversal_between_pretreatments'] for v in r['pretreatment_by_storage_interactions'].values())
    assert r['new_strict_qualified_doi_groups'] == r['new_strict_manufacturing_comparisons'] == 0
    assert r['independent_sample_count_established'] is None
    assert not r['scientific_GO'] and not r['predictive_models_evaluated']


@pytest.mark.parametrize('mutator', [
    lambda x: x.update(doi='10.1039/other'),
    lambda x: x.update(raw_original_sha256='forged-hash'),
    lambda x: x.update(independent_blind_eligibility=True),
    lambda x: x.update(new_strict_qualified_doi_groups=1),
    lambda x: x['measurement_scope'].update(temperature_C=30),
    lambda x: x['measurement_scope'].update(conductivity_type='BULK'),
    lambda x: x['measurement_scope'].update(unit='mS/cm'),
    lambda x: x['measurement_scope'].update(final_sinter_C=1200),
    lambda x: x['table1'][0].update(sample='Air0'),
    lambda x: x['table1'][0].update(pretreatment='AIR'),
    lambda x: x['table1'][0].update(storage_days=7),
    lambda x: x['table1'][0].update(conductivity_literal_S_cm=None),
    lambda x: x['table1'][4].update(conductivity_literal_S_cm='5.00e-4'),
    lambda x: x['table1'][0].update(conductivity_literal_S_cm='1e9'),
])
def test_source_or_admission_mutations_fail_closed(mutator):
    lead = copy.deepcopy(sample())
    mutator(lead)
    with pytest.raises(ValueError):
        evaluate_exposed_processing_interaction(lead)


def test_numeric_mutation_never_upgrades_an_unverified_source():
    lead = copy.deepcopy(sample())
    lead['table1'][0]['conductivity_literal_S_cm'] = '1.99e-4'
    result = evaluate_exposed_processing_interaction(lead)
    assert result['evidence_tier'].endswith('NOT_RAW_BYTE_AUTHENTICATED')
    assert not result['numerical_uncertainty_attested']
    assert not result['OBELIX_TEST_121_accessed']
    assert result['new_strict_qualified_doi_groups'] == 0
