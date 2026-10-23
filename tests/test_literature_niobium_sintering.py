"""Actual table-cell and frozen source-embargo failures; no synthetic source truth."""
import copy
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest
from rhombus.literature import niobium_sintering as n

ROOT = Path(__file__).resolve().parents[1]
EXCERPT = ROOT/'data/development/niobium_table1_fact_excerpt_20261023_v1.xml'
REPORT = ROOT/'data/development/niobium_choice_attempt_20261023_v1.json'
TRAINING = ROOT/'data/development/process_feature_identifiability_20261021_v1.json'

def report(): return json.loads(REPORT.read_text())
def tree(): return ET.fromstring(EXCERPT.read_bytes())


def test_actual_three_paired_columns_bind_twelve_distinct_conditions():
    rows = n.parse_original_table(tree())
    assert len(rows) == 12 and len({r['condition_id'] for r in rows}) == 12
    assert [r['conductivity_S_cm'] for r in rows if r['Nb_x'] == '0.4'] == [1.56e-4, 3.56e-4, 3.86e-4, 2.62e-4]
    assert next(r for r in rows if r['condition_id'] == 'Nb0.4-4h')['original_cell'] == 'R4C4'
    assert rows == [{k:r[k] for k in rows[0]} for r in report()['measurements']]


@pytest.mark.parametrize('mutation', ['unit','value','swap','sample','duration','duplicate','span','table','observable','missing'])
def test_reject_wrong_units_values_process_labels_and_population(mutation):
    root=tree(); t=root.find('.//table-wrap'); rows=t.findall('.//tr')
    if mutation=='unit': rows[0][1].text='Conductivity(mS/cm)'
    if mutation=='value': rows[1][1].text='9.1e-4'
    if mutation=='swap': rows[1][1].text,rows[1][3].text=rows[1][3].text,rows[1][1].text
    if mutation=='sample': rows[1][0].text='x = 0.3, 2 h'
    if mutation=='duration': rows[1][0].text='x = 0.2, 20 h'
    if mutation=='duplicate': rows[2][0].text=rows[1][0].text
    if mutation=='span': rows[1][0].set('rowspan','2')
    if mutation=='table': root.find('body').append(copy.deepcopy(t))
    if mutation=='observable': t.find('caption/p').text='Bulk conductivity'
    if mutation=='missing': t.find('.//tbody').remove(rows[-1])
    with pytest.raises(ValueError): n.parse_original_table(root)


def test_factual_excerpt_is_not_original_authentication():
    with pytest.raises(ValueError,match='source bytes'): n.extract_niobium_sintering(EXCERPT.read_bytes())
    with pytest.raises(ValueError,match='DOI/PMC'): n.extract_niobium_sintering(b'fake',pmcid='PMC1')


def test_actual_frozen_attempt_uses_full_source_formula_component_embargo(monkeypatch):
    r=report()
    # Production byte authentication is separately required. Reuse only the
    # retained reviewed rows here to exercise the frozen receipt/support path.
    monkeypatch.setattr(n,'extract_niobium_sintering',lambda raw:r['measurements'])
    result=n.assess_frozen_choice_feasibility(b'explicit-unit-only-row-stub',TRAINING.read_bytes())
    assert result==r['feasibility']
    assert result['source_choice_abstentions']==6
    assert result['out_of_support_candidate_evaluations']==24
    assert result['formula_embargo_blocked_attempts']==3
    for fold in result['folds']:
        assert fold['authorized_choice'] is None and fold['model_vs_baseline_score'] is None
        assert not fold['model_fitted']
        if fold['train_DOI']=='10.3390/ma13030560':
            # All THREE target-formula pools must quarantine this training DOI,
            # including x=.2/.4, which do not themselves match its x=.6 formula.
            assert 'TRAIN_SOURCE_FORMULA_COMPONENT_OVERLAP' in fold['reasons']
        for c in fold['process_support']['candidates']:
            assert 'OUTSIDE_FINAL_TEMPERATURE_C' in c['reasons']


def test_training_receipt_mutation_is_rejected_before_target_inspection(monkeypatch):
    def no_target(*args): raise AssertionError('target inspected after invalid training receipt')
    monkeypatch.setattr(n,'extract_niobium_sintering',no_target)
    with pytest.raises(ValueError,match='training receipt'): n.assess_frozen_choice_feasibility(b'',TRAINING.read_bytes()+b' ')


def test_record_preserves_unknown_temperature_uncertainty_and_specimens():
    r=report()
    assert r['source']['raw_sha256']==n.RAW_SHA256
    assert hashlib.sha256(EXCERPT.read_bytes()).hexdigest()==r['source']['factual_excerpt_sha256']
    assert hashlib.sha256((json.dumps(r['protocol'],ensure_ascii=False,indent=2)+'\n').encode()).hexdigest()==r['protocol_sha256']
    assert r['protocol_sha256']=='20733fd69bea8c0755dced898b054a7e7b085ddfa2d3f51a49963f237cb3d927'
    for row in r['measurements']:
        assert row['measurement_temperature_C'] is None and row['measurement_methods_range_C']==[25,50]
        assert row['conductivity_uncertainty_S_cm'] is row['physical_specimen_id'] is None
        assert row['tier']=='EXPLORATORY' and not row['eligible_for_new_heldout_evaluation']
        assert not row['post_sinter_density_used_as_feature']
        assert row['lithium_excess']['normalized_elemental_fraction'] is None
    assert {r['nominal_formula'] for r in r['measurements']}=={'Li6.8La3Zr1.8Nb0.2O12','Li6.6La3Zr1.6Nb0.4O12','Li6.4La3Zr1.4Nb0.6O12'}
    assert not r['claim_boundaries']['TEST121_accessed'] and not r['claim_boundaries']['checkpoint0195_consumed']


def synthetic_source(monkeypatch):
    root=tree();root.set('article-type','research-article');front=ET.SubElement(root,'front');meta=ET.SubElement(front,'article-meta')
    ET.SubElement(meta,'article-id',{'pub-id-type':'doi'}).text=n.DOI
    ET.SubElement(meta,'article-id',{'pub-id-type':'pmcid'}).text=n.PMC
    ET.SubElement(ET.SubElement(meta,'title-group'),'article-title').text=n.TITLE
    ET.SubElement(ET.SubElement(ET.SubElement(meta,'permissions'),'license'),'license-p').text='http://creativecommons.org/licenses/by/4.0/'
    ps=[ET.SubElement(root.find('body'),'p') for _ in range(19)]
    for i,p in enumerate(ps):p.text=f'Synthetic unit context {i}: methods25–50C, Figure5 room temperature'
    all_ps=root.findall('.//body//p')
    monkeypatch.setattr(n,'CONTEXT_HASHES',{i:hashlib.sha256(n._text(all_ps[i]).encode()).hexdigest() for i in n.CONTEXT_HASHES})
    raw=ET.tostring(root);monkeypatch.setattr(n,'RAW_SHA256',hashlib.sha256(raw).hexdigest())
    return root


def test_dispatch_does_not_convert_methods_range_to_table_temperature(monkeypatch):
    from rhombus.literature.harvest import extract_registered_measurements
    root=synthetic_source(monkeypatch)
    rows=extract_registered_measurements(ET.tostring(root),n.DOI,n.PMC)
    assert len(rows)==12 and all(r['measurement_temperature_C'] is None for r in rows)
    assert all(r['observable_type']=='TOTAL' and r['tier']=='EXPLORATORY' for r in rows)


@pytest.mark.parametrize('index',[3,4,7,13,18])
def test_changed_source_processing_or_temperature_context_rejected(monkeypatch,index):
    root=synthetic_source(monkeypatch)
    root.findall('.//body//p')[index].text='Changed1250C process or asserted25C table temperature'
    raw=ET.tostring(root);monkeypatch.setattr(n,'RAW_SHA256',hashlib.sha256(raw).hexdigest())
    with pytest.raises(ValueError,match='context changed'): n.extract_niobium_sintering(raw)
