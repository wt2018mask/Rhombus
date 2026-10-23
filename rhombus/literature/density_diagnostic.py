"""Post-sinter density vs 25 C TOTAL point ranks; never a prospective predictor.

This retrospective diagnostic uses two PUBLICLY EXPOSED Table 1 leads, not
authenticated original bytes. The density assay is a manufacturing OUTCOME,
not an input available before choosing the manufacturing process. Neither
pairwise ranking nor an observed maximum establishes independent replicates.
"""
from __future__ import annotations
from decimal import Decimal, InvalidOperation
from itertools import combinations
import json
from pathlib import Path

DOI = '10.1039/d0ta11096e'
DENSITY_SCHEMA = 'rhombus-rosen2021-relative-density-table1-unverified-lead-v1'
PROCESS_SCHEMA = 'rhombus-rosen-2021-public-table1-lead-v1'


def _literal(value, *, unit, lo, hi):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f'{unit} must be a literal string')
    try:
        v = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f'{unit} invalid') from exc
    if not v.is_finite() or not lo < v < hi:
        raise ValueError(f'{unit} out of bounds')
    return v


def analyze_density_confounding(process_lead, density_lead):
    """Count observed rank reversals while enforcing unqualified provenance."""
    from .pretreatment_interaction import evaluate_exposed_processing_interaction, _ROWS
    prior = evaluate_exposed_processing_interaction(process_lead)
    if (not isinstance(density_lead, dict) or density_lead.get('schema_version') != DENSITY_SCHEMA
            or density_lead.get('doi') != DOI
            or density_lead.get('source_status') != 'PUBLISHER_TABLE_HTML_VIEWED_NO_FROZEN_RAW_BYTES'
            or density_lead.get('original_raw_sha256') is not None
            or density_lead.get('measurement_type') != 'POST_SINTER_RELATIVE_DENSITY_PERCENT'
            or density_lead.get('density_numeric_uncertainty') is not None
            or density_lead.get('sample_pellet_ids_verified') is not False
            or density_lead.get('density_assay') != {
                'method': 'ARCHIMEDES_WITH_WATER',
                'specimens_per_reported_density_mean': 2,
                'conductivity_specimens_identical_to_density_specimens': None,
                'independent_conductivity_replicate_count': None,
            }
            or density_lead.get('new_strict_qualified_doi_groups') != 0
            or density_lead.get('new_strict_manufacturing_comparisons') != 0):
        raise ValueError('density source admission or identity drift')
    if process_lead.get('schema_version') != PROCESS_SCHEMA or process_lead.get('doi') != DOI:
        raise ValueError('conductivity source identity drift')
    rows = density_lead.get('table1_density_rows')
    conductivity_rows = process_lead.get('table1')
    if not isinstance(rows, list) or len(rows) != 11 or not isinstance(conductivity_rows, list):
        raise ValueError('missing original Table1 condition population')
    densities = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('invalid density record')
        code = row.get('sample')
        if code not in _ROWS or code in densities:
            raise ValueError('unknown or duplicated sample code')
        expected = 'NOT_PRODUCED' if code in ('Argon1,7', 'Air1,7') else 'MEASURED'
        if row.get('row_status') != expected:
            raise ValueError('source missingness boundary changed')
        value = _literal(row.get('relative_density_percent_literal'),
                         unit='relative density', lo=Decimal(0), hi=Decimal(100))
        if (code in ('Argon1,7', 'Air1,7')) != (value is None):
            raise ValueError('density missingness changed')
        densities[code] = value
    if set(densities) != set(_ROWS):
        raise ValueError('density cohort drift')
    values = {}
    for row in conductivity_rows:
        code = row['sample']
        conductivity = _literal(row['conductivity_literal_S_cm'], unit='total conductivity',
                                lo=Decimal('1e-9'), hi=Decimal('1e-1'))
        if (density := densities[code]) is not None and conductivity is not None:
            values[code] = (density, conductivity)
        elif density is not None or conductivity is not None:
            raise ValueError('source numerical rows cannot mismatch')
    if len(values) != 9:
        raise ValueError('nine measured conditions required')
    concordant = discordant = ties = 0
    for (_, (da, ca)), (_, (db, cb)) in combinations(values.items(), 2):
        relation = (da-db)*(ca-cb)
        if relation > 0: concordant += 1
        elif relation < 0: discordant += 1
        else: ties += 1
    if concordant+discordant+ties != 36:
        raise ValueError('pairwise coverage changed')
    def change(prefix):
        a,b = values[f'{prefix}0'],values[f'{prefix}7']
        return {'relative_density_change_percentage_points':float(b[0]-a[0]),
                'total_conductivity_change_S_cm':float(b[1]-a[1]),
                'opposite_direction':(b[0]-a[0])*(b[1]-a[1])<0}
    densest = max(values, key=lambda code: values[code][0])
    highest = max(values, key=lambda code: values[code][1])
    return {
        'schema_version':'rhombus-rosen2021-density-outcome-rank-diagnostic-v1',
        'doi':DOI, 'numeric_25C_TOTAL_conditions':len(values),
        'comparisons_within_one_unreplicated_author_study':36,
        'density_conductivity_rank_concordant_pairs':concordant,
        'density_conductivity_rank_discordant_pairs':discordant,
        'rank_ties':ties,
        'argon_7day_air_storage_change':change('Argon'),
        'air_7day_air_storage_change':change('Air'),
        'densest_sample':densest,'largest_observed_conductivity_sample':highest,
        'retrospective_same_row_oracle_not_a_deployable_density_policy':True,
        'relative_density_is_POST_SINTER_CHARACTERIZATION_NOT_PRESELECTION_INPUT':True,
        'density_alone_cannot_preserve_every_observed_pair_order':discordant>0,
        'density_assay_specimens_per_condition': 2,
        'density_is_author_reported_two_specimen_mean': True,
        'conductivity_observation_replicate_count': None,
        'density_specimens_same_as_conductivity_specimens': None,
        'independent_pellet_or_replicate_counts':None,
        'numeric_cond_uncertainty_verified':False,
        'original_raw_source_sha256_verified':False,
        'model_fitted_or_evaluated':False,
        'statistical_significance_or_generalization_claim':False,
        'new_strict_qualified_doi_groups':0,
        'new_strict_manufacturing_comparisons':0,
        'scientific_GO':False,'production_enabled':False,
        'official_TEST_121_accessed':False,
        'upstream_conductivity_lead_rows':prior['table_rows'],
    }


def run_files(process_path, density_path):
    """Read two user-visible PUBLIC leads; no source or TEST access."""
    return analyze_density_confounding(json.loads(Path(process_path).read_text()),
                                       json.loads(Path(density_path).read_text()))
