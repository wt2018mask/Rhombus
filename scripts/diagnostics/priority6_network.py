"""Common-junction three-winding sampled-string experiment, no MD dispatch."""
import argparse,hashlib,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import numpy as np
from scipy.optimize import minimize
from rhombus.transport.cif_probe import prepare_cif_evaluation_probe
from rhombus.transport.bvse_parameters import build_charge_scaled_evaluator,host_radii
from rhombus.transport.periodic_string import relax_periodic_string
from rhombus.transport.path_numerical_audit import inspect_witness

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--graph',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():raise FileExistsError('refuse overwrite')
 start=time.monotonic();data=json.loads(a.graph.read_text());s=prepare_cif_evaluation_probe(ROOT/data['input_file'])['structure'];host=build_charge_scaled_evaluator(s);lat=s.lattice;n=data['grid'][0];origin=data['origin_voxel_fraction']/n;axis=np.arange(n)/n+origin;f=np.stack(np.meshgrid(axis,axis,axis,indexing='ij'),axis=-1).reshape(-1,3);x=lat.get_cartesian_coords(f);en=np.concatenate([host(x[i:i+2048])[0] for i in range(0,len(x),2048)]);v=x[np.argmin(en)];width=max(lat.abc)/n
 def fun(z):
  e,force=host(z[None,:]);return float(e[0]),-force[0]
 local=minimize(fun,v,jac=True,method='L-BFGS-B',bounds=[(t-width,t+width) for t in v],options={'maxiter':200,'gtol':1e-5});anchor=np.asarray(local.x);af=lat.get_fractional_coords(anchor);host_pos=[x.frac_coords for x in s if x.specie.symbol!='Li'];radii=host_radii(s);outputs=[];cycles=data['segment_graph']['cycles_3d'];vectors=np.asarray([c['winding_vector'] for c in cycles]);rank=int(np.linalg.matrix_rank(vectors))
 for c in cycles:
  frac=np.asarray(c['fractional_path']);frac=frac+np.rint(af-frac[0]);w=np.asarray(c['winding_vector']);path=np.vstack((af,frac,af+w));cart=lat.get_cartesian_coords(path);keep=np.r_[True,np.linalg.norm(np.diff(cart,axis=0),axis=1)>1e-9];cart=cart[keep];before=inspect_witness(lat.get_fractional_coords(cart),w,lat,host,host_pos,radii,max_spacing_A=.025)
  try:
   result=relax_periodic_string(cart,host,max_iterations=200,force_tolerance_eV_A=.05,step_scale=.01,max_step_A=.05);after=inspect_witness(lat.get_fractional_coords(result['points_cartesian']),w,lat,host,host_pos,radii,max_spacing_A=.025);outputs.append({'winding':w.tolist(),'before':before,'after':after,'string':result,'error':None})
  except Exception as e:outputs.append({'winding':w.tolist(),'before':before,'after':None,'string':None,'error':repr(e)})
 after=[r['after']['sampled_max_eV'] for r in outputs if r['after'] is not None];payload={'schema':'priority6-network-v1','base_commit':'b04a96c48e0e225879a791fb3266cd60c1914dfb','graph_path':str(a.graph),'graph_sha256':sha(a.graph),'driver_sha256':sha(Path(__file__)),'string_sha256':sha(ROOT/'rhombus/transport/periodic_string.py'),'anchor_cartesian':anchor.tolist(),'anchor_energy_eV':float(host(anchor[None,:])[0][0]),'anchor_force_norm_eV_A':float(np.linalg.norm(host(anchor[None,:])[1][0])),'anchor_scope':'LOCAL_BOUNDED_NOT_PROVEN_GLOBAL','anchor_optimizer_success':bool(local.success),'winding_rank':rank,'paths':outputs,'discrete_barrier_eV':data['segment_graph']['barrier_3d_eV'],'connected_sampled_network_barrier_eV':max(after)-float(host(anchor[None,:])[0][0]) if len(after)==3 and rank==3 else None,'all_strings_converged':len(outputs)==3 and all(r['string'] and r['string']['converged'] for r in outputs),'clearance_string':'NOT_EXECUTED_NONSMOOTH_NEAREST_ATOM_FORCE_NOT_AVAILABLE','scope':'FIXED_COMMON_JUNCTION_NOT_GLOBAL_OR_CONTINUUM_CERTIFICATION','qualification':'ABSTAIN','seconds':time.monotonic()-start};a.output.write_text(json.dumps(payload,indent=2,sort_keys=True,allow_nan=False)+'\n');print(a.graph, 'barrier',payload['connected_sampled_network_barrier_eV'],'converged',payload['all_strings_converged'],flush=True)
if __name__=='__main__':main()
