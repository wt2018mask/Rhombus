"""Retrospective clustered OOB threshold refitting; never external validation."""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import numpy as np
from scipy.stats import rankdata
from importlib.util import spec_from_file_location,module_from_spec
spec=spec_from_file_location('p6stats',ROOT/'scripts/diagnostics/priority6_statistics.py');p6=module_from_spec(spec);spec.loader.exec_module(p6)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def nested_bootstrap(rows,group,score,label,*,iterations,seed):
    groups=sorted({r[group] for r in rows if r.get(group) is not None});rng=np.random.default_rng(seed);results=[];skipped={'NO_OOB':0,'ONE_CLASS_TRAIN':0,'NO_VALID_ROWS':0}
    for _ in range(iterations):
        chosen=rng.choice(groups,size=len(groups),replace=True);selected=set(chosen);train=[r for g in chosen for r in rows if r[group]==g];test=[r for r in rows if r[group] not in selected]
        if not test:skipped['NO_OOB']+=1;continue
        threshold=p6.choose_threshold([r[score] for r in train],[r[label] for r in train])
        if threshold is None:skipped['ONE_CLASS_TRAIN']+=1;continue
        preds=[int(r[score]>=threshold)==r[label] for r in test];results.append(float(np.mean(preds)))
    return {'n_groups':len(groups),'iterations':iterations,'valid':len(results),'skipped':skipped,'accuracy_ci95':np.quantile(results,[.025,.975]).tolist() if results else None,'mean_accuracy':float(np.mean(results)) if results else None,'scope':'REFIT_EACH_BOOTSTRAP_OOB_RETROSPECTIVE_NOT_INDEPENDENT'}
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():raise FileExistsError('refuse overwrite')
 base=ROOT/'data/benchmarks/v3_static';p6path=base/'priority6_statistics_v2.json';p4path=base/'priority4_grouped_v3.json';p2path=base/'priority2_statistics_v1.json';steric=json.loads(p6path.read_text())['steric_rows'];runs=json.loads(p4path.read_text())['rows'];host={r['batch_id']:r for r in json.loads(p2path.read_text())['host_rows']}
 for row in steric:
  raw=json.loads((ROOT/host[row['id']]['p1_path']).read_text());row['parent_id']=raw.get('parent_id');row['completion']=int(row['subset']=='COMPLETED')
 for row in runs:row['high_displacement']=int(row['mean_li_displacement_A']>=.8)
 stage1=[r for r in steric if r['anion_min_A'] is not None and r['parent_id'] is not None];stage2=[r for r in runs if r['parent_id'] is not None];folds=[]
 for parent in sorted(set(r['parent_id'] for r in stage1)):
  train1=[r for r in stage1 if r['parent_id']!=parent];test1=[r for r in stage1 if r['parent_id']==parent];t1=p6.choose_threshold([r['anion_min_A'] for r in train1],[r['completion'] for r in train1]);train2=[r for r in stage2 if r['parent_id']!=parent];test2=[r for r in stage2 if r['parent_id']==parent];t2=p6.choose_threshold([r['fixed_0.5'] for r in train2],[r['high_displacement'] for r in train2]);
  t2_saddle=p6.choose_threshold([r['saddle'] for r in train2],[r['high_displacement'] for r in train2])
  def clean(x):return x if x is not None and np.isfinite(x) else ('ALWAYS_POSITIVE' if x==-np.inf else 'ALWAYS_NEGATIVE' if x==np.inf else None)
  predictions1=[{'id':r['id'],'prediction':int(r['anion_min_A']>=t1),'truth':r['completion']} for r in test1] if t1 is not None else []
  stage1_by_id={r['id']:r['prediction'] for r in predictions1};predictions2=[{'id':r['batch_id'],'score_prediction':int(r['fixed_0.5']>=t2),'combined_prediction':int(stage1_by_id[r['batch_id']] and r['fixed_0.5']>=t2),'truth':r['high_displacement']} for r in test2 if r['batch_id'] in stage1_by_id] if t2 is not None else []
  folds.append({'stage1_predictions':predictions1,'stage2_predictions':predictions2,'held_parent':parent,'stage1_training_n':len(train1),'stage1_test_n':len(test1),'stage1_threshold':clean(t1),'stage1_correct':sum(int(r['anion_min_A']>=t1)==r['completion'] for r in test1) if t1 is not None else None,'stage2_training_n':len(train2),'stage2_test_n':len(test2),'stage2_threshold':clean(t2),'stage2_correct':sum(int(r['fixed_0.5']>=t2)==r['high_displacement'] for r in test2) if t2 is not None else None,'stage2_saddle_threshold':clean(t2_saddle),'stage2_saddle_correct':sum(int(r['saddle']>=t2_saddle)==r['high_displacement'] for r in test2) if t2_saddle is not None else None})
 payload={'schema':'priority7-statistics-v1','base_commit':'aa2555a5a92900722060e01356aae1590482e857','sources_sha256':{str(p.relative_to(ROOT)):sha(p) for p in (p6path,p4path,p2path)},'driver_sha256':sha(Path(__file__)),'threshold_code_sha256':sha(ROOT/'scripts/diagnostics/priority6_statistics.py'),'seed':20261029,'stage1':{'structures_total':len(steric),'evaluable':len(stage1),'missing':len(steric)-len(stage1),'parents':len(set(r['parent_id'] for r in stage1))},'stage2':{'runs':len(stage2),'label':'post-hoc 0.8 A displacement; not diffusion'},'leave_one_parent_out_folds':folds,'bootstrap':{'stage1_parent':nested_bootstrap(stage1,'parent_id','anion_min_A','completion',iterations=1000,seed=20261029),'stage1_radius_parent':nested_bootstrap([r for r in stage1 if r['anion_radius_ratio'] is not None],'parent_id','anion_radius_ratio','completion',iterations=1000,seed=20261028),'stage1_radius_structure':nested_bootstrap([r for r in stage1 if r['anion_radius_ratio'] is not None],'relaxed_sha256','anion_radius_ratio','completion',iterations=1000,seed=20261027),'stage1_structure':nested_bootstrap(stage1,'relaxed_sha256','anion_min_A','completion',iterations=1000,seed=20261030),'stage2_parent':nested_bootstrap(stage2,'parent_id','fixed_0.5','high_displacement',iterations=1000,seed=20261031),'stage2_saddle_parent':nested_bootstrap(stage2,'parent_id','saddle','high_displacement',iterations=1000,seed=20261102),'stage2_saddle_structure':nested_bootstrap(stage2,'relaxed_sha256','saddle','high_displacement',iterations=1000,seed=20261103),'stage2_structure':nested_bootstrap(stage2,'relaxed_sha256','fixed_0.5','high_displacement',iterations=1000,seed=20261101)},'scope':'TWO_SEPARATE_RETROSPECTIVE_GATES_NOT_PROSPECTIVE_PIPELINE_PERFORMANCE','qualification':'ABSTAIN'}
 a.output.write_text(json.dumps(payload,indent=2,sort_keys=True,allow_nan=False)+'\n')
if __name__=='__main__':main()
