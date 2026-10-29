"""Small CPU budget probe; optimizations are deliberately non-certifying."""
import argparse,hashlib,json,platform,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import numpy as np
from pymatgen.core import Lattice,Structure
from rhombus.transport.bvse_percolation import percolation_thresholds,build_softbv_evaluator,SiteEnergyEvaluator
from rhombus.transport.bvse_parameters import build_charge_scaled_evaluator,host_radii
from rhombus.transport.cif_probe import prepare_cif_evaluation_probe
from rhombus.transport.path_numerical_audit import inspect_witness
from rhombus.transport.continuous_path_diagnostic import relax_witness_path

def sha(p):return hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
def run():
 files=['data/benchmarks/known_material/structures/cod/9009060-latest-freeze-v1.cif','data/benchmarks/known_material/structures/cod/1008166-latest-freeze-v1.cif','data/benchmarks/known_material/structures/literature/tetragonal-llzo-awaka-2009-nd-v1.cif']; rows=[]; start=time.monotonic()
 for path in files:
  s=prepare_cif_evaluation_probe(ROOT/path)['structure'];host=build_charge_scaled_evaluator(s);host_frac=[x.frac_coords for x in s if x.specie.symbol!='Li'];radii=host_radii(s);lat=s.lattice;field=host.grid(min_dimension=12,max_dimension=12);graph=percolation_thresholds(field);cycle=graph['percolating_cycles']['3D'][0];p=np.asarray(cycle['fractional_path']);cart=lat.get_cartesian_coords(p);obj=lambda x:host(x)[0]
  before=inspect_witness(p,cycle['winding_vector'],lat,host,host_frac,radii,max_spacing_A=.025)
  opt=relax_witness_path(cart,obj,subdivisions=2,smoothing_ev=.05,displacement_bound_A=.05,max_iterations=2);q=lat.get_fractional_coords(opt['path_cartesian']);after=inspect_witness(q,cycle['winding_vector'],lat,host,host_frac,radii,max_spacing_A=.025)
  rows.append({'path':path,'initial_minimum_eV':graph['minimum_energy_eV'],'voxel_saddle_eV':graph['minimum_energy_eV']+graph['barriers_eV']['3D'],'graph_barrier_eV':graph['barriers_eV']['3D'],'winding':cycle['winding_vector'],'before':before,'after':after,'optimizer':opt,'status':'RESOURCE_LIMITED_NOT_CONVERGED'})
  print(path,flush=True)
 # Explicit switching and minimum-image probes use a single oxygen in a 30 A periodic box.
 s=Structure(Lattice.cubic(30),['Li','O'],[[.3,.3,.3],[0,0,0]]); models={'cutoff':SiteEnergyEvaluator(s,anions={'O':(2.,.4,1.)},cations={},pauli=False,periodic_cutoff_A=8.),'minimum_image':SiteEnergyEvaluator(s,anions={'O':(2.,.4,1.)},cations={},pauli=False)};boundary=[]
 for name,model in models.items():
  for r in ((7.,8.) if name=='cutoff' else (15.,)):
   h=1e-5;x=np.array([[r-h,0,0],[r,0,0],[r+h,0,0]]);e,f=model(x);boundary.append({'model':name,'radius_A':r,'h_A':h,'energy_eV':e.tolist(),'force_x_eV_A':f[:,0].tolist(),'central_difference_eV_A':float((e[2]-e[0])/(2*h)),'scope':'BOUNDARY_POINT_MAY_BE_NONDIFFERENTIABLE'})
 files_code=['rhombus/transport/continuous_path_diagnostic.py','rhombus/transport/bvse_percolation.py','rhombus/transport/bvse_parameters.py','rhombus/transport/path_numerical_audit.py','scripts/diagnostics/priority4_optimizer.py']
 return {'schema':'priority4-optimizer-v1','base_commit':'c343e080d6e8a72c8e9128c8665ef8a75d954412','input_sha256':{p:sha(p) for p in files},'code_sha256':{p:sha(p) for p in files_code},'device':'CPU','python':platform.python_version(),'command':'OPENBLAS_NUM_THREADS=1 python scripts/diagnostics/priority4_optimizer.py --output <new-file>','settings':{'n':12,'optimizer':'L-BFGS-B','max_iterations':2,'subdivisions':2,'smoothing_ev':.05,'displacement_bound_A':.05,'independent_spacing_A':.025},'rows':rows,'boundary_probes':boundary,'seconds':time.monotonic()-start,'qualification':'ABSTAIN'}
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():raise FileExistsError('refuse overwrite')
 a.output.write_text(json.dumps(run(),indent=2,sort_keys=True,allow_nan=False)+'\n')
if __name__=='__main__':main()
