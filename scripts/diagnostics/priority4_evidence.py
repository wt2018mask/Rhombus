"""Offline grouped and mixed-run provenance audits; no MD or provider access."""
import argparse, hashlib, json, math, platform, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import numpy as np
from scipy.stats import rankdata, spearmanr
from pymatgen.core import Lattice
from pymatgen.util.coord import pbc_shortest_vectors
from rudeus.mlip.p2_traj import verify_traj_artifact
B=ROOT/'data/benchmarks/v3_static'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def metric(x,y):
 x=np.array(x); y=np.array(y); label=y>=.8; pos=int(label.sum()); neg=len(y)-pos
 return {'rho':float(spearmanr(x,y).statistic) if len(set(x))>1 and len(set(y))>1 else None,'auc':float((sum(rankdata(x)[label])-pos*(pos+1)/2)/(pos*neg)) if pos and neg else None,'positive':pos,'negative':neg}
def build():
 data=json.loads((B/'priority2_statistics_v1.json').read_text());joint=json.loads((B/'joint_mobility_diagnostic_v1.json').read_text());prior=json.loads((B/'priority3_offline_audit_v1.json').read_text());ji={r['relaxed_sha256']:r['score'] for r in joint['records']};rows=[]
 for row in data['run_rows']:
  path=ROOT/row['p2_path']; p=json.loads(path.read_text());v=p['result']; row=dict(row);row.update(parent_id=v.get('parent_id') or p.get('parent_id'),protocol=v.get('p2_protocol_version'),trajectory=(v.get('trajectory_artifact') or {}).get('sha256'),p2_file_sha256=sha(path),cohort_relative=ji[row['relaxed_sha256']]); rows.append(row)
 rng=np.random.default_rng(20261101); results={};scores=['saddle','fixed_0.3','fixed_0.5','cohort_relative']
 for steps in (1000,3000,8000):
  groups={}
  for r in rows:
   if r['production_steps']==steps:groups.setdefault(r['formula'],[]).append(r)
  formula=[{'formula':f,**{k:float(np.mean([x[k] for x in a])) for k in scores+['mean_li_displacement_A']}} for f,a in sorted(groups.items())];n=len(formula);draw=rng.integers(0,n,(1000,n));y=np.array([r['mean_li_displacement_A'] for r in formula]);metrics={};boots={}
  for key in scores:
   x=np.array([r[key] for r in formula]);m=metric(x,y); vals=[metric(x[d],y[d]) for d in draw];boots[key]=vals
   for k in ('rho','auc'):
    z=[a[k] for a in vals if a[k] is not None and math.isfinite(a[k])];m[k+'_ci95']=np.quantile(z,[.025,.975]).tolist() if z else None;m[k+'_bootstrap_valid']=len(z)
   observed=m['rho'];perms=[metric(x,rng.permutation(y))['rho'] for _ in range(1000)]; valid=[z for z in perms if z is not None and math.isfinite(z)];m['permutation_p_two_sided']=(1+sum(abs(z)>=abs(observed)-1e-12 for z in valid))/(len(valid)+1) if observed is not None else None;m['permutation_valid']=len(valid);metrics[key]=m
  paired={}
  for key in ('fixed_0.3','fixed_0.5','cohort_relative'):
   paired[key]={}
   for k in ('rho','auc'):
    dif=[b[k]-a[k] for a,b in zip(boots['saddle'],boots[key]) if a[k] is not None and b[k] is not None];paired[key][k]={'ci95':np.quantile(dif,[.025,.975]).tolist() if dif else None,'valid':len(dif)}
  results[str(steps)]={'n_formulas':n,'formula_rows':formula,'metrics':metrics,'paired_difference_vs_saddle':paired}
 group_comparisons={}
 for steps in (1000,3000,8000):
  group_comparisons[str(steps)]={}
  for field in ('relaxed_sha256','formula','parent_id'):
   groups={}
   for row in rows:
    if row['production_steps']==steps and row.get(field) is not None:groups.setdefault(row[field],[]).append(row)
   aggregated=[{k:float(np.mean([r[k] for r in group])) for k in scores+['mean_li_displacement_A']} for group in groups.values()]
   group_comparisons[str(steps)][field]={'n_groups':len(aggregated),'metrics':{key:metric([r[key] for r in aggregated],[r['mean_li_displacement_A'] for r in aggregated]) for key in scores},'scope':'RETROSPECTIVE_GROUPING_NOT_INDEPENDENT_HOLDOUT'}
 mixed=[]
 for entry in prior['mixed']:
  r=dict(entry); r['runs']=[dict(run) for run in r['runs']]
  for run in r['runs']:
   original=json.loads((ROOT/run['path']).read_text()); value=original['result']; run['calc_full']=(value.get('provenance') or {}).get('calc');run['recorded_initial_velocity_rng_force_neighbor_settings']='NOT_RECORDED_IN_RESULT_SUMMARY'
  arts=[run['trajectory_artifact'] for run in r['runs']];alignment={'status':'UNAVAILABLE'}
  if len(arts)==2 and all(a and (ROOT/a['path']).is_file() for a in arts):
   a,b=[verify_traj_artifact(ROOT/i['path'],i['sha256']) for i in arts];common=np.intersect1d(a['frame_steps'],b['frame_steps'])
   if len(common) and a['species']==b['species'] and np.allclose(a['cell'],b['cell']):
    step=common[0];pa=a['positions'][np.flatnonzero(a['frame_steps']==step)[0]];pb=b['positions'][np.flatnonzero(b['frame_steps']==step)[0]]; lattice=Lattice(a['cell']);fa=lattice.get_fractional_coords(pa);fb=lattice.get_fractional_coords(pb);vectors=np.array([pbc_shortest_vectors(lattice,[u],[v])[0,0] for u,v in zip(fa,fb)]);shift=np.mean(vectors,axis=0);aligned=vectors-shift
    alignment={'status':'FIRST_COMMON_PRODUCTION_FRAME','frame_step':int(step),'n_common':int(len(common)),'frame_hash_a_sha256':hashlib.sha256(np.asarray(pa,dtype='<f8').tobytes()).hexdigest(),'frame_hash_b_sha256':hashlib.sha256(np.asarray(pb,dtype='<f8').tobytes()).hexdigest(),'raw_rms_A':float(np.sqrt(np.mean(np.sum((pa-pb)**2,axis=1)))),'raw_max_A':float(np.linalg.norm(pa-pb,axis=1).max()),'mic_translation_aligned_rms_A':float(np.sqrt(np.mean(np.sum(aligned**2,axis=1)))),'mic_translation_aligned_max_A':float(np.linalg.norm(aligned,axis=1).max()),'scope':'MIC_THEN_MEAN_TRANSLATION_NO_ROTATION_NOT_INITIAL_STATE'}
  r['frame_comparison']=alignment;mixed.append(r)
 sources=['priority2_statistics_v1.json','priority3_offline_audit_v1.json','joint_mobility_diagnostic_v1.json'];meta={'schema':'priority4-evidence-v1','base_commit':'c343e080d6e8a72c8e9128c8665ef8a75d954412','inputs_sha256':{s:sha(B/s) for s in sources},'driver_sha256':sha(__file__),'python':platform.python_version(),'random_seed':20261101,'bootstrap_iterations':1000,'permutation_iterations':1000,'qualification':'ABSTAIN'}
 return {**meta,'rows':rows,'matched_step_formula':results,'group_comparisons':group_comparisons,'independent_validation':'INDEPENDENT_VALIDATION_NOT_AVAILABLE','threshold_scope':'POST_HOC_0.8_ANGSTROM','holdout_scope':'NO_MODEL_FITTING_NO_INDEPENDENT_HOLDOUT'}, {**meta,'mixed':mixed,'interpretation':'SAME_SEED_NOT_SAME_RNG_STATE_NO_CAUSAL_ATTRIBUTION'}
def main():
 p=argparse.ArgumentParser();p.add_argument('--stats',type=Path,required=True);p.add_argument('--md',type=Path,required=True);a=p.parse_args()
 if a.stats.exists() or a.md.exists():raise FileExistsError('refuse overwrite')
 s,m=build();a.stats.write_text(json.dumps(s,indent=2,sort_keys=True,allow_nan=False)+'\n');a.md.write_text(json.dumps(m,indent=2,sort_keys=True,allow_nan=False)+'\n')
if __name__=='__main__':main()
