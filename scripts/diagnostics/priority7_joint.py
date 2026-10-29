"""Bounded shared-junction smooth-max optimization of sampled winding strings."""
import argparse,hashlib,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import numpy as np
from scipy.optimize import minimize
from scipy.special import logsumexp
from rhombus.transport.cif_probe import prepare_cif_evaluation_probe
from rhombus.transport.bvse_parameters import build_charge_scaled_evaluator,host_radii
from rhombus.transport.path_numerical_audit import inspect_witness

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def refine(points,host):
 """Insert points at ≤0.1 A and at a 0.025 A sampled overshoot >0.02 eV."""
 out=[];inserted=0
 for a,b in zip(points[:-1],points[1:]):
  length=np.linalg.norm(b-a);n=max(1,int(np.ceil(length/.1)));m=max(1,int(np.ceil(length/.025)));ts=np.arange(m+1)/m;vals=host(a[None,:]+ts[:,None]*(b-a))[0];extra=[float(ts[int(np.argmax(vals))])] if max(vals)-max(vals[0],vals[-1])>.02 else []
  t=np.unique(np.r_[np.arange(n)/n,extra]);out.extend(a+t[:,None]*(b-a));inserted+=len(t)-1
 out.append(points[-1]);return np.asarray(out),inserted

def joint_relax(paths,host,*,max_iterations=10,smoothing_eV=.05,bound_A=.05):
    anchor=paths[0][0].copy();windings=[p[-1]-p[0] for p in paths]
    if any(not np.allclose(p[0],anchor,atol=1e-8) for p in paths):raise ValueError('junction mismatch')
    sizes=[len(p)-2 for p in paths];initial=np.r_[anchor,*[p[1:-1].ravel() for p in paths]]
    def unpack(z):
        junction=z[:3];out=[];off=3
        for size,w in zip(sizes,windings):
            inner=z[off:off+3*size].reshape(size,3);off+=3*size;out.append(np.vstack([junction,inner,junction+w]))
        return out
    def objective(z):
        ps=unpack(z);e=[];f=[]
        for p in ps:
            a,b=host(p);e.extend(a);f.extend(b)
        e=np.asarray(e);f=np.asarray(f);lw=e/smoothing_eV;z0=logsumexp(lw);weight=np.exp(lw-z0);jac=np.zeros_like(z);off=3;i=0
        for size in sizes:
            count=size+2;g=-f[i:i+count]*weight[i:i+count,None];jac[:3]+=g[0]+g[-1];jac[off:off+3*size]=g[1:-1].ravel();off+=3*size;i+=count
        return float(smoothing_eV*z0),jac
    result=minimize(objective,initial,jac=True,method='L-BFGS-B',bounds=[(x-bound_A,x+bound_A) for x in initial],options={'maxiter':max_iterations,'gtol':1e-5});return unpack(result.x),{'success':bool(result.success),'message':str(result.message),'iterations':int(result.nit),'objective_eV':float(result.fun),'jacobian_inf_norm':float(np.max(np.abs(result.jac))),'junction_shift_A':float(np.linalg.norm(result.x[:3]-anchor))}

def main():
 p=argparse.ArgumentParser();p.add_argument('--network',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():raise FileExistsError('refuse overwrite')
 start=time.monotonic();net=json.loads(a.network.read_text());g=json.loads(Path(net['graph_path']).read_text());s=prepare_cif_evaluation_probe(ROOT/g['input_file'])['structure'];host=build_charge_scaled_evaluator(s);lat=s.lattice;hosts=[z.frac_coords for z in s if z.specie.symbol!='Li'];r=host_radii(s);paths=[];inserted=[]
 for z in net['paths']:
  if z['string'] is None:raise ValueError('input path unavailable')
  refined,count=refine(np.asarray(z['string']['points_cartesian']),host);paths.append(refined);inserted.append(count)
 if sum(map(len,paths))>6000:payload={'status':'RESOURCE_LIMITED_TOO_MANY_BEADS','initial_beads':sum(map(len,paths)),'qualification':'ABSTAIN'}
 else:
  rounds=[];final=paths
  for iteration in range(3):
   final,opt=joint_relax(final,host);maxlen=max(float(np.linalg.norm(np.diff(p,axis=0),axis=1).max()) for p in final)
   refined=[];counts=[]
   for p in final:
    pp,count=refine(p,host);refined.append(pp);counts.append(count)
   rounds.append({'optimizer':opt,'post_relax_max_segment_A':maxlen,'additional_insertions':counts})
   if sum(counts)==0:break
   if sum(map(len,refined))>6000:break
   if iteration<2:final=refined
  checks=[inspect_witness(lat.get_fractional_coords(p),z['winding'],lat,host,hosts,r,max_spacing_A=.025) for p,z in zip(final,net['paths'])];payload={'status':'EXPLORATORY_NOT_CERTIFIED','initial_beads':sum(map(len,paths)),'inserted':inserted,'joint_optimizer':opt,'rounds':rounds,'final_points_cartesian':[p.tolist() for p in final],'final_checks':checks,'sampled_barrier_eV':max(z['sampled_max_eV'] for z in checks)-net['reference_energy_eV'],'post_relax_max_segment_A':maxlen,'adaptive_post_recheck':'PASSED' if sum(counts)==0 else 'ITERATION_OR_RESOURCE_LIMIT','qualification':'ABSTAIN'}
 payload.update(schema='priority7-joint-v1',network_sha256=sha(a.network),driver_sha256=sha(Path(__file__)),network_path=str(a.network),settings={'max_segment_A':.1,'overshoot_eV':.02,'verification_spacing_A':.025,'max_iterations':10,'max_refinement_rounds':3,'bound_A':.05,'smoothing_eV':.05},seconds=time.monotonic()-start);a.output.write_text(json.dumps(payload,sort_keys=True,indent=2,allow_nan=False)+'\n');print(a.network,payload['status'],payload.get('sampled_barrier_eV'),flush=True)
if __name__=='__main__':main()
