"""Nonsmooth clearance-string exploratory diagnostic with tie rejection."""
import argparse,hashlib,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import numpy as np
from pymatgen.util.coord import pbc_shortest_vectors
from rhombus.transport.cif_probe import prepare_cif_evaluation_probe
from rhombus.transport.bvse_parameters import host_radii
from rhombus.transport.periodic_string import relax_periodic_string
from rhombus.transport.path_numerical_audit import inspect_witness

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--network',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():raise FileExistsError('refuse overwrite')
 t=time.monotonic();network=json.loads(a.network.read_text());graph=json.loads(Path(network['graph_path']).read_text());s=prepare_cif_evaluation_probe(ROOT/graph['input_file'])['structure'];lat=s.lattice;hosts=[v.frac_coords for v in s if v.specie.symbol!='Li'];radii=np.asarray(host_radii(s))
 def evaluate(x):
  vectors=pbc_shortest_vectors(lat,lat.get_fractional_coords(x),hosts);dist=np.linalg.norm(vectors,axis=2);gaps=dist-radii;order=np.argsort(gaps,axis=1);first=order[:,0];nearest=gaps[np.arange(len(x)),first]
  if len(hosts)>1 and np.any(gaps[np.arange(len(x)),order[:,1]]-nearest<1e-8):raise ValueError('NONDIFFERENTIABLE_CLEARANCE_TIE')
  d=dist[np.arange(len(x)),first]
  if np.any(d<1e-10):raise ValueError('UNDEFINED_CLEARANCE_HOST_CENTER')
  force=-vectors[np.arange(len(x)),first]/d[:,None]
  return -nearest,force
 out=[]
 for c in network['paths']:
  try:
   if c['string'] is None:raise ValueError('ENERGY_PATH_UNAVAILABLE')
   points=np.asarray(c['string']['points_cartesian']);result=relax_periodic_string(points,evaluate,max_iterations=200,force_tolerance_eV_A=.05,step_scale=.01,max_step_A=.05);check=inspect_witness(lat.get_fractional_coords(result['points_cartesian']),c['winding'],lat,evaluate,hosts,radii,max_spacing_A=.025);out.append({'winding':c['winding'],'string':result,'verification':check,'error':None})
  except Exception as exc:out.append({'winding':c['winding'],'string':None,'verification':None,'error':repr(exc)})
 success=all(r['string'] is not None for r in out) and network['winding_rank']==3
 payload={'schema':'priority6-clearance-v1','network_sha256':sha(a.network),'network_path':str(a.network),'driver_sha256':sha(Path(__file__)),'settings':{'tie_tolerance_A':1e-8,'max_iterations':200,'force_tolerance':.05,'step_scale':.01,'max_step_A':.05,'verification_spacing_A':.025},'paths':out,'sampled_minimum_clearance_A':min(r['verification']['sampled_min_clearance_A'] for r in out) if success else None,'all_strings_converged':success and all(r['string']['converged'] for r in out),'scope':'NONSMOOTH_LOCAL_BRANCH_MIN_CLEARANCE_NOT_GLOBAL_CERTIFICATION','qualification':'ABSTAIN','seconds':time.monotonic()-t};a.output.write_text(json.dumps(payload,indent=2,sort_keys=True,allow_nan=False)+'\n');print(a.network,'radius',payload['sampled_minimum_clearance_A'],'converged',payload['all_strings_converged'],flush=True)
if __name__=='__main__':main()
