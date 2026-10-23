"""Bounded historical-publication exposure audit for literature discovery.

This is a NON-EXHAUSTIVE, original-repository-evidence-bound registry.
Unlisted DOIs have UNKNOWN historical status, never presumed to be new,
independent, blind, or eligible for a new benchmark. Prior exposure and
scientific validity are separate facts. Historical records are not rewritten.
"""
from __future__ import annotations

# Source code or original checkpoint documentation that already used each DOI.
# The record identifies prior Rhombus use, NOT independent-pellet provenance.
# DOIs are normalized lower-case. Add entries only after checking originals.
KNOWN_USES = {
    '10.3390/ma14071671': (
        'ORIGINAL_LABELS_ALREADY_EXPOSED', 'NB-CHOICE-20261023',
        'rhombus/literature/niobium_sintering.py'),
    '10.1016/j.heliyon.2024.e36206': (
        'ORIGINAL_LABELS_ALREADY_EXPOSED', 'MICROWAVE-20261021',
        'rhombus/literature/microwave.py'),
    '10.1039/d2ta09250f': (
        'UNAUTHENTICATED_LABELS_ALREADY_EXPOSED', 'RSC-LEAD-20261021',
        'data/development/literature_rsc_ga_llzo_2023_lead_v1.json'),
    '10.3390/ma14164737': (
        'ORIGINAL_LABELS_ALREADY_EXPOSED', 'LATP-20261021',
        'rhombus/literature/cold_sintering.py'),
    '10.1038/s41467-025-58108-7': (
        'ORIGINAL_LABELS_ALREADY_EXPOSED', 'PILOT-20261020',
        'rhombus/literature/source_parsers.py'),
    '10.1039/d5ra03917g': (
        'RETROSPECTIVE_EVALUATION', '0186',
        'scripts/science/obelix_solo_oxide_primary_0186.py'),
    '10.3390/nano12172946': (
        'RETROSPECTIVE_EVALUATION', '0187',
        'scripts/science/obelix_solo_oxide_jats_three_doi_0187.py'),
    '10.3390/ma13030560': (
        'RETROSPECTIVE_EVALUATION', '0187',
        'scripts/science/obelix_solo_oxide_jats_three_doi_0187.py'),
    '10.1039/c8ra01329b': (
        'RETROSPECTIVE_EVALUATION', '0188',
        'scripts/science/obelix_solo_oxide_five_doi_0188.py'),
    '10.3390/ma14226809': (
        'RETROSPECTIVE_EVALUATION', '0188',
        'scripts/science/obelix_solo_oxide_five_doi_0188.py'),
    '10.1021/acsorginorgau.5c00021': (
        'RETROSPECTIVE_EVALUATION', '0190',
        'scripts/science/obelix_solo_oxide_original_manufacturing_0190.py'),
    '10.1021/acsomega.2c06544': (
        'RETROSPECTIVE_EVALUATION', '0192',
        'docs/PHASE3_SOLO_OXIDE_NEW_SOURCE_0192.md'),
    '10.1002/cssc.202300399': (
        'ORIGINAL_LABELS_ALREADY_EXPOSED', '0194',
        'docs/PHASE3_SOLO_OXIDE_TE_HOTPRESS_ORIGINAL_0194.md'),
    '10.1038/s41467-026-74887-z': (
        'ORIGINAL_LABELS_ALREADY_EXPOSED', 'MOESM5-20261020',
        'docs/LITERATURE_HARVESTING.md'),
    '10.1002/smll.202506257': (
        'ORIGINAL_LABELS_ALREADY_EXPOSED', 'PILOT-20261020',
        'docs/LITERATURE_HARVESTING.md'),
}


def audit_prior_exposure(measurements):
    """Audit provenance of parsed rows; do not modify their scientific tier.

    No unreviewed DOI is automatically marked novel. This audit cannot by
    itself prove independent laboratories, pellets, or future heldout status.
    """
    from .harvest import normalize_doi
    groups = {}
    for row in measurements:
        if not isinstance(row, dict) or not isinstance(row.get('doi'), str):
            raise ValueError('measurement missing source DOI')
        doi = normalize_doi(row['doi'])
        if row['doi'] != doi:
            raise ValueError('source DOI must be normalized for historical audit')
        groups[doi] = groups.get(doi, 0) + 1
    records = []
    for doi in sorted(groups):
        info = KNOWN_USES.get(doi)
        records.append({
            'doi': doi, 'row_count': groups[doi],
            'history_status': info[0] if info else 'PRIOR_HISTORY_UNREVIEWED',
            'prior_checkpoint': info[1] if info else None,
            'repository_evidence_path': info[2] if info else None,
            'new_independent_evaluation_authorized': False,
        })
    return {
        'schema_version': 'rhombus-literature-prior-exposure-audit-v1',
        'scope': 'NON_EXHAUSTIVE_HISTORICAL_REGISTRY; UNKNOWN_IS_NOT_NEW',
        'doi_groups_in_measurements': len(records),
        'historically_evaluated_doi_groups': sum(
            r['history_status'] == 'RETROSPECTIVE_EVALUATION' for r in records),
        'previously_exposed_other_doi_groups': sum(
            r['history_status'] in {'ORIGINAL_LABELS_ALREADY_EXPOSED',
                                   'UNAUTHENTICATED_LABELS_ALREADY_EXPOSED'} for r in records),
        'history_unreviewed_doi_groups': sum(
            r['history_status'] == 'PRIOR_HISTORY_UNREVIEWED' for r in records),
        'new_independent_evaluation_doi_groups_authorized': 0,
        'independent_blind_claim': False,
        'records': records,
    }
