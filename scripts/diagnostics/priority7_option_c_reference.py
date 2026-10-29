"""Exact-coordinate M0-C handoff with optional local hash-verified MACE points.

No download or MD. Missing model/evidence yields NOT_EXECUTED, never fake values.
"""
import argparse,hashlib,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import numpy as np
from pymatgen.core import Structure
from rhombus.transport.cif_probe import prepare_cif_evaluation_probe
from rhombus.transport.bvse_parameters import build_charge_scaled_evaluator
EXPECTED='75428afe3a1d7d8062e19bcaabd5c433623cabf308242ec9fb493e38604fb638'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--model',type=Path);a=p.parse_args()
 if a.output.exists():raise FileExistsError('refuse overwrite')
 rows=[];base=ROOT/'data/benchmarks/v3_static'
 for material in ('li2s','lialo2','llzo'):
  path=base/f'priority7_{material}_n16_o0_joint_r1_v4.json';retained=json.loads(path.read_text());network=json.loads(Path(retained['network_path']).read_text());graph=json.loads(Path(network['graph_path']).read_text());s=prepare_cif_evaluation_probe(ROOT/graph['input_file'])['structure'];points=np.array(retained['final_points_cartesian'][0]);mobile=[i for i,site in enumerate(s) if site.specie.symbol=='Li'];dist=s.lattice.get_all_distances([s.lattice.get_fractional_coords(points[0])],[s[i].frac_coords for i in mobile])[0];active=mobile[int(np.argmin(dist))];host=build_charge_scaled_evaluator(s);pick=np.unique([0,int(np.argmax(host(points)[0])),len(points)-1]);frames=[]
  for index in pick:
   frame=s.copy();frame.replace(active,'Li',s.lattice.get_fractional_coords(points[index])%1);dm=frame.distance_matrix.copy();np.fill_diagonal(dm,np.inf);serial=json.dumps(frame.as_dict(),sort_keys=True,separators=(',',':'));frames.append({'path_index':int(index),'structure_dict':frame.as_dict(),'coordinate_identity_sha256':hashlib.sha256(serial.encode()).hexdigest(),'min_pair_A':float(dm.min()),'static_energy_eV':float(host(points[index:index+1])[0][0])})
  rows.append({'material':material,'path_sha256':sha(path),'active_mobile_index':active,'frames':frames,'status':'NOT_EXECUTED_MODEL_UNAVAILABLE','reference_scope':'FROZEN_FULL_STRUCTURE_MOVING_ONE_LI_SPECTATORS_RETAINED','applicability':'UNVERIFIED_CONTROLLED_MODEL_COMPARISON_NOT_GROUND_TRUTH'})
 cohort=json.loads((base/'priority2_statistics_v1.json').read_text())['host_rows']
 for family in ('O','S','Se'):
  selected=next((r for r in cohort if r['anion_counts'].get(family,0)>0),None)
  rows.append({'material':selected['formula'] if selected else None,'family':family,'p1_path':selected['p1_path'] if selected else None,'status':'NOT_EXECUTED_NO_RETAINED_CONTINUOUS_WITNESS'})
 if a.model is not None:
  if sha(a.model)!=EXPECTED:raise ValueError('model SHA256 mismatch before deserialization')
  import torch
  torch.set_num_threads(1)
  from mace.calculators import MACECalculator
  from pymatgen.io.ase import AseAtomsAdaptor
  calculator=MACECalculator(model_paths=str(a.model),device='cpu',default_dtype='float64');start=time.monotonic()
  for row in rows:
   if 'frames' not in row:continue
   energies=[]
   for frame in row['frames']:
    if time.monotonic()-start>60:row['status']='RESOURCE_LIMITED';break
    if frame['min_pair_A']<.8:row['status']='INVALID_CLOSE_CONTACT_PROBE';break
    atoms=AseAtomsAdaptor.get_atoms(Structure.from_dict(frame['structure_dict']));atoms.calc=calculator;energy=float(atoms.get_potential_energy());frame['atomistic_energy_eV']=energy;energies.append(energy)
   else:
    row['status']='MEASURED_SINGLE_POINT_SUBSAMPLE';row['atomistic_sampled_barrier_eV']=max(energies)-energies[0];static=[f['static_energy_eV'] for f in row['frames']];row['static_sampled_barrier_eV']=max(static)-static[0]
 result={'schema':'option-c-m0c-v1','driver_sha256':sha(Path(__file__)),'expected_model_sha256':EXPECTED,'rows':rows,'scope':'THREE_SUBSAMPLED_COORDINATES_NOT_NEB_OR_PHYSICAL_TRUTH','qualification':'ABSTAIN'};a.output.write_text(json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+'\n')
if __name__=='__main__':main()
