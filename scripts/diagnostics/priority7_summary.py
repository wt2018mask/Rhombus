"""Rebase all six grids to one observed multistart energy per material."""
import argparse,hashlib,json,glob
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'data/benchmarks/v3_static'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def qualifies(joint, residual):
 return bool(joint.get('topology_valid') and joint.get('final_max_segment_length_A',float('inf'))<=.1+1e-9 and residual is not None and residual<=.02 and joint.get('adaptive_post_recheck')=='PASSED' and joint.get('convergence_classification')=='LOCALLY_STATIONARY_ON_FIXED_BEADS')
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--joint-suffix',default='_joint_v3.json');p.add_argument('--clearance-suffix',default='_clearance_v1.json');a=p.parse_args()
 if a.output.exists():raise FileExistsError('refuse overwrite')
 results={};inputs={}
 for mat in ('li2s','lialo2','llzo'):
  entries=[]
  for n in (16,20,24):
   for ori in ('0','0.5'):
    prefix=f'priority7_{mat}_n{n}_o{ori}';paths={k:BASE/(prefix+s) for k,s in [('network','_v1.json'),('joint',a.joint_suffix),('clearance',a.clearance_suffix)]}
    for q in paths.values():inputs[str(q.relative_to(ROOT))]=sha(q)
    entries.append({'n':n,'origin':float(ori),**{k:json.loads(q.read_text()) for k,q in paths.items()}})
  reference=min(r['network']['reference_energy_eV'] for r in entries);rows=[]
  for r in entries:
   net=r['network'];joint=r['joint'];clear=r['clearance'];oldref=net['reference_energy_eV'];discrete=net['discrete_common_reference_barrier_eV']+oldref-reference;sampled=joint.get('sampled_barrier_eV');sampled=(sampled+oldref-reference) if sampled is not None else None
   residual=max((x['missed_barrier_eV'] for x in joint.get('final_checks',[])),default=None)
   opt=joint.get('joint_optimizer',{});qual=qualifies(joint,residual)
   rows.append({'grid_n':r['n'],'origin':r['origin'],'discrete_eV':discrete,'joint_eV':sampled,'joint_optimizer_success':opt.get('success'), 'adaptive_status':joint.get('adaptive_post_recheck'),'qualifying_joint':qual,'qualification_reason':'NUMERICAL_DIAGNOSTIC_ONLY' if qual else 'INCOMPLETE_NUMERICAL_CONVERGENCE','verification_max_excess_eV':residual,'clearance_exact_A':clear.get('exact_clearance_A'),'clearance_bound_A':min((p['exact_check']['verified_1lipschitz_lower_bound_A'] for p in clear.get('paths',[]) if p.get('exact_check') and 'verified_1lipschitz_lower_bound_A' in p['exact_check']),default=None),'clearance_converged':clear.get('all_converged')})
  vals=lambda k:[r[k] for r in rows if r[k] is not None];results[mat]={'reference_energy_eV':reference,'reference_scope':'LOWEST_LOCAL_MULTISTART_OBSERVED_NOT_PROVEN_GLOBAL','rows':rows,'discrete_range_eV':[min(vals('discrete_eV')),max(vals('discrete_eV'))],'joint_range_eV':[min(vals('joint_eV')),max(vals('joint_eV'))] if vals('joint_eV') else None,'joint_qualifying_count':sum(r['qualifying_joint'] for r in rows),'max_verification_excess_eV':max(vals('verification_max_excess_eV')) if vals('verification_max_excess_eV') else None,'exact_clearance_observed_range_A':[min(vals('clearance_exact_A')),max(vals('clearance_exact_A'))] if vals('clearance_exact_A') else None,'clearance_converged_count':sum(r['clearance_converged'] for r in rows)}
 payload={'schema':'priority7-summary-v1','driver_sha256':sha(Path(__file__)),'input_sha256':inputs,'results':results,'scope':'REFERENCE_REBASED_LOCAL_SAMPLED_NOT_CERTIFIED','qualification':'ABSTAIN'};a.output.write_text(json.dumps(payload,indent=2,sort_keys=True,allow_nan=False)+'\n')
if __name__=='__main__':main()
