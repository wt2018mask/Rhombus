"""Bounded owner-constant challenge on retained CIFs; no desired-label fitting."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import time

from pymatgen.core import Structure
from .static_assessment import assess_static_transport
from .bvse_parameters import parameter_identity
from rhombus.generation.defect_engine import expand_supercell, seed_vacancies
from rhombus.generation.autonomous_generator import AutonomousCandidateGenerator


def evaluate_reference_crystals(root):
    root = Path(root)
    base = root/'data/benchmarks/known_material/structures'
    paths = {'gamma_LiAlO2_COD1008166': base/'cod/1008166-latest-freeze-v1.cif',
             'Li2S_COD9009060': base/'cod/9009060-latest-freeze-v1.cif',
             'tetragonal_LLZO': base/'literature/tetragonal-llzo-awaka-2009-nd-v1.cif'}
    rows = []
    def calculate(name, structure, origin, source_sha=None, target=None):
        start = time.monotonic()
        result = assess_static_transport(structure, vacancy_fractional_target=target)
        rows.append({'candidate': name, 'formula': structure.composition.element_composition.formula,
                     'atom_count': len(structure), 'origin': origin, 'source_sha256': source_sha,
                     'elapsed_seconds': time.monotonic()-start, 'static_result': result,
                     'energy_above_hull_meV_atom': None, 'voltage_window_V': None,
                     'missing_evidence': ['COMPATIBLE_COMPETING_PHASE_ENERGIES', 'VALIDATED_FAST_CONDUCTOR_CALIBRATION'],
                     'final_qualification': 'ABSTAIN'})
    structures = {}
    for name, path in paths.items():
        structures[name] = Structure.from_file(path)
        calculate(name, structures[name], 'RETAINED_CIF', hashlib.sha256(path.read_bytes()).hexdigest())
    sulfide = structures['Li2S_COD9009060']
    supercell = expand_supercell(sulfide)
    calculate('Li2S_2x2x2', supercell, 'RETAINED_CIF_SUPERCELL')
    vacancy = seed_vacancies(sulfide)[0]
    calculate('Li2S_single_Li_vacancy_2x2x2_CHARGED_PROBE', Structure.from_dict(vacancy['structure']),
              'CHARGED_INTRINSIC_VACANCY_PROBE', target=vacancy['vacant_fractional_targets'][0])
    generated = AutonomousCandidateGenerator().generate()
    for candidate in generated:
        # Four hypothetical metal variants are proposals; retain Y as the one
        # halide numerical illustration, not four independent real benchmarks.
        if candidate['domain'] == 'HALIDE' and 'Li3YCl6' not in candidate['template_id']:
            continue
        calculate(candidate['domain']+'_'+candidate['template_id'], Structure.from_dict(candidate['structure']),
                  candidate['origin']+'_ALIOVALENT_PROPOSAL', candidate['source_sha256'],
                  target=candidate['defect']['vacant_fractional_targets'][0])
    grid_challenge = {}
    for name in ('gamma_LiAlO2_COD1008166', 'Li2S_COD9009060'):
        result = assess_static_transport(structures[name], grid_dimension=32, run_mep=False)
        grid_challenge[name] = {'grid_shape': result['grid_shape'], 'barriers_eV': result['barriers_eV'],
                                'bottleneck_radius_A': result['bottleneck_radius_A']}
    files = [p for p in (root/'rhombus').rglob('*.py') if '__pycache__' not in p.parts]
    source = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    return {'schema_version': 'rhombus-static-calibration-challenge-v1', 'parameter_identity': parameter_identity(),
            'observed_git_head': subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip(),
            'executed_source_file_hashes': source,
            'runtime': {'python': platform.python_version(), 'numpy': importlib.metadata.version('numpy'),
                        'scipy': importlib.metadata.version('scipy'), 'pymatgen': importlib.metadata.version('pymatgen')},
            'rows': rows, 'grid_challenge_32': grid_challenge,
            'calibration_verdict': 'NOT_ESTABLISHED_OWNER_PARAMETERS_FAIL_REQUESTED_ORDERING_ON_RETAINED_CONTROLS',
            'fast_control_status': 'NO_AUTHENTICATED_FAST_SUPERIONIC_CONTROL_TETRAGONAL_LLZO_NOT_CUBIC_LLZO',
            'vacancy_scope': 'REMOVING_LI_LEAVES_STATIC_HOST_FIELD_IDENTICAL_IN_THE_SAME_CELL',
            'remote_science': 'REMOTE_SCIENCE_NOT_EXECUTED', 'qualification': 'ABSTAIN'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('new output file required; preserve previous evidence')
    report = evaluate_reference_crystals(Path(__file__).resolve().parents[2])
    raw = (json.dumps(report, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('xb') as stream:
        stream.write(raw)
    print(json.dumps({'path': str(args.output), 'sha256': hashlib.sha256(raw).hexdigest(),
                      'calibration_verdict': report['calibration_verdict']}))


if __name__ == '__main__':
    main()
