"""Reviewed Heliyon MW/sol-gel evidence; unresolved fields never become labels."""
from __future__ import annotations

import hashlib
import io
import re
import xml.etree.ElementTree as ET
import zipfile

DOI = '10.1016/j.heliyon.2024.e36206'
PMC = 'PMC11382057'
TITLE = 'Microwave-assisted solvothermal synthesis of nanostructured Ga-Doped Li7La3Zr2O12 solid electrolyte with enhanced densification and Li-ion conductivity'
JATS_SHA256 = 'cc61d1f66861f32280a86c5120cac2c8504610ff4d279ad14cb0bf43b4efbab4'
ARCHIVE_SHA256 = '891e92618f330b35370296aa7b9901dc62ef8e91c594e0e34492bd5fd234757e'
DOCX_SHA256 = 'ca417a6b2bef57b8d887e4cade9cbb96b45e3ce5eca356d1801d5ac80a14ee48'
FIGURE6_SHA256 = '2407b43a80df1a42c68f90006c1030586e5b5d4108edfb151e6dc07ada8599e4'
CONTEXT_HASHES = {
    'p0065': '4bfb700f24c951f054d71114e0cf154b476845bb2be72065467fccd61922fb32',
    'p0070': 'f3eeeee23a85fcb9b95a9df4f635095f09ea82a28bd24f1e4f75bc4ffc9a447a',
    'p0080': 'd373d82af66f4086ca2d9201b96548d0930f73a892f48d3a173e8d867361700f',
    'p0100': 'b844b59883a26b4ef00c0a03e34268214e92e0d20c3bd0d00b97250b76f2cd08',
    'p0105': 'f3af0ccdbbb140fd840c36afb314cad28dbf868366b448fb7a30d477b39262f9',
    'p0130': '83f26599c2cb5a697121d33b6bd4384a5aa2c88ea30ee567db3fa3982978fdca',
}
AUTHORS = ('Seong-Jun Jo', 'Young Gyu Jeon', 'Dong-Kyu Kim', 'Sang Yeop Hwang',
           'Byeong-Heon Lee', 'Chea Yun Kang', 'Seung-Hwan Lee', 'Sung-Hwan Lim',
           'R. Vasant Kumar', 'Yu-Jin Han', 'Kwang-Bum Kim', 'Hyun-Kyung Kim')


def text(element):
    if element is None: raise ValueError('missing original text element')
    return ' '.join(''.join(element.itertext()).split())


def authenticate_source(raw, doi=DOI, pmcid=PMC):
    if ((doi, pmcid) != (DOI, PMC) or not isinstance(raw, bytes) or not 0 < len(raw) <= 8_000_000
            or hashlib.sha256(raw).hexdigest() != JATS_SHA256):
        raise ValueError('unreviewed original MW source identity or bytes')
    from .harvest import inspect_jats
    inspect_jats(raw, doi, pmcid)
    root = ET.fromstring(raw)
    names = tuple((a.findtext('given-names') or '')+' '+(a.findtext('surname') or '')
                  for a in root.findall('.//front//contrib[@contrib-type="author"]/name'))
    permissions = root.find('.//front//permissions')
    if (text(root.find('.//front//article-title')) != TITLE or names != AUTHORS
            or permissions is None or 'creativecommons.org/licenses/by-nc/4.0/' not in text(permissions)):
        raise ValueError('original authors or document-specific CC BY-NC 4.0 changed')
    return root


def parse_table1(root):
    """Key actual cells by author metal ratio; do not manufacture an O count."""
    from .harvest import _source_number
    matches = root.findall('.//table-wrap[@id="tbl1"]')
    if len(matches) != 1: raise ValueError('missing or duplicate original Table1')
    table = matches[0]
    if any(x.get('rowspan', '1') != '1' or x.get('colspan', '1') != '1' for x in table.iter()):
        raise ValueError('spanning source table requires another adapter')
    if text(table.find('label')) != 'Table 1' or 'total conductivity' not in text(table.find('caption')):
        raise ValueError('original TOTAL caption changed')
    rows = [[text(c) for c in tr if c.tag in ('th', 'td')] for tr in table.findall('.//tr')]
    if (len(rows) != 4 or any(len(r) != 4 for r in rows) or rows[0] != [
            'Li:La:Zr:Ga', 'Lattice parameter (Å)', 'Li-ion conductivity (S cm−1)', 'Activation energy (eV)']):
        raise ValueError('source Table1 units/columns/population changed')
    expected = {'6.4:3:2:0.2': 1.91e-4, '6.1:3:2:0.3': 3.84e-4, '5.8:3:2:0.4': 1.04e-3}
    found = {}
    for number, row in enumerate(rows[1:], 2):
        ratio = row[0]
        if ratio not in expected or ratio in found: raise ValueError('metal ratio identity changed')
        value = _source_number(row[2])
        if value != expected[ratio]: raise ValueError('keyed original conductivity cell changed')
        found[ratio] = {'source_metal_ratio_literal': ratio,
                        'source_metal_ratios': dict(zip(('Li', 'La', 'Zr', 'Ga'), map(float, ratio.split(':')), strict=True)),
                        'source_cell': row[2], 'original_cell': f'R{number}C3',
                        'conductivity_S_cm': value, 'source_dopant_label': ratio.split(':')[-1]}
    return list(found.values())


def extract_microwave_comparison(raw, doi=DOI, pmcid=PMC):
    root = authenticate_source(raw, doi, pmcid)
    contexts = {}
    for identifier, digest in CONTEXT_HASHES.items():
        matches = root.findall(f'.//body//p[@id="{identifier}"]')
        if len(matches) != 1 or hashlib.sha256(text(matches[0]).encode()).hexdigest() != digest:
            raise ValueError('manufacturing/measurement source context changed')
        contexts[identifier] = text(matches[0])
    # p0100 explicitly measures MW0.2–0.4 at25C. p0130 supplies the SG
    # point but NOT its exact temperature; the methods'25–80C range cannot fill it.
    if 'at 25 °C' not in contexts['p0100'] or 'total resistances' not in contexts['p0130']:
        raise ValueError('TOTAL or exact-temperature association missing')
    rows = parse_table1(root)
    match = re.search(r'only (1\.13\s*×\s*10−4) S cm−1', contexts['p0130'])
    if match is None: raise ValueError('SG source point/units changed')
    from .harvest import _source_number
    rows.append({'source_metal_ratio_literal': None, 'source_metal_ratios': None,
                 'source_cell': match[1], 'original_cell': None,
                 'conductivity_S_cm': _source_number(match[1]), 'source_dopant_label': '0.4'})
    for i, row in enumerate(rows):
        sg = i == 3
        row.update(doi=DOI, pmcid=PMC, source_sha256=JATS_SHA256,
                   sample_code=('SG' if sg else 'MW')+' '+row['source_dopant_label']+' Ga–LLZO',
                   sample_code_basis='AUTHOR_MATERIAL_CONDITION_NOT_INDEPENDENT_PELLET_ID',
                   nominal_formula=None, source_host_formula='Li7La3Zr2O12',
                   oxygen_stoichiometry_per_condition=None,
                   formula_interpretation='AUTHOR_METAL_RATIOS_AND_HOST_ONLY; NO_INFERRED_COMPLETE_FORMULA',
                   manufacturing_route='CONVENTIONAL_SINTERING',
                   powder_synthesis_route='SOL_GEL' if sg else 'MICROWAVE_ASSISTED_SOLVOTHERMAL',
                   process_temperature_C=1150, holding_time_min=600,
                   calcination={'temperature_C': 700, 'time_min': 300, 'atmosphere': 'air'},
                   precursor_excess={'reported_percent': 20, 'precursor': 'LiNO3' if sg else 'LiOH',
                                     'author_unit': '%', 'denominator': None, 'normalized_elemental_Li_fraction': None},
                   cold_press_pressure_psi=3000, pressure_MPa=None, atmosphere=None,
                   heating_rate_K_min=None, cooling_rate_K_min=None,
                   measurement_temperature_C=None if sg else 25,
                   measurement_methods_temperature_range_C=[25, 80],
                   measurement_temperature_evidence='p0130: unspecified' if sg else 'p0100: explicit MW0.2–0.4 at25C',
                   observable_type='TOTAL', source_unit='S/cm', conductivity_uncertainty_S_cm=None,
                   original_table_id=None if sg else 'tbl1',
                   original_prose_id='p0130' if sg else 'p0105',
                   manufacturing_history_ref='SG' if sg else 'MW',
                   preparation_context_id='p0070' if sg else 'p0065',
                   preparation_context_sha256=CONTEXT_HASHES['p0070' if sg else 'p0065'],
                   physical_specimen_id=None, independent_replicate_count=None,
                   tier='EXPLORATORY',
                   reasons=['UNCERTAINTY_UNSPECIFIED_OR_INVALID', 'ATMOSPHERE_UNSPECIFIED',
                            'COMPLETE_NOMINAL_FORMULA_NOT_EXPLICIT_IN_CONDITION_ROW']+
                           (['SG_POINT_EXACT_MEASUREMENT_TEMPERATURE_UNSPECIFIED'] if sg else []),
                   eligible_for_new_heldout_evaluation=False,
                   source_license='CC BY-NC 4.0; raw and extended source text kept local only')
    return rows


def review_supplement(archive, raw_jats):
    """Offline exact-member review; never execute Word, macros or external links."""
    root = authenticate_source(raw_jats)
    links = {x.get('{http://www.w3.org/1999/xlink}href') for x in root.findall('.//supplementary-material/media')}
    if (links != {'mmc1.docx'} or not isinstance(archive, bytes) or len(archive) > 8_000_000
            or hashlib.sha256(archive).hexdigest() != ARCHIVE_SHA256):
        raise ValueError('unreviewed original supplementary archive/link')
    def checked_zip(raw, members, expanded):
        z = zipfile.ZipFile(io.BytesIO(raw))
        infos = z.infolist()
        if (len(infos) > members or len({i.filename for i in infos}) != len(infos)
                or sum(i.file_size for i in infos) > expanded or z.testzip() is not None):
            raise ValueError('supplement ZIP integrity or expansion budget')
        return z
    z = checked_zip(archive, 30, 20_000_000)
    docx, figure = z.read('mmc1.docx'), z.read('gr6.jpg')
    if hashlib.sha256(docx).hexdigest() != DOCX_SHA256 or hashlib.sha256(figure).hexdigest() != FIGURE6_SHA256:
        raise ValueError('reviewed SI or Figure6 member changed')
    document = checked_zip(docx, 100, 40_000_000).read('word/document.xml')
    if b'<!DOCTYPE' in document.upper() or b'<!ENTITY' in document.upper(): raise ValueError('unsafe DOCX XML')
    word = ET.fromstring(document); ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    content = '\n'.join(''.join(p.itertext()) for p in word.findall('.//w:p', ns))
    title = text(root.find('.//article-title'))
    if title not in content: raise ValueError('supplement article title mismatch')
    tables = [[[text(c) for c in row.findall('w:tc', ns)] for row in t.findall('w:tr', ns)]
              for t in word.findall('.//w:tbl', ns)]
    if len(tables) != 2 or tables[1][1] != ['Rbulk Ohm)', '76', '43']:
        raise ValueError('original TableS2 component evidence changed')
    prose = [p for p in root.findall('.//body//p') if re.search(r'Rb decreased from 76 to 46', text(p))]
    if len(prose) != 1: raise ValueError('original cycling-component prose changed')
    before, after = map(int, re.search(r'Rb decreased from (\d+) to (\d+)', text(prose[0])).groups())
    return {'archive_sha256': ARCHIVE_SHA256, 'docx_sha256': DOCX_SHA256,
            'figure6_sha256': FIGURE6_SHA256, 'document_xml_sha256': hashlib.sha256(document).hexdigest(),
            'SI_reuse_license': None, 'source_tables': tables,
            'SG_exact25C_attested': False, 'conductivity_uncertainty_defined': False,
            'main_prose_after_cycling_Rbulk_ohm': after,
            'main_component_prose_id': prose[0].get('id'),
            'main_component_prose_sha256': hashlib.sha256(text(prose[0]).encode()).hexdigest(),
            'SI_TableS2_after_cycling_Rbulk_ohm': int(tables[1][1][2]),
            'conflict_resolved': False, 'component_resistances_admitted_as_conductivity': False}


def summarize_route_comparability(rows):
    if (len(rows) != 4 or len({r['sample_code'] for r in rows}) != 4
            or {r['sample_code'] for r in rows} != {'MW 0.2 Ga–LLZO', 'MW 0.3 Ga–LLZO', 'MW 0.4 Ga–LLZO', 'SG 0.4 Ga–LLZO'}
            or any(r['source_sha256'] != JATS_SHA256 or r['doi'] != DOI for r in rows)):
        raise ValueError('source population/binding changed')
    sg = next(r for r in rows if r['sample_code'] == 'SG 0.4 Ga–LLZO')
    if (sg['measurement_temperature_C'] is not None
            or sg['powder_synthesis_route'] != 'SOL_GEL'
            or any(r['conductivity_uncertainty_S_cm'] is not None or r['nominal_formula'] is not None
                   or r['observable_type'] != 'TOTAL' or r['source_unit'] != 'S/cm' for r in rows)
            or any(r['measurement_temperature_C'] != 25 for r in rows if r is not sg)):
        raise ValueError('unsupported temperature or uncertainty promotion')
    return {'reported_point_rows': 4, 'explicit25C_TOTAL_table_rows': 3,
            'complete_reported_condition_formulas': 0,
            'same_temperature_MW_vs_SG_pair_qualified': False,
            'process_effect_ratio': None, 'route_policy_regret': None,
            'frozen_numeric_feature_vectors_constructed': False,
            'new_model_fitted': False, 'new_strict_DOI_groups': 0,
            'new_strict_manufacturing_comparisons': 0,
            'reason': 'Do not infer SG temperature, full condition formula or numeric uncertainty. No qualified common-condition route comparison.'}
