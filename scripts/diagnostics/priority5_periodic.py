"""Retained-crystal periodic, supercell and force difference checks."""
import argparse,hashlib,json,platform,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import numpy as np
from rhombus.transport.cif_probe import prepare_cif_evaluation_probe
from rhombus.transport.bvse_parameters import build_charge_scaled_evaluator

def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():raise FileExistsError('refuse overwrite')
 files=['data/benchmarks/known_material/structures/cod/9009060-latest-freeze-v1.cif','data/benchmarks/known_material/structures/cod/1008166-latest-freeze-v1.cif','data/benchmarks/known_material/structures/literature/tetragonal-llzo-awaka-2009-nd-v1.cif'];rows=[]
 for file in files:
  s=prepare_cif_evaluation_probe(ROOT/file)['structure'];ev=build_charge_scaled_evaluator(s);supercell=s.copy();supercell.make_supercell([2,2,2]);ev2=build_charge_scaled_evaluator(supercell);points=s.lattice.get_cartesian_coords([[.49999,.213,.371],[.50001,.213,.371],[.19,.36,.73]]);en,fo=ev(points);en2,fo2=ev2(points);translated,ft=ev(points+s.lattice.matrix[0]);h=1e-5;g=np.column_stack([(ev(points+h*d)[0]-ev(points-h*d)[0])/(2*h) for d in np.eye(3)]);rows.append({'cif':file,'input_sha256':hashlib.sha256((ROOT/file).read_bytes()).hexdigest(),'max_supercell_energy_abs_eV':float(np.max(np.abs(en-en2))),'max_supercell_force_abs_eV_A':float(np.max(np.abs(fo-fo2))),'max_translation_energy_abs_eV':float(np.max(np.abs(en-translated))),'max_translation_force_abs_eV_A':float(np.max(np.abs(fo-ft))),'finite_difference_h_A':h,'gradient_max_abs_eV_A':float(np.max(np.abs(g+fo))),'points_fractional':[[.49999,.213,.371],[.50001,.213,.371],[.19,.36,.73]],'q_li_primitive':ev.charge_metadata['q_Li'],'q_li_supercell':ev2.charge_metadata['q_Li']})
 payload={'schema':'priority5-periodic-v1','rows':rows,'driver_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'python':platform.python_version(),'cutoff_A':8,'taper_on_A':7,'scope':'THREE_POINTS_PER_STRUCTURE_C2_AWAY_FROM_SINGULARITIES_NO_GLOBAL_PROOF','qualification':'ABSTAIN'};a.output.write_text(json.dumps(payload,indent=2,sort_keys=True,allow_nan=False)+'\n')
if __name__=='__main__':main()
