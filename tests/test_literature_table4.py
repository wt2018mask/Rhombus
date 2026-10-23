"""Attributed original-source excerpt tests; not raw-source authentication."""
import copy
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from rhombus.literature import table4 as t

ROOT = Path(__file__).resolve().parents[1]
EXCERPT = ROOT/'data/development/table4_6809_source_excerpt_20261020_v1.xml'


def tree(): return ET.fromstring(EXCERPT.read_bytes())


def table(root, identifier=t.TABLE_ID):
    return root.find(f'.//table-wrap[@id="{identifier}"]')


def test_keyed_total_cells_and_existing_gate_remain_separate():
    rows=t.parse_table4_tree(tree())
    assert [r['sample_code'] for r in rows]==list(t.ROUTES)
    assert [r['source_cell'] for r in rows]==['3.14(7)','2.64(3)','2.02(2)','3.28(3)']
    assert [r['conductivity_S_cm'] for r in rows]==[.000314,.000264,.000202,.000328]
    assert [r['original_cell'] for r in rows]==['R7C2','R7C3','R7C4','R7C5']
    assert all(r['observable_type']=='TOTAL' and r['measurement_temperature_C']==25 for r in rows)
    assert all(r['tier']=='EXPLORATORY' and r['conductivity_uncertainty_S_cm'] is None
               and 'UNCERTAINTY_UNSPECIFIED_OR_INVALID' in r['reasons'] for r in rows)
    assert all(r['parenthetical_statistical_meaning']=='UNKNOWN' for r in rows)
    assert all(r['holding_time_min']==1800 and r['process_temperature_C']==1200
               and r['pressure_MPa'] is None for r in rows)  # cold pressing is separate
    assert all(len(r['method_evidence'])==7 and r['individual_pellet_id'] is None for r in rows)


@pytest.mark.parametrize('change',['values','labels','bulk_values','total_bulk_rows','multiplier','units','duplicate_table'])
def test_column_row_observable_and_units_adversaries(change):
    root=tree(); element=table(root); rows=element.findall('.//tr')
    if change=='values':
        a,b=rows[6][1],rows[6][4];a.text,b.text=b.text,a.text
    if change=='labels':rows[0][2].text='SSR'
    if change=='bulk_values':rows[6][1].text=rows[7][1].text
    if change=='total_bulk_rows':
        parent=element.find('table/tbody');children=list(parent);parent.remove(children[5]);parent.insert(6,children[5])
    if change in ('multiplier','units'):
        cell=rows[6][0]
        if change=='multiplier':cell.find('sup').text='−3'
        else:cell.find('sup').tail=' mS/cm)'
    if change=='duplicate_table':root.find('body').append(copy.deepcopy(element))
    with pytest.raises(ValueError):t.parse_table4_tree(root)


@pytest.mark.parametrize('section,old,new',[
 ('sec2dot2','25 °C','room temperature'),
 ('sec2dot1dot1','850','900'),('sec2dot1dot2','seven days','one day'),
 ('sec2dot1dot3','10% excess','stoichiometric'),('sec2dot1dot4','300','150'),
 ('sec2dot1dot5','30 h','3 h'),('sec2dot1dot5','120 MPa','53 MPa'),
])
def test_missing_or_changed_route_steps_and_measurement_temperature(section,old,new):
    root=tree();element=root.find(f'.//sec[@id="{section}-materials-14-06809"]')
    raw=ET.tostring(element,encoding='unicode');assert old in raw
    parent=root.find('body');index=list(parent).index(element);parent.remove(element)
    parent.insert(index,ET.fromstring(raw.replace(old,new)))
    with pytest.raises(ValueError,match='context changed'):t.parse_table4_tree(root)


@pytest.mark.parametrize('change',['doi','pmcid','rights','authors','review'])
def test_specific_source_identity_and_rights_denials(change):
    root=tree()
    if change=='doi':root.find('.//article-id[@pub-id-type="doi"]').text='10.1234/wrong'
    if change=='pmcid':root.find('.//article-id[@pub-id-type="pmcid"]').text='999999'
    if change=='rights':
        link=root.find('.//permissions/license//ext-link');link.set('{http://www.w3.org/1999/xlink}href','https://creativecommons.org/licenses/by-nc/4.0/')
    if change=='authors':root.find('.//contrib/name/given-names').text='Unverified'
    if change=='review':root.set('article-type','review-article')
    with pytest.raises(ValueError,match='not authenticated'):t.parse_table4_tree(root)


def test_derived_excerpt_is_not_the_original_authenticated_response():
    with pytest.raises(ValueError,match='raw bytes'):t.extract_route_comparison(EXCERPT.read_bytes())


def test_duplicate_summary_rows_and_duplicate_measurements_denied():
    root=tree();summary=table(root,'materials-14-06809-t005');summary.findall('.//tr')[2][0].text='SSR'
    with pytest.raises(ValueError):t.parse_table4_tree(root)
    rows=t.parse_table4_tree(tree());rows[1]=copy.deepcopy(rows[0])
    with pytest.raises(ValueError):t.summarize_decision_information(rows)


def test_decision_information_is_one_comparison_not_six_independent_pairs():
    rows=t.parse_table4_tree(tree());out=t.summarize_decision_information(rows)
    assert out['reported_point_value_order']==['SD','SSR','SASSR','CP']
    assert out['uniform_route_baseline_expected_S_cm']==pytest.approx(2.77e-4)
    assert out['descriptive_oracle_minus_uniform_S_cm']==pytest.approx(5.1e-5)
    assert out['descriptive_SD_minus_SSR_S_cm']==pytest.approx(1.4e-5)
    assert out['independent_comparison_units']==1
    assert out['SD_significantly_better_than_SSR'] is None
    assert not out['new_model_fitted'] and not out['independent_predictive_validation']
    rows[0]['observable_type']='BULK'
    with pytest.raises(ValueError,match='TOTAL decision'):t.summarize_decision_information(rows)


def author_doc(doi='10.1234/other'):
    return {'doi':doi,'authors':[{'name':'Martin Finsterbusch','orcid':None,'affiliation_ids':['A']}],
            'affiliations':{'A':'Forschungszentrum Jülich GmbH'},'citations':[]}


def test_shared_authors_do_not_merge_specimens_or_attest_experimental_independence():
    out=t.audit_source_dependency(author_doc(t.DOI),author_doc())
    assert len(out['shared_authors'])==1
    assert out['laboratory_independence']=='NOT_INDEPENDENT_FZJ_LAB_CONTEXT'
    assert out['experimental_independence']=='UNKNOWN'
    assert not out['experimental_measurements_merged_due_to_authors']
    assert out['cross_paper_dataset_reuse']=='NOT_ESTABLISHED'


@pytest.mark.parametrize('change',['given_name','affiliation','orcid'])
def test_incorrect_author_overlap_cannot_create_an_identity_match(change):
    a=author_doc(t.DOI);b=author_doc()
    if change=='given_name':b['authors'][0]['name']='M. Finsterbusch'
    if change=='affiliation':b['affiliations']['A']='Different institution'
    if change=='orcid':a['authors'][0]['orcid']='id-one';b['authors'][0]['orcid']='id-two'
    assert not t.audit_source_dependency(a,b)['shared_authors']


def test_reference_doi_in_href_is_preserved_without_claiming_dataset_reuse():
    root=tree();back=ET.SubElement(root,'back');ref=ET.SubElement(back,'ref',id='synthetic-link-only')
    link=ET.SubElement(ref,'ext-link',{'ext-link-type':'doi','{http://www.w3.org/1999/xlink}href':'10.1234/other'})
    a=t.source_identity(root);b=author_doc()
    edge,=t.audit_source_dependency(a,b)['explicit_citation_edges']
    assert edge['type']=='DECLARED_DOI_CITATION' and edge['bibliographic_identity_requires_crosscheck']


def test_registry_dispatch_with_explicit_derived_fixture_hash(monkeypatch):
    from rhombus.literature.harvest import extract_registered_measurements
    raw=EXCERPT.read_bytes()
    # Unit fixture only; the scientific receipt pins the different ORIGINAL hash.
    monkeypatch.setattr(t,'JATS_SHA256',hashlib.sha256(raw).hexdigest())
    rows=extract_registered_measurements(raw,t.DOI,t.PMC)
    assert len(rows)==4 and all(r['tier']=='EXPLORATORY' for r in rows)


def test_scientific_report_preserves_all_bindings_and_unknowns():
    report=json.loads((ROOT/'data/development/table4_6809_qualification_20261020_v1.json').read_text())
    for file,digest in report['artifact_bindings'].items():
        assert hashlib.sha256((ROOT/file).read_bytes()).hexdigest()==digest
    assert hashlib.sha256((ROOT/report['ancestry']['prior_lead_path']).read_bytes()).hexdigest()==report['ancestry']['prior_lead_sha256']
    expected=t.parse_table4_tree(tree())
    for row,original in zip(report['measurements'],expected,strict=True):
        assert all(row[key]==value for key,value in original.items())
        history=report['manufacturing_histories'][row['route_history_ref']]
        assert history['common_final_process']['sinter_temperature_C']==1200
        assert history['common_final_process']['sinter_time_h']==30
        assert history['common_final_process']['actual_EIS_pellet_geometry'] is None
        assert row['final_pellet_exact_composition'] is None
    assert [report['manufacturing_histories'][route]['calcination_total_h'] for route in t.ROUTES]==[40,21,1,1]
    assert report['source']['Table_S1_geometry'] is None
    assert report['uncertainty_audit']['numeric_uncertainty_S_cm'] is None
    q=report['qualification']
    assert q['new_strict_qualified_DOI_groups']==0 and q['new_strict_original_manufacturing_comparisons']==0
    assert not q['checkpoint_0195_consumed'] and not q['scientific_GO']


def test_actual_graph_checks_metadata_conflict_and_distinguishes_publication_from_experiment():
    r=json.loads((ROOT/'data/development/table4_6809_qualification_20261020_v1.json').read_text())
    graphs=r['source_dependency_audit']['relationships']
    core=next(g for g in graphs if g['DOIs'][1]=='10.1038/s41467-026-74887-z')
    assert {a['name'] for a in core['shared_authors']}=={'Martin Finsterbusch','Dina Fattakhova-Rohlfing','Olivier Guillon'}
    assert core['experimental_independence']=='UNKNOWN'
    assert not core['experimental_measurements_merged_due_to_authors']
    cited=next(g for g in graphs if g['DOIs'][1]=='10.1002/advs.202404682')
    assert {e['bibliographic_identity_crosscheck'] for e in cited['explicit_citation_edges']}=={
        'CONSISTENT_WITH_2021_MATERIALS_14_6809','CONFLICTING_RENDERED_REFERENCE_METADATA'}
