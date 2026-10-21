"""Cell/provenance tests: source facts do not authorize missing-context filling."""
import copy
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from rhombus.literature import microwave as m

ROOT = Path(__file__).resolve().parents[1]
EXCERPT = ROOT/'data/development/microwave_table1_fact_excerpt_20261021_v1.xml'
REPORT = ROOT/'data/development/microwave_36206_qualification_20261021_v1.json'


def tree(): return ET.fromstring(EXCERPT.read_bytes())
def report(): return json.loads(REPORT.read_text())


def test_original_factual_cells_units_and_metal_ratios():
    rows = m.parse_table1(tree())
    assert [r['conductivity_S_cm'] for r in rows] == [1.91e-4, 3.84e-4, 1.04e-3]
    assert [r['original_cell'] for r in rows] == ['R2C3', 'R3C3', 'R4C3']
    assert [r['source_metal_ratios']['Ga'] for r in rows] == [.2, .3, .4]
    assert all('O' not in r['source_metal_ratios'] for r in rows)
    assert rows == [{k: r[k] for k in rows[0]} for r in report()['measurements'][:3]]


@pytest.mark.parametrize('change', ['values', 'units', 'multiplier', 'Ga_basis', 'row_mapping',
                                   'duplicate_row', 'duplicate_table', 'uncertainty', 'bulk', 'spanning'])
def test_table_mapping_and_unit_adversaries(change):
    root = tree(); table = root.find('.//table-wrap'); rows = table.findall('.//tr')
    if change == 'values': rows[1][2].text = '9.1e-4'
    if change == 'units': rows[0][2].text = 'Li-ion conductivity (mS/cm)'
    if change == 'multiplier': rows[1][2].find('sup').text = '−3'
    if change == 'Ga_basis': rows[3][0].text = '5.8:3:2:0.004'
    if change == 'row_mapping': rows[1][0].text, rows[2][0].text = rows[2][0].text, rows[1][0].text
    if change == 'duplicate_row': table.find('.//tbody').append(copy.deepcopy(rows[1]))
    if change == 'duplicate_table': root.find('body').append(copy.deepcopy(table))
    if change == 'uncertainty': rows[1][2].text = '1.91(1) × 10'
    if change == 'bulk': table.find('caption/p').text = 'Bulk conductivity of samples'
    if change == 'spanning': rows[1][0].set('rowspan', '2')
    with pytest.raises(ValueError): m.parse_table1(root)


def unit_source(monkeypatch):
    """Synthetic context fixture; never a stand-in for the original response hash."""
    root = tree(); root.set('article-type', 'research-article')
    front = ET.SubElement(root, 'front'); meta = ET.SubElement(front, 'article-meta')
    ET.SubElement(meta, 'article-id', {'pub-id-type': 'doi'}).text = m.DOI
    ET.SubElement(meta, 'article-id', {'pub-id-type': 'pmcid'}).text = m.PMC
    ET.SubElement(ET.SubElement(meta, 'title-group'), 'article-title').text = m.TITLE
    group = ET.SubElement(meta, 'contrib-group')
    for full in m.AUTHORS:
        given, surname = full.rsplit(' ', 1)
        name = ET.SubElement(ET.SubElement(group, 'contrib', {'contrib-type': 'author'}), 'name')
        ET.SubElement(name, 'given-names').text = given; ET.SubElement(name, 'surname').text = surname
    permission = ET.SubElement(meta, 'permissions')
    ET.SubElement(ET.SubElement(permission, 'license'), 'license-p').text = 'http://creativecommons.org/licenses/by-nc/4.0/'
    body = root.find('body')
    clauses = {'p0065': 'Synthetic MW method fixture', 'p0070': 'Synthetic SG method fixture',
               'p0080': 'Synthetic EIS range25–80C fixture', 'p0100': 'MW values measured at 25 °C',
               'p0105': 'Synthetic table crossreference fixture',
               'p0130': 'The total resistances differ; SG conductivity is only 1.13 × 10−4 S cm−1.'}
    for key, value in clauses.items(): ET.SubElement(body, 'p', id=key).text = value
    monkeypatch.setattr(m, 'CONTEXT_HASHES', {k: hashlib.sha256(v.encode()).hexdigest() for k, v in clauses.items()})
    monkeypatch.setattr(m, 'JATS_SHA256', hashlib.sha256(ET.tostring(root)).hexdigest())
    return root


def test_registry_dispatch_under_explicit_synthetic_source_hash(monkeypatch):
    from rhombus.literature.harvest import extract_registered_measurements
    root = unit_source(monkeypatch)
    rows = extract_registered_measurements(ET.tostring(root), m.DOI, m.PMC)
    assert len(rows) == 4 and all(r['tier'] == 'EXPLORATORY' for r in rows)
    assert rows[-1]['measurement_temperature_C'] is None
    assert rows[-1]['conductivity_S_cm'] == 1.13e-4
    assert all(r['nominal_formula'] is None and r['conductivity_uncertainty_S_cm'] is None for r in rows)


@pytest.mark.parametrize('change', ['title', 'doi', 'pmc', 'author', 'license', 'MW_method', 'SG_method', 'EIS_temperature'])
def test_metadata_or_context_change_cannot_be_hidden_by_a_new_raw_hash(monkeypatch, change):
    root = unit_source(monkeypatch)
    if change == 'title': root.find('.//article-title').text = 'Wrong original'
    if change == 'doi': root.find('.//article-id[@pub-id-type="doi"]').text = '10.1234/other'
    if change == 'pmc': root.find('.//article-id[@pub-id-type="pmcid"]').text = 'PMC1'
    if change == 'author': root.find('.//given-names').text = 'Other'
    if change == 'license': root.find('.//license-p').text = 'http://creativecommons.org/licenses/by/4.0/'
    if change == 'MW_method': root.find('.//p[@id="p0065"]').text = 'Changed final temperature'
    if change == 'SG_method': root.find('.//p[@id="p0070"]').text = 'Changed precursor'
    if change == 'EIS_temperature': root.find('.//p[@id="p0100"]').text = 'MW at30C'
    raw = ET.tostring(root); monkeypatch.setattr(m, 'JATS_SHA256', hashlib.sha256(raw).hexdigest())
    with pytest.raises(ValueError): m.extract_microwave_comparison(raw)


@pytest.mark.parametrize('change', ['SG_temperature', 'MW_temperature', 'uncertainty', 'formula', 'observable', 'units', 'duplicate'])
def test_no_route_policy_on_unqualified_context_or_guessed_inputs(change):
    rows = report()['measurements']
    if change == 'SG_temperature': rows[-1]['measurement_temperature_C'] = 25
    if change == 'MW_temperature': rows[0]['measurement_temperature_C'] = 30
    if change == 'uncertainty': rows[0]['conductivity_uncertainty_S_cm'] = .00001
    if change == 'formula': rows[0]['nominal_formula'] = 'Li6.4Ga0.2La3Zr2O12'
    if change == 'observable': rows[0]['observable_type'] = 'BULK'
    if change == 'units': rows[0]['source_unit'] = 'mS/cm'
    if change == 'duplicate': rows[1] = copy.deepcopy(rows[0])
    with pytest.raises(ValueError): m.summarize_route_comparability(rows)


def test_excerpt_and_challenge_cannot_authenticate_originals_or_supplements(monkeypatch):
    with pytest.raises(ValueError, match='identity or bytes'): m.extract_microwave_comparison(EXCERPT.read_bytes())
    root = unit_source(monkeypatch)
    with pytest.raises(ValueError, match='archive/link'): m.review_supplement(b'partial ZIP', ET.tostring(root))


def test_supplement_expansion_budget_checked_before_crc_or_xml(monkeypatch):
    root = unit_source(monkeypatch)
    media = ET.SubElement(ET.SubElement(root.find('body'), 'supplementary-material'), 'media')
    media.set('{http://www.w3.org/1999/xlink}href', 'mmc1.docx')
    raw = ET.tostring(root); monkeypatch.setattr(m, 'JATS_SHA256', hashlib.sha256(raw).hexdigest())
    archive = b'expansion-budget-unit-fixture'
    monkeypatch.setattr(m, 'ARCHIVE_SHA256', hashlib.sha256(archive).hexdigest())
    class Oversized:
        filename = 'mmc1.docx'; file_size = 20_000_001
    class FakeZip:
        def infolist(self): return [Oversized()]
        def testzip(self): raise AssertionError('oversized member expanded')
    monkeypatch.setattr(m.zipfile, 'ZipFile', lambda *args: FakeZip())
    with pytest.raises(ValueError, match='expansion budget'): m.review_supplement(archive, raw)


def test_process_histories_keep_precursors_and_measurement_equilibration_separate():
    r = report(); a, b = r['manufacturing_histories']['MW'], r['manufacturing_histories']['SG']
    assert a['Li_precursor'] == 'LiOH' and b['Li_precursor'] == 'LiNO3'
    assert a['steps'][1] == {'stage': 'sealed Teflon microwave solvothermal', 'temperature_C': 250, 'time_min': 10}
    assert b['steps'][1] == {'stage': 'gel/dry', 'temperature_C': 100, 'time_min': 720}
    for h in (a, b):
        assert h['percentage_denominator'] is None
        assert h['final_sinter']['temperature_C'] == 1150 and h['final_sinter']['time_min'] == 600
        assert h['final_sinter']['atmosphere'] is None and h['calcination']['atmosphere'] == 'air'
        assert h['pressing']['pressure_psi'] == 3000
    assert r['measurement_context']['pre_measurement_equilibration_hold_min'] == 60
    assert not r['measurement_context']['approximate_geometry_used_to_recalculate_sigma']
    assert all(h['actual_individual_EIS_pellet_geometry'] is None for h in (a, b))


def test_receipt_bindings_and_negative_scientific_findings():
    r = report()
    assert hashlib.sha256(EXCERPT.read_bytes()).hexdigest() == r['source']['factual_excerpt_sha256']
    assert r['source']['JATS_sha256'] == m.JATS_SHA256
    assert r['source']['source_license'] == 'CC BY-NC 4.0'
    assert r['qualification'] == m.summarize_route_comparability(r['measurements'])
    si = r['supplement']
    assert si['docx_sha256'] == m.DOCX_SHA256 and si['archive_sha256'] == m.ARCHIVE_SHA256
    assert si['main_prose_after_cycling_Rbulk_ohm'] == 46
    assert si['SI_TableS2_after_cycling_Rbulk_ohm'] == 43 and not si['conflict_resolved']
    assert not si['component_resistances_admitted_as_conductivity']
    assert r['visual_review']['reviewed_from_actual_archive_bytes']
    assert r['rejected_cached_laser_lead']['actual_Nyquist_measurement_temperature_C'] == 30
    assert r['coverage']['six_MW_other_conductivities'] is None
    assert r['qualification']['route_policy_regret'] is r['qualification']['process_effect_ratio'] is None
    assert r['source_history']['new_bibliographic_DOI'] is False
    assert not r['claim_boundaries']['checkpoint_0195_consumed']
    assert not r['claim_boundaries']['official_TEST_121_accessed']
