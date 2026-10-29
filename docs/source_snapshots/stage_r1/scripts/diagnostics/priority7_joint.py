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

def sampling_diagnostic(points,host,smoothing_eV=.05):
    """Compare bead distributions and arclength quadrature; not optimized."""
    p=np.asarray(points,float);length=np.linalg.norm(np.diff(p,axis=0),axis=1);arc=np.r_[0.,np.cumsum(length)]
    if np.any(length<=0):return {'status':'DEGENERATE_PATH'}
    def resample(u):return np.column_stack([np.interp(u*arc[-1],arc,p[:,i]) for i in range(3)])
    def measure(u):
        q=resample(u);energy=host(q)[0];raw=float(smoothing_eV*logsumexp(energy/smoothing_eV));return {'n':len(u),'raw_eV':raw,'normalized_eV':raw-smoothing_eV*np.log(len(u)),'max_eV':float(energy.max())}
    N=min(40,max(3,len(p)));mid=(p[1:]+p[:-1])/2;energy=host(mid)[0];weighted=float(smoothing_eV*(logsumexp(energy/smoothing_eV,b=length)-np.log(length.sum())))
    return {'uniform_N':measure(np.linspace(0,1,N)),'uniform_2N':measure(np.linspace(0,1,2*N)),'nonuniform_2N':measure(np.linspace(0,1,2*N)**2),'arclength_midpoint_diagnostic_eV':weighted,'scope':'QUADRATURE_NOT_OPTIMIZED_NO_WEIGHT_DERIVATIVES_NEEDED'}


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
        return float(smoothing_eV*(z0-np.log(len(e)))),jac
    result=minimize(objective,initial,jac=True,method='L-BFGS-B',bounds=[(x-bound_A,x+bound_A) for x in initial],options={'maxiter':max_iterations,'gtol':1e-5});
    final=unpack(result.x); energies=np.concatenate([host(p)[0] for p in final]);raw=float(smoothing_eV*logsumexp(energies/smoothing_eV));normal=raw-smoothing_eV*np.log(len(energies))
    projected=result.jac.copy();projected[(result.x<=initial-bound_A+1e-9)&(result.jac>0)]=0;projected[(result.x>=initial+bound_A-1e-9)&(result.jac<0)]=0
    perp=[];peak_perp=None;peak=float(energies.max());junction_force=np.zeros(3)
    for p in final:
        e,f=host(p);t=p[2:]-p[:-2];norm=np.linalg.norm(t,axis=1)
        if np.any(norm<1e-12):raise ValueError('undefined tangent')
        t=t/norm[:,None];g=f[1:-1]-(f[1:-1]*t).sum(axis=1)[:,None]*t;perp.extend(np.linalg.norm(g,axis=1));idx=int(np.argmax(e))
        if e[idx]==peak and 0<idx<len(p)-1:peak_perp=float(np.linalg.norm(g[idx-1]))
    # Junction derivative refers to the actual normalized smooth-max objective.
    return final,{'success':bool(result.success),'message':str(result.message),'iterations':int(result.nit),'objective_eV':normal,'smoothmax_raw_eV':raw,'smoothmax_normalized_eV':normal,'maximum_bead_energy_eV':peak,'jacobian_inf_norm':float(np.max(np.abs(result.jac))),'constraint_projected_gradient_inf':float(np.max(np.abs(projected))),'final_junction_force_norm_ev_per_A':float(np.linalg.norm(result.jac[:3])),'final_max_perp_force_ev_per_A':float(max(perp)) if perp else None,'final_peak_bead_perp_force_ev_per_A':peak_perp,'junction_shift_A':float(np.linalg.norm(result.x[:3]-anchor))}


def main():
 p=argparse.ArgumentParser();p.add_argument('--network',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():raise FileExistsError('refuse overwrite')
 start=time.monotonic();net=json.loads(a.network.read_text());g=json.loads(Path(net['graph_path']).read_text());s=prepare_cif_evaluation_probe(ROOT/g['input_file'])['structure'];host=build_charge_scaled_evaluator(s);lat=s.lattice;hosts=[z.frac_coords for z in s if z.specie.symbol!='Li'];r=host_radii(s);paths=[];inserted=[]
 for z in net['paths']:
  if z['string'] is None:raise ValueError('input path unavailable')
  refined,count=refine(np.asarray(z['string']['points_cartesian']),host);paths.append(refined);inserted.append(count)
 if sum(map(len,paths))>6000:payload={'status':'RESOURCE_LIMITED_TOO_MANY_BEADS','initial_beads':sum(map(len,paths)),'qualification':'ABSTAIN'}
 else:
  rounds=[];final=paths;used=0;termination='MAX_ITER_EXHAUSTED';counts=[];opt={}
  for iteration in range(3):
   remaining=30-used
   if remaining<=0:break
   final,opt=joint_relax(final,host,max_iterations=min(10,remaining));used+=opt['iterations'];maxlen=max(float(np.linalg.norm(np.diff(p,axis=0),axis=1).max()) for p in final)
   refined=[];counts=[]
   for p in final:
    pp,count=refine(p,host);refined.append(pp);counts.append(count)
   rounds.append({'optimizer':opt,'post_relax_max_segment_A':maxlen,'additional_insertions':counts})
   if sum(counts)==0:
    termination='STATIONARY_TOL_MET' if opt['success'] and opt['final_max_perp_force_ev_per_A'] is not None and opt['final_max_perp_force_ev_per_A']<=.05 and opt['constraint_projected_gradient_inf']<=1e-5 else 'FEASIBLE_NONSTATIONARY_OR_OPTIMIZER_LIMIT';break
   if sum(map(len,refined))>6000:
    termination='EVAL_BUDGET_EXHAUSTED';break
   final=refined
   if iteration==2 and used<30:
    final,opt=joint_relax(final,host,max_iterations=min(10,30-used));used+=opt['iterations'];termination='FINAL_POLISH_COMPLETED' if opt['success'] else 'MAX_ITER_EXHAUSTED'
   elif iteration==2:termination='FINAL_REFINEMENT_ACCEPTED_NO_POLISH_BUDGET'
  # If no budget remained for final accepted beads, recompute diagnostics at
  # precisely those beads using a zero-movement bounded optimizer call.
  if termination=='FINAL_REFINEMENT_ACCEPTED_NO_POLISH_BUDGET':
   _,opt=joint_relax(final,host,max_iterations=1,bound_A=1e-14)
   opt['success']=False
  maxlen=max(float(np.linalg.norm(np.diff(p,axis=0),axis=1).max()) for p in final)
  counts=[refine(p,host)[1] for p in final]
  shared=max(float(np.linalg.norm(p[0]-final[0][0])) for p in final)
  windings=np.array([np.rint(lat.get_fractional_coords(p[-1]-p[0])).astype(int) for p in final]);rank=int(np.linalg.matrix_rank(windings));topology=shared<1e-8 and rank==3 and np.array_equal(windings,np.asarray([z['winding'] for z in net['paths']])) and all(np.allclose(lat.get_fractional_coords(p[-1]-p[0]),w,atol=1e-8) for p,w in zip(final,windings))
  checks=[inspect_witness(lat.get_fractional_coords(p),z['winding'],lat,host,hosts,r,max_spacing_A=.025) for p,z in zip(final,net['paths'])];payload={'status':'EXPLORATORY_NOT_CERTIFIED','initial_beads':sum(map(len,paths)),'inserted':inserted,'joint_optimizer':opt,'rounds':rounds,'sampling_diagnostic':sampling_diagnostic(final[0],host),'termination_reason':termination,'winding_rank':rank,'topology_valid':bool(topology),'shared_junction_max_gap_A':shared,'final_max_segment_length_A':maxlen,'convergence_classification':('TOPOLOGY_INVALID' if not topology else 'LOCALLY_STATIONARY_ON_FIXED_BEADS' if opt['success'] and opt['final_max_perp_force_ev_per_A'] is not None and opt['final_max_perp_force_ev_per_A']<=.05 and opt['constraint_projected_gradient_inf']<=1e-5 else 'FEASIBLE_WITNESS_NON_STATIONARY'),'global_reference_barrier_state':'UNCERTIFIED_MISSING_GLOBAL_MIN_AND_SADDLE_LOWER_BOUNDS','witness_peak_sampled_ev':max(z['sampled_max_eV'] for z in checks),'anchor_relative_barrier_sampled_ev':max(z['sampled_max_eV'] for z in checks)-float(host(final[0][0][None,:])[0][0]),'final_points_cartesian':[p.tolist() for p in final],'final_checks':checks,'sampled_barrier_eV':max(z['sampled_max_eV'] for z in checks)-net['reference_energy_eV'],'post_relax_max_segment_A':maxlen,'adaptive_post_recheck':'PASSED' if sum(counts)==0 else 'ITERATION_OR_RESOURCE_LIMIT','qualification':'ABSTAIN'}
 payload.update(schema='priority7-joint-v1',network_sha256=sha(a.network),driver_sha256=sha(Path(__file__)),network_path=str(a.network),settings={'max_segment_A':.1,'overshoot_eV':.02,'verification_spacing_A':.025,'max_iterations':10,'max_refinement_rounds':3,'bound_A':.05,'smoothing_eV':.05},seconds=time.monotonic()-start);a.output.write_text(json.dumps(payload,sort_keys=True,indent=2,allow_nan=False)+'\n');print(a.network,payload['status'],payload.get('sampled_barrier_eV'),flush=True)
if __name__=='__main__':main()
