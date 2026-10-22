"""Descriptive surface-conditioning interaction; unqualified exposed original HTML.

No original raw-source SHA, predictive training, sample-level independence,
statistical significance or new scientific admission is established.
"""
from __future__ import annotations
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

DOI = '10.1039/d0ta11096e'
SOURCE_SCHEMA = 'rhombus-rosen-2021-public-table1-lead-v1'
_VALUES = re.compile(r'\d+(?:\.\d+)?e-\d+\Z')
_ROWS = {
    'Argon0': ('ARGON', 'NONE', 0),
    'Argon0,1': ('ARGON', 'ETHANOL', 1),
    'Argon1': ('ARGON', 'AIR', 1),
    'Argon7': ('ARGON', 'AIR', 7),
    'Argon1,7': ('ARGON', 'ETHANOL', 7),
    'Air0': ('AIR', 'NONE', 0),
    'Air0,1': ('AIR', 'ETHANOL', 1),
    'Air1': ('AIR', 'AIR', 1),
    'Air7': ('AIR', 'AIR', 7),
    'Air1,7': ('AIR', 'ETHANOL', 7),
    'Milled': ('AS_MILLED', 'NONE', 0),
}


def evaluate_exposed_processing_interaction(lead: dict) -> dict:
    """Calculate matched descriptive effects, not valid predictive model gain."""
    if not isinstance(lead, dict) or lead.get('schema_version') != SOURCE_SCHEMA or lead.get('doi') != DOI:
        raise ValueError('unreviewed article identity')
    if (lead.get('raw_original_sha256') is not None or
            lead.get('source_status') != 'ORIGINAL_PUBLISHER_HTML_VIEWED; RAW_BYTES_NOT_FROZEN' or
            lead.get('new_strict_qualified_doi_groups') != 0 or
            lead.get('new_strict_manufacturing_comparisons') != 0 or
            lead.get('independent_blind_eligibility') is not False):
        raise ValueError('source identity or unsupported admission')
    scope = lead.get('measurement_scope')
    if (not isinstance(scope, dict) or scope.get('temperature_C') != 25 or
            scope.get('conductivity_type') != 'TOTAL' or scope.get('unit') != 'S/cm' or
            scope.get('nominal_composition') != 'Li6.45Al0.05La3Zr1.6Ta0.4O12' or
            scope.get('final_sinter_C') != 1175 or scope.get('final_sinter_h') != 10 or
            scope.get('final_sinter_atmosphere') != 'air'):
        raise ValueError('unreviewed conductivity or manufacturing context')
    observations = lead.get('table1')
    if not isinstance(observations, list) or len(observations) != len(_ROWS):
        raise ValueError('full table population, including missing rows, required')
    point = {}
    for row in observations:
        if not isinstance(row, dict):
            raise ValueError('invalid original row')
        code = row.get('sample')
        if code not in _ROWS or code in point:
            raise ValueError('unknown/duplicate author condition')
        if (row.get('pretreatment'), row.get('storage_medium'), row.get('storage_days')) != _ROWS[code]:
            raise ValueError('swapped treatment or storage association')
        literal = row.get('conductivity_literal_S_cm')
        if literal is None:
            if code not in ('Argon1,7', 'Air1,7'):
                raise ValueError('unexpected missing observation')
            point[code] = None
            continue
        if code in ('Argon1,7', 'Air1,7') or not isinstance(literal, str) or not _VALUES.fullmatch(literal):
            raise ValueError('unexpected source notation or imputed missing value')
        try:
            val = Decimal(literal)
        except InvalidOperation as exc:
            raise ValueError('malformed conductivity') from exc
        if not Decimal('1e-9') < val < Decimal('1e-1'):
            raise ValueError('invalid conductivity range')
        point[code] = val
    if set(point) != set(_ROWS):
        raise ValueError('incomplete author sample codes')
    change = {}
    interactions = {}
    for day in (1, 7):
        diff = {}
        for pretreatment, prefix in (('ARGON', 'Argon'), ('AIR', 'Air')):
            diff[pretreatment] = point[f'{prefix}{day}'] - point[f'{prefix}0']
        change[str(day)] = {pre: float(val) for pre, val in diff.items()}
        interactions[str(day)] = {
            'difference_in_differences_air_minus_argon_S_cm': float(diff['AIR'] - diff['ARGON']),
            'sign_reversal_between_pretreatments': diff['AIR'] < 0 < diff['ARGON'],
        }
    return {
        'schema_version': 'rhombus-rosen-2021-exposed-process-interaction-v1',
        'doi': DOI,
        'evidence_tier': 'EXPLORATORY_ORIGINAL_HTML_TABLE_VIEW; NOT_RAW_BYTE_AUTHENTICATED',
        'table_rows': len(point),
        'numerical_total25C_rows': sum(v is not None for v in point.values()),
        'explicit_missing_conductivity_rows': sorted(k for k, v in point.items() if v is None),
        'one_paper_not_independent_labs_or_replicates': True,
        'matched_air_storage_change_S_cm': change,
        'pretreatment_by_storage_interactions': interactions,
        'fresh_air_over_fresh_argon_ratio': float(point['Air0']/point['Argon0']),
        'seven_day_argon_over_seven_day_air_ratio': float(point['Argon7']/point['Air7']),
        'independent_sample_count_established': None,
        'numerical_uncertainty_attested': False,
        'predictive_models_evaluated': False,
        'statistical_significance_claim': False,
        'new_strict_qualified_doi_groups': 0,
        'new_strict_manufacturing_comparisons': 0,
        'scientific_GO': False,
        'production_enabled': False,
        'OBELIX_TEST_121_accessed': False,
    }


def run_lead(path: str | Path) -> dict:
    return evaluate_exposed_processing_interaction(json.loads(Path(path).read_text(encoding='utf-8')))
