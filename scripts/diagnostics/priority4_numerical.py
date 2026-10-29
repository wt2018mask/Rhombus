"""CPU-only voxel witness audit; never runs MLIP/MD or dispatches jobs."""
import argparse, hashlib, json, os, platform, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import numpy as np
import scipy
import pymatgen.core
from importlib.metadata import version
from pymatgen.util.coord import pbc_shortest_vectors
from rhombus.transport.cif_probe import prepare_cif_evaluation_probe
from rhombus.transport.bvse_parameters import build_charge_scaled_evaluator,host_radii
from rhombus.transport.bvse_percolation import percolation_thresholds
from rhombus.transport.path_numerical_audit import inspect_witness

FILES=['data/benchmarks/known_material/structures/cod/9009060-latest-freeze-v1.cif','data/benchmarks/known_material/structures/cod/1008166-latest-freeze-v1.cif','data/benchmarks/known_material/structures/literature/tetragonal-llzo-awaka-2009-nd-v1.cif']
def digest(p): return hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
def run():
 rows=[];started=time.monotonic(); force=[]
 for file in FILES:
  s=prepare_cif_evaluation_probe(ROOT/file)['structure'];host=build_charge_scaled_evaluator(s); hosts=[x.frac_coords for x in s if x.specie.symbol!='Li']; radii=np.asarray(host_radii(s)); lat=s.lattice
  points=lat.get_cartesian_coords(np.array([[.13,.27,.39],[.36,.19,.72],[.62,.53,.41]])); h=1e-4; ene,f=host(points); grad=[]
  for ax in np.eye(3):grad.append((host(points+h*ax)[0]-host(points-h*ax)[0])/(2*h))
  error=np.linalg.norm(np.asarray(grad).T+f,axis=1); shifted=host(points+lat.matrix[0])[0]
  force.append({'path':file,'step_A':h,'points_fractional':[[.13,.27,.39],[.36,.19,.72],[.62,.53,.41]],'absolute_force_errors_eV_A':error.tolist(),'max_error_eV_A':float(max(error)),'median_error_eV_A':float(np.median(error)),'translation_energy_max_abs_eV':float(max(abs(ene-shifted))),'scope':'THREE_SMOOTH_POINTS_ONLY_NOT_CUTOFF_OR_MIC_BOUNDARIES'})
  for n in (12,16):
   for origin in (0.,.5):
    try:
     frac=np.stack(np.meshgrid(*([np.arange(n)/n]*3),indexing='ij'),axis=-1).reshape(-1,3)+origin/n; cart=lat.get_cartesian_coords(frac)
     field=np.concatenate([host(cart[i:i+2048])[0] for i in range(0,len(cart),2048)]).reshape((n,n,n))
     clearance=np.concatenate([(np.linalg.norm(pbc_shortest_vectors(lat,frac[i:i+128],hosts),axis=2)-radii).min(axis=1) for i in range(0,len(frac),128)]).reshape((n,n,n))
     for neighborhood in (6,18,26):
      graph=percolation_thresholds(field,neighborhood=neighborhood);geo=percolation_thresholds(-clearance,neighborhood=neighborhood)
      cycles=graph['percolating_cycles']['3D']; inspected=[]
      for cycle in cycles:
       path=np.asarray(cycle['fractional_path'])+origin/n
       inspected.append({str(sp):inspect_witness(path,cycle['winding_vector'],lat,host,hosts,radii,max_spacing_A=sp) for sp in (.05,.025)})
      wind=[x['winding_vector'] for x in cycles]
      grows=[]
      for cycle in geo['percolating_cycles']['3D']:
       path=np.asarray(cycle['fractional_path'])+origin/n
       grows.append(inspect_witness(path,cycle['winding_vector'],lat,host,hosts,radii,max_spacing_A=.025))
      rows.append({'path':file,'n':n,'origin_voxel_fraction':origin,'actual_spacing_A':(np.asarray(lat.abc)/n).tolist(),'neighborhood':neighborhood,'minimum_eV':graph['minimum_energy_eV'],'voxel_3d_saddle_eV':graph['minimum_energy_eV']+graph['barriers_eV']['3D'],'voxel_channel_eV':graph['barriers_eV']['3D'],'winding_vectors':wind,'winding_rank':int(np.linalg.matrix_rank(wind)),'witness':inspected,'voxel_geometry_radius_A':-(geo['minimum_energy_eV']+geo['barriers_eV']['3D']),'geometry_witness':grows,'status':'EXPLORATORY_NOT_CONVERGED'})
    except Exception as e:rows.append({'path':file,'n':n,'origin_voxel_fraction':origin,'status':'FAILED','error':repr(e)})
    print(file,n,origin,flush=True)
 return {'schema':'priority4-numerical-v1','base_commit':'c343e080d6e8a72c8e9128c8665ef8a75d954412','input_sha256':{p:digest(p) for p in FILES},'code_sha256':{p:digest(p) for p in ['rhombus/transport/bvse_parameters.py','rhombus/transport/bvse_percolation.py','rhombus/transport/path_numerical_audit.py','scripts/diagnostics/priority4_numerical.py']},'versions':{'python':platform.python_version(),'numpy':np.__version__,'scipy':scipy.__version__,'pymatgen':version('pymatgen'),'device':'CPU','machine':platform.machine()},'execution_command':'OPENBLAS_NUM_THREADS=1 python scripts/diagnostics/priority4_numerical.py --output <new-file>','voxel_budget':262144,'predefined_diagnostic_tolerances':{'channel_spread_eV':.03,'geometry_spread_A':.03,'scope':'NUMERICAL_ONLY_NOT_PHYSICAL_ACCURACY'},'force':force,'rows':rows,'seconds':time.monotonic()-started,'qualification':'ABSTAIN','scope':'FINITE_SAMPLING_NO_CONTINUOUS_GLOBAL_CERTIFICATION'}
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);a=p.parse_args()
 if a.output.exists():raise FileExistsError('refuse overwrite')
 a.output.write_text(json.dumps(run(),indent=2,sort_keys=True,allow_nan=False)+'\n')
if __name__=='__main__':main()
