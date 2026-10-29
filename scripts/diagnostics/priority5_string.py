"""Relax one sampled-edge witness; no remote calls, inference or MD."""
import argparse,hashlib,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import numpy as np
from rhombus.transport.cif_probe import prepare_cif_evaluation_probe
from rhombus.transport.bvse_parameters import build_charge_scaled_evaluator,host_radii
from rhombus.transport.periodic_string import relax_periodic_string
from rhombus.transport.path_numerical_audit import inspect_witness

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--graph',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():raise FileExistsError('refuse overwrite')
 start=time.monotonic();source=json.loads(a.graph.read_text());s=prepare_cif_evaluation_probe(ROOT/source['input_file'])['structure'];host=build_charge_scaled_evaluator(s);cycle=source['segment_graph']['cycles_3d'][0];pts=s.lattice.get_cartesian_coords(cycle['fractional_path']);hf=[x.frac_coords for x in s if x.specie.symbol!='Li'];radii=host_radii(s);before=inspect_witness(cycle['fractional_path'],cycle['winding_vector'],s.lattice,host,hf,radii,max_spacing_A=.025)
 try:
  result=relax_periodic_string(pts,host,max_iterations=200,force_tolerance_eV_A=.05,step_scale=.01,max_step_A=.05);after=inspect_witness(s.lattice.get_fractional_coords(result['points_cartesian']),cycle['winding_vector'],s.lattice,host,hf,radii,max_spacing_A=.025);error=None
 except Exception as exc:result=None;after=None;error=repr(exc)
 payload={'schema':'priority5-string-v1','base_commit':'0da67fb330e45d56578545be73e60e2542e8fba3','graph_input_sha256':sha(a.graph),'driver_sha256':sha(Path(__file__)),'string_code_sha256':sha(ROOT/'rhombus/transport/periodic_string.py'),'settings':{'max_iterations':200,'force_tolerance_eV_A':.05,'step_scale':.01,'max_step_A':.05,'verification_spacing_A':.025},'voxel_minimum_eV':source['segment_graph']['minimum_energy_eV'],'graph_threshold_eV':source['segment_graph']['thresholds_eV']['3D'],'before':before,'after':after,'string':result,'error':error,'scope':'ONE_WITNESS_NO_GLOBAL_3D_CONNECTIVITY','qualification':'ABSTAIN','seconds':time.monotonic()-start};a.output.write_text(json.dumps(payload,indent=2,sort_keys=True,allow_nan=False)+'\n');print(a.output, 'converged',result['converged'] if result else None, 'error',error,flush=True)
if __name__=='__main__':main()
