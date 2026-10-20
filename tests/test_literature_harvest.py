"""Hostile-source and bounded intake tests; fixtures are not scientific evidence."""
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError

import pytest

from rhombus.literature import harvest as h

DOI = '10.1234/oxide'
PMC = 'PMC12345'


def jats(*, doi=DOI, pmcid=PMC, kind='research-article', license=True, rows=None):
    rows = rows or [['Sample', 'nominal formula', 'route', 'sintering temperature (°C)',
                     'holding time (h)', 'measurement temperature (°C)',
                     'total ionic conductivity (S/cm)', 'uncertainty (S/cm)', 'atmosphere'],
                    ['A', 'Li7La3Zr2O12', 'conventional sintering', '1200', '2', '25', '1e-4', '1e-6', 'air']]
    table = ''.join('<tr>' + ''.join('<td>' + x + '</td>' for x in row) + '</tr>' for row in rows)
    rights = '<permissions><license><license-p>Creative Commons Attribution</license-p></license></permissions>' if license else ''
    return (f'<article article-type="{kind}"><front><article-meta><article-id pub-id-type="doi">{doi}</article-id>'
            f'<article-id pub-id-type="pmc">{pmcid[3:]}</article-id>{rights}</article-meta></front>'
            f'<body><table-wrap id="t1"><label>Table 1</label><caption>Conductivity</caption>'
            f'<table>{table}</table></table-wrap></body></article>').encode()


@pytest.mark.parametrize('text', ['10.1234/OXIDE', 'https://doi.org/10.1234/Oxide', 'doi invalid'])
def test_doi_identity(text):
    if text == 'doi invalid':
        with pytest.raises(ValueError): h.normalize_doi(text)
    else:
        assert h.normalize_doi(text) == DOI


def test_explicit_flat_row_preserves_exact_cells_and_units():
    source = h.inspect_jats(jats(), DOI, PMC)
    row, = source['measurements']
    assert row['tier'] == 'STRICT_QUALIFIED'
    assert row['conductivity_S_cm'] == 1e-4
    assert row['holding_time_min'] == 120
    assert row['observable_type'] == 'TOTAL'
    assert row['row_index'] == 1 and row['column_bindings']['sigma'] == 6
    assert row['source_sha256'] == hashlib.sha256(jats()).hexdigest()
    assert not row['eligible_for_new_heldout_evaluation']
    assert not row['final_pellet_composition_verified']


@pytest.mark.parametrize('old,new,reason', [
    (b'>25<', b'>room temperature<', 'MEASUREMENT_NOT_EXPLICIT_EXACT_25C'),
    (b'total ionic', b'bulk ionic', 'NON_TOTAL_OBSERVABLE'),
    (b'conventional sintering', b'hot pressing', 'MISSING_HOT_PRESS_PRESSURE'),
    (b'Li7La3Zr2O12', b'Li6PS5Cl', 'OUTSIDE_LI_O_ONLY_COMPOSITION_PROXY'),
    (b'>air<', b'><', 'ATMOSPHERE_UNSPECIFIED'),
    (b'>1e-6<', b'>unknown<', 'UNCERTAINTY_UNSPECIFIED_OR_INVALID'),
])
def test_missing_context_cannot_be_strict(old, new, reason):
    row, = h.inspect_jats(jats().replace(old, new), DOI, PMC)['measurements']
    assert row['tier'] != 'STRICT_QUALIFIED' and reason in row['reasons']


@pytest.mark.parametrize('old,new', [(b'S/cm', b'mS/cm'), (b'>1e-4<', b'>&lt;1e-4<'),
                                     (b'>1e-4<', b'>1e-4 to 2e-4<'),
                                     (b'>1e-4<', b'>NaN<')])
def test_ambiguous_values_or_units_are_not_point_labels(old, new):
    assert not h.inspect_jats(jats().replace(old,new), DOI, PMC)['measurements']


def test_spanning_columns_and_contradictory_headers_refuse_positional_guess():
    assert not h.inspect_jats(jats().replace(b'<td>Sample', b'<td colspan="2">Sample'), DOI, PMC)['measurements']


@pytest.mark.parametrize('kwargs', [{'doi':'10.1234/wrong'}, {'pmcid':'PMC999'},
                                    {'kind':'review-article'}, {'license':False}])
def test_source_identity_article_type_and_rights_fail_closed(kwargs):
    with pytest.raises(ValueError): h.inspect_jats(jats(**kwargs), DOI, PMC)


def test_referenced_doi_cannot_replace_article_identity():
    raw = jats(doi='10.1234/other').replace(b'</body>', f'<ref><article-id pub-id-type="doi">{DOI}</article-id></ref></body>'.encode())
    with pytest.raises(ValueError): h.inspect_jats(raw, DOI, PMC)


@pytest.mark.parametrize('raw', [b'<!DOCTYPE article [<!ENTITY x "unsafe">]><article/>',
                               jats().decode().encode('utf-16')])
def test_entity_and_non_utf8_xml_denied(raw):
    with pytest.raises(ValueError): h.inspect_jats(raw, DOI, PMC)


def test_metadata_dedup_and_original_study_status_are_not_scientific_admission():
    raw=json.dumps({'resultList':{'result':[
        {'doi':DOI.upper(),'title':'Garnet sintering conductivity','pmcid':PMC,'isOpenAccess':'Y'},
        {'doi':DOI,'title':'Review of garnet electrolytes','isOpenAccess':'Y'},
        {'title':'no DOI'}]},'nextCursorMark':'next'}).encode()
    rows,cursor=h.parse_discovery('europepmc',raw)
    assert rows[0]['doi']==rows[1]['doi']==DOI
    assert rows[1]['original_study_status']=='REVIEW_EXCLUDED'
    assert rows[2]['rejection']=='MISSING_OR_INVALID_DOI'
    assert not rows[0]['independent_author_study_verified']
    assert cursor=='next'


@pytest.mark.parametrize('url', ['http://www.ebi.ac.uk/', 'https://localhost/',
                               'https://user:pass@www.ebi.ac.uk/', 'https://www.ebi.ac.uk:8080/'])
def test_untrusted_endpoints_never_requested(tmp_path,url):
    client=h.PublicClient(tmp_path/'cache')
    with pytest.raises(ValueError): client.fetch(url)
    assert client.events==[]


class DeniedClient:
    interval=10
    def __init__(self, directory):
        self.events=[]
    def fetch(self,url):
        self.events.append({'url':url,'http_status':403})
        raise HTTPError(url,403,'denied',{},None)


def test_blocked_pilot_reports_real_counts_and_no_evaluation(tmp_path):
    result=h.run_pilot(tmp_path/'run',client_factory=DeniedClient)
    assert result['unique_doi_groups_discovered']==0
    assert result['http_requests']==3 and len(result['failures'])==3
    assert result['full_text_attempts']==0 and result['strict_qualified_records']==0
    assert result['heldout_model_evaluation']=='NOT_RUN_NO_QUALIFIED_NEW_COHORT'
    assert not result['official_OBELiX_TEST_121_read']
    with pytest.raises(FileExistsError): h.run_pilot(tmp_path/'run',client_factory=DeniedClient)


def quota_evidence(tmp_path):
    raw=b'Fixture policy, NOT real terms verification'
    (tmp_path/'policy.txt').write_bytes(raw)
    value={'provider':'europepmc','documentation_url':h.API_DOCS['europepmc'],
           'documentation_file':'policy.txt','documentation_sha256':hashlib.sha256(raw).hexdigest(),
           'verified_utc':datetime.now(timezone.utc).isoformat(),
           'free_fulltext_access_confirmed':True,'max_publications':100,
           'requests_per_second':0.1,'terms_evidence_excerpt':'fixture only'}
    path=tmp_path/'quota.json';path.write_text(json.dumps(value))
    return path,value


def test_quota_document_integrity_and_recency(tmp_path):
    path,value=quota_evidence(tmp_path)
    h.validate_quota_evidence(path,100)
    for change in [{'documentation_sha256':'0'*64}, {'requests_per_second':1},
                   {'verified_utc':(datetime.now(timezone.utc)-timedelta(days=8)).isoformat()},
                   {'documentation_file':'../../outside'}, {'free_fulltext_access_confirmed':False}]:
        path.write_text(json.dumps(value|change))
        with pytest.raises((ValueError,FileNotFoundError)): h.validate_quota_evidence(path,100)


def test_frozen_cohort_to_local_fulltext_and_exact_row_e2e(tmp_path,monkeypatch):
    path,_=quota_evidence(tmp_path)
    discovery=tmp_path/'discovery.json'
    discovery.write_text(json.dumps({DOI:[{'doi':DOI,'title':'Garnet sintering conductivity',
        'pmcid':PMC,'open_access_asserted':True,'original_study_status':'UNVERIFIED'}]}))
    monkeypatch.setattr(h,'extract_registered_measurements',lambda *args:[])
    class Client(DeniedClient):
        def fetch(self,url):
            assert url.endswith(PMC+'/fullTextXML')
            self.events.append({'url':url,'http_status':200})
            return jats()
    report=h.run_pilot(tmp_path/'run',client_factory=Client,quota_evidence=path,discovery_path=discovery)
    assert report['full_text_attempts']==report['full_text_responses_obtained']==1
    assert report['strict_qualified_records']==1 and report['http_requests']==1
    assert report['heldout_model_evaluation']=='NOT_RUN_NO_QUALIFIED_NEW_COHORT'
    assert not report['scientific_GO']
    source=json.loads((tmp_path/'run/source-results.json').read_bytes())[0]
    assert source['measurements'][0]['source_cells'][6]=='1e-4'


def hotpress_fixture():
    methods = ('Commercially available Li6.25Al0.25La3Zr2O12 powder was used under an Ar atmosphere. '
               'Samples were pre-pressed into pellets at 10 MPa with fixed applied pressure of 25 MPa '
               'and fixed holding time of 5 min; heat treatment at 850 °C for 4 h in air.')
    xml = ('<article><body><p>'+methods+'</p><p>The ionic conductivity of the samples at RT was determined '
           'by EIS with measurement at RT. Water density was measured at 25 °C.</p>'
           '<table-wrap id="t3"><label>Table 3</label><caption>RT ionic conductivity</caption><table>'
           '<tr><td>Sintering temperature [°C]</td><td>950</td><td>1000</td><td>1050</td><td>1100</td></tr>'
           '<tr><td>Ionic conductivity [mS cm−1] (HP)</td><td>0.000065</td><td>0.0035</td><td>0.093</td><td>0.45</td></tr>'
           '<tr><td>Ionic conductivity [mS cm−1] (SPS)</td><td>0.0015</td><td>0.24</td><td>0.45</td><td/></tr>'
           '</table></table-wrap></body></article>')
    return xml.encode()


def test_new_hotpress_source_maps_seven_cells_and_never_fills_missing_sps(monkeypatch):
    from rhombus.literature import source_parsers as s
    raw=hotpress_fixture()
    monkeypatch.setattr(s,'HOT_PRESS_JATS_SHA256',hashlib.sha256(raw).hexdigest())
    rows=s.extract_hot_press_comparison(raw,s.HOT_PRESS_DOI,s.HOT_PRESS_PMC)
    assert len(rows)==7
    assert not any(r['manufacturing_route']=='SPARK_PLASMA_SINTERING' and r['process_temperature_C']==1100 for r in rows)
    hp=next(r for r in rows if r['manufacturing_route']=='INDUCTION_HOT_PRESS' and r['process_temperature_C']==950)
    assert hp['conductivity_S_cm']==pytest.approx(6.5e-8)
    assert all(r['measurement_temperature_C'] is None for r in rows)
    assert all(r['observable_type']=='IONIC_UNRESOLVED_TOTAL_VS_BULK' for r in rows)
    assert all(r['tier']=='EXPLORATORY' and r['pressure_MPa']==25 for r in rows)
    assert all(r['pre_press_pressure_MPa']==10 for r in rows)
    assert all(r['post_processing']['holding_time_min']==240 for r in rows)


@pytest.mark.parametrize('old,new', [(b'0.0035',b'0.035'),(b'(HP)',b'(SPS)'),(b'>1100<',b'>1150<'),
                                     (b'25 MPa',b'56 MPa'),(b'RT was',b'25 C was')])
def test_new_hotpress_parser_cannot_ignore_changed_source_bytes(monkeypatch,old,new):
    from rhombus.literature import source_parsers as s
    raw=hotpress_fixture()
    monkeypatch.setattr(s,'HOT_PRESS_JATS_SHA256',hashlib.sha256(raw).hexdigest())
    with pytest.raises(ValueError,match='source bytes differ'):
        s.extract_hot_press_comparison(raw.replace(old,new),s.HOT_PRESS_DOI,s.HOT_PRESS_PMC)


def test_reference_column_cannot_qualify_a_secondary_compilation():
    raw=jats().replace(b'<td>atmosphere</td>',b'<td>references</td>')
    row,=h.inspect_jats(raw,DOI,PMC)['measurements']
    assert 'POSSIBLE_SECONDARY_LITERATURE_TABLE' in row['reasons']
    assert row['tier']=='EXPLORATORY'


def test_replay_requires_original_retrieval_hash_and_never_redownloads(tmp_path):
    original=tmp_path/'original'; original.mkdir()
    cache=original/'raw-local-only';cache.mkdir()
    raw=jats();digest=hashlib.sha256(raw).hexdigest()
    (cache/digest).write_bytes(raw)
    url='https://www.ebi.ac.uk/europepmc/webservices/rest/'+PMC+'/fullTextXML'
    (original/'pilot-report.json').write_text(json.dumps({'request_events':[{'url':url,'http_status':200,'sha256':digest}]}))
    (original/'acquisition-plan.json').write_text(json.dumps({'cohort':[{'doi':DOI,'pmcid':PMC}]}))
    report=h.replay_acquisition(original,tmp_path/'replay')
    assert report['fresh_network_requests']==0 and report['strict_qualified_records']==1
    assert not report['current_live_source_verified']
    (cache/digest).write_bytes(raw+b'changed')
    rejected=h.replay_acquisition(original,tmp_path/'corrupt')
    assert rejected['strict_qualified_records']==0
    assert rejected['failures'][0]['reason']=='cached source hash differs from retrieval event'


@pytest.mark.parametrize('value,reason,tier', [(1e-4,'DUPLICATE_CONDITION_IDENTITY','EXPLORATORY'),
                                             (2e-4,'CONTRADICTORY_CONDITION_IDENTITY','REJECTED')])
def test_duplicates_and_contradictions_are_never_counted_as_strict(value,reason,tier):
    import copy
    first=h.inspect_jats(jats(),DOI,PMC)['measurements'][0]
    second=copy.deepcopy(first);second['conductivity_S_cm']=value
    rows=h.qualify_duplicate_conditions([first,second])
    assert all(r['tier']==tier and reason in r['reasons'] for r in rows)
