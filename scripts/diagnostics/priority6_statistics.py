"""Exploratory host sterics and grouped held-out threshold assessment."""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import numpy as np
from scipy.stats import rankdata,spearmanr
from pymatgen.core import Structure
from rhombus.transport.bvse_parameters import ANIONS,CATIONS
from rhombus.transport.cohort_evidence import _digest_structure


def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def metrics(x,y):
 x=np.asarray(x,float);y=np.asarray(y,int);pos=int(y.sum());neg=len(y)-pos
 return {'n':len(y),'positive':pos,'negative':neg,'auc':float((rankdata(x)[y==1].sum()-pos*(pos+1)/2)/(pos*neg)) if pos and neg else None,'rho':float(spearmanr(x,y).statistic) if len(set(x))>1 and pos and neg else None}
def choose_threshold(x,y):
 x=np.asarray(x,float);y=np.asarray(y,int)
 if not y.any() or y.all():return None
 uniq=np.unique(x);thresholds=np.r_[-np.inf,(uniq[1:]+uniq[:-1])/2,np.inf]
 return float(max(thresholds,key=lambda t:((x[y==1]>=t).mean()-(x[y==0]>=t).mean(),-t)))
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);args=p.parse_args()
 if args.output.exists():raise FileExistsError('refuse overwrite')
 base=ROOT/'data/benchmarks/v3_static';src=base/'priority2_statistics_v1.json'; grouped=base/'priority4_grouped_v3.json';data=json.loads(src.read_text());rows=[]
 for r in data['host_rows']:
  path=ROOT/r['p1_path'];d=json.loads(path.read_text())['result']['relaxed_structure_dict']
  if _digest_structure(d)!=r['relaxed_sha256']:raise ValueError('structure digest mismatch')
  s=Structure.from_dict(d); symbols=[site.specie.symbol for site in s];dm=s.distance_matrix
  def pair(indices,radii=None):
   if len(indices)<2:return None
   vals=dm[np.ix_(indices,indices)].copy();np.fill_diagonal(vals,np.inf)
   if radii is not None:
    rs=np.array([radii[symbols[i]] for i in indices]);vals=vals/(rs[:,None]+rs[None,:])
   return float(vals.min())
  ai=[i for i,v in enumerate(symbols) if v in ANIONS];ci=[i for i,v in enumerate(symbols) if v in CATIONS]
  rows.append({'id':r['batch_id'],'formula':r['formula'],'subset':r['subset'],'relaxed_sha256':r['relaxed_sha256'],'anion_min_A':pair(ai),'anion_radius_ratio':pair(ai,{k:v[3] for k,v in ANIONS.items()}),'cation_min_A':pair(ci),'volume_per_atom_A3':float(s.volume/len(s)),'has_O':r['anion_counts']['O']>0,'has_OS':r['anion_counts']['O']>0 and r['anion_counts']['S']>0})
 keys=('anion_min_A','anion_radius_ratio','cation_min_A','volume_per_atom_A3');summary={}
 for group in ('all','O','OS'):
  selected=[r for r in rows if group=='all' or r['has_'+group]];summary[group]={}
  for key in keys:
   valid=[r for r in selected if r[key] is not None];entry={}
   for cls in ('COMPLETED','EXPLOSIVE'):
    vals=[r[key] for r in valid if r['subset']==cls];entry[cls]={'n':len(vals),'q1_median_q3':np.quantile(vals,[.25,.5,.75]).tolist() if vals else None}
   entry['comparison']=metrics([r[key] for r in valid],[int(r['subset']=='COMPLETED') for r in valid]);summary[group][key]=entry
 obs=json.loads(grouped.read_text())['rows'];score='saddle';rng=np.random.default_rng(20261029);holdouts={}
 for mode in ('all','1000'):
  arr=[r for r in obs if mode=='all' or r['production_steps']==1000]
  for group in ('parent_id','formula'):
   predicted=[];groups=sorted(set(r[group] for r in arr if r.get(group) is not None))
   for held in groups:
    tr=[r for r in arr if r[group]!=held];te=[r for r in arr if r[group]==held];t=choose_threshold([r[score] for r in tr],[int(r['mean_li_displacement_A']>=.8) for r in tr]);
    for r in te:predicted.append({'id':r['batch_id'],'p2_path':r['p2_path'],'parent_id':r['parent_id'],'formula':r['formula'],'relaxed_sha256':r['relaxed_sha256'],'group':held,'score':r[score],'label':int(r['mean_li_displacement_A']>=.8),'threshold':t if t is not None and np.isfinite(t) else ('POSITIVE_ALWAYS' if t==-np.inf else 'NEGATIVE_ALWAYS' if t==np.inf else None),'prediction':int(r[score]>=t) if t is not None else None,'training_n':len(tr)})
   valid=[r for r in predicted if r['prediction'] is not None];raw=metrics([r['score'] for r in valid],[r['label'] for r in valid]);raw['accuracy']=float(np.mean([r['prediction']==r['label'] for r in valid])) if valid else None
   parents=sorted(set(r['parent_id'] for r in valid if r['parent_id'] is not None));boot=[];boot_rho=[];boot_accuracy=[]
   if parents:
    for _ in range(1000):
     ids=rng.choice(parents,size=len(parents),replace=True);draw=[r for parent in ids for r in valid if r['parent_id']==parent];m=metrics([r['score'] for r in draw],[r['label'] for r in draw]);
     if m['auc'] is not None:boot.append(m['auc'])
     if m['rho'] is not None:boot_rho.append(m['rho'])
     if draw:boot_accuracy.append(float(np.mean([r['prediction']==r['label'] for r in draw])))
   holdouts[mode+'_'+group]={'folds':len(groups),'results':raw,'parent_cluster_bootstrap_auc_ci95':np.quantile(boot,[.025,.975]).tolist() if boot else None,'valid_bootstraps':len(boot),'parent_cluster_bootstrap_rho_ci95':np.quantile(boot_rho,[.025,.975]).tolist() if boot_rho else None,'valid_rho_bootstraps':len(boot_rho),'parent_cluster_bootstrap_accuracy_ci95':np.quantile(boot_accuracy,[.025,.975]).tolist() if boot_accuracy else None,'predictions':predicted,'scope':'EXPLORATORY_POST_HOC_LABEL_NOT_INDEPENDENT_VALIDATION'}
 result={'schema':'priority6-statistics-v1','base_commit':'b04a96c48e0e225879a791fb3266cd60c1914dfb','sources_sha256':{str(p.relative_to(ROOT)):digest(p) for p in (src,grouped)},'driver_sha256':digest(Path(__file__)),'definitions':{'positive':'completed','anion_radius':'minimum pairwise d/(r_i+r_j), owner-supplied radii','cation':'includes Li and other CATIONS','distances':'MIC distinct sites only, no periodic self images','label':'post-hoc mean displacement >=0.8 A','threshold':'training-fold Youden J, no pre-registered independent data'},'steric_rows':rows,'steric_summary':summary,'holdouts':holdouts,'qualification':'ABSTAIN','independent_validation':'NOT_AVAILABLE'}
 args.output.write_text(json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+'\n')
if __name__=='__main__':main()
