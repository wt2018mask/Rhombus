"""Sampled-edge maximin host-clearance graph; ionic radii are unverified priors."""
import argparse,hashlib,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import numpy as np
from pymatgen.util.coord import pbc_shortest_vectors
from rhombus.transport.cif_probe import prepare_cif_evaluation_probe
from rhombus.transport.bvse_parameters import host_radii
from rhombus.transport.bvse_percolation import percolation_thresholds
from rhombus.transport.segment_percolation import segment_percolation

def main():
 p=argparse.ArgumentParser();p.add_argument('--cif',required=True);p.add_argument('--n',type=int,required=True);p.add_argument('--origin',type=float,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():raise FileExistsError('refuse overwrite')
 if a.n<2 or a.n**3>262144:raise ValueError('voxel budget exceeded')
 start=time.monotonic();s=prepare_cif_evaluation_probe(ROOT/a.cif)['structure'];lat=s.lattice;hosts=[site.frac_coords for site in s if site.specie.symbol!='Li'];radii=np.asarray(host_radii(s));origin=np.full(3,a.origin/a.n)
 def clearance(x):
  f=lat.get_fractional_coords(x);v=[]
  for i in range(0,len(f),128):v.append(-(np.linalg.norm(pbc_shortest_vectors(lat,f[i:i+128],hosts),axis=2)-radii).min(axis=1))
  return np.concatenate(v),np.zeros_like(x)
 axes=[np.arange(a.n)/a.n]*3;frac=np.stack(np.meshgrid(*axes,indexing='ij'),axis=-1).reshape(-1,3)+origin;field=clearance(lat.get_cartesian_coords(frac))[0].reshape((a.n,)*3)
 old=percolation_thresholds(field);new=segment_percolation(field,lat,clearance,origin=origin,max_spacing_A=.2)
 payload={'schema':'priority5-clearance-v1','source_sha256':hashlib.sha256((ROOT/a.cif).read_bytes()).hexdigest(),'driver_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'cif':a.cif,'n':a.n,'origin_voxel_fraction':a.origin,'edge_spacing_A':.2,'old_radius_A':-(old['minimum_energy_eV']+old['barriers_eV']['3D']),'sampled_edge_radius_A':-new['thresholds_eV']['3D'],'qualification':'ABSTAIN','scope':'SAMPLED_CLEARANCE_NOT_CONTINUUM_OR_PHYSICAL_VALIDATION','seconds':time.monotonic()-start};a.output.write_text(json.dumps(payload,indent=2,sort_keys=True,allow_nan=False)+'\n');print(a.output,payload['old_radius_A'],payload['sampled_edge_radius_A'],flush=True)
if __name__=='__main__':main()
