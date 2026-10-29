"""Conservative, deterministic summary of supplied audit observations."""
import json


def synthesize_scientific_opinion(audit_record: dict) -> dict:
    """Summarize supplied evidence; missing fields remain unknown and qualification abstains."""
    if not isinstance(audit_record, dict):
        raise TypeError('audit_record must be a dictionary')
    row = json.loads(json.dumps(audit_record, allow_nan=False))
    static = row.get('relaxed') or row.get('static') or {}
    geometry = row.get('geometric') or {}
    p2_records = row.get('p2_records', row.get('p2', row.get('runs', [])))
    p2_summary = []
    for p2 in p2_records:
        termination = p2.get('termination') or {}
        completed = termination.get('completed')
        status = ('COMPLETED' if completed is True else
                  'UNFINISHED_EXPLOSIVE_STEP' if completed is False and termination.get('note') == 'explosive-step'
                  else 'UNFINISHED' if completed is False else 'UNKNOWN')
        p2_summary.append({'path': p2.get('path'), 'status': status,
            'temperature_K': p2.get('temperature_K'), 'verdict': p2.get('p2_verdict', p2.get('verdict')),
            'mean_li_displacement_A': (p2.get('mobile_ion_metrics') or {}).get('mobile_mean_displacement_A', p2.get('mean_li_displacement_A'))})
    sections = {
        'section_1_structure_and_provenance': {'formula': row.get('formula'), 'spacegroup': static.get('spacegroup'),
            'sites': static.get('sites'), 'relaxed_sha256': row.get('relaxed_sha256') or row.get('p1_relaxed_sha256'),
            'p2_records': row.get('p2_records', row.get('p2', []))},
        'section_2_electronic_and_composition_gate': {'electronic_gate': static.get('electronic_gate'),
            'q_Li': static.get('q_Li'), 'x_vac': static.get('x_vac')},
        'section_3_geometric_and_static_percolation': {'geometric_bottleneck_radius_3d_A': geometry.get('radius_A', row.get('radius_A')),
            'geometry_scope': geometry.get('scope'), 'unrelaxed_channel_3d_ev': (row.get('unrelaxed') or {}).get('host_channel_barrier_3d_ev', row.get('unrelaxed_channel_ev')),
            'p1_relaxed_channel_3d_ev': static.get('host_channel_barrier_3d_ev', row.get('channel_ev')),
            'normalized_channel_ev': static.get('normalized_channel_ev', row.get('normalized_channel_ev')),
            'basin_diagnostic': static.get('basin_diagnostic', row.get('basin')),
            'host_min_distance_A': static.get('host_min_distance_A', row.get('host_min_distance_A')),
            'host_steric_collision_warning': static.get('host_steric_collision_warning', row.get('host_steric_collision_warning'))},
        'section_4_thermochemical_and_dynamic_linkage': {'p1_hull_ev_atom': row.get('p1_hull_ev_atom', row.get('p1_energy_above_hull')),
            'esw': row.get('esw'), 'p2_records': p2_records, 'p2_summary': p2_summary,
            'p25_records': row.get('p25_records', row.get('p25', []))},
        'section_5_scientific_verdict_and_limitations': {'static_verdict': static.get('static_verdict'),
            'qualification': 'ABSTAIN', 'model_applicability': 'UNQUALIFIED',
            'limitations': ['Static voxel screening is not a transport measurement.',
                            'Input evidence and model applicability are not independently certified.']}}
    sections['markdown_summary'] = ('## Scientific opinion\n\n'
        + '\n\n'.join('### ' + name + '\n\n```json\n' + json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + '\n```'
                        for name, value in sections.items()))
    return sections
