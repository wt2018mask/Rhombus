"""Sampled-edge minimax connectors and multistart anchor diagnostics."""
import argparse,hashlib,heapq,json,sys,time
from itertools import product
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import numpy as np
from scipy.ndimage import minimum_filter
from scipy.optimize import minimize
from rhombus.transport.cif_probe import prepare_cif_evaluation_probe
from rhombus.transport.bvse_parameters import build_charge_scaled_evaluator,host_radii
from rhombus.transport.periodic_string import relax_periodic_string
from rhombus.transport.path_numerical_audit import inspect_witness

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def minimax_tree(field,lat,evaluator,origin,spacing,source):
 shape=np.array(field.shape);n=field.size;cells=np.array(np.unravel_index(np.arange(n),field.shape)).T;directions=[np.array(v) for v in product((-1,0,1),repeat=3) if v!=(0,0,0) and next(x for x in v if x)>0];weights=[]
 for d in directions:
  other=np.ravel_multi_index(((cells+d)%shape).T,field.shape);peak=np.maximum(field.ravel(),field.ravel()[other]).copy();length=np.linalg.norm(lat.get_cartesian_coords(d/shape));parts=max(1,int(np.ceil(length/spacing)))
  for k in range(1,parts):
   points=(cells+d*k/parts)/shape+origin
   for i in range(0,n,2048):peak[i:i+2048]=np.maximum(peak[i:i+2048],evaluator(lat.get_cartesian_coords(points[i:i+2048]))[0])
  weights.append(peak)
 dist=np.full(n,np.inf);prev=np.full(n,-1,int);delta=np.zeros((n,3),int);dist[source]=field.ravel()[source];queue=[(dist[source],int(source))]
 while queue:
  cost,u=heapq.heappop(queue)
  if cost!=dist[u]:continue
  cell=cells[u]
  for j,d in enumerate(directions):
   for sign in (1,-1):
    step=d*sign;other=int(np.ravel_multi_index(tuple((cell+step)%shape),field.shape));weight=weights[j][u if sign==1 else other];val=max(cost,weight)
    if val<dist[other]:dist[other]=val;prev[other]=u;delta[other]=step;heapq.heappush(queue,(val,other))
 return {'dist':dist,'prev':prev,'delta':delta,'source':int(source),'shape':shape}
def tree_path(tree,target):
 seq=[];v=int(target)
 while v!=tree['source']:
  if v<0 or tree['prev'][v]<0:raise ValueError('no path to target')
  seq.append(tree['delta'][v]);v=int(tree['prev'][v])
 seq.reverse();point=np.array(np.unravel_index(tree['source'],tuple(tree['shape'])),int);out=[point.copy()]
 for d in seq:point=point+d;out.append(point.copy())
 return np.asarray(out)/tree['shape']
def adaptive_insert(points,max_segment_A):
 x=np.asarray(points,float);out=[]
 for a,b in zip(x[:-1],x[1:]):
  n=max(1,int(np.ceil(np.linalg.norm(b-a)/max_segment_A)));out.extend(a+(b-a)*(np.arange(n)[:,None]/n))
 return np.vstack([out,x[-1]])
def main():
 p=argparse.ArgumentParser();p.add_argument('--graph',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():raise FileExistsError('refuse overwrite')
 start=time.monotonic();data=json.loads(a.graph.read_text());s=prepare_cif_evaluation_probe(ROOT/data['input_file'])['structure'];host=build_charge_scaled_evaluator(s);lat=s.lattice;n=data['grid'][0];origin=np.full(3,data['origin_voxel_fraction']/n);axis=np.arange(n)/n;f=np.stack(np.meshgrid(axis,axis,axis,indexing='ij'),axis=-1).reshape(-1,3)+origin;x=lat.get_cartesian_coords(f);en=np.concatenate([host(x[i:i+2048])[0] for i in range(0,len(x),2048)]);field=en.reshape((n,)*3);mask=field==minimum_filter(field,size=3,mode='wrap');ids=np.flatnonzero(mask);ids=ids[np.argsort(en[ids],kind='stable')[:8]];width=max(lat.abc)/n;minima=[]
 def fun(z):e,force=host(z[None,:]);return float(e[0]),-force[0]
 for i in ids:
  v=x[i];r=minimize(fun,v,jac=True,method='L-BFGS-B',bounds=[(t-width,t+width) for t in v],options={'maxiter':200,'gtol':1e-5});minima.append({'grid_index':int(i),'energy_eV':float(r.fun),'position':r.x.tolist(),'success':bool(r.success),'force_norm_eV_A':float(np.linalg.norm(host(r.x[None,:])[1][0]))})
 best=min(minima,key=lambda z:z['energy_eV']);anchor=np.array(best['position']);af=lat.get_fractional_coords(anchor);tree=minimax_tree(field,lat,host,origin,data['edge_spacing_A'],best['grid_index']);hosts=[site.frac_coords for site in s if site.specie.symbol!='Li'];radii=host_radii(s);paths=[]
 for c in data['segment_graph']['cycles_3d']:
  cyc=np.asarray(c['fractional_path']);w=np.asarray(c['winding_vector']);wrapped=np.rint((cyc[:-1]-origin)*n).astype(int)%n;inds=np.ravel_multi_index(wrapped.T,field.shape);i=int(np.argmin(tree['dist'][inds]));connector=tree_path(tree,inds[i])+origin;rot=np.vstack([cyc[i:-1],cyc[:i+1]+w]);rot+=np.rint(connector[-1]-rot[0]);loop=np.vstack([af,connector,rot[1:],connector[-2::-1]+w,af+w]);cart=lat.get_cartesian_coords(loop);cart=cart[np.r_[True,np.linalg.norm(np.diff(cart,axis=0),axis=1)>1e-9]];before=inspect_witness(lat.get_fractional_coords(cart),w,lat,host,hosts,radii,max_spacing_A=.025)
  try:
   opt=relax_periodic_string(cart,host,max_iterations=200,force_tolerance_eV_A=.05,step_scale=.01,max_step_A=.05);after=inspect_witness(lat.get_fractional_coords(opt['points_cartesian']),w,lat,host,hosts,radii,max_spacing_A=.025);paths.append({'winding':w.tolist(),'connector_threshold_eV':float(tree['dist'][inds[i]]),'connector_points_fractional':connector.tolist(),'before':before,'after':after,'string':opt,'adaptive_midpoints':None,'error':None})
  except Exception as e:paths.append({'winding':w.tolist(),'connector_threshold_eV':float(tree['dist'][inds[i]]),'before':before,'after':None,'string':None,'error':repr(e)})
 eligible=[r['after']['sampled_max_eV'] for r in paths if r['after']];rank=int(np.linalg.matrix_rank([c['winding_vector'] for c in data['segment_graph']['cycles_3d']]));E=best['energy_eV'];payload={'schema':'priority7-network-v1','base_commit':'aa2555a5a92900722060e01356aae1590482e857','graph_path':str(a.graph),'graph_sha256':sha(a.graph),'driver_sha256':sha(Path(__file__)),'reference_minima':minima,'reference_energy_eV':E,'reference_scope':'LOWEST_OF_UP_TO_EIGHT_LOCAL_MINIMA_NOT_PROVEN_GLOBAL','discrete_common_reference_barrier_eV':data['segment_graph']['thresholds_eV']['3D']-E,'winding_rank':rank,'paths':paths,'network_sampled_barrier_eV':max(eligible)-E if len(eligible)==3 and rank==3 else None,'all_converged':len(paths)==3 and all(r['string'] and r['string']['converged'] for r in paths),'joint_junction_optimization':'NOT_IMPLEMENTED_FIXED_ANCHOR','adaptive_midpoint_refinement':'NOT_EXECUTED','scope':'SAMPLED_LOCAL_DIAGNOSTIC_NOT_GLOBAL','qualification':'ABSTAIN','seconds':time.monotonic()-start};a.output.write_text(json.dumps(payload,sort_keys=True,indent=2,allow_nan=False)+'\n');print(a.graph,payload['network_sampled_barrier_eV'],payload['all_converged'],flush=True)
if __name__=='__main__':main()
