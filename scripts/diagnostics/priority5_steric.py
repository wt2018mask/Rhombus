"""Offline cohort distance stratification: no provider interaction or MLIP."""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import numpy as np
from pymatgen.core import Structure
from rhombus.transport.bvse_parameters import ANIONS
from rhombus.transport.cohort_evidence import _digest_structure

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path);a=parser.parse_args()
 if a.output.exists():raise FileExistsError('refuse overwrite')
 source=ROOT/'data/benchmarks/v3_static/priority2_statistics_v1.json';rows=[]
 for row in json.loads(source.read_text())['host_rows']:
  p=ROOT/row['p1_path'];record=json.loads(p.read_text());structure=record['result']['relaxed_structure_dict']
  if _digest_structure(structure)!=row['relaxed_sha256']:raise ValueError('relaxed structure hash mismatch')
  s=Structure.from_dict(structure);idx=[i for i,site in enumerate(s) if site.specie.symbol in ANIONS]
  distance=None;pair=None
  if len(idx)>=2:
   d=s.distance_matrix[np.ix_(idx,idx)].copy();np.fill_diagonal(d,np.inf);i,j=np.unravel_index(np.argmin(d),d.shape);distance=float(d[i,j]);pair=sorted([s[idx[i]].specie.symbol,s[idx[j]].specie.symbol])
  rows.append({'batch_id':row['batch_id'],'formula':row['formula'],'subset':row['subset'],'p1_path':row['p1_path'],'relaxed_sha256':row['relaxed_sha256'],'anion_min_distance_A':distance,'anion_min_pair':pair,'host_min_distance_A':row['min_distance_A'],'closest_host_pair':row['closest_pair'],'has_O':bool(row['anion_counts']['O']),'has_OS':bool(row['anion_counts']['O'] and row['anion_counts']['S'])})
 summary={}
 for group in ('all','O','OS'):
  summary[group]={}
  for subset in ('COMPLETED','EXPLOSIVE'):
   rr=[x for x in rows if x['subset']==subset and (group=='all' or x['has_O' if group=='O' else 'has_OS'])]
   summary[group][subset]={'n':len(rr),'anion_available':sum(x['anion_min_distance_A'] is not None for x in rr),'anion_quantiles_A':np.quantile([x['anion_min_distance_A'] for x in rr if x['anion_min_distance_A'] is not None],[.25,.5,.75]).tolist() if any(x['anion_min_distance_A'] is not None for x in rr) else None,'host_quantiles_A':np.quantile([x['host_min_distance_A'] for x in rr],[.25,.5,.75]).tolist() if rr else None}
 payload={'schema':'priority5-steric-v1','source_sha256':sha(source),'driver_sha256':sha(Path(__file__)),'anion_symbols':sorted(ANIONS),'scope':'DISTINCT_SITES_MIC_NO_PERIODIC_SELF_IMAGES_NO_CAUSAL_INFERENCE','rows':rows,'summary':summary,'qualification':'ABSTAIN'};a.output.write_text(json.dumps(payload,indent=2,sort_keys=True,allow_nan=False)+'\n')
if __name__=='__main__':main()
