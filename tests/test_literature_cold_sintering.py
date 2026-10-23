"""Original-prose association, source tampering and exposed-label boundaries."""
import copy
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from rhombus.literature import cold_sintering as c
from rhombus.literature.harvest import extract_registered_measurements
from rhombus.literature.prior_exposure import audit_prior_exposure

ROOT = Path(__file__).resolve().parents[1]
EXCERPT = ROOT/'data/development/latp_cold_sintering_source_excerpt_20261021_v1.xml'


def tree():
    return ET.fromstring(EXCERPT.read_bytes())


def test_explicit_respectively_clause_binds_three_water_conditions_only():
    rows = c.parse_cold_sintering_tree(tree())
    assert [r['holding_time_min'] for r in rows] == [5, 10, 30]
    assert [r['conductivity_S_cm'] for r in rows] == [1.4e-4, 1.8e-4, 3e-4]
    for row in rows:
        assert row['observable_type'] == 'TOTAL' and row['measurement_temperature_C'] == 25
        assert row['pressure_MPa'] == 25 and row['process_temperature_C'] == 200
        assert row['temperature_reference'] == 'PREHEATED_MOLD_TARGET'
        assert not row['isothermal_sample_hold_at_200_C_verified']
        assert row['water_to_sheet_mass_ratio'] == .3 and row['atmosphere'] is None
        assert row['tier'] == 'EXPLORATORY' and row['conductivity_uncertainty_S_cm'] is None
        assert row['individual_specimen_id'] is row['independent_replicate_count'] is None
        assert row['table_id'] is row['original_cell'] is None
        assert 'respectively' in row['source_clause'] and not row['eligible_for_new_heldout_evaluation']
    # The porous and no-water controls have no authenticated comparable dwell.
    assert all('WATER_' in r['condition_id'] for r in rows)


@pytest.mark.parametrize('old,new', [
    ('1.4 × 10<sup>−4</sup>', '3.0 × 10<sup>−4</sup>'), ('S/cm at 25', 'mS/cm at 25'),
    ('S/cm at 25', 'S/cm at 20'), ('5, 10, and 30 min', '30, 10, and 5 min'),
    ('respectively.', 'approximately.'), ('total conductivities', 'bulk conductivities'),
    ('25 MPa', '200 MPa'), ('200 °C', '250 °C'), ('1:0.3', '1:0'),
    ('550 °C for 3 h', '550 °C for 1 h'), ('650 °C for 2 h', '650 °C for 5 h'),
    ('3.0 × 10<sup>−4</sup>', '3.0(1) × 10<sup>−4</sup>'),
])
def test_changed_conditions_units_observable_values_or_uncertainty_denied(old, new):
    raw = EXCERPT.read_bytes(); assert old.encode() in raw
    changed = raw.replace(old.encode(), new.encode())
    with pytest.raises(ValueError, match='context missing or changed'):
        c.parse_cold_sintering_tree(ET.fromstring(changed))
    with pytest.raises(ValueError, match='original raw bytes'):
        c.extract_cold_sintering_comparison(changed)


@pytest.mark.parametrize('change', ['doi', 'pmc', 'title', 'author', 'rights', 'review', 'duplicate_context'])
def test_identity_and_duplicate_context_adversaries(change):
    r = tree()
    if change == 'doi': r.find('.//article-id[@pub-id-type="doi"]').text = '10.1234/other'
    if change == 'pmc': r.find('.//article-id[@pub-id-type="pmcid"]').text = 'PMC1'
    if change == 'title': r.find('.//article-title').text = 'A different paper'
    if change == 'author': r.find('.//contrib/name/given-names').text = 'Other'
    if change == 'rights':
        for link in r.findall('.//permissions/license//ext-link'): link.attrib.clear()
    if change == 'review': r.set('article-type', 'review-article')
    if change == 'duplicate_context': r.find('body').append(copy.deepcopy(r.find('body/p')))
    with pytest.raises(ValueError): c.parse_cold_sintering_tree(r)


def test_excerpt_never_substitutes_for_original_response_or_rsc_source():
    with pytest.raises(ValueError, match='original raw bytes'):
        c.extract_cold_sintering_comparison(EXCERPT.read_bytes())
    with pytest.raises(ValueError, match='DOI/PMC mismatch'):
        c.extract_cold_sintering_comparison(EXCERPT.read_bytes(), '10.1039/d2ta09250f', c.PMC)
    assert extract_registered_measurements(b'not a source', '10.1039/d2ta09250f', '') == []


def test_rsc_unverified_labels_are_exposed_without_becoming_authenticated():
    report = audit_prior_exposure([{'doi': '10.1039/d2ta09250f', 'tier': 'EXPLORATORY'}])
    assert report['records'][0]['history_status'] == 'UNAUTHENTICATED_LABELS_ALREADY_EXPOSED'
    assert report['previously_exposed_other_doi_groups'] == 1
    assert report['history_unreviewed_doi_groups'] == 0
    assert not report['independent_blind_claim']
    assert report['new_independent_evaluation_doi_groups_authorized'] == 0


def test_scientific_receipt_matches_source_rows_and_no_predictive_win():
    report = json.loads((ROOT/'data/development/rsc_access_latp_qualification_20261021_v1.json').read_text())
    assert report['latp']['measurements'] == c.parse_cold_sintering_tree(tree())
    assert hashlib.sha256(EXCERPT.read_bytes()).hexdigest() == report['latp']['excerpt_sha256']
    assert report['rsc']['original_raw_sha256'] is None
    assert report['rsc']['verified_original_table_cells'] == 0
    assert len(report['rsc']['acquisition_failures']) == 3
    assert all(x['bytes'] == 0 and not x['complete'] for x in report['rsc']['acquisition_failures'])
    d = report['latp']['retrospective_decision']
    assert d['uniform_choice_expected_S_cm'] == pytest.approx((1.4e-4+1.8e-4+3e-4)/3)
    assert d['always_longest_dwell_S_cm'] == d['point_oracle_S_cm'] == 3e-4
    assert d['observed_model_advantage_over_longest_dwell'] is None
    assert d['independent_comparison_units_established'] == 0
    assert not report['qualification']['checkpoint_0195_consumed']
    assert report['qualification']['new_strict_qualified_doi_groups'] == 0
