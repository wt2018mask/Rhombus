"""Source-bound 2021 Al-LLZO Table 4; retrospective rows, no model fitting."""
from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from decimal import Decimal

DOI = '10.3390/ma14226809'
PMC = 'PMC8620275'
JATS_SHA256 = '0da4f7639daec04bf41c0a96e952a7ec8846eb5034ae531f60694e415d6350c3'
TABLE_ID = 'materials-14-06809-t004'
ROUTES = ('SSR','SASSR','CP','SD')
AUTHOR_NAMES = ('Markus Mann','Michael Küpers','Grit Häuschen','Martin Finsterbusch',
                'Dina Fattakhova-Rohlfing','Olivier Guillon')
METHOD_HASHES = {
 'sec1-materials-14-06809':'b7d1c4156dedea40ba1367b857ab204c190469bba805158c2d812f7172725184',
 'sec2dot1dot1-materials-14-06809':'8a4726fc3c5d8a6a9b8b64e1fa0e24250e18a965afd5d77409bcd4a583628310',
 'sec2dot1dot2-materials-14-06809':'4753929ce24943ca46009846dd215061ec172d010137c59e30125016615f0427',
 'sec2dot1dot3-materials-14-06809':'5a7b77a52fa3122802a7be32b38e5cfae7bfbffd75caf7eb9ee14a78bb19c1ef',
 'sec2dot1dot4-materials-14-06809':'2bc39adebe50b29cbc720194e21b3357231f4546a8206f01b11be05b1405e2fb',
 'sec2dot1dot5-materials-14-06809':'9a49cb1fca0f3bd72a9f193ea858981a927e437cee35506ee8ac72615ae9ea7e',
 'sec2dot2-materials-14-06809':'1bab37eecb66b95c286904e8adb39d491bf515c12ad879a51804d420b22675ae',
}


def text(element):
    return ' '.join(''.join(element.itertext()).split())


def source_identity(root):
    """Keep author identity, laboratory and citation evidence separate."""
    front = root.find('front')
    if front is None: raise ValueError('missing source identity')
    authors = []
    affs = {a.get('id'):text(a) for a in front.findall('.//aff')}
    for group in front.findall('.//contrib-group'):
        if group.get('content-type') not in (None,'author'): continue
        for person in group.findall('contrib'):
            name = person.find('name')
            if name is None or person.get('contrib-type') not in (None,'author'): continue
            authors.append({'name':(name.findtext('given-names') or '')+' '+(name.findtext('surname') or ''),
                            'orcid':person.findtext('contrib-id[@contrib-id-type="orcid"]'),
                            'affiliation_ids':[x.get('rid') for x in person.findall('xref[@ref-type="aff"]')]})
    dois = [text(d).lower() for d in front.findall('.//article-id[@pub-id-type="doi"]')]
    citations = []
    for ref in root.findall('.//ref'):
        reference_dois = [text(x) for x in ref.findall('.//pub-id[@pub-id-type="doi"]')]
        reference_dois += [x.get('{http://www.w3.org/1999/xlink}href') or text(x)
                           for x in ref.findall('.//ext-link[@ext-link-type="doi"]')]
        reference_dois = [re.sub(r'^https?://(?:dx\.)?doi\.org/','',x.strip().lower())
                          for x in reference_dois]
        citations.append({'id':ref.get('id'),'text':text(ref),
                          'dois':sorted(set(reference_dois + re.findall(r'10\.\d{4,9}/[^\s<>]+',text(ref))))})
    return {'doi':dois[0] if len(set(dois))==1 else None,'authors':authors,
            'affiliations':affs,'citations':citations}


def authenticate_tree(root):
    """Specific rights and front identity; never use citation DOIs as identity."""
    ident = source_identity(root)
    front = root.find('front')
    pmcs = {text(x).removeprefix('PMC') for x in front.findall('.//article-id')
            if x.get('pub-id-type') in ('pmc','pmcid')}
    rights = front.findall('.//permissions/license')
    ccby = any(e.get('{http://www.w3.org/1999/xlink}href') ==
               'https://creativecommons.org/licenses/by/4.0/' for p in rights for e in p.iter())
    if (ident['doi'] != DOI or pmcs != {PMC[3:]} or root.get('article-type')!='research-article'
            or tuple(a['name'] for a in ident['authors']) != AUTHOR_NAMES or not ccby):
        raise ValueError('original DOI/PMC/authors/document-specific CC BY 4.0 not authenticated')
    return ident


def _table(root, identifier):
    matches = root.findall(f'.//table-wrap[@id="{identifier}"]')
    if len(matches)!=1: raise ValueError('missing or duplicate original table')
    element = matches[0]
    if any(x.get('rowspan','1')!='1' or x.get('colspan','1')!='1' for x in element.iter()):
        raise ValueError('ambiguous spanning source cells')
    return [[text(c) for c in row if c.tag in ('td','th')]
            for row in element.findall('.//tr')]


def parse_table4_tree(root):
    """Associate columns/observable first, then compare independently keyed cells.

    Used for derived-excerpt regression; live extraction additionally pins raw
    JATS and invokes the generic identity/type/rights intake checks.
    """
    from .harvest import extract_explicit_table_measurements
    authenticate_tree(root)
    methods = {}
    for sid, digest in METHOD_HASHES.items():
        matches = root.findall(f'.//sec[@id="{sid}"]')
        if len(matches)!=1: raise ValueError('missing/ambiguous manufacturing section')
        paragraphs = [text(p) for p in matches[0].findall('p')]
        if hashlib.sha256('\n'.join(paragraphs).encode()).hexdigest()!=digest:
            raise ValueError('manufacturing/measurement/composition context changed')
        methods[sid] = {'paragraphs':paragraphs,'sha256':digest}
    table = _table(root,TABLE_ID)
    if (len(table)!=9 or any(len(r)!=5 for r in table) or table[0][0]!='Parameter'
            or set(table[0][1:])!=set(ROUTES) or len(set(table[0]))!=5):
        raise ValueError('original Table4 route/row population changed')
    total_label = 'σtotal (10−4 S/cm)'
    positions = [i for i,r in enumerate(table) if r[0]==total_label]
    if len(positions)!=1: raise ValueError('explicit TOTAL units/multiplier missing')
    position = positions[0]
    # No positional substitution with the bulk/GB rows.
    if table[position-1][0]!='CGB (10−8 F)' or table[position+1][0]!='σBulk (10−4 S/cm)':
        raise ValueError('TOTAL/BULK/GB source row structure changed')
    expected = {'SSR':'3.14(7)','SASSR':'2.64(3)','CP':'2.02(2)','SD':'3.28(3)'}
    corroboration = _table(root,'materials-14-06809-t005')
    if len(corroboration)!=5 or any(len(r)!=6 for r in corroboration):
        raise ValueError('Table5 summary population changed')
    summary = {r[0]:r for r in corroboration[1:]}
    if len(summary)!=4 or set(summary)!=set(ROUTES): raise ValueError('duplicate summary route')
    result = []
    for route in ROUTES:
        column = table[0].index(route)
        literal = table[position][column]
        match = re.fullmatch(r'(\d+\.\d+)\((\d+)\)',literal)
        if match is None or literal!=expected[route] or summary[route][5]!=literal:
            raise ValueError('keyed original TOTAL cell/duplicate summary differs')
        value = float(Decimal(match[1])*Decimal('1e-4'))
        # Do not fill the generic uncertainty field from undefined parentheses.
        headers = ['Sample','nominal formula','route','sintering temperature (°C)',
                   'holding time (h)','measurement temperature (°C)',
                   'total ionic conductivity (S/cm)','atmosphere']
        derived = [route,'Li6.4Al0.2La3Zr2O12','conventional sintering','1200','30','25',str(value),'air']
        row, = extract_explicit_table_measurements([headers,derived], 'Source-bound original Table4',
            {'doi':DOI,'pmcid':PMC,'source_sha256':JATS_SHA256})
        row.update(table_id=TABLE_ID,table_label='Table 4',row_index=position,
                   column_index=column,original_cell=f'R{position+1}C{column+1}',
                   source_row_label=total_label,source_column_label=route,
                   source_cell=literal,source_unit='10^-4 S/cm',powder_synthesis_route=route,
                   parenthetical_digits=match[2],parenthetical_statistical_meaning='UNKNOWN',
                   parenthetical_numeric_uncertainty_S_cm=None,
                   uncertainty_scale_interpretation_verified=False,
                   method_evidence=methods,relative_sintered_density_percent=float(summary[route][4]),
                   calcined_powder_phase_purity_percent=float(summary[route][1]),
                   final_pellet_exact_composition=None,individual_pellet_id=None,
                   table5_is_duplicate_of_table4=True,original_comparison_id=DOI+'#FOUR_ROUTE_COMPARISON',
                   previously_public_evaluation_labels=True)
        row['reasons'].append('PARENTHETICAL_UNCERTAINTY_MEANING_AND_SCALE_UNATTESTED')
        result.append(row)
    return result


def extract_route_comparison(raw, doi=DOI, pmcid=PMC):
    from .harvest import inspect_jats
    if (doi,pmcid)!=(DOI,PMC) or hashlib.sha256(raw).hexdigest()!=JATS_SHA256:
        raise ValueError('unreviewed original source identity or raw bytes')
    inspect_jats(raw,doi,pmcid)
    return parse_table4_tree(ET.fromstring(raw))


def audit_source_dependency(first, second):
    """Shared bibliographic authors/lab are not merged specimen identities."""
    def fzj(ident, author):
        return any('Forschungszentrum Jülich' in ident['affiliations'].get(i,'')
                   for i in author['affiliation_ids'])
    shared = []
    for a in first['authors']:
        for b in second['authors']:
            if a['name']!=b['name'] or not fzj(first,a) or not fzj(second,b): continue
            if a.get('orcid') and b.get('orcid') and a['orcid']!=b['orcid']: continue
            shared.append({'name':a['name'],'identity_evidence':'EXACT_FULL_NAME_AND_SHARED_FZJ_AFFILIATION',
                           'first_affiliation_ids':a['affiliation_ids'],
                           'second_affiliation_ids':b['affiliation_ids'],
                           'mutual_ORCID_match':bool(a.get('orcid') and a['orcid']==b.get('orcid'))})
    edges = []
    for a,b in [(first,second),(second,first)]:
        for ref in a['citations']:
            if b['doi'] in ref['dois']:
                edges.append({'from':a['doi'],'to':b['doi'],'type':'DECLARED_DOI_CITATION',
                              'reference':ref,'bibliographic_identity_requires_crosscheck':True})
    return {'DOIs':[first['doi'],second['doi']],'shared_authors':shared,
            'explicit_citation_edges':edges,'laboratory_independence':'NOT_INDEPENDENT_FZJ_LAB_CONTEXT' if shared else 'UNKNOWN',
            'source_originality':'DISTINCT_ARTICLE_IDENTITIES_EXPERIMENTAL_ORIGINALITY_SEPARATE',
            'experimental_independence':'UNKNOWN','specimen_overlap':'UNKNOWN',
            'batch_overlap':'UNKNOWN','cross_paper_dataset_reuse':'NOT_ESTABLISHED',
            'experimental_measurements_merged_due_to_authors':False,
            'blindness':'NOT_BLIND_PUBLIC_AND_EXPOSED',
            'graph_scope':'TWO_AUTHENTICATED_SOURCES; absence of an edge is not proof of independence'}


def summarize_decision_information(rows):
    if len(rows)!=4 or {r['powder_synthesis_route'] for r in rows}!=set(ROUTES):
        raise ValueError('one unique original row per route required')
    if len({(r['doi'],r['original_cell']) for r in rows})!=4:
        raise ValueError('duplicate original measurement')
    expected = dict(zip(ROUTES,(0.000314,0.000264,0.000202,0.000328)))
    if any(r['doi']!=DOI or r['source_sha256']!=JATS_SHA256 or r['observable_type']!='TOTAL'
           or r['measurement_temperature_C']!=25 or
           r['conductivity_S_cm']!=expected[r['powder_synthesis_route']] for r in rows):
        raise ValueError('unverified original TOTAL decision inputs')
    values = {r['powder_synthesis_route']:r['conductivity_S_cm'] for r in rows}
    ordered = sorted(values,key=values.get,reverse=True)
    best = values[ordered[0]]; mean = sum(values.values())/4
    return {'reported_point_value_order':ordered,'uniform_route_baseline_expected_S_cm':mean,
            'observed_oracle_S_cm':best,'descriptive_oracle_minus_uniform_S_cm':best-mean,
            'descriptive_SD_minus_SSR_S_cm':values['SD']-values['SSR'],
            'uniform_route_top1_chance':0.25,'independent_comparison_units':1,
            'pre_exposure_predictions_attested':False,'new_model_fitted':False,
            'independent_predictive_validation':False,'SD_significantly_better_than_SSR':None,
            'frozen_composition_features_distinguish_routes':False,
            'frozen_final_sintering_temperature_hold_features_distinguish_routes':False,
            'interpretation':'Retrospective point-value comparison, not significance or measured predictive gain.'}
