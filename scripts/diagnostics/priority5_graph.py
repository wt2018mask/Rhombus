"""CPU-only segment-edge diagnostic for one crystal/grid/origin."""
import argparse,hashlib,json,platform,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import numpy as np
from pymatgen.core import Structure
from rhombus.transport.cif_probe import prepare_cif_evaluation_probe
from rhombus.transport.bvse_parameters import build_charge_scaled_evaluator,host_radii
from rhombus.transport.bvse_percolation import percolation_thresholds
from rhombus.transport.segment_percolation import segment_percolation
from rhombus.transport.path_numerical_audit import inspect_witness

def sha(p):return hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--cif',required=True);p.add_argument('--n',type=int,required=True);p.add_argument('--origin',type=float,required=True);p.add_argument('--edge-spacing',type=float,default=.2);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():raise FileExistsError('refuse overwrite')
 if a.n<2 or a.n**3>262144:raise ValueError('voxel budget exceeded')
 start=time.monotonic();s=prepare_cif_evaluation_probe(ROOT/a.cif)['structure'];host=build_charge_scaled_evaluator(s);lat=s.lattice;origin=np.full(3,a.origin/a.n); axes=[np.arange(a.n)/a.n]*3;frac=np.stack(np.meshgrid(*axes,indexing='ij'),axis=-1).reshape(-1,3)+origin;pts=lat.get_cartesian_coords(frac);field=np.concatenate([host(pts[i:i+2048])[0] for i in range(0,len(pts),2048)]).reshape((a.n,)*3)
 old=percolation_thresholds(field);new=segment_percolation(field,lat,host,origin=origin,max_spacing_A=a.edge_spacing);hf=[x.frac_coords for x in s if x.specie.symbol!='Li'];radii=host_radii(s);validated=[inspect_witness(x['fractional_path'],x['winding_vector'],lat,host,hf,radii,max_spacing_A=.025) for x in new['cycles_3d']]
 payload={'schema':'priority5-segment-graph-v1','base_commit':'0da67fb330e45d56578545be73e60e2542e8fba3','input_file':a.cif,'input_sha256':sha(a.cif),'code_sha256':{f:sha(f) for f in ['rhombus/transport/segment_percolation.py','rhombus/transport/bvse_percolation.py','rhombus/transport/bvse_parameters.py','rhombus/transport/path_numerical_audit.py','scripts/diagnostics/priority5_graph.py']},'python':platform.python_version(),'device':'CPU','grid':[a.n]*3,'actual_spacing_A':(np.asarray(lat.abc)/a.n).tolist(),'origin_voxel_fraction':a.origin,'edge_spacing_A':a.edge_spacing,'verification_spacing_A':.025,'old_vertex_graph':old,'segment_graph':new,'independent_witness_verification':validated,'verification_gap_eV':max((x['sampled_max_eV']-new['thresholds_eV']['3D'] for x in validated),default=None),'optimizer_status':'NOT_RUN','status':'EXPLORATORY_NOT_CONVERGED','qualification':'ABSTAIN','seconds':time.monotonic()-start}
 a.output.write_text(json.dumps(payload,indent=2,sort_keys=True,allow_nan=False)+'\n');print(a.output, payload['old_vertex_graph']['barriers_eV']['3D'],new['barrier_3d_eV'],payload['verification_gap_eV'],flush=True)
if __name__=='__main__':main()
