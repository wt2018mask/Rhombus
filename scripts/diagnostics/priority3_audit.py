"""Reproduce the offline Priority 3 audit; never dispatch or run an MD job."""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy.stats import rankdata, spearmanr

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from rudeus.mlip.p2_traj import verify_traj_artifact
BASE = ROOT / 'data/benchmarks/v3_static'


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate(rows, score):
    x = np.array([r[score] for r in rows]); y = np.array([r['mean_li_displacement_A'] for r in rows])
    labels = y >= .8
    positives = int(sum(labels)); negatives = len(y) - positives
    rho = float(spearmanr(x, y).statistic) if len(set(x)) > 1 and len(set(y)) > 1 else None
    auc = float((sum(rankdata(x)[labels])-positives*(positives+1)/2)/(positives*negatives)) if positives and negatives else None
    return {'n': len(rows), 'positive': positives, 'rho': rho, 'auc': auc}


def build():
    stats_path = BASE/'priority2_statistics_v1.json'; mixed_path = BASE/'priority1_deconfounding_v1.json'
    data = json.loads(stats_path.read_text()); prior = json.loads(mixed_path.read_text()); output = {}
    rng = np.random.default_rng(20261029)
    for steps in (1000, 3000, 8000):
        groups = {}
        for row in data['run_rows']:
            if row['production_steps'] == steps:
                groups.setdefault(row['formula'], []).append(row)
        formulas = [{'formula': formula, **{key: float(np.mean([row[key] for row in runs]))
                       for key in ('saddle', 'fixed_0.3', 'fixed_0.5', 'mean_li_displacement_A')},
                     'run_count': len(runs)} for formula, runs in sorted(groups.items())]
        scores = {}
        draws = rng.integers(0, len(formulas), (1000, len(formulas))) if formulas else []
        for key in ('saddle', 'fixed_0.3', 'fixed_0.5'):
            m = evaluate(formulas, key); boot = [evaluate([formulas[i] for i in draw], key) for draw in draws]
            for metric in ('rho', 'auc'):
                values = [r[metric] for r in boot if r[metric] is not None and math.isfinite(r[metric])]
                m[metric+'_ci95'] = np.quantile(values, [.025, .975]).tolist() if values else None
                m[metric+'_valid'] = len(values)
            scores[key] = m
        output[str(steps)] = {'formula_rows': formulas, 'metrics': scores}
    mixed = []
    for row in prior['mixed']:
        runs = []
        for rec in row['runs']:
            path = ROOT / rec['path']; record = json.loads(path.read_text()); v = record['result']; calc = (v.get('provenance') or {}).get('calc') or {}
            runs.append({'path':rec['path'], 'file_sha256':file_hash(path), 'input_hash':v.get('p2_input_relaxed_sha256'),
                         'seed':v.get('seed'), 'temperature_K':v.get('temperature_K'), 'timestep_fs':v.get('timestep_fs'),
                         'equilibration_steps':v.get('equilibration_steps'), 'completed_steps':v.get('production_steps_completed'),
                         'termination':v.get('termination'), 'verdict':v.get('p2_verdict'), 'protocol':v.get('p2_protocol'),
                         'config_hash':v.get('p2_config_hash'), 'worker':record.get('worker'),
                         'calc':{k:calc.get(k) for k in ('sha256','dtype','python_version','torch_version','ase_version','device','torch_num_threads')},
                         'trajectory_artifact':v.get('trajectory_artifact'), 'initial_velocity_or_rng_state':'NOT_VERIFIED_IN_SUMMARY'})
        trajectory_comparison = {'status':'UNAVAILABLE'}
        artifacts = [r['trajectory_artifact'] for r in runs]
        if len(artifacts) == 2 and all(a and (ROOT / a['path']).is_file() for a in artifacts):
            paths = [ROOT / a['path'] for a in artifacts]
            for path, artifact in zip(paths, artifacts):
                verify_traj_artifact(path, artifact['sha256'])
            with np.load(paths[0], allow_pickle=False) as a, np.load(paths[1], allow_pickle=False) as b:
                common = np.intersect1d(a['frame_steps'], b['frame_steps'])
                if len(common) and np.array_equal(a['species'],b['species']) and np.allclose(a['cell'],b['cell']):
                    step = common[0]; av = a['positions'][np.flatnonzero(a['frame_steps']==step)[0]]; bv = b['positions'][np.flatnonzero(b['frame_steps']==step)[0]]
                    # MIC wrapping is reliable here only for matching orthogonal cells; no MIC claim for general cells.
                    trajectory_comparison = {'status':'FIRST_COMMON_PRODUCTION_FRAME_RAW_CARTESIAN', 'step':int(step), 'n_common_steps':int(len(common)), 'rms_raw_cartesian_difference_A':float(np.sqrt(np.mean(np.sum((av-bv)**2,axis=1)))), 'scope':'NO_PERIODIC_ALIGNMENT_OR_INITIAL_VELOCITY_RECONSTRUCTION'}
                else:
                    trajectory_comparison = {'status':'NO_COMPARABLE_COMMON_PRODUCTION_FRAME'}
        mixed.append({'trajectory_comparison':trajectory_comparison, 'batch_id':row['batch_id'], 'formula':row['formula'], 'p1_sha256':row['relaxed_sha256'],
                      'all_p2_input_hashes_match_p1':all(x['input_hash'] == row['relaxed_sha256'] for x in runs),
                      'p1':row['p1'], 'host_min_distance_A':row['host_host_distance_A'], 'runs':runs})
    return {'schema':'rhombus-priority3-offline-v1', 'source_commit':'66437016a97328147174236eb34ae3d7de5d3ba2',
            'inputs_sha256':{str(p.relative_to(ROOT)):file_hash(p) for p in (stats_path,mixed_path)},
            'driver_sha256':file_hash(Path(__file__)), 'matched_step_formula_results':output, 'mixed':mixed,
            'scope':'RETROSPECTIVE_NONINDEPENDENT_NOT_CAUSAL', 'qualification':'ABSTAIN'}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--output', type=Path, required=True); args = parser.parse_args()
    if args.output.exists(): raise FileExistsError('refusing to overwrite existing audit artifact')
    args.output.write_text(json.dumps(build(), indent=2, sort_keys=True, allow_nan=False)+'\n')


if __name__ == '__main__': main()
