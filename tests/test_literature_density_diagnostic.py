"""Exposed 2021 published Table1 rank inversions; NOT independent validation."""
import copy
import json
from pathlib import Path
import pytest

from rhombus.literature.density_diagnostic import analyze_density_confounding, run_files

ROOT=Path(__file__).resolve().parents[1]
PRE=ROOT/'data/development/rosen_2021_surface_storage_lead_v1.json'
DEN=ROOT/'data/development/rosen_2021_relative_density_table1_lead_v1.json'


def fixture():
    return json.loads(PRE.read_text()),json.loads(DEN.read_text())


def test_actual_publisher_viewed_table1_density_rank_reversals_and_no_predictor():
    result=run_files(PRE,DEN)
    assert result['numeric_25C_TOTAL_conditions']==9
    assert result['comparisons_within_one_unreplicated_author_study']==36
    assert result['density_conductivity_rank_concordant_pairs']==23
    assert result['density_conductivity_rank_discordant_pairs']==13
    assert result['rank_ties']==0
    assert result['densest_sample']==result['largest_observed_conductivity_sample']=='Air0'
    assert result['argon_7day_air_storage_change']['relative_density_change_percentage_points']==-2.4
    assert result['argon_7day_air_storage_change']['total_conductivity_change_S_cm']==pytest.approx(8.6e-5)
    assert result['argon_7day_air_storage_change']['opposite_direction'] is True
    assert result['air_7day_air_storage_change']['relative_density_change_percentage_points']==-13.3
    assert result['air_7day_air_storage_change']['total_conductivity_change_S_cm']==pytest.approx(-3.8213e-4)
    assert not result['air_7day_air_storage_change']['opposite_direction']
    assert result['relative_density_is_POST_SINTER_CHARACTERIZATION_NOT_PRESELECTION_INPUT']
    assert result['retrospective_same_row_oracle_not_a_deployable_density_policy']
    assert not result['model_fitted_or_evaluated']
    assert not result['original_raw_source_sha256_verified']
    assert result['new_strict_qualified_doi_groups']==result['new_strict_manufacturing_comparisons']==0
    assert not result['scientific_GO'] and not result['production_enabled']
    assert not result['official_TEST_121_accessed']


@pytest.mark.parametrize('side,mutation', [
    ('density',lambda d:d.update(doi='10.1234/other')),
    ('density',lambda d:d.update(source_status='RAW_AUTHENTICATED')),
    ('density',lambda d:d.update(original_raw_sha256='fabricated')),
    ('density',lambda d:d.update(measurement_type='PRESELECTION_DENSITY_FEATURE')),
    ('density',lambda d:d.update(new_strict_qualified_doi_groups=1)),
    ('density',lambda d:d.update(sample_pellet_ids_verified=True)),
    ('density',lambda d:d['table1_density_rows'][0].update(sample='Air0')),
    ('density',lambda d:d['table1_density_rows'][0].update(relative_density_percent_literal='110')),
    ('density',lambda d:d['table1_density_rows'][0].update(relative_density_percent_literal='NaN')),
    ('density',lambda d:d['table1_density_rows'][4].update(relative_density_percent_literal='87.1')),
    ('density',lambda d:d['table1_density_rows'][4].update(row_status='MEASURED')),
    ('density',lambda d:d['table1_density_rows'][0].update(row_status='NOT_PRODUCED')),
    ('conductivity',lambda d:d['table1'][0].update(conductivity_literal_S_cm='1e6')),
    ('conductivity',lambda d:d['table1'][4].update(conductivity_literal_S_cm='2.1e-4')),
    ('conductivity',lambda d:d.update(new_strict_qualified_doi_groups=1)),
])
def test_mutation_cannot_promote_density_to_science_or_impute_missing(side,mutation):
    a,b=fixture()
    mutation(a if side=='conductivity' else b)
    with pytest.raises(ValueError):
        analyze_density_confounding(a,b)


def test_density_literal_change_keeps_public_unverified_tier():
    a,b=fixture()
    b['table1_density_rows'][0]['relative_density_percent_literal']='91.1'
    result=analyze_density_confounding(a,b)
    assert not result['original_raw_source_sha256_verified']
    assert not result['model_fitted_or_evaluated']
    assert not result['scientific_GO']
