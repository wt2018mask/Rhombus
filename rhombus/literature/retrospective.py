"""Descriptive policy audit for publicly exposed, unauthenticated Ga-LLZO lead.

NOT original-paper authentication, prospective preregistration, model evaluation
or scientific admission. No source uncertainty is inferred from parentheses.
"""
from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

DOI = '10.1039/d2ta09250f'
CELL = re.compile(r'([0-9]+(?:\.[0-9]+)?)\(([0-9]+)\)\Z')


def summarize_exposed_lead(lead: dict) -> dict:
    """Compute purely descriptive consequences of fixed policies over exposed labels."""
    if not isinstance(lead, dict) or lead.get('doi') != DOI:
        raise ValueError('incorrect original DOI')
    if lead.get('source_authentication') != (
            'RAW_PDF_SHA256_NOT_OBSERVED; ORIGINAL_TABLE_VALUES_TRANSCRIBED_FROM_PUBLIC_SOURCE; '
            'REQUIRES_BYTE_AUTHENTICATION'):
        raise ValueError('this adapter requires the explicitly unauthenticated lead')
    gates = lead.get('scientific_gates', {})
    if (gates.get('new_strict_qualified_doi_groups') != 0 or
            gates.get('new_strict_manufacturing_comparisons') != 0 or
            gates.get('heldout_model_evaluation') != 'NOT_RUN_LABELS_ALREADY_EXPOSED' or
            gates.get('scientific_GO') is not False):
        raise ValueError('exposure/admission boundary changed')
    methods = lead.get('shared_methods', {})
    if (methods.get('conductivity_measurement_temperature_C') != 25 or
            methods.get('observable') != 'TOTAL_IONIC_CONDUCTIVITY' or
            methods.get('author_unit') != 'mS/cm' or
            methods.get('final_sintering_temperature_C') != 1175 or
            methods.get('final_sintering_atmosphere') != 'air'):
        raise ValueError('unsupported source methods or units')
    tab = lead.get('table6', {})
    excess = tab.get('lithium_excess_percent')
    dwells = tab.get('dwell_hours')
    literals = tab.get('literal_reported_values')
    numeric = tab.get('point_values_mS_cm')
    if (excess != [0, 5, 10, 20] or dwells != [1, 5, 10, 20] or
            not isinstance(literals, list) or len(literals) != 4 or
            not isinstance(numeric, list) or len(numeric) != 4 or
            tab.get('per_cell_uncertainty_numeric') is not None):
        raise ValueError('incomplete or reinterpreted source grid')
    cells = {}
    for ex, ls, ns in zip(excess, literals, numeric, strict=True):
        if not isinstance(ls, list) or not isinstance(ns, list) or len(ls) != 4 or len(ns) != 4:
            raise ValueError('incomplete manufacturing row')
        for dwell, literal, number in zip(dwells, ls, ns, strict=True):
            match = CELL.fullmatch(literal) if isinstance(literal, str) else None
            if match is None or not isinstance(number, (int, float)) or isinstance(number, bool):
                raise ValueError('source literal/value invalid')
            try:
                parsed, provided = Decimal(match.group(1)), Decimal(str(number))
            except InvalidOperation as exc:
                raise ValueError('unparseable source number') from exc
            if not provided.is_finite() or not 0 < provided < 10 or provided != parsed:
                raise ValueError('changed or nonphysical reported value')
            cells[(ex, dwell)] = provided
    if len(cells) != 16:
        raise ValueError('duplicate manufacturing condition')
    maximum = max(cells.values())
    winners = [key for key, value in cells.items() if value == maximum]
    # Value-independent selectors. Means/regrets are calculated AFTER exposure;
    # even a seemingly successful policy here is not a prospective prediction.
    policies = {
        'uniform_all_16': list(cells),
        'minimum_lithium_excess_uniform_dwell': [k for k in cells if k[0] == 0],
        'maximum_lithium_excess_uniform_dwell': [k for k in cells if k[0] == 20],
        'shortest_dwell_uniform_excess': [k for k in cells if k[1] == 1],
        'longest_dwell_uniform_excess': [k for k in cells if k[1] == 20],
        'minimum_excess_shortest_dwell': [(0, 1)],
        'minimum_excess_longest_dwell': [(0, 20)],
    }
    summaries = {}
    for name, keys in policies.items():
        expectation = sum((cells[k] for k in keys), Decimal(0)) / len(keys)
        summaries[name] = {
            'uniform_tie_choices': len(keys),
            'expected_mS_cm': float(expectation),
            'expected_S_cm': float(expectation / 1000),
            'point_oracle_regret_mS_cm': float(maximum - expectation),
        }
    by_dwell = {str(d): float(sum((cells[(ex, d)] for ex in excess), Decimal(0)) / 4)
                for d in dwells}
    return {
        'schema_version': 'rhombus-rsc-exposed-lead-descriptive-policy-v1',
        'doi': DOI,
        'evidence_class': 'UNAUTHENTICATED_PUBLICLY_EXPOSED_LEAD_ONLY',
        'original_raw_sha256': None,
        'table6_verified_from_raw_bytes': False,
        'source_DOI_groups': 1,
        'published_condition_point_values': 16,
        'independent_sample_count_established': None,
        'numeric_uncertainty_attested': False,
        'point_oracle': {'lithium_excess_percent': winners[0][0],
                         'dwell_hours': winners[0][1],
                         'conductivity_mS_cm': float(maximum),
                         'tied_condition_count': len(winners)},
        'heuristic_policy_consequences': summaries,
        'dwell_only_uniform_undistinguished_excess_mS_cm': by_dwell,
        'frozen_feature_identifiability': {
            'constant_nominal_formula_and_sinter_temperature': True,
            'temperature_plus_dwell_unique_condition_classes': 4,
            'condition_count': 16,
            'lithium_excess_not_encoded_in_temperature_plus_dwell': True,
            'existing_frozen_predictor_predictions_computed': False,
        },
        'trained_or_evaluated_model': False,
        'prospective_or_independent_heldout_claim': False,
        'statistical_significance_claim': False,
        'new_strict_qualified_doi_groups': 0,
        'new_strict_manufacturing_comparisons': 0,
        'scientific_GO': False,
        'production_enabled': False,
        'OBELIX_TEST_121_accessed': False,
    }


def run_exposed_lead(lead_path: str | Path) -> dict:
    """Hash the preliminary JSON lead, not an inaccessible original PDF."""
    raw = Path(lead_path).read_bytes()
    report = summarize_exposed_lead(json.loads(raw))
    report['lead_json_sha256'] = hashlib.sha256(raw).hexdigest()
    return report
