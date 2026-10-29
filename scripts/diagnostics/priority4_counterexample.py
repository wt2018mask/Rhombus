"""Periodic analytic counterexample to endpoint-only edge checks."""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import numpy as np
from pymatgen.core import Lattice
from rhombus.transport.path_numerical_audit import inspect_witness

def periodic(x):
    d=np.sin(np.pi*(x-np.array([1.,1.,0.]))/4)
    return np.exp(-np.sum(d*d,axis=1)/.02),np.zeros_like(x)
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);a=parser.parse_args()
    if a.output.exists():raise FileExistsError('refuse overwrite')
    path=[[0,0,0],[.5,.5,0],[1,1,0]]
    samples={str(h):inspect_witness(path,[1,1,0],Lattice.cubic(4),periodic,[[.25,.25,0]],[.3],max_spacing_A=h) for h in (.05,.025)}
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__),ROOT/'rhombus/transport/path_numerical_audit.py')}
    payload={'schema':'priority4-analytic-counterexample-v1','potential':'exp(-sum(sin(pi*(r-[1,1,0])/4)^2)/0.02) eV','lattice_A':4,'path_fractional':path,'host_fractional':[[.25,.25,0]],'host_radius_A':.3,'winding':[1,1,0],'samples':samples,'code_sha256':hashes,'qualification':'ABSTAIN','scope':'ANALYTIC_COUNTEREXAMPLE_NOT_MATERIAL'}
    a.output.write_text(json.dumps(payload,indent=2,sort_keys=True,allow_nan=False)+'\n')
if __name__=='__main__':main()
