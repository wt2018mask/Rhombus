"""Finite-image softmin continuation; exact clearance checked independently."""
import argparse,hashlib,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import numpy as np
from rhombus.transport.cif_probe import prepare_cif_evaluation_probe
from rhombus.transport.bvse_parameters import build_charge_scaled_evaluator,host_radii
from rhombus.transport.soft_clearance import soft_clearance
from rhombus.transport.periodic_clearance import complete_images,periodic_clearance,sampled_lipschitz_bound
from rhombus.transport.periodic_string import relax_periodic_string
from rhombus.transport.path_numerical_audit import inspect_witness

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--network',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():raise FileExistsError('refuse overwrite')
 start=time.monotonic();d=json.loads(a.network.read_text());graph=json.loads(Path(d['graph_path']).read_text());s=prepare_cif_evaluation_probe(ROOT/graph['input_file'])['structure'];host=build_charge_scaled_evaluator(s);lat=s.lattice;pos=[x.frac_coords for x in s if x.specie.symbol!='Li'];radii=np.asarray(host_radii(s));images,image_radii,completeness=complete_images(lat,pos,radii,margin_A=.025);rows=[]
 if images is None or not completeness['periodic_image_completeness_verified']:raise ValueError('PERIODIC_IMAGE_COMPLETENESS_UNAVAILABLE')
 for path in d['paths']:
  phases=[];exact=None;error=None
  try:
   if path['string'] is None:raise ValueError('initial energy string unavailable')
   xyz=np.asarray(path['string']['points_cartesian'])
   for beta in (15.,30.,60.):
    def evaluate(points):
     wrapped=lat.get_cartesian_coords(lat.get_fractional_coords(points)%1);val,grad=soft_clearance(wrapped,images,image_radii,beta);return -val,grad
    result=relax_periodic_string(xyz,evaluate,max_iterations=40,force_tolerance_eV_A=.05,step_scale=.01,max_step_A=.05);phases.append({'beta':beta,'converged':result['converged'],'iterations':result['iterations'],'max_perpendicular_clearance_gradient_norm':result['max_perpendicular_force_eV_A']});xyz=np.asarray(result['points_cartesian'])
   bound=sampled_lipschitz_bound(xyz,lat,images,image_radii,max_spacing_A=.025)
   vertex=periodic_clearance(xyz,lat,images,image_radii);sampled=[]
   for left,right in zip(xyz[:-1],xyz[1:]):
    count=max(1,int(np.ceil(np.linalg.norm(right-left)/.025)));sampled.extend(left+(right-left)*np.arange(count)[:,None]/count)
   sampled=np.vstack([sampled,xyz[-1]]);exact_values=periodic_clearance(sampled,lat,images,image_radii);bottleneck=sampled[np.argmin(exact_values)];wrapped=lat.get_cartesian_coords(lat.get_fractional_coords(bottleneck[None,:])%1);soft,_=soft_clearance(wrapped,images,image_radii,60.);soft_vertices,_=soft_clearance(lat.get_cartesian_coords(lat.get_fractional_coords(xyz)%1),images,image_radii,60.)
   exact={'unsmoothed_vertex_min_clearance_A':float(vertex.min()),'unsmoothed_0025A_sampled_min_clearance_A':bound['sampled_min_clearance_A'],'verified_1lipschitz_lower_bound_A':bound['lower_bound_A'],'softmin_surrogate_min_A':float(soft_vertices.min()),'softmin_surrogate_at_exact_bottleneck_A':float(soft[0]),'final_points_cartesian':xyz.tolist(),'softmin_bias_at_bottleneck_A':float(exact_values.min()-soft[0]),'softmin_finite_image_bias_bound_A':float(np.log(len(images))/60.),'final_max_perp_clearance_grad_norm':float(result['max_perpendicular_force_eV_A']),'bound_scope':bound['scope'],'sample_count':bound['samples']}
  except Exception as exc:error=repr(exc)
  rows.append({'winding':path['winding'],'phases':phases,'exact_check':exact,'error':error})
 successful=all(len(r['phases'])==3 and all(p['converged'] for p in r['phases']) and r['exact_check'] for r in rows);payload={'schema':'priority7-clearance-v1','network_path':str(a.network),'network_sha256':sha(a.network),'driver_sha256':sha(Path(__file__)),'softmin_sha256':sha(ROOT/'rhombus/transport/soft_clearance.py'),'phases_beta_A_inverse':[15,30,60],'image_count':len(images),'periodic_image_completeness':completeness,'max_iterations_per_phase':40,'paths':rows,'exact_clearance_A':min(r['exact_check']['unsmoothed_0025A_sampled_min_clearance_A'] for r in rows) if all(r['exact_check'] is not None for r in rows) else None,'all_converged':bool(successful),'scope':'EXACT_NEAREST_IMAGE_COMPLETE_SOFTMIN_FINITE_IMAGE_NOT_GLOBAL','qualification':'ABSTAIN','seconds':time.monotonic()-start};a.output.write_text(json.dumps(payload,indent=2,sort_keys=True,allow_nan=False)+'\n');print(a.network,'exact',payload['exact_clearance_A'],'converged',payload['all_converged'],flush=True)
if __name__=='__main__':main()
