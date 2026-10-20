"""Real attributed cell extracts and synthetic hostile-input tests; no raw XLSB."""
import hashlib
import json
from pathlib import Path

import pytest

from rhombus.literature import workbook as w

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT/'data/development/moesm5_74887_cells_20261020_v1.json'


def cells():
    return json.loads(FIXTURE.read_text())['sheets']['Fig 3a EIS']


def test_exact_source_coordinates_roles_and_sample_counts():
    rows = w.extract_eis_evidence(cells())
    assert len(rows)==666
    assert [sum(r['sample']==sample and r['series_role']=='tested' for r in rows)
            for sample in ('S-LLZO','SF-LLZO','Annealed SF-LLZO')]==[69,57,69]
    assert sum(r['series_role']=='Fitted' for r in rows)==471
    assert rows[0]['cells']==['A4','B4'] and rows[0]['source_values']==[0.50696,0.62301]
    assert all(r['conductivity_S_cm'] is None and r['geometry'] is None for r in rows)
    assert w.verify_eis_rows(rows,cells())


@pytest.mark.parametrize('key,value', [('A1','SF-LLZO'),('A3','Z’ (Ω)'),
                                     ('A3','Z’ (KΩ cm)'),('A2','replicate 1'),
                                     ('B4',None),('B4','NaN')])
def test_wrong_units_specimen_role_and_incomplete_pair_denied(key,value):
    raw=cells();raw[key]=value
    with pytest.raises(ValueError): w.extract_eis_evidence(raw)


def test_swapping_values_or_specimen_series_breaks_source_binding():
    for key in ['source_values','sample','unit','series_role']:
        rows=w.extract_eis_evidence(cells())
        other=next(i for i,r in enumerate(rows) if r['sample']=='SF-LLZO')
        rows[0][key],rows[other][key]=rows[other][key],rows[0][key]
        if key in ('unit','series_role'): rows[0][key]='invented'
        with pytest.raises(ValueError,match='keyed workbook cells'):w.verify_eis_rows(rows,cells())


@pytest.mark.parametrize('field,value', [('specimen_id','pellet-1'),
    ('geometry',{'thickness_cm':0.1,'area_cm2':1}),('resistance_component','TOTAL'),
    ('replicate_id','replicate-2'),('conductivity_S_cm',1.11e-3)])
def test_plausible_missing_joins_cannot_be_filled(field,value):
    row=w.extract_eis_evidence(cells())[0]
    assert w.assess_conductivity_join(row)['qualification']=='EXPLORATORY'
    row[field]=value
    assert w.assess_conductivity_join(row)['qualification']=='REJECTED'


def test_fitted_curves_are_not_experimental_repeats():
    rows=w.extract_eis_evidence(cells())
    fit=next(r for r in rows if r['series_role']=='Fitted')
    assert w.assess_conductivity_join(fit)['qualification']=='REJECTED'
    fit['series_role']='tested'
    with pytest.raises(ValueError):w.verify_eis_rows([fit],cells())


@pytest.mark.parametrize('raw', [b'\x01',b'\x01\x05ab',b'\x81'*5])
def test_truncated_binary_records_fail_closed(raw):
    with pytest.raises(ValueError):list(w._records(raw))


def test_formula_record_bytes_are_preserved_not_executed():
    payload=b'not-an-executable-formula'
    kind,offset,raw=next(w._records(bytes([9,len(payload)])+payload))
    assert (kind,offset,raw)==(9,0,payload)


def test_unreviewed_workbook_and_archive_rejected_before_parse(tmp_path,monkeypatch):
    with pytest.raises(ValueError,match='unreviewed'):w.inspect_workbook(b'fake workbook')
    monkeypatch.setattr(w.source,'authenticate_article',lambda raw:None)
    raw=(f'<article xmlns:xlink="http://www.w3.org/1999/xlink"><supplementary-material id="MOESM5"><media xlink:href="{w.FILENAME}"><caption>Source data</caption></media></supplementary-material></article>').encode()
    path=tmp_path/'fake.zip';path.write_bytes(b'fake')
    with pytest.raises(ValueError,match='archive size/hash'):w.verify_workbook_member(path,raw)
    with pytest.raises(ValueError,match='JATS membership'):w.verify_workbook_member(path,raw.replace(b'MOESM5_ESM.xlsb',b'MOESM1_ESM.pdf'))


def test_receipt_preserves_original_units_no_geometry_and_no_repeat_inflation():
    r=json.loads((ROOT/'data/development/moesm5_74887_qualification_20261020_v1.json').read_text())
    for file,digest in r['artifact_bindings'].items():
        assert hashlib.sha256((ROOT/file).read_bytes()).hexdigest()==digest
    assert r['ancestry']['sha256']==hashlib.sha256((ROOT/r['ancestry']['path']).read_bytes()).hexdigest()
    assert len(r['inspection']['sheets'])==26
    assert sum(s['nonempty_cells'] for s in r['inspection']['sheets'])==1699094
    assert all(not s['cell_formula_records'] for s in r['inspection']['sheets'])
    assert len(r['inspection']['defined_names'])==6
    assert len(r['measured_eis_rows'])==195
    assert all(x['replicate_id'] is None and x['conductivity_S_cm'] is None
               and x['specimen_id'] is None for x in r['measured_eis_rows'])
    for row in r['measured_eis_rows']:
        assert row['unit']=='KΩ'
        assert row['nominal_composition']==r['sample_contexts'][row['sample']]['nominal_composition']
        expected=next(x for x in w.extract_eis_evidence(cells())
                      if x['sample']==row['sample'] and x['cells']==row['cells'] and x['series_role']=='tested')
        assert all(row[k]==v for k,v in expected.items())
    q=r['qualification']
    assert q['verdict']=='INCONCLUSIVE' and q['new_strict_qualified_doi_groups']==0
    assert q['new_strict_original_manufacturing_comparisons']==0
    assert not q['checkpoint_0195_consumed'] and not q['future_source_heldout_admissible']


def test_arrhenius_diagnostics_do_not_repair_units_or_become_total_comparisons():
    r=json.loads((ROOT/'data/development/moesm5_74887_qualification_20261020_v1.json').read_text())
    for row in r['arrhenius_diagnostics']:
        assert row['conductivity_S_cm'] is None
        assert row['source_units'][1]=='ln[σT (mSK cm-1)]'
        assert row['qualification']=='EXPLORATORY'
        assert row['conditional_back_transform']['status']=='DIAGNOSTIC_NOT_ADMITTED_MEASUREMENT'
    sf=r['sample_contexts']['SF-LLZO']
    assert sf['fixed_peak_temperature_C'] is None and sf['fixed_hold_min'] is None
    # A process displacement or the 1330-valued pressure series is not geometry/T.
    sheet=next(x for x in r['inspection']['sheets'] if x['sheet']=='FigS3c SPS sintering')
    assert sheet['headers']['B2']=='pressure (Pa)'
    assert sheet['headers']['B3']==1330
